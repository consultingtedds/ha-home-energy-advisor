"""A change in a battery's capacity is a revaluation, never a loss (ADR-0035).

What a battery holds is its level times its usable capacity, and the loss is
measured from an anchor as what went in, less what came out, less what the
battery gained since (ADR-0028). A capacity that moves changes what the battery
holds without any energy moving, so read naively it books a loss when the
capacity falls and hides one when it rises.

The engine is told each battery's capacity with its level. When one differs from
the last it was told, the anchor is moved by `(new - old) x level`, for the pool
and for that battery's share, and the measurement carries on.

The scenario is the battery pool test's: 2 kWh more charged, 1.2 kWh gained, so
0.3 kWh lost. Each test below moves the capacity at the reading the gain is
measured at and expects that same 0.3.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.battery_shares import BatteryMeters

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
OVERNIGHT = Decimal("0.093")
A_DAY = timedelta(hours=24)

TWO_BATTERIES = {
    "anker": BatteryMeters(
        charge=("sensor.anker_charge",), discharge=("sensor.anker_discharge",)
    ),
    "growatt": BatteryMeters(
        charge=("sensor.growatt_charge",), discharge=("sensor.growatt_discharge",)
    ),
}
ONE_BATTERY = {"anker": TWO_BATTERIES["anker"]}

# A 10 kWh battery that reads 25% when measuring begins and 37% after the span.
TEN = Decimal("10.0")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _q(value: Decimal) -> Decimal:
    """To a billionth, past the engine's division residue in the 27th place."""
    return value.quantize(Decimal("1e-9"))


def _accountant(batteries: dict[str, BatteryMeters]) -> Accountant:
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: "sensor.generation",
            SourceRole.BATTERY_CHARGE: tuple(
                meter for battery in batteries.values() for meter in battery.charge
            ),
            SourceRole.BATTERY_DISCHARGE: tuple(
                meter for battery in batteries.values() for meter in battery.discharge
            ),
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
        batteries=batteries,
    )


def _home(batteries: dict[str, BatteryMeters]) -> Accountant:
    """A fully metered house, every meter at zero, with an overnight price."""
    acc = _accountant(batteries)
    acc.record_price(at(0), OVERNIGHT)
    meters = ["sensor.grid_import", "sensor.grid_export"]
    meters += ["sensor.generation", "sensor.house_load"]
    meters += [
        meter
        for battery in batteries.values()
        for meter in (*battery.charge, *battery.discharge)
    ]
    for meter in meters:
        acc.observe(meter, at(0), Decimal(0))
    acc.finalize(at(40))
    return acc


def _observe(acc: Accountant, when: datetime, readings: dict[str, str]) -> None:
    for meter, value in readings.items():
        acc.observe(meter, when, Decimal(value))


def _reconcile(
    acc: Accountant,
    when: datetime,
    levels: dict[str, str],
    capacities: dict[str, Decimal],
) -> None:
    held = {battery: Decimal(level) for battery, level in levels.items()}
    acc.reconcile_battery(
        sum(held.values(), Decimal(0)), when, levels=held, capacities=capacities
    )


def _one_battery_charged(acc: Accountant) -> None:
    """4 kWh in at the start, measuring begins at 25%, then 2 kWh more."""
    _observe(
        acc,
        at(45),
        {
            "sensor.grid_import": "4.0",
            "sensor.house_load": "1.0",
            "sensor.anker_charge": "4.0",
        },
    )
    acc.finalize(at(85))
    _reconcile(acc, at(85), {"anker": "2.5"}, {"anker": TEN})
    _observe(
        acc,
        at(90),
        {
            "sensor.grid_import": "6.0",
            "sensor.house_load": "1.5",
            "sensor.anker_charge": "6.0",
        },
    )
    acc.finalize(at(130))


def _settled(acc: Accountant, level: str, capacity: Decimal) -> None:
    """The span's level, then again a day on, when the loss is published."""
    _reconcile(acc, at(130), {"anker": level}, {"anker": capacity})
    _reconcile(acc, at(130) + A_DAY, {"anker": level}, {"anker": capacity})


def test_a_capacity_that_falls_is_not_a_loss() -> None:
    # Given - 37% of a capacity that has just fallen from 10 to 9 kWh reads
    # 3.33, where at 10 kWh it would have read 3.7
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)

    # When
    _settled(acc, "3.33", Decimal("9.0"))

    # Then - the 0.37 kWh the capacity took away is not booked as lost
    assert _q(acc.totals().battery.energy_kwh) == Decimal("0.300000000")


def test_a_capacity_that_rises_does_not_hide_a_loss() -> None:
    # Given - 37% of 11 kWh reads 4.07
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)

    # When
    _settled(acc, "4.07", Decimal("11.0"))

    # Then - the loss is still there, rather than covered by the 0.37 kWh gained
    assert _q(acc.totals().battery.energy_kwh) == Decimal("0.300000000")


def test_a_capacity_that_does_not_change_revalues_nothing() -> None:
    # Given / When - the same capacity throughout
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)
    _settled(acc, "3.7", TEN)

    # Then - the figure the pool test publishes, and no revaluation recorded
    assert _q(acc.totals().battery.energy_kwh) == Decimal("0.300000000")
    assert acc.battery_diagnostics()["capacity"]["last_revaluation"] is None


def test_a_capacity_that_changed_across_a_restart_is_revalued() -> None:
    # Given - measuring began at 10 kWh, and the capacity is 9 when Home
    # Assistant comes back
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)
    restarted = _accountant(ONE_BATTERY)
    restarted.restore(acc.snapshot())

    # When
    _settled(restarted, "3.33", Decimal("9.0"))

    # Then - the capacity it was last told survived, so the change is revalued
    assert _q(restarted.totals().battery.energy_kwh) == Decimal("0.300000000")


def test_the_last_capacity_used_survives_a_restart() -> None:
    # Given - told 10 kWh before a restart
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)
    restarted = _accountant(ONE_BATTERY)

    # When
    restarted.restore(acc.snapshot())

    # Then - the reader can fall back on it while a capacity sensor is silent
    assert restarted.battery_capacity("anker") == TEN
    assert _accountant(ONE_BATTERY).battery_capacity("anker") is None


def test_a_snapshot_from_before_capacities_were_kept_revalues_nothing() -> None:
    # Given - a snapshot that never knew a capacity, so no change can be known
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)
    snapshot: dict[str, Any] = acc.snapshot()
    del snapshot["battery_loss"]["capacities"]
    restarted = _accountant(ONE_BATTERY)
    restarted.restore(snapshot)

    # When - the first capacity it is told is 9 kWh
    _settled(restarted, "3.33", Decimal("9.0"))

    # Then - it is recorded, not revalued: the reading is taken as it stands,
    # 2 kWh in and 0.83 gained
    assert _q(restarted.totals().battery.energy_kwh) == Decimal("0.670000000")
    assert restarted.battery_capacity("anker") == Decimal("9.0")


def test_one_batterys_capacity_moves_only_its_own_share() -> None:
    # Given - two batteries, the second at 10% of 5 kWh, whose capacity falls to
    # 4 kWh, so 10% reads 0.4 rather than 0.5
    acc = _home(TWO_BATTERIES)
    _observe(
        acc,
        at(45),
        {
            "sensor.grid_import": "4.0",
            "sensor.house_load": "1.0",
            "sensor.anker_charge": "3.0",
            "sensor.growatt_charge": "1.0",
        },
    )
    acc.finalize(at(85))
    capacities = {"anker": TEN, "growatt": Decimal("5.0")}
    _reconcile(acc, at(85), {"anker": "2.0", "growatt": "0.5"}, capacities)
    _observe(
        acc,
        at(90),
        {
            "sensor.grid_import": "6.0",
            "sensor.house_load": "1.5",
            "sensor.anker_charge": "4.5",
            "sensor.growatt_charge": "1.5",
        },
    )
    acc.finalize(at(130))

    # When
    fallen = {"anker": TEN, "growatt": Decimal("4.0")}
    _reconcile(acc, at(130), {"anker": "3.2", "growatt": "0.4"}, fallen)
    _reconcile(acc, at(130) + A_DAY, {"anker": "3.2", "growatt": "0.4"}, fallen)

    # Then - the pool loses 0.3 and splits it 3:5 exactly as it would have at
    # an unchanged capacity
    totals = acc.totals()
    assert _q(totals.battery.energy_kwh) == Decimal("0.300000000")
    assert _q(totals.batteries["anker"].energy_kwh) == Decimal("0.112500000")
    assert _q(totals.batteries["growatt"].energy_kwh) == Decimal("0.187500000")


def test_the_download_shows_the_capacity_in_force_and_the_last_revaluation() -> None:
    # Given / When - the capacity falls from 10 to 9 kWh at 37%
    acc = _home(ONE_BATTERY)
    _one_battery_charged(acc)
    _settled(acc, "3.33", Decimal("9.0"))

    # Then - the capacity used, and what the change moved the anchor by
    capacity = acc.battery_diagnostics()["capacity"]
    assert capacity["kwh"] == {"anker": "9.0"}
    assert capacity["last_revaluation"] == {
        "at": at(130).isoformat(),
        "battery": "anker",
        "from_kwh": "10.0",
        "to_kwh": "9.0",
        "kwh": "-0.37",
    }
