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
    AccountingWindows,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.energy_source import DecisionReason

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


def test_battery_discharged_straight_to_export_is_not_booked_as_consumption() -> None:
    # Given - a house with no generation and low load, discharging its battery
    # straight out to the grid. Nothing generated, so the old export clamp had
    # no source to take the export from except a floor at zero
    acc = a_generating_home()

    # When - the battery discharges 4 kWh and all 4 are exported in the same
    # interval, with no generation and negligible import
    acc.observe(BATTERY_DISCHARGE, at(5), Decimal(4))
    acc.observe(GRID_EXPORT, at(5), Decimal(4))
    acc.finalize(at(60))

    # Then - the house is not billed for energy that went straight through it.
    # Charging the export to the discharge before it is booked as consumption
    # is what stops a house that empties its battery into the grid from being
    # told it burned every kWh the battery gave up
    assert acc.totals().whole_home.energy_kwh == Decimal(0)


def test_only_the_share_of_a_discharge_not_exported_is_booked_as_consumption() -> None:
    # Given - the same house, discharging more than it exports: some of the
    # battery served the house, the rest left as export
    acc = a_generating_home()

    # When - 4 kWh discharged, only 3 kWh of it exported
    acc.observe(BATTERY_DISCHARGE, at(5), Decimal(4))
    acc.observe(GRID_EXPORT, at(5), Decimal(3))
    acc.finalize(at(60))

    # Then - only the 1 kWh that stayed in the house is booked, not the full 4
    assert acc.totals().whole_home.energy_kwh == Decimal(1)


def test_export_unexplained_by_generation_and_discharge_is_held_not_dropped() -> None:
    # Given - a house whose export outruns both what it generated and what its
    # battery discharged this interval - the counterpart is still to come
    acc = a_generating_home()

    # When - export ticks 5 kWh, while generation and discharge together only
    # explain 4 of it so far
    acc.observe(GENERATION, at(5), Decimal(2))
    acc.observe(BATTERY_DISCHARGE, at(5), Decimal(2))
    acc.observe(GRID_EXPORT, at(5), Decimal(5))
    acc.finalize(at(60))

    # Then - what neither could cover is carried, not forgotten
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


def test_a_house_counter_silent_past_the_ring_still_reaches_the_total() -> None:
    """A meter that goes quiet for a night, then reveals the whole rise (HEA-186).

    A cloud-polled inverter does this: its value climbs while the reading we see
    stands still, and one poll later the whole accrual arrives with a span
    reaching back hours. The energy is real and the span is right - what has to
    hold is that all of it is counted.

    Portions falling in intervals that have already closed cannot be placed
    where they belong, and dropping them loses energy the house genuinely used.
    A device's late energy is reattributed inside the retained ring; a house
    meter's had nowhere to go, so 2.17 kWh of 2.2 silently disappeared.
    """
    # Given - a home importing steadily all night while its generation meter
    # says nothing at all
    acc = a_generating_home()
    minutes_of_night = 1070
    for minute in range(5, minutes_of_night + 5, 5):
        acc.observe(GRID_IMPORT, at(minute), Decimal("0.002") * minute)
        acc.finalize(at(minute))

    # When - the generation meter finally reports, revealing 2.2 kWh that accrued
    # right across the night
    acc.observe(GENERATION, at(minutes_of_night), Decimal("2.2"))
    acc.finalize(at(minutes_of_night + 30))

    # Then - the house is credited with all of it. The meters recorded 2.14
    # imported and 2.2 generated, and with nothing exported or stored that is
    # what the house used
    totals = acc.totals()
    assert totals.whole_home.energy_from_generation.quantize(
        Decimal("0.001")
    ) == Decimal("2.200")
    assert totals.whole_home.energy_kwh.quantize(Decimal("0.001")) == Decimal("4.340")


def test_late_generation_is_a_saving_rather_than_a_charge() -> None:
    # Given - a home that imported through an hour, with every interval of it
    # closed. Finalising well past the hour puts the whole of the generation
    # delta below the watermark, so all of it takes the correction path rather
    # than part of it landing live
    acc = a_generating_home()
    for minute in range(5, 65, 5):
        acc.observe(GRID_IMPORT, at(minute), Decimal("0.01") * minute)
    acc.finalize(at(200))
    before = acc.totals().whole_home

    # When - generation reports late for intervals that have closed
    acc.observe(GENERATION, at(60), Decimal("1.0"))
    acc.finalize(at(260))

    # Then - the household used it and did not pay for it. The counterfactual is
    # the import price, so what arrives is saving, not spending: charging the
    # bucket's blend would bill a household for their own sunshine
    after = acc.totals().whole_home
    assert after.energy_kwh > before.energy_kwh
    assert after.actual_cost == before.actual_cost
    assert after.cost_savings > before.cost_savings


def test_a_late_export_never_pulls_a_published_figure_down() -> None:
    """Export subtracts, and a finalised figure only ever rises (HEA-85).

    Import, generation and a discharge all add to what the house used, so a late
    one can correct the interval it served. Export and battery charge subtract,
    so applying them to a closed interval would publish a whole-home total lower
    than the one already shown - which Home Assistant's statistics read as a
    meter reset. `HouseBalance` carries both forward instead.
    """
    # Given - a home that has generated and had its total published
    acc = a_generating_home()
    acc.observe(GENERATION, at(5), Decimal(3))
    for minute in range(10, 70, 5):
        acc.finalize(at(minute))
    published = acc.totals().whole_home.energy_kwh
    assert published > 0

    # When - the export meter finally ticks for intervals long closed
    acc.observe(GRID_EXPORT, at(60), Decimal(2))
    acc.finalize(at(180))

    # Then - nothing the household has already been shown goes backwards
    assert acc.totals().whole_home.energy_kwh >= published


def test_a_house_portion_past_the_ring_is_dropped_but_says_so() -> None:
    """Beyond the ring the choice is losing the energy or misdating it.

    ADR-0006 already made it for devices: dropped, with a `DROPPED_LATE` entry,
    never silently. A house meter gets the same, so a household whose total sits
    under their own meter can be shown why from the diagnostics download.
    """
    # Given - a home whose ring keeps only half an hour, and an hour of closed
    # intervals behind it
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID_IMPORT,
            SourceRole.GENERATION: GENERATION,
        },
        device_energy_entities={},
        windows=AccountingWindows(retention=timedelta(minutes=30)),
    )
    acc.record_price(at(0), TARIFF)
    acc.observe(GRID_IMPORT, at(0), Decimal(0))
    acc.observe(GENERATION, at(0), Decimal(0))
    for minute in range(5, 125, 5):
        acc.observe(GRID_IMPORT, at(minute), Decimal("0.01") * minute)
        acc.finalize(at(minute))

    # When - generation reveals an hour that has already fallen out of the ring
    acc.observe(GENERATION, at(120), Decimal("1.0"))
    acc.finalize(at(180))

    # Then - the loss is on the record rather than invisible, and the record says
    # how much was lost. The ring holds half an hour of a 2-hour reveal, so the
    # portions before it are dropped and the diagnostics name the quantity a
    # household's total is short by
    decisions = acc.source_diagnostics()[GENERATION].recent_decisions
    dropped = [
        entry for entry in decisions if entry.reason is DecisionReason.DROPPED_LATE
    ]
    assert dropped != []
    # The reveal spans 120 minutes. The watermark trails the last finalisation by
    # the lateness margin, and the ring holds 30 minutes behind that, so the
    # first 70 of those minutes have nowhere to go: 70/120 of the kilowatt-hour
    lost = sum((entry.kwh or Decimal(0) for entry in dropped), Decimal(0))
    assert lost.quantize(Decimal("0.0001")) == (Decimal(70) / Decimal(120)).quantize(
        Decimal("0.0001")
    )
