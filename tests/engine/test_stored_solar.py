"""How much of a device's battery energy was sunshine stored earlier (ADR-0033).

The battery's discharge is one figure per device, and the meters cannot say what
charged it. The ledger can: every charge is booked as grid or generation, so a
discharge knows its share of each. Handing that share to the device that used
it is what lets a self-sufficiency headline count stored sunshine without
counting a battery filled from cheap overnight import.

Measured in kWh, never read from the forgone export value, which is zero for a
household paid nothing for export. Every home here has no export price for that
reason.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)

GRID = "sensor.grid_import"
EXPORT = "sensor.grid_export"
GENERATION = "sensor.generation"
CHARGE = "sensor.battery_charge"
DISCHARGE = "sensor.battery_discharge"
HOUSE = "sensor.house_consumption"
AIRCON = "sensor.aircon_energy"
PUMP = "sensor.pump_energy"

IMPORT_PRICE = Decimal("0.30")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


class _Home:
    """A home with panels, a battery and two devices, read meter by meter.

    No quiet span, and a meter reports only when it moves, then also its
    unchanged reading a minute before. So a rise lands in the interval it is
    given in rather than being spread back across a quiet run (HEA-74). A minute
    is short, so every rise here stays under the credible-step limit on power.
    """

    def __init__(self) -> None:
        self.acc = Accountant(
            house_sources={
                SourceRole.GRID_IMPORT: GRID,
                SourceRole.GRID_EXPORT: EXPORT,
                SourceRole.GENERATION: GENERATION,
                SourceRole.BATTERY_CHARGE: CHARGE,
                SourceRole.BATTERY_DISCHARGE: DISCHARGE,
                SourceRole.HOUSE_CONSUMPTION: HOUSE,
            },
            device_energy_entities={"aircon": AIRCON, "pump": PUMP},
            windows=AccountingWindows(max_quiet_span=timedelta(0)),
        )
        self.acc.record_price(at(0), IMPORT_PRICE)
        self.readings = dict.fromkeys(
            (GRID, EXPORT, GENERATION, CHARGE, DISCHARGE, HOUSE, AIRCON, PUMP),
            Decimal(0),
        )
        for entity in self.readings:
            self.acc.observe(entity, at(0), Decimal(0))

    def step(self, minute: int, *, silent: str = "", **rises: str) -> None:
        """Every named meter rises by its amount over the minute before ``minute``.

        A ``silent`` meter rises without reporting, as a coarse counter would.
        """
        moves = {_ENTITY_OF[name]: Decimal(kwh) for name, kwh in rises.items()}
        for entity, kwh in moves.items():
            if entity != _ENTITY_OF.get(silent):
                self.acc.observe(entity, at(minute - 1), self.readings[entity])
            self.readings[entity] += kwh
        for entity in moves:
            if entity != _ENTITY_OF.get(silent):
                self.acc.observe(entity, at(minute), self.readings[entity])

    def a_mixed_charge_and_an_evening(self) -> None:
        """0.5 kWh bought and 1.5 kWh of sunshine stored, then 1 kWh taken out.

        Three quarters of the battery is sunshine, so three quarters of what the
        evening takes out is: 0.75 kWh of the 1.
        """
        self.step(5, grid="0.5", charge="0.5")
        self.step(10, generation="1.5", charge="1.5")
        self.step(15, discharge="1.0", house="1.0", aircon="0.5", pump="0.3")
        self.acc.finalize(at(60))


_ENTITY_OF = {
    "grid": GRID,
    "generation": GENERATION,
    "charge": CHARGE,
    "discharge": DISCHARGE,
    "house": HOUSE,
    "aircon": AIRCON,
    "pump": PUMP,
}


def test_each_device_is_given_its_share_of_the_stored_sunshine() -> None:
    """ADR-0033's own test: known charges, a partial discharge, exact shares."""
    # Given - a battery holding 0.5 kWh bought and 1.5 kWh of sunshine
    home = _Home()

    # When - the evening takes 1 kWh out: the aircon 0.5 kWh, the pump 0.3 kWh,
    # and the rest of the house 0.2 kWh
    home.a_mixed_charge_and_an_evening()
    totals = home.acc.totals()

    # Then - each is given three quarters of its battery energy as sunshine
    aircon = totals.devices["aircon"]
    pump = totals.devices["pump"]
    assert aircon.energy_from_battery == Decimal("0.5")
    assert aircon.energy_from_battery_solar == Decimal("0.375")
    assert pump.energy_from_battery == Decimal("0.3")
    assert pump.energy_from_battery_solar == Decimal("0.225")
    assert totals.untracked.energy_from_battery_solar == Decimal("0.15")
    assert totals.whole_home.energy_from_battery_solar == Decimal("0.75")


def test_a_battery_filled_from_the_grid_gives_no_sunshine() -> None:
    """The case Home Assistant's own gauge gets wrong, counting it as self-made."""
    # Given - a battery filled from cheap import
    home = _Home()
    home.step(5, grid="1.0", charge="1.0")

    # When - the aircon runs off it
    home.step(10, discharge="1.0", house="1.0", aircon="1.0")
    home.acc.finalize(at(60))

    # Then - it came from the battery, and none of it was sunshine
    aircon = home.acc.totals().devices["aircon"]
    assert aircon.energy_from_battery == Decimal("1.0")
    assert aircon.energy_from_battery_solar == Decimal(0)


def test_sunshine_used_straight_off_the_panels_is_not_counted_twice() -> None:
    """Only the battery's share is new; direct generation stays where it was."""
    # Given - panels serving the aircon directly, with nothing stored
    home = _Home()

    # When
    home.step(5, generation="1.0", house="1.0", aircon="1.0")
    home.acc.finalize(at(60))

    # Then - it is generation, and the battery gave nothing, sunshine or not
    aircon = home.acc.totals().devices["aircon"]
    assert aircon.energy_from_generation == Decimal("1.0")
    assert aircon.energy_from_battery_solar == Decimal(0)


def test_the_stored_sunshine_sums_to_the_whole_home() -> None:
    """A sibling figure reconciles like every other: devices + Untracked = home."""
    # Given / When - the mixed charge and the evening
    home = _Home()
    home.a_mixed_charge_and_an_evening()
    totals = home.acc.totals()

    # Then - the parts account for the whole, exactly, and the battery's own
    # losses carry none: energy lost to heat reached no device
    parts = sum(
        (device.energy_from_battery_solar for device in totals.devices.values()),
        totals.untracked.energy_from_battery_solar,
    )
    assert parts == totals.whole_home.energy_from_battery_solar
    assert totals.battery.energy_from_battery_solar == Decimal(0)


def test_late_energy_is_given_the_sunshine_of_its_own_interval() -> None:
    """A device reporting late is attributed to its own bucket's sources.

    So it takes that bucket's share of sunshine too, not whatever the battery
    holds when the reading finally arrives.
    """
    # Given - the evening, with the pump drawing 0.3 kWh it has not yet reported
    home = _Home()
    home.step(5, grid="0.5", charge="0.5")
    home.step(10, generation="1.5", charge="1.5")
    home.step(15, discharge="1.0", house="1.0", aircon="0.5", pump="0.3", silent="pump")

    # And - the battery is then refilled from the grid, so its blend has moved,
    # and the evening is finalised
    home.step(20, grid="1.5", charge="1.5")
    home.acc.finalize(at(35))

    # When - the pump's reading for the evening arrives late
    home.acc.observe(PUMP, at(14), Decimal(0))
    home.acc.observe(PUMP, at(15), Decimal("0.3"))
    home.acc.finalize(at(120))

    # Then - three quarters of it was sunshine, as it was for the aircon beside
    # it, and Untracked gave up exactly what the pump took
    totals = home.acc.totals()
    assert totals.devices["pump"].energy_from_battery_solar == Decimal("0.225")
    assert totals.untracked.energy_from_battery_solar == Decimal("0.15")
    assert totals.whole_home.energy_from_battery_solar == Decimal("0.75")


def test_the_stored_sunshine_survives_a_restart() -> None:
    # Given - a home whose devices have been given stored sunshine
    home = _Home()
    home.a_mixed_charge_and_an_evening()
    before = home.acc.totals()

    # When - the engine is restarted from its snapshot
    restarted = _Home()
    restarted.acc.restore(home.acc.snapshot())

    # Then - every device's share is still there
    after = restarted.acc.totals()
    assert after.devices["aircon"].energy_from_battery_solar == Decimal("0.375")
    assert after.whole_home == before.whole_home


def test_a_snapshot_from_before_it_was_counted_restores_as_nothing() -> None:
    """Upgrading starts from nothing given, the way the forgone value did."""
    # Given - a snapshot whose running totals predate the figure
    home = _Home()
    home.a_mixed_charge_and_an_evening()
    snapshot = home.acc.snapshot()
    for running in (*snapshot["running"].values(), snapshot["house"]):
        del running["energy_from_battery_solar"]

    # When - it is restored
    restarted = _Home()
    restarted.acc.restore(snapshot)

    # Then - the energy is all still there, and none of it is called sunshine
    aircon = restarted.acc.totals().devices["aircon"]
    assert aircon.energy_from_battery == Decimal("0.5")
    assert aircon.energy_from_battery_solar == Decimal(0)
