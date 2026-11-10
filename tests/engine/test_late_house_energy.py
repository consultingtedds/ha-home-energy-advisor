"""House meters that report after a device has already claimed the energy (HEA-269).

A device reporting every few minutes can claim energy before the house meters
for the same interval have arrived. Its excess over what the house metered is
held as debt at the import price (ADR-0014), to be repaid when the house energy
turns up. Late house energy for an interval that has closed corrects it
(HEA-186) - and it has to repay that debt as it does, because the energy it
brings is the energy the device already claimed. Left unpaid, the debt expires
at the import price while the late energy is counted a second time: a house
served by its battery or its panels is billed for the grid it never used
(discussion 58).

A house with its own consumption meter adds a second rule. There the house
meter alone says how much the house used, and the others only say where it came
from - so a late house reading raises what the house used, and a late discharge,
generation or import reading never does.

The shapes are generated: a steady 600 W load under house meters that report
once an hour, the way a daily counter can after a restart.
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

BASE = datetime(2026, 11, 10, 1, 0, tzinfo=UTC)
TARIFF = Decimal("0.45")
OFF_PEAK = Decimal("0.15")
HOUR = 60

GRID_IMPORT = "sensor.inverter_daily_grid_import"
GRID_EXPORT = "sensor.inverter_total_grid_export"
GENERATION = "sensor.inverter_total_pv_generation"
BATTERY_CHARGE = "sensor.inverter_daily_battery_charge"
BATTERY_DISCHARGE = "sensor.inverter_daily_battery_discharge"
HOUSE = "sensor.inverter_daily_load_consumption"
STEADY_LOAD = "sensor.steady_load_energy"

# Every five minutes of a steady 600 W load
STEP = Decimal("0.05")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_home(
    roles: dict[SourceRole, str],
    windows: AccountingWindows | None = None,
    *,
    unread: tuple[str, ...] = (),
) -> Accountant:
    """A home whose meters all read zero at the start, but for ``unread``."""
    acc = Accountant(
        house_sources=roles,
        device_energy_entities={"steady_load": STEADY_LOAD},
        windows=windows,
    )
    acc.record_price(at(0), TARIFF)
    for entity in (*roles.values(), STEADY_LOAD):
        if entity not in unread:
            acc.observe(entity, at(0), Decimal(0))
    return acc


def a_generating_home() -> Accountant:
    """Import, export and generation metered; consumption derived from them."""
    return a_home(
        {
            SourceRole.GRID_IMPORT: GRID_IMPORT,
            SourceRole.GRID_EXPORT: GRID_EXPORT,
            SourceRole.GENERATION: GENERATION,
        }
    )


def a_house_metered_home(
    windows: AccountingWindows | None = None, *, unread: tuple[str, ...] = ()
) -> Accountant:
    """Every meter an inverter offers, the house's own consumption among them."""
    return a_home(
        {
            SourceRole.GRID_IMPORT: GRID_IMPORT,
            SourceRole.GRID_EXPORT: GRID_EXPORT,
            SourceRole.GENERATION: GENERATION,
            SourceRole.BATTERY_CHARGE: BATTERY_CHARGE,
            SourceRole.BATTERY_DISCHARGE: BATTERY_DISCHARGE,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        windows,
        unread=unread,
    )


def run_the_steady_load(
    acc: Accountant,
    *,
    live: tuple[str, ...],
    still: tuple[str, ...] = (GRID_IMPORT, GRID_EXPORT),
    start: int = 0,
    minutes: int = HOUR,
) -> None:
    """The load for a while, reported every five minutes beside the ``live`` meters.

    Each ``live`` meter climbs with the load from zero; each ``still`` one
    reports, unmoved, so it stays readable without supplying anything.
    """
    for minute in range(start + 5, start + minutes + 5, 5):
        climbed = STEP * ((minute - start) // 5)
        acc.observe(STEADY_LOAD, at(minute), climbed)
        for entity in live:
            acc.observe(entity, at(minute), climbed)
        for entity in still:
            acc.observe(entity, at(minute), Decimal(0))
        acc.finalize(at(minute))


def long_after(acc: Accountant, minute: int) -> None:
    """Long enough for any debt still outstanding to have expired."""
    acc.finalize(at(minute + 240))


def test_late_generation_repays_what_a_device_claimed_ahead_of_it() -> None:
    # Given - an hour of a steady load served by the panels, whose meter says
    # nothing until the hour is over. By then most of the hour's intervals have
    # closed with the device's draw and no house energy beside it
    acc = a_generating_home()
    run_the_steady_load(acc, live=())

    # When - generation reports the hour's 0.6 kWh
    acc.observe(GENERATION, at(HOUR), Decimal("0.6"))
    long_after(acc, HOUR)

    # Then - the house used 0.6 kWh of its own sunshine, once, and paid nothing
    # for it. Nothing was imported, so nothing is unreconciled either
    totals = acc.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal(0)
    assert totals.devices["steady_load"].actual_cost == Decimal(0)
    assert totals.unreconciled_kwh == Decimal(0)
    # ...and all of it is shown as sunshine, the house's and the device's alike,
    # as HEA-278 asks
    assert totals.whole_home.energy_from_generation == Decimal("0.6")
    assert totals.devices["steady_load"].energy_from_generation == Decimal("0.6")


def test_a_late_house_reading_is_served_by_the_panels_beside_it() -> None:
    # Given - the panels reporting live, the house meter silent for the hour
    acc = a_house_metered_home()
    run_the_steady_load(
        acc,
        live=(GENERATION,),
        still=(GRID_IMPORT, GRID_EXPORT, BATTERY_CHARGE, BATTERY_DISCHARGE),
    )

    # When
    acc.observe(HOUSE, at(HOUR), Decimal("0.6"))
    long_after(acc, HOUR)

    # Then - dropping the late house energy left the device's debt to expire at
    # the import price: 0.27 for sunshine
    totals = acc.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal(0)
    assert totals.unreconciled_kwh == Decimal(0)


def test_a_late_house_reading_is_served_by_the_battery_discharging_beside_it() -> None:
    # Given - a battery filled off-peak with 1 kWh, then an hour of the load on
    # the battery at peak, its discharge reported live and the house meter not.
    # The meters that move with the load are first read as it starts: one quiet
    # since the start of the charge would spread its step across the charge too
    with_the_load = (HOUSE, BATTERY_DISCHARGE, STEADY_LOAD)
    acc = a_house_metered_home(unread=with_the_load)
    acc.record_price(at(0), OFF_PEAK)
    for minute in range(5, 35, 5):
        charged = Decimal("0.2") * (minute // 5)
        acc.observe(GRID_IMPORT, at(minute), min(charged, Decimal(1)))
        acc.observe(BATTERY_CHARGE, at(minute), min(charged, Decimal(1)))
        acc.finalize(at(minute))
    acc.record_price(at(30), TARIFF)
    for entity in with_the_load:
        acc.observe(entity, at(30), Decimal(0))
    run_the_steady_load(
        acc,
        live=(BATTERY_DISCHARGE,),
        still=(GENERATION, GRID_EXPORT),
        start=30,
    )

    # When
    acc.observe(HOUSE, at(30 + HOUR), Decimal("0.6"))
    long_after(acc, 30 + HOUR)

    # Then - the charge went into the battery, not the house, so the house used
    # the hour's 0.6 kWh at what it cost to store, and every cent saved against
    # the peak is the battery's
    totals = acc.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal("0.6") * OFF_PEAK
    assert totals.whole_home.battery_savings == Decimal("0.6") * (TARIFF - OFF_PEAK)
    assert totals.unreconciled_kwh == Decimal(0)


def test_a_late_house_reading_explains_the_import_already_counted() -> None:
    # Given - the import meter reporting live, so the hour closed on grid energy
    # beyond what the silent house meter had said
    acc = a_house_metered_home()
    run_the_steady_load(
        acc,
        live=(GRID_IMPORT,),
        still=(GRID_EXPORT, GENERATION, BATTERY_CHARGE, BATTERY_DISCHARGE),
    )

    # When
    acc.observe(HOUSE, at(HOUR), Decimal("0.6"))
    long_after(acc, HOUR)

    # Then - the house reading is the grid energy already counted, not more
    totals = acc.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal("0.6") * TARIFF


def test_a_late_house_reading_after_a_restart_is_still_served_by_the_panels() -> None:
    # Given - half the hour, a restart, then the other half: the house meter
    # silent throughout, as a daily counter can be while it comes back
    acc = a_house_metered_home()
    still = (GRID_IMPORT, GRID_EXPORT, BATTERY_CHARGE, BATTERY_DISCHARGE)
    run_the_steady_load(acc, live=(GENERATION,), still=still, minutes=30)
    acc.flush(at(30))
    restored = a_house_metered_home()
    restored.restore(acc.snapshot())
    for minute in range(35, HOUR + 5, 5):
        restored.observe(STEADY_LOAD, at(minute), STEP * (minute // 5))
        restored.observe(GENERATION, at(minute), STEP * (minute // 5))
        for entity in still:
            restored.observe(entity, at(minute), Decimal(0))
        restored.finalize(at(minute))

    # When
    restored.observe(HOUSE, at(HOUR), Decimal("0.6"))
    long_after(restored, HOUR)

    # Then
    totals = restored.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal(0)
    assert totals.unreconciled_kwh == Decimal(0)


def test_a_late_discharge_never_raises_what_a_metered_house_used() -> None:
    # Given - the house meter reporting live, the discharge that served it not
    acc = a_house_metered_home()
    run_the_steady_load(
        acc,
        live=(HOUSE,),
        still=(GRID_IMPORT, GRID_EXPORT, GENERATION, BATTERY_CHARGE),
    )

    # When
    acc.observe(BATTERY_DISCHARGE, at(HOUR), Decimal("0.6"))
    long_after(acc, HOUR)

    # Then - the house meter said 0.6, and the discharge says where it came from,
    # not that the house used it again
    assert acc.totals().whole_home.energy_kwh == Decimal("0.6")


def test_late_generation_never_raises_what_a_metered_house_used() -> None:
    # Given
    acc = a_house_metered_home()
    run_the_steady_load(
        acc,
        live=(HOUSE,),
        still=(GRID_IMPORT, GRID_EXPORT, BATTERY_CHARGE, BATTERY_DISCHARGE),
    )

    # When
    acc.observe(GENERATION, at(HOUR), Decimal("0.6"))
    long_after(acc, HOUR)

    # Then
    assert acc.totals().whole_home.energy_kwh == Decimal("0.6")


def test_a_late_import_charges_what_it_cost_over_the_sunshine_it_replaced() -> None:
    # Given - the house and the panels reporting live, so the hour closed as
    # sunshine; the import meter says nothing until it is over
    acc = a_house_metered_home()
    run_the_steady_load(
        acc,
        live=(HOUSE, GENERATION),
        still=(GRID_EXPORT, BATTERY_CHARGE, BATTERY_DISCHARGE),
    )
    published = acc.totals().whole_home

    # When - the import meter reveals the hour came off the grid after all
    acc.observe(GRID_IMPORT, at(HOUR), Decimal("0.6"))
    long_after(acc, HOUR)

    # Then - the house used no more than its meter said, and paid the grid for
    # it. Where it came from stays as published: a published share never falls
    totals = acc.totals().whole_home
    assert totals.energy_kwh == Decimal("0.6")
    assert totals.actual_cost == Decimal("0.6") * TARIFF
    assert totals.cost_savings == Decimal(0)
    assert totals.energy_from_generation == published.energy_from_generation


def test_a_house_reading_past_the_ring_is_dropped_but_says_so() -> None:
    # Given - a ring a quarter of an hour deep, under an hour of closed intervals
    acc = a_house_metered_home(AccountingWindows(retention=timedelta(minutes=15)))
    run_the_steady_load(
        acc,
        live=(GENERATION,),
        still=(GRID_IMPORT, GRID_EXPORT, BATTERY_CHARGE, BATTERY_DISCHARGE),
    )

    # When
    acc.observe(HOUSE, at(HOUR), Decimal("0.6"))
    acc.finalize(at(HOUR + 30))

    # Then - the energy with nowhere to go is on the record, not silently gone
    decisions = acc.source_diagnostics()[HOUSE].recent_decisions
    assert any(entry.reason is DecisionReason.DROPPED_LATE for entry in decisions)
