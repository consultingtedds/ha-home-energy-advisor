"""A device counter that reports rarely while it runs (HEA-225).

Some plugs update their power continuously and their energy counter only every
hour or two, so one reading reveals a long run at once. The plausibility guard
weighs a device against the house over an hour (HEA-60). It used to add every
late portion of such a step to the newest interval of that hour, so a two-hour
step was weighed against one hour of house and a pump drawing far less than the
house was condemned as impossible.

The shape is generated from the reference household's report rather than
captured: a pump drawing a steady 1.27 kW under a house drawing about 1.7 kW,
whose counter reads once after an hour and a half and once after two hours.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.energy_source import DecisionReason

START = datetime(2026, 10, 16, 8, 0, tzinfo=UTC)
PRICE = Decimal("0.234")
# About 1.7 kW, every five minutes: more than the pump in every interval.
HOUSE_PER_BUCKET = Decimal("0.14")
HOUSE_BUCKETS = 54  # 08:00 to 12:30

# The pump's counter: a baseline, a reading 88 minutes later, and one after
# 119 minutes more that reveals 2.53 kWh, a steady 1.27 kW.
PUMP_READINGS = (
    (START, Decimal("100.00")),
    (START + timedelta(minutes=88), Decimal("100.48")),
    (START + timedelta(minutes=207), Decimal("103.01")),
)


def _home() -> Accountant:
    accountant = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_consumption",
        },
        device_energy_entities={"steady_pump": "sensor.steady_pump_energy"},
    )
    accountant.record_price(START, PRICE)
    return accountant


def _readings() -> list[tuple[datetime, str, Decimal]]:
    readings: list[tuple[datetime, str, Decimal]] = []
    house = Decimal(0)
    for bucket in range(HOUSE_BUCKETS + 1):
        at = START + timedelta(minutes=5 * bucket)
        readings.append((at, "sensor.house_consumption", house))
        readings.append((at, "sensor.grid_import", house))
        house += HOUSE_PER_BUCKET
    readings.extend(
        (at, "sensor.steady_pump_energy", value) for at, value in PUMP_READINGS
    )
    readings.sort(key=lambda row: row[0])
    return readings


def _feed(
    accountant: Accountant,
    readings: list[tuple[datetime, str, Decimal]],
) -> Accountant:
    for at, entity, value in readings:
        accountant.observe(entity, at, value)
        accountant.finalize(at)
    return accountant


def _replay() -> Accountant:
    """Run the house and the pump through the engine, finalising as time passes."""
    accountant = _feed(_home(), _readings())
    accountant.finalize(START + timedelta(hours=6))
    return accountant


def _restarted_before_the_step(*, drop_window_starts: bool = False) -> Accountant:
    """The same morning, with a restart ten minutes before the step arrives.

    ``drop_window_starts`` writes the snapshot as a version without HEA-225
    would have: the window's entries carry no interval.
    """
    restart = START + timedelta(minutes=197)
    readings = _readings()
    before = [row for row in readings if row[0] <= restart]
    after = [row for row in readings if row[0] > restart]
    snapshot = _feed(_home(), before).snapshot()
    if drop_window_starts:
        for entry in snapshot["window"]:
            del entry["start"]
    restored = _home()
    restored.restore(snapshot)
    _feed(restored, after)
    restored.finalize(START + timedelta(hours=6))
    return restored


def test_a_two_hour_step_from_a_device_under_the_house_is_not_condemned() -> None:
    # Given / When - the pump's two-hour step arrives at 11:27
    accountant = _replay()

    # Then - weighed against the hour it belongs to, it is well inside the house,
    # so nothing is condemned and nothing was refused along the way
    assert accountant.implausible_devices() == frozenset()
    decisions = accountant.source_diagnostics()[
        "sensor.steady_pump_energy"
    ].recent_decisions
    assert [d.reason for d in decisions if d.reason is DecisionReason.IMPLAUSIBLE] == []


def test_its_energy_is_booked_in_full() -> None:
    # Given / When
    accountant = _replay()

    # Then - 0.48 and 2.53, all of it the pump's, none of it left to Untracked.
    # Spreading divides at full Decimal precision, so the reassembled total
    # carries a residue far below a milliwatt-hour
    booked = accountant.totals().devices["steady_pump"].energy_kwh
    assert abs(booked - Decimal("3.01")) < Decimal("0.000001"), f"booked {booked}"


def test_a_restart_before_the_step_keeps_the_window_s_intervals() -> None:
    # Given / When - the window is snapshotted and restored ten minutes before
    # the step lands, which is what a restart does
    accountant = _restarted_before_the_step()

    # Then - the restored window still knows which interval each entry is, so
    # the late portions are weighed where they belong, as without the restart
    assert accountant.implausible_devices() == frozenset()
    booked = accountant.totals().devices["steady_pump"].energy_kwh
    assert abs(booked - Decimal("3.01")) < Decimal("0.000001"), f"booked {booked}"


def test_a_snapshot_from_before_intervals_were_kept_still_restores() -> None:
    # Given / When - an upgrade from a version whose window carried no interval
    accountant = _restarted_before_the_step(drop_window_starts=True)

    # Then - it loads and keeps counting. Until the window refreshes it weighs
    # late energy as that version did, on the newest entry, so the step that
    # lands in that hour is judged the old way: condemned, as before the fix
    decisions = accountant.source_diagnostics()[
        "sensor.steady_pump_energy"
    ].recent_decisions
    assert any(d.reason is DecisionReason.IMPLAUSIBLE for d in decisions)
    booked = accountant.totals().devices["steady_pump"].energy_kwh
    assert Decimal(0) < booked < Decimal("3.01")
