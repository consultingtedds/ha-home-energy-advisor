"""Whose energy a battery charge is, when solar, grid and battery are all busy.

The meters cannot see where energy went inside one interval. Where the house
imports, the panels generate and the battery charges in the same five minutes,
what charged the battery depends on why it was charging, which the household
says (HEA-233):

- **only from spare solar**, the default: the loads took turns inside the
  interval, the battery charging in the minutes of surplus and the grid feeding
  the house in the others, so generation charged it first;
- **from the grid too**, on a schedule or by an optimiser: the import exists
  because of the charge, so it charged the battery first;
- **solar only**, grid charging off: generation charged it and nothing else,
  and what generation has not yet covered waits for the generation tick still
  to come.

The interval is one five-minute bucket from the household that reported it
(Discussion 35), at a solar-first inverter with no house meter: import 0.0117,
generation 0.0204, charge 0.0212 kWh. No device is tracked, so everything the
house used is Untracked and its sources read straight off.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.house_balance import ChargeSource

START = datetime(2026, 10, 16, 9, 50, tzinfo=UTC)
PRICE = Decimal("0.3948")
IMPORTED = Decimal("0.0117")
GENERATED = Decimal("0.0204")
CHARGED = Decimal("0.0212")


def _busy_interval(
    charge_source: ChargeSource | None, *, then_generated: Decimal = Decimal(0)
) -> Accountant:
    """One interval with import, generation and charging all at once.

    `then_generated` is a generation tick five minutes later, alone: the
    panels' meter catching up with a charge that ran ahead of it.
    """
    # Left out entirely for the default, so it is the constructor's own default
    # under test rather than an explicit choice.
    options: dict[str, Any] = (
        {} if charge_source is None else {"charge_source": charge_source}
    )
    accountant = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: "sensor.solar",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
        },
        device_energy_entities={},
        **options,
    )
    accountant.record_price(START, PRICE)
    meters = (
        "grid_import",
        "grid_export",
        "solar",
        "battery_charge",
        "battery_discharge",
    )
    for meter in meters:
        accountant.observe(f"sensor.{meter}", START, Decimal(0))
    later = START + timedelta(minutes=5)
    accountant.observe("sensor.grid_import", later, IMPORTED)
    accountant.observe("sensor.solar", later, GENERATED)
    accountant.observe("sensor.battery_charge", later, CHARGED)
    accountant.observe("sensor.grid_export", later, Decimal(0))
    accountant.observe("sensor.battery_discharge", later, Decimal(0))
    if then_generated:
        after = later + timedelta(minutes=5)
        accountant.observe("sensor.grid_import", after, IMPORTED)
        accountant.observe("sensor.solar", after, GENERATED + then_generated)
        accountant.observe("sensor.battery_charge", after, CHARGED)
        accountant.observe("sensor.grid_export", after, Decimal(0))
        accountant.observe("sensor.battery_discharge", after, Decimal(0))
    accountant.finalize(START + timedelta(minutes=30))
    return accountant


def _stored_cost(accountant: Accountant) -> Decimal:
    return Decimal(accountant.snapshot()["battery"]["stored_cost"])


def test_by_default_solar_fills_the_battery_and_the_grid_runs_the_house() -> None:
    # Given / When - a household that has said nothing
    accountant = _busy_interval(None)
    untracked = accountant.totals().untracked

    # Then - the battery took the 0.0204 of sunshine and 0.0008 of import, so
    # the house ran on the other 0.0109 imported, at the price of the time
    assert untracked.energy_kwh == Decimal("0.0109")
    assert untracked.energy_from_grid == Decimal("0.0109")
    assert untracked.energy_from_generation == Decimal(0)
    assert untracked.actual_cost == Decimal("0.0109") * PRICE
    assert _stored_cost(accountant) == Decimal("0.0008") * PRICE


def test_spare_solar_is_the_default_when_asked_for_by_name() -> None:
    # Given / When / Then - choosing it is the same as saying nothing
    chosen = _busy_interval(ChargeSource.SPARE_SOLAR)
    default = _busy_interval(None)
    assert chosen.totals().untracked == default.totals().untracked
    assert _stored_cost(chosen) == _stored_cost(default)


def test_a_battery_charged_from_the_grid_too_takes_the_import_first() -> None:
    # Given / When - an optimiser charging from the grid while the sun is up
    accountant = _busy_interval(ChargeSource.GRID_TOO)
    untracked = accountant.totals().untracked

    # Then - all 0.0117 imported went into the battery because of the charge,
    # so the house kept 0.0109 of sunshine, at no cost
    assert untracked.energy_kwh == Decimal("0.0109")
    assert untracked.energy_from_generation == Decimal("0.0109")
    assert untracked.energy_from_grid == Decimal(0)
    assert untracked.actual_cost == Decimal(0)
    assert _stored_cost(accountant) == Decimal("0.0117") * PRICE


def test_a_solar_only_battery_never_takes_import() -> None:
    # Given / When - grid charging is off, and the charge meter has run 0.0008
    # ahead of the panels' meter in this interval
    accountant = _busy_interval(ChargeSource.SOLAR_ONLY)
    untracked = accountant.totals().untracked

    # Then - every kWh imported ran the house, and the battery holds sunshine
    # alone: what it later gives back costs nothing
    assert untracked.energy_from_grid == IMPORTED
    assert untracked.energy_from_generation == Decimal(0)
    assert untracked.actual_cost == IMPORTED * PRICE
    assert _stored_cost(accountant) == Decimal(0)


def test_a_solar_only_charge_ahead_of_its_generation_waits_for_the_tick() -> None:
    # Given / When - five minutes later the panels' meter catches up by 0.0010,
    # with nothing else moving
    accountant = _busy_interval(
        ChargeSource.SOLAR_ONLY, then_generated=Decimal("0.0010")
    )
    untracked = accountant.totals().untracked

    # Then - 0.0008 of the tick settles the charge that was waiting for it and
    # the other 0.0002 ran the house. The house's total is what the meters say
    # it used across both - 0.0117 + 0.0214 - 0.0212 - and still no import was
    # ever booked to the battery
    assert untracked.energy_kwh == Decimal("0.0119")
    assert untracked.energy_from_grid == IMPORTED
    assert untracked.energy_from_generation == Decimal("0.0002")
    assert _stored_cost(accountant) == Decimal(0)
