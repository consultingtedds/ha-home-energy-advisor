from __future__ import annotations

from decimal import Decimal

import pytest

from custom_components.home_energy_advisor.engine.battery_ledger import BatteryLedger

# Predbat charges the Huawei battery cheaply overnight and discharges at peak.
OVERNIGHT = Decimal("0.093")
PEAK = Decimal("0.234")


def test_battery_grid_charge_is_returned_at_the_price_it_was_bought() -> None:
    # Given — 5 kWh forced-charged from the grid overnight
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(5), OVERNIGHT)

    # When — all of it is later discharged at peak time
    cost = ledger.discharge(Decimal(5))

    # Then — it is priced at the overnight rate it was bought at, not the peak rate
    assert cost == Decimal("0.465")


def test_battery_solar_charge_is_free_on_discharge() -> None:
    # Given — 4 kWh charged from surplus solar
    ledger = BatteryLedger()
    ledger.charge_from_solar(Decimal(4))

    # When — it is discharged
    cost = ledger.discharge(Decimal(4))

    # Then — solar-sourced energy costs nothing to draw back out
    assert cost == Decimal(0)


def test_battery_mixed_charge_discharges_at_the_weighted_average() -> None:
    # Given — a battery half-filled from grid, half from solar
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(5), OVERNIGHT)
    ledger.charge_from_solar(Decimal(5))

    # When — 5 kWh is discharged
    cost = ledger.discharge(Decimal(5))

    # Then — it is priced at the blended stored cost, €0.465 spread over 10 kWh
    assert ledger.unit_cost == Decimal("0.0465")
    assert cost == Decimal("0.2325")


def test_battery_partial_discharge_leaves_the_unit_cost_unchanged() -> None:
    # Given — 10 kWh stored at a known blended rate
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(10), Decimal("0.10"))

    # When — only part is discharged
    cost = ledger.discharge(Decimal(3))

    # Then — the draw is priced at that rate and the rest keeps the same rate
    assert cost == Decimal("0.30")
    assert ledger.stored_kwh == Decimal(7)
    assert ledger.unit_cost == Decimal("0.10")


def test_battery_charges_at_different_prices_blend_by_energy() -> None:
    # Given — two grid charges bought in different price windows
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(2), OVERNIGHT)
    ledger.charge_from_grid(Decimal(2), PEAK)

    # When / Then — the stored cost is the energy-weighted blend
    assert ledger.unit_cost == Decimal("0.1635")


def test_battery_discharge_from_empty_ledger_is_free() -> None:
    # Given — a freshly started ledger with no charge history (cold start)
    ledger = BatteryLedger()

    # When — the pre-existing charge of unknown cost is discharged
    cost = ledger.discharge(Decimal(5))

    # Then — with no cost basis it is treated as solar-charged: free, and the
    # ledger stays empty rather than going negative
    assert cost == Decimal(0)
    assert ledger.stored_kwh == Decimal(0)


def test_battery_discharge_beyond_stored_prices_only_the_shortfall_at_zero() -> None:
    # Given — 3 kWh of known grid-charged energy
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(3), Decimal("0.10"))

    # When — 5 kWh is discharged, outrunning what the ledger has priced
    cost = ledger.discharge(Decimal(5))

    # Then — the 3 tracked kWh cost their real rate; the 2 kWh excess is free
    assert cost == Decimal("0.30")
    assert ledger.stored_kwh == Decimal(0)


def test_battery_full_discharge_zeroes_the_ledger_exactly() -> None:
    # Given — a fully charged, then fully drained battery
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(3), OVERNIGHT)
    ledger.discharge(Decimal(3))

    # When — the drained ledger is discharged again
    cost = ledger.discharge(Decimal(1))

    # Then — nothing lingered on the books to misprice the next draw
    assert ledger.stored_kwh == Decimal(0)
    assert ledger.unit_cost == Decimal(0)
    assert cost == Decimal(0)


def test_battery_simultaneous_charge_and_discharge_applies_charge_first() -> None:
    # Given — a battery holding 5 kWh at €0.10 when a reading shows both a fresh
    # charge and a discharge in the same interval
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(5), Decimal("0.10"))

    # When — the charge is applied before the discharge
    ledger.charge_from_grid(Decimal(5), Decimal("0.20"))
    cost = ledger.discharge(Decimal(5))

    # Then — the discharge is priced against the blend including the fresh charge
    assert cost == Decimal("0.75")


def test_battery_round_trip_loss_is_not_inflated_leaving_stranded_cost() -> None:
    # Given — 10 kWh charged, of which only 9 is retrievable (a 10% round trip)
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(10), Decimal("0.10"))

    # When — the retrievable 9 kWh is discharged
    cost = ledger.discharge(Decimal(9))

    # Then — discharge is not inflated for the loss: it is priced at the plain
    # weighted average, and the lost kWh's cost stays stranded on the books. This
    # is the deliberate, documented optimistic bias, not a bug.
    assert cost == Decimal("0.90")
    assert ledger.stored_kwh == Decimal(1)
    assert ledger.unit_cost == Decimal("0.10")


def test_battery_rejects_a_negative_charge() -> None:
    # Given — a ledger
    ledger = BatteryLedger()

    # When / Then — a negative charge is nonsensical for an energy counter
    with pytest.raises(ValueError, match="negative"):
        ledger.charge_from_grid(Decimal(-1), OVERNIGHT)


def test_battery_rejects_a_negative_price() -> None:
    # Given — a ledger
    ledger = BatteryLedger()

    # When / Then — a negative import price cannot price a charge
    with pytest.raises(ValueError, match="negative"):
        ledger.charge_from_grid(Decimal(1), Decimal("-0.05"))


def test_battery_rejects_a_negative_discharge() -> None:
    # Given — a charged ledger
    ledger = BatteryLedger()
    ledger.charge_from_solar(Decimal(2))

    # When / Then — a negative discharge would mint energy and cost
    with pytest.raises(ValueError, match="negative"):
        ledger.discharge(Decimal(-1))


def test_battery_zero_movements_are_harmless_no_ops() -> None:
    # Given — a charged ledger
    ledger = BatteryLedger()
    ledger.charge_from_grid(Decimal(4), OVERNIGHT)

    # When — zero-energy movements are recorded
    ledger.charge_from_solar(Decimal(0))
    cost = ledger.discharge(Decimal(0))

    # Then — nothing changes and no cost is drawn
    assert cost == Decimal(0)
    assert ledger.stored_kwh == Decimal(4)
    assert ledger.unit_cost == OVERNIGHT
