"""A household whose generation comes from more than one meter (HEA-219).

Home Assistant's Energy Dashboard takes any number of solar sources and adds
them up; a household with panels on two inverter inputs has two counters and no
single one that holds the lot. The engine counts each meter on its own and adds
what each revealed, which is the only way that survives one of them resetting: a
sum of two counters is not itself a counter once either one falls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)
PEAK = Decimal("0.30")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _two_panel_home() -> Accountant:
    """Import, export and two generation meters, with no house meter.

    No house meter on purpose: consumption is then derived from the balance, so
    every kWh of generation the engine sees or misses shows in Untracked.
    """
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: (
                "sensor.east_array_energy",
                "sensor.west_array_energy",
            ),
        },
        device_energy_entities={},
    )


def _baseline(acc: Accountant, east: str = "0", west: str = "0") -> None:
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.grid_export", at(0), Decimal(0))
    acc.observe("sensor.east_array_energy", at(0), Decimal(east))
    acc.observe("sensor.west_array_energy", at(0), Decimal(west))


def test_both_meters_are_counted_and_added() -> None:
    # Given
    acc = _two_panel_home()
    _baseline(acc)

    # When - one interval: the east array makes 1.5 kWh, the west 0.5, the house
    # imports 1 and exports 1
    acc.observe("sensor.east_array_energy", at(5), Decimal("1.5"))
    acc.observe("sensor.west_array_energy", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("1.0"))
    acc.finalize(at(30))

    # Then - the house used 1 imported and 2 generated less 1 exported. Reading
    # only one array would have put 0.5 or 1.5 here, not 2.0
    untracked = acc.totals().untracked
    assert untracked.energy_kwh == Decimal("2.0")
    assert untracked.energy_from_generation == Decimal("1.0")
    assert untracked.energy_from_grid == Decimal("1.0")
    assert untracked.actual_cost == Decimal("0.30")


def test_one_meter_resetting_counts_only_what_that_meter_made() -> None:
    # Given - two lifetime counters well above zero
    acc = _two_panel_home()
    _baseline(acc, east="10", west="5")

    # When - the east counter resets to zero between readings and has made 0.2
    # since, while the west one simply climbs
    acc.observe("sensor.east_array_energy", at(5), Decimal(11))
    acc.observe("sensor.west_array_energy", at(5), Decimal("5.5"))
    acc.observe("sensor.east_array_energy", at(10), Decimal("0.2"))
    acc.observe("sensor.west_array_energy", at(10), Decimal("6.0"))
    acc.finalize(at(40))

    # Then - 1 + 0.5 + 0.2 + 0.5, nothing imported and nothing exported. A single
    # summed counter would have fallen from 16.5 to 6.2 and booked the whole 6.2
    # as new energy, the west array's lifetime included
    untracked = acc.totals().untracked
    assert untracked.energy_kwh == Decimal("2.2")
    assert untracked.energy_from_generation == Decimal("2.2")


def test_generation_is_unreadable_while_any_of_its_meters_is_silent() -> None:
    # Given
    acc = _two_panel_home()
    _baseline(acc)

    # When - the west meter goes unavailable and the east one then reports
    acc.observe("sensor.west_array_energy", at(5), None)
    acc.observe("sensor.east_array_energy", at(5), Decimal("1.0"))
    acc.observe("sensor.grid_import", at(5), Decimal("0.2"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.3"))
    acc.finalize(at(30))

    # Then - generation is treated exactly as a single dead generation meter is
    # (HEA-67): left out, rather than half of it booked as though it were all.
    # One array reporting must not vouch for the other
    assert acc.totals().untracked.energy_kwh == Decimal("0.2")


def test_generation_is_readable_again_once_every_meter_reports() -> None:
    # Given - the west meter was silent for a while
    acc = _two_panel_home()
    _baseline(acc)
    acc.observe("sensor.west_array_energy", at(5), None)
    acc.observe("sensor.east_array_energy", at(5), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal(0))
    acc.observe("sensor.grid_export", at(5), Decimal(0))

    # When - it comes back, and the next interval generates on both
    acc.observe("sensor.west_array_energy", at(10), Decimal(0))
    acc.observe("sensor.east_array_energy", at(15), Decimal("1.0"))
    acc.observe("sensor.west_array_energy", at(15), Decimal("0.5"))
    acc.observe("sensor.grid_import", at(15), Decimal("0.2"))
    acc.observe("sensor.grid_export", at(15), Decimal("0.3"))
    acc.finalize(at(45))

    # Then - 0.2 imported plus 1.5 generated less 0.3 exported
    assert acc.totals().untracked.energy_kwh == Decimal("1.4")
