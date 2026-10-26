"""A device that is most of the house, under a house meter coarser than it (HEA-243).

The plausibility guard sets aside a device that claims more than the whole house
over an hour (HEA-60). On a heating day a heat pump can be nearly all of the
load, and it is often metered finely, every 30 seconds, while the house is read
off an inverter's register that counts in 0.1 kWh steps. The house's hour is
built from readings each rounded down to the last step, so it can read up to a
step low per meter, and the heat pump came out ahead: "1.51 kWh against 1.50 kWh
for the whole house" (GitHub discussion 47). Set aside, its energy went to
Untracked for as long as the step persisted.

A second, separate gap: a house meter's reading that arrived after its interval
had closed raised the house's figures but never the guard's own hour, while a
device's late reading reached both.

The shapes are generated rather than captured: a heat pump cycling between
1.8 kW and 0.2 kW under a house that adds a steady 30 W.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import TYPE_CHECKING

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.energy_source import DecisionReason

if TYPE_CHECKING:
    from collections.abc import Callable

START = datetime(2026, 10, 25, 6, 0, tzinfo=UTC)
PRICE = Decimal("0.20")
HOURS = 3
PUMP = "sensor.heat_pump_energy"
HOUSE = "sensor.house_consumption"
IMPORT = "sensor.grid_import"
TICK = 30  # seconds between the heat pump's reports


def _cycling_kw(second: int) -> Decimal:
    """1.8 kW for seven minutes and 0.2 kW for three, out of step with the house."""
    return Decimal("1.8") if (second + 130) % 600 < 420 else Decimal("0.2")


def _home() -> Accountant:
    accountant = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: IMPORT,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        device_energy_entities={"heat_pump": PUMP},
    )
    accountant.record_price(START, PRICE)
    return accountant


def _readings(
    *,
    house_every: int,
    house_step: Decimal,
    pump_kw: Callable[[int], Decimal] = _cycling_kw,
    base_kw: Decimal = Decimal("0.03"),
    claim_factor: Decimal = Decimal(1),
) -> tuple[list[tuple[datetime, str, Decimal]], Decimal]:
    """The morning's readings, and what the heat pump really used.

    ``claim_factor`` scales what the heat pump's counter says without changing
    what the house meters see: a source lying about the device.
    """
    readings: list[tuple[datetime, str, Decimal]] = []
    pump = Decimal(100)
    house = Decimal(500)
    used = Decimal(0)
    for second in range(0, HOURS * 3600 + 1, TICK):
        at = START + timedelta(seconds=second)
        if second:
            kwh = pump_kw(second) * TICK / Decimal(3600)
            used += kwh
            pump += kwh * claim_factor
            house += kwh + base_kw * TICK / Decimal(3600)
        readings.append((at, PUMP, pump.quantize(Decimal("0.001"))))
        if second % house_every == 0:
            shown = house.quantize(house_step, rounding=ROUND_FLOOR)
            readings.append((at, HOUSE, shown))
            readings.append((at, IMPORT, shown))
    return readings, used


def _feed(
    accountant: Accountant, readings: list[tuple[datetime, str, Decimal]]
) -> Accountant:
    for at, entity, value in readings:
        accountant.observe(entity, at, value)
        accountant.finalize(at)
    return accountant


def _set_aside(accountant: Accountant) -> bool:
    decisions = accountant.source_diagnostics()[PUMP].recent_decisions
    return any(d.reason is DecisionReason.IMPLAUSIBLE for d in decisions)


def _booked(accountant: Accountant) -> Decimal:
    accountant.finalize(START + timedelta(hours=HOURS + 2))
    return accountant.totals().devices["heat_pump"].energy_kwh


def test_a_heat_pump_under_a_house_meter_counting_in_tenths_is_not_set_aside() -> None:
    # Given - the house read every ten minutes off a register counting 0.1 kWh
    readings, used = _readings(house_every=600, house_step=Decimal("0.1"))

    # When
    accountant = _feed(_home(), readings)

    # Then - a step's rounding is not evidence against the heat pump, so none of
    # its readings is refused and all of its energy is its own, not Untracked's
    assert not _set_aside(accountant)
    booked = _booked(accountant)
    assert abs(booked - used) < Decimal("0.001"), f"booked {booked} of {used}"


def test_a_heat_pump_under_a_house_meter_quiet_for_21_minutes_is_kept() -> None:
    # Given - a house meter quieter than the 20 minutes an interval stays open,
    # so part of every reading lands after its interval has closed
    readings, used = _readings(house_every=1260, house_step=Decimal("0.01"))

    # When
    accountant = _feed(_home(), readings)

    # Then
    assert not _set_aside(accountant)
    booked = _booked(accountant)
    assert abs(booked - used) < Decimal("0.001"), f"booked {booked} of {used}"


def test_late_house_energy_reaches_the_hour_the_guard_weighs() -> None:
    # Given - a steady 1.2 kW heat pump under a steady 1.23 kW house, the house
    # read every 25 minutes, so each reading spreads exactly 0.1025 kWh over each
    # five minutes it covers, and most of it arrives after those have closed
    readings, _ = _readings(
        house_every=1500,
        house_step=Decimal("0.0001"),
        pump_kw=lambda _second: Decimal("1.2"),
    )
    # Ending on a house reading, so every interval in the last hour is covered
    end = START + timedelta(minutes=175)
    readings = [row for row in readings if row[0] <= end]

    # When
    accountant = _feed(_home(), readings)
    accountant.finalize(end + timedelta(hours=1))

    # Then - the guard's hour holds all of the house, exactly as the house's own
    # figures do: twelve intervals of 0.1025 against the heat pump's twelve of 0.1
    assert accountant.plausibility_evidence("heat_pump") == (
        Decimal("1.2"),
        Decimal("1.23"),
    )


def test_a_device_claiming_twice_what_it_used_is_still_set_aside() -> None:
    # Given - the same coarse house meter, under a heat pump whose counter
    # double-counts: the fault the guard exists for (HEA-60)
    readings, _ = _readings(
        house_every=600, house_step=Decimal("0.1"), claim_factor=Decimal(2)
    )

    # When
    accountant = _feed(_home(), readings)

    # Then - one step of the house meter does not cover a device claiming double
    assert _set_aside(accountant)


def _restarted_halfway(*, drop_steps: bool) -> tuple[Accountant, Decimal]:
    readings, used = _readings(house_every=600, house_step=Decimal("0.1"))
    restart = START + timedelta(minutes=95)
    snapshot = _feed(_home(), [r for r in readings if r[0] <= restart]).snapshot()
    if drop_steps:
        del snapshot["house_meter_steps"]
    restored = _home()
    restored.restore(snapshot)
    return _feed(restored, [r for r in readings if r[0] > restart]), used


def test_each_house_meter_s_step_survives_a_snapshot() -> None:
    # Given - 95 busy minutes on the coarse meter, which never moved by less than
    # two of its steps: the step learned is its smallest movement, never less
    readings, _ = _readings(house_every=600, house_step=Decimal("0.1"))
    morning = [r for r in readings if r[0] <= START + timedelta(minutes=95)]
    snapshot = _feed(_home(), morning).snapshot()
    assert snapshot["house_meter_steps"] == {HOUSE: "0.2", IMPORT: "0.2"}

    # When
    restored = _home()
    restored.restore(snapshot)

    # Then
    assert restored.snapshot()["house_meter_steps"] == {HOUSE: "0.2", IMPORT: "0.2"}


def test_a_restart_keeps_what_each_house_meter_s_step_is() -> None:
    # Given / When - a restart halfway through the morning
    accountant, used = _restarted_halfway(drop_steps=False)

    # Then - as without the restart
    assert not _set_aside(accountant)
    booked = _booked(accountant)
    assert abs(booked - used) < Decimal("0.001"), f"booked {booked} of {used}"


def test_a_snapshot_from_before_steps_were_kept_learns_them_again() -> None:
    # Given / When - an upgrade from a version that kept no steps
    accountant, used = _restarted_halfway(drop_steps=True)

    # Then - the house meters move again within minutes, long before an interval
    # closes, so nothing is set aside on the way
    assert not _set_aside(accountant)
    booked = _booked(accountant)
    assert abs(booked - used) < Decimal("0.001"), f"booked {booked} of {used}"
