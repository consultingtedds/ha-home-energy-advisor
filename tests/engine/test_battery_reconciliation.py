"""Booking the cost of energy the battery never gave back (HEA-178).

The ledger's inventory is inferred, not measured, and two things leave a battery
by a door it does not subtract from: round-trip losses, and any discharge its
configured meter does not count. So it drifts upwards for ever - 15.69 kWh on the
books of a 5 kWh battery on the reference instance - and because its only
self-correction is being drained to empty, the drift is what prevents the
correction.

Reconciling against what the battery really holds fixes the inventory. These
tests are about the **money** that write-down releases, which is the part that
cannot simply be dropped: when the battery charges from the grid, that import is
taken *out* of house consumption for the interval and only becomes a cost when the
energy is discharged. So energy that goes in and never comes out is money the
household really paid the grid that nothing ever publishes.

**The cost is booked and the energy is not**, and that asymmetry is deliberate.
The loss happens inside the battery, so the house-consumption meter never saw it;
publishing it as consumption would push the published total above the meter and
trip the unreconciled-energy Repair at 1 %, on the reference instance by 2-3 %.
The money belongs in the totals because the grid really was paid it. The energy
does not, because the house really did not use it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
OVERNIGHT = Decimal("0.093")
PEAK = Decimal("0.234")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _home_with_a_charged_battery() -> Accountant:
    """A household that charged 4 kWh from the grid overnight and used 2 of it."""
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.battery_discharge", "0"),
        ("sensor.house_load", "0"),
        ("sensor.coarse_step_energy", "0"),
    ):
        acc.observe(entity, at(5), Decimal(value))
    acc.record_price(at(5), PEAK)
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.battery_discharge", "2.0"),
        ("sensor.house_load", "2.0"),
        ("sensor.coarse_step_energy", "2.0"),
    ):
        acc.observe(entity, at(10), Decimal(value))
    acc.finalize(at(40))
    return acc


def test_the_write_off_is_booked_as_cost_the_household_really_paid() -> None:
    # Given - a household whose ledger believes it holds 2 kWh at the overnight
    # rate, when the battery is actually empty
    acc = _home_with_a_charged_battery()
    before = acc.totals().whole_home.actual_cost
    assert Decimal(acc.battery_diagnostics()["stored_kwh"]) == Decimal("2.0")

    # When - the battery reports itself flat
    acc.reconcile_battery(Decimal(0))

    # Then - the stranded EUR 0.186 is published. That money was paid to the grid
    # to charge the battery and is taken out of house consumption at charge time,
    # so until it is booked here nothing ever publishes it and the household's
    # totals sit below their real bill
    assert acc.totals().whole_home.actual_cost == before + Decimal("0.186")


def test_the_write_off_publishes_no_energy() -> None:
    # Given - a household with a drifted ledger
    acc = _home_with_a_charged_battery()
    energy_before = acc.totals().whole_home.energy_kwh
    share_before = acc.unreconciled_share()

    # When - the inventory is written down
    acc.reconcile_battery(Decimal(0))

    # Then - not a kilowatt-hour is added. The loss happened inside the battery,
    # so the house meter never saw it; publishing it as consumption would push the
    # published total above the meter and raise the unreconciled Repair, which on
    # the reference instance it would do by 2-3 %
    assert acc.totals().whole_home.energy_kwh == energy_before
    assert acc.unreconciled_share() == share_before


def test_the_write_off_leaves_cost_savings_alone() -> None:
    # Given - a household with a drifted ledger
    acc = _home_with_a_charged_battery()
    savings_before = acc.totals().whole_home.cost_savings

    # When - the inventory is written down
    acc.reconcile_battery(Decimal(0))

    # Then - unchanged, because the counterfactual moves with the cost: this
    # energy *was* bought from the grid, so what it would have cost from the grid
    # is what it cost. Whether a round-trip loss should reduce what the battery
    # saved is a separate question, and a figure that answers it by accident is
    # worse than one that does not answer it at all (HEA-174)
    assert acc.totals().whole_home.cost_savings == savings_before


def test_the_write_off_charges_no_device_for_it() -> None:
    # Given - a household with one tracked device carrying real cost
    acc = _home_with_a_charged_battery()
    device_before = acc.totals().devices["coarse_step_aircon"].actual_cost
    assert device_before > 0

    # When - the inventory is written down
    acc.reconcile_battery(Decimal(0))

    # Then - the device is untouched. No appliance ran on the energy the battery
    # lost, so charging one for it would move money between households' devices
    # to fix a figure about the battery
    assert acc.totals().devices["coarse_step_aircon"].actual_cost == device_before


def test_a_battery_holding_what_the_ledger_thinks_books_nothing() -> None:
    # Given - a household whose ledger agrees with its battery
    acc = _home_with_a_charged_battery()
    before = acc.totals().whole_home.actual_cost

    # When - the battery confirms the 2 kWh on the books
    acc.reconcile_battery(Decimal("2.0"))

    # Then - nothing is booked. The ordinary case has to cost nothing, or every
    # interval would publish a write-off it invented
    assert acc.totals().whole_home.actual_cost == before


def test_the_written_off_cost_is_explainable_from_the_diagnostics() -> None:
    # Given / When - a household whose ledger is written down twice
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal("1.0"))
    acc.reconcile_battery(Decimal(0))

    # Then - the running total is in the download. A cost that appears in the
    # household's total with nothing anywhere explaining it is exactly the kind of
    # figure this project's diagnostics exist to account for
    assert Decimal(acc.battery_diagnostics()["written_off_cost"]) == Decimal("0.186")


def test_the_written_off_total_survives_a_restart() -> None:
    # Given - a household that has written some off
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal(0))
    snapshot = acc.snapshot()

    # When - the engine is rebuilt from the snapshot
    resumed = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    resumed.restore(snapshot)

    # Then - it is carried, so the diagnostics still explain a cost the household
    # is still being shown
    assert Decimal(resumed.battery_diagnostics()["written_off_cost"]) == Decimal(
        "0.186"
    )


def test_a_snapshot_written_before_this_existed_still_restores() -> None:
    # Given - a snapshot as the released version wrote it, with no such figure
    acc = _home_with_a_charged_battery()
    snapshot = acc.snapshot()
    del snapshot["battery"]["written_off_cost"]

    # When / Then - it restores, reading the absent total as nothing rather than
    # refusing. Refusing would cold-start every installed household and throw away
    # the very ledger this ticket is about (ADR-0021)
    resumed = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={},
    )
    resumed.restore(snapshot)
    assert Decimal(resumed.battery_diagnostics()["written_off_cost"]) == Decimal(0)
