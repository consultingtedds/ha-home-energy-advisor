"""HEA-60 end-to-end: a counter with a real upstream bug, replayed.

The guard's rules are pinned synthetically in ``test_accountant.py``. This module
pins the *outcome* against the failure mode that motivated the ticket - a cloud
metering plug whose integration accumulates

    total_energy += consumption

on every poll, instead of assigning it. Each poll therefore re-adds the plug's
entire lifetime counter, and the reported total runs away from reality by roughly
two orders of magnitude while the plug itself reports no load at all.

The readings are **generated**, not captured. A real capture of this exists but
carries whole-house consumption at 5-minute resolution, which is an occupancy
trace and never goes in a public repo (HEA-63). Reproducing the arithmetic is
enough: the signature is what the guard has to survive, and the real capture is
kept locally to confirm the generated series matches it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.energy_source import DecisionReason

START = datetime(2026, 8, 2, tzinfo=UTC)
PRICE = Decimal("0.234")

# Two days at a realistic domestic scale, matching the observed incident: the
# house moves ~44 kWh/day, the plug's real usage is ~1.5 kWh/day, and the plug is
# cloud-polled every half hour.
BUCKETS = 2 * 24 * 12
HOUSE_PER_BUCKET = Decimal("0.153")
POLLS = 2 * 24 * 2
REAL_PER_POLL = Decimal("0.031")
OPENING_LIFETIME = Decimal("5.043")


def _honest_readings() -> list[tuple[datetime, Decimal]]:
    """What the plug's own lifetime counter reports - slow, monotonic, true."""
    return [
        (START + timedelta(minutes=30 * poll), OPENING_LIFETIME + REAL_PER_POLL * poll)
        for poll in range(POLLS + 1)
    ]


def _bugged_readings() -> list[tuple[datetime, Decimal]]:
    """The same plug through the broken integration: ``total += consumption``.

    Every poll adds the *absolute* lifetime value again, so the counter climbs by
    roughly its own magnitude each time rather than by the energy actually used.
    """
    running = Decimal("338.058")
    out: list[tuple[datetime, Decimal]] = []
    for at, lifetime in _honest_readings():
        running += lifetime
        out.append((at, running))
    return out


def _replay(plug: list[tuple[datetime, Decimal]]) -> Accountant:
    """Run the house and one plug through the engine, finalising as time passes."""
    accountant = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_consumption",
        },
        device_energy_entities={"utility_plug": "sensor.utility_plug_energy"},
    )
    accountant.record_price(START, PRICE)

    readings: list[tuple[datetime, str, Decimal]] = []
    house = Decimal(0)
    for bucket in range(BUCKETS + 1):
        at = START + timedelta(minutes=5 * bucket)
        readings.append((at, "sensor.house_consumption", house))
        readings.append((at, "sensor.grid_import", house))
        house += HOUSE_PER_BUCKET
    readings.extend((at, "sensor.utility_plug_energy", value) for at, value in plug)
    readings.sort(key=lambda row: row[0])

    for at, entity, value in readings:
        accountant.observe(entity, at, value)
        accountant.finalize(at)
    accountant.finalize(START + timedelta(days=3))
    return accountant


def test_the_runaway_counter_is_caught_and_its_energy_refused() -> None:
    # Given / When - the bugged counter is replayed against a normal household
    accountant = _replay(_bugged_readings())
    claimed = _bugged_readings()[-1][1] - _bugged_readings()[0][1]

    # Then - it is condemned: no load inside a house can exceed the house itself
    assert "utility_plug" in accountant.implausible_devices()

    # And - nearly all of the claim is refused. Some still lands: detection needs a
    # full window of evidence, so up to an hour of the lie is booked before the
    # guard trips. That is the accepted trade-off and the Repair says so
    booked = accountant.totals().devices["utility_plug"].energy_kwh
    assert booked < claimed / 20, f"booked {booked} of a claimed {claimed}"

    # And - the refusal is on the record rather than a silent gap
    decisions = accountant.source_diagnostics()[
        "sensor.utility_plug_energy"
    ].recent_decisions
    assert any(d.reason is DecisionReason.IMPLAUSIBLE for d in decisions)


def test_the_same_plugs_honest_counter_is_left_alone() -> None:
    # Given / When - the truthful lifetime counter, same plug, same house. This is
    # the sensor a user is told to switch to
    accountant = _replay(_honest_readings())

    # Then - nothing is condemned and the real usage is booked in full. A guard
    # that cannot separate these two would be worthless; they differ ~100-fold
    assert accountant.implausible_devices() == frozenset()
    booked = accountant.totals().devices["utility_plug"].energy_kwh
    expected = REAL_PER_POLL * POLLS
    # Spreading a delta across buckets divides at full Decimal precision, so the
    # reassembled total carries a residue far below a milliwatt-hour.
    assert abs(booked - expected) < Decimal("0.000001"), (
        f"expected {expected} kWh, booked {booked}"
    )


def test_the_guard_bounds_how_far_a_lie_can_move_the_household_total() -> None:
    # Given - the same window replayed against each source in turn
    lying = _replay(_bugged_readings()).totals().whole_home.energy_kwh
    honest = _replay(_honest_readings()).totals().whole_home.energy_kwh
    metered = HOUSE_PER_BUCKET * BUCKETS
    claimed = _bugged_readings()[-1][1] - _bugged_readings()[0][1]

    # Then - with an honest source the whole-home figure is exactly what the house
    # meter said
    assert honest == metered

    # And - with a lying one it is inflated, because whole-home is
    # `max(consumption, draw)` so that the split always reconciles (ADR-0006). The
    # guard does not prevent that; it *bounds* it, to the window it takes to
    # detect the lie. Contamination is a few kWh instead of the ~600 claimed
    inflation = lying - metered
    assert inflation > 0, "the pre-detection window is expected to leak"
    assert inflation < claimed / 50, f"inflated by {inflation} of a claimed {claimed}"
