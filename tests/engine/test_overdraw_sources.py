"""Where energy a device drew ahead of the house meters came from (HEA-278).

An interval whose tracked draw outruns its house meters gives sources only to
what those meters metered. The rest is energy the meters have not reported yet,
so nothing is known about what served it. When a later interval's surplus or a
late house reading repays it, that is learned: the repaid energy takes the
source that repaid it, on the device and on the house. Debt that expires
unrepaid keeps no source, and shows as energy unaccounted for.

The source figures only ever rise, so a source is added to energy that has none
and never taken from energy that has one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    DeviceTotals,
    SourceRole,
)

BASE = datetime(2026, 11, 10, 1, 0, tzinfo=UTC)
TARIFF = Decimal("0.45")
EXACT = Decimal("0.000000001")

GRID_IMPORT = "sensor.inverter_total_grid_import"
GRID_EXPORT = "sensor.inverter_total_grid_export"
GENERATION = "sensor.inverter_total_pv_generation"
COARSE_STEP_LOAD = "sensor.coarse_step_load_energy"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_generating_home() -> Accountant:
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID_IMPORT,
            SourceRole.GRID_EXPORT: GRID_EXPORT,
            SourceRole.GENERATION: GENERATION,
        },
        device_energy_entities={"coarse_step_load": COARSE_STEP_LOAD},
    )
    acc.record_price(at(0), TARIFF)
    for entity in (GRID_IMPORT, GRID_EXPORT, GENERATION, COARSE_STEP_LOAD):
        acc.observe(entity, at(0), Decimal(0))
    return acc


def sourced(totals: DeviceTotals) -> Decimal:
    return (
        totals.energy_from_grid
        + totals.energy_from_generation
        + totals.energy_from_battery
    )


def test_a_later_intervals_surplus_gives_the_overdraw_its_own_source() -> None:
    # Given - the device steps 0.1 kWh inside the first five minutes, while the
    # generation meter that served it reports the same 0.1 at minute nine, so
    # five ninths of it land beside the device and four ninths in the next
    # interval, which has nothing else to spend them on
    acc = a_generating_home()
    acc.observe(COARSE_STEP_LOAD, at(4), Decimal("0.1"))
    acc.observe(GENERATION, at(4), Decimal(0))
    acc.observe(GENERATION, at(9), Decimal("0.1"))

    # When
    acc.finalize(at(60))

    # Then - the device's 0.1 kWh was all sunshine, the part metered beside it
    # and the part repaid a few minutes later alike, and so was the house's
    totals = acc.totals()
    device = totals.devices["coarse_step_load"]
    assert device.energy_kwh.quantize(EXACT) == Decimal("0.100000000")
    assert device.energy_from_generation.quantize(EXACT) == Decimal("0.100000000")
    assert totals.whole_home.energy_from_generation.quantize(EXACT) == Decimal(
        "0.100000000"
    )
    assert device.energy_from_grid == Decimal(0)


def test_an_overdraw_that_expires_unrepaid_keeps_no_source() -> None:
    # Given - the device steps 0.1 kWh, and no house meter ever reports it
    acc = a_generating_home()
    acc.observe(COARSE_STEP_LOAD, at(4), Decimal("0.1"))

    # When - long enough for the debt to expire
    acc.finalize(at(240))

    # Then - nothing was learned about what served it, so nothing is claimed: it
    # is energy unaccounted for, which is what the household's own meters say
    totals = acc.totals()
    device = totals.devices["coarse_step_load"]
    assert device.energy_kwh == Decimal("0.1")
    assert sourced(device) == Decimal(0)
    assert sourced(totals.whole_home) == Decimal(0)
    assert totals.unreconciled_kwh == Decimal("0.1")


def test_a_device_outrunning_a_sliver_of_import_is_not_shown_all_grid() -> None:
    # Given - the device steps 0.1 kWh in an interval where the house metered
    # only 0.02 kWh from the grid, and no house meter accounts for the rest
    acc = a_generating_home()
    acc.observe(COARSE_STEP_LOAD, at(4), Decimal("0.1"))
    acc.observe(GRID_IMPORT, at(4), Decimal("0.02"))

    # When
    acc.finalize(at(240))

    # Then - the grid served the 0.02 that was metered, and no more
    device = acc.totals().devices["coarse_step_load"]
    assert device.energy_from_grid == Decimal("0.02")
    assert sourced(device) == Decimal("0.02")
