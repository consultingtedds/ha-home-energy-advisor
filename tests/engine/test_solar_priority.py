"""Whose energy a battery charge is, when solar, grid and battery are all busy.

The meters cannot see where energy went inside one interval. Where the house
imports, the panels generate and the battery charges at once, the engine has to
choose which supplied the charge. By default the import does, which is right for
a battery that takes only what the house does not use. Some inverters are set the
other way - the panels fill the battery and the grid runs the house - and for them
a household says so (HEA-217).

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

START = datetime(2026, 10, 16, 9, 50, tzinfo=UTC)
PRICE = Decimal("0.3948")
IMPORTED = Decimal("0.0117")
GENERATED = Decimal("0.0204")
CHARGED = Decimal("0.0212")


def _one_busy_interval(*, battery_first: bool | None) -> Accountant:
    """One interval with import, generation and charging all at once."""
    # Left out entirely for the default, so it is the constructor's own default
    # under test rather than an explicit False.
    options: dict[str, Any] = (
        {} if battery_first is None else {"battery_first": battery_first}
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
    accountant.finalize(START + timedelta(minutes=30))
    return accountant


def test_by_default_the_import_charges_the_battery_and_solar_runs_the_house() -> None:
    # Given / When - a household that has said nothing about its inverter
    untracked = _one_busy_interval(battery_first=None).totals().untracked

    # Then - today's order, unchanged: all 0.0117 imported went into the battery,
    # so the house ran on 0.0109 of sunshine, at no cost
    assert untracked.energy_kwh == Decimal("0.0109")
    assert untracked.energy_from_generation == Decimal("0.0109")
    assert untracked.energy_from_grid == Decimal(0)
    assert untracked.actual_cost == Decimal(0)


def test_solar_first_fills_the_battery_and_the_grid_runs_the_house() -> None:
    # Given / When - the household says its solar charges the battery first
    untracked = _one_busy_interval(battery_first=True).totals().untracked

    # Then - the battery took 0.0204 of sunshine and 0.0008 of import, so the
    # house ran on the other 0.0109 imported, at the price of the time - no
    # morning saving where none was made
    assert untracked.energy_kwh == Decimal("0.0109")
    assert untracked.energy_from_grid == Decimal("0.0109")
    assert untracked.energy_from_generation == Decimal(0)
    assert untracked.actual_cost == Decimal("0.0109") * PRICE


def test_solar_first_stores_sunshine_in_the_battery() -> None:
    # Given / When
    battery_first = _one_busy_interval(battery_first=True)
    import_first = _one_busy_interval(battery_first=False)

    # Then - what the battery holds is priced by where it came from: 0.0008 of
    # import against 0.0117, so its later discharge carries that much less cost
    held = battery_first.snapshot()["battery"]
    held_by_default = import_first.snapshot()["battery"]
    assert Decimal(held["stored_cost"]) == Decimal("0.0008") * PRICE
    assert Decimal(held_by_default["stored_cost"]) == Decimal("0.0117") * PRICE
