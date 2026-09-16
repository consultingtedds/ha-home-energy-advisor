"""House counters that tick a whole kWh at a time, and never together.

An inverter that publishes its lifetime figures as whole kilowatt-hours is
ordinary, and it reports each of them when it pleases. Within one 5-minute
interval, then, generation can tick while export has not, or the battery can
take a charge before the import meter that supplied it moves.

What the house used is not knowable inside such an interval, only across the few
that follow. So these tests assert over a period, exactly as the reconciliation
tests do: what the meters recorded, against what was published, once the
counterpart has arrived.

Dropping the leftover instead is what brought this here. It can only ever raise
what the house is said to have used, so it never cancels, and a household with
coarse counters watches their total drift above their own meter (HEA-133,
GitHub #19, ADR-0015's amendment).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)

BASE = datetime(2026, 9, 15, 10, 0, tzinfo=UTC)
TARIFF = Decimal("0.30")

GRID_IMPORT = "sensor.inverter_total_energy_import"
GRID_EXPORT = "sensor.inverter_total_energy_export"
GENERATION = "sensor.inverter_total_pv_generation"
BATTERY_CHARGE = "sensor.inverter_total_battery_charge"
BATTERY_DISCHARGE = "sensor.inverter_total_battery_discharge"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_generating_home() -> Accountant:
    """A home whose only meters are its inverter's, with no house meter.

    The shape of the household in GitHub #19: generation and export are metered,
    household consumption is not, so consumption is derived from the balance.
    """
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID_IMPORT,
            SourceRole.GRID_EXPORT: GRID_EXPORT,
            SourceRole.GENERATION: GENERATION,
            SourceRole.BATTERY_CHARGE: BATTERY_CHARGE,
            SourceRole.BATTERY_DISCHARGE: BATTERY_DISCHARGE,
        },
        device_energy_entities={},
    )
    acc.record_price(at(0), TARIFF)
    for entity in (
        GRID_IMPORT,
        GRID_EXPORT,
        GENERATION,
        BATTERY_CHARGE,
        BATTERY_DISCHARGE,
    ):
        acc.observe(entity, at(0), Decimal(0))
    return acc


def test_charging_before_the_import_meter_ticks_is_not_charged_to_the_house() -> None:
    # Given - a home drawing from the grid to fill its battery. The battery
    # counter records the 1 kWh charge at :05; the import counter, which only
    # moves in whole kWh, catches up at :10. Nothing else runs, so the house
    # itself consumed nothing: that kWh is in the battery
    acc = a_generating_home()

    # When
    acc.observe(BATTERY_CHARGE, at(5), Decimal(1))
    acc.observe(GRID_IMPORT, at(10), Decimal(1))
    acc.finalize(at(60))

    # Then - the house is charged for nothing. Taking each interval alone, the
    # charge arrives with no import beside it and looks like the sun filling the
    # battery for free, and the import that follows looks like a kWh the house
    # burned - which is also the same kWh counted twice, once on its way in and
    # again when the battery gives it back
    assert acc.totals().whole_home.energy_kwh == Decimal(0)


def test_exported_generation_is_taken_off_the_generation_that_follows() -> None:
    # Given - two hours of a house generating while nobody is in, so every kWh
    # made goes straight back out. The two counters tick the same kilowatt-hours
    # five minutes apart, over and over, which is what quantised counters do
    acc = a_generating_home()
    generated = exported = Decimal(0)
    minute = 0
    for _ in range(6):
        minute += 5
        generated += 1
        acc.observe(GENERATION, at(minute), generated)
        minute += 5
        exported += 1
        acc.observe(GRID_EXPORT, at(minute), exported)

    # ...and one last generation tick, by which time every export has a
    # generation figure to be taken from
    minute += 5
    generated += 1
    acc.observe(GENERATION, at(minute), generated)
    acc.finalize(at(minute + 60))

    # Then - the house is credited with the one kWh it kept, and not with the
    # six it sent out. Flooring each interval at zero published every one of
    # those six as energy the house had used
    assert generated - exported == Decimal(1)
    assert acc.totals().whole_home.energy_kwh == Decimal(1)


def test_an_export_still_waiting_for_its_generation_is_held_not_dropped() -> None:
    # Given - the same house, stopped at the moment an export has ticked and the
    # generation counter has not caught up
    acc = a_generating_home()
    acc.observe(GENERATION, at(5), Decimal(2))
    acc.observe(GRID_EXPORT, at(10), Decimal(2))
    acc.finalize(at(70))

    # Then - what cannot be settled yet is held, and the download says so. It is
    # taken off the next generation rather than forgotten, which is what stops a
    # household's total drifting above their own meter
    assert acc.balance_diagnostics()["export_awaiting_generation"] == "1"


def test_a_days_worth_of_quantised_counters_matches_the_meters() -> None:
    # Given - an ordinary generating hour, every counter quantised to whole kWh
    # and none of them ticking in the same interval as another. The meters
    # record: 3 generated, 1 exported, 1 charged into the battery, 1 discharged
    # out of it, 2 imported
    acc = a_generating_home()

    # When
    acc.observe(GENERATION, at(5), Decimal(3))
    acc.observe(GRID_EXPORT, at(10), Decimal(1))
    acc.observe(BATTERY_CHARGE, at(15), Decimal(1))
    acc.observe(GRID_IMPORT, at(20), Decimal(2))
    acc.observe(BATTERY_DISCHARGE, at(25), Decimal(1))
    # ...and the generation counter ticks once more, so the export and the
    # charge before it both have a figure to be taken from
    acc.observe(GENERATION, at(30), Decimal(4))
    acc.finalize(at(90))

    # Then - the house used what the meters say it used: what came in, less what
    # left or was stored. 4 generated + 2 imported + 1 discharged, less 1
    # exported and 1 charged, is 5. Quantised because spreading a step across
    # intervals divides, and the last digit of a 28-digit Decimal is not a
    # household's concern
    published = acc.totals().whole_home.energy_kwh
    assert published.quantize(Decimal("0.000000001")) == Decimal("5.000000000")
