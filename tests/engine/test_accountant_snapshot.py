"""The accountant's runtime state survives a restart.

The property under test: replaying a run through a snapshot and restore produces
exactly what an uninterrupted run produces, whatever instant the break falls on.
The scenario exercises the state that a restart puts at risk - open buckets, the
battery's stored cost, the retained ring, and carried debt.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
    Totals,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
OFF_PEAK = Decimal("0.093")
PEAK = Decimal("0.234")

GRID = "sensor.grid_import"
GENERATION = "sensor.generation"
CHARGE = "sensor.battery_charge"
DISCHARGE = "sensor.battery_discharge"
COARSE_AIRCON = "sensor.coarse_step_energy"
STEADY_PUMP = "sensor.steady_pump_energy"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _accountant() -> Accountant:
    """A house with generation and a battery, and two differently-metered devices."""
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.GENERATION: GENERATION,
            SourceRole.BATTERY_CHARGE: CHARGE,
            SourceRole.BATTERY_DISCHARGE: DISCHARGE,
        },
        device_energy_entities={
            "coarse_step_aircon": COARSE_AIRCON,
            "steady_pump": STEADY_PUMP,
        },
    )


# A run that exercises the state a restart destroys: the battery is charged from
# the grid at the cheap rate and discharged at the dear one (the stored-cost
# ledger), a coarse counter steps once across several intervals (the retained
# ring and the held corrections it feeds), and the devices briefly out-draw the
# house meters (the debt ledger).
_PRICES = ((0, OFF_PEAK), (30, PEAK))
_READINGS = (
    (GRID, 0, "0"),
    (GENERATION, 0, "0"),
    (CHARGE, 0, "0"),
    (DISCHARGE, 0, "0"),
    (COARSE_AIRCON, 0, "0"),
    (STEADY_PUMP, 0, "0"),
    # Cheap overnight import, most of it into the battery.
    (GRID, 5, "4.0"),
    (CHARGE, 5, "3.0"),
    (STEADY_PUMP, 5, "0.4"),
    (GRID, 10, "5.2"),
    (CHARGE, 10, "3.6"),
    (STEADY_PUMP, 10, "0.8"),
    # Sun up: generation serves the house and tops the battery.
    (GENERATION, 15, "2.5"),
    (CHARGE, 15, "4.6"),
    (STEADY_PUMP, 15, "1.2"),
    (GENERATION, 20, "5.0"),
    (STEADY_PUMP, 20, "1.6"),
    # The coarse counter finally steps, covering every interval since 0.
    (COARSE_AIRCON, 20, "2.4"),
    # Battery discharges into the evening peak, priced from the ledger.
    (DISCHARGE, 35, "1.5"),
    (STEADY_PUMP, 35, "2.0"),
    (GRID, 35, "5.6"),
    (DISCHARGE, 40, "2.8"),
    (STEADY_PUMP, 40, "2.4"),
    (COARSE_AIRCON, 40, "3.6"),
)


_LAST_MINUTE = 90


def _run(restart_at: int | None) -> Totals:
    """Replay the scenario minute by minute, optionally restarting part-way.

    Both paths observe and finalise on exactly the same schedule, the way the
    coordinator's timer does. That matters: finalising once at the end and
    finalising progressively are legitimately different runs, so a harness that
    varied the schedule as well as the restart would be measuring the wrong
    thing and would call a correct snapshot broken.
    """
    acc = _accountant()
    for minute in range(_LAST_MINUTE + 1):
        if minute == restart_at:
            carried = acc.snapshot()
            acc = _accountant()
            acc.restore(carried)
        for when, price in _PRICES:
            if when == minute:
                acc.record_price(at(minute), price)
        for entity, when, value in _READINGS:
            if when == minute:
                acc.observe(entity, at(minute), Decimal(value))
        acc.finalize(at(minute))
    return acc.totals()


def test_snapshot_restore_reproduces_an_uninterrupted_run_exactly() -> None:
    # Given - a run whose readings span a battery charge/discharge cycle, a
    # coarse counter's late step, and an overdraw
    expected = _run(restart_at=None)

    # When - the same run is cut by a restart mid-interval, after the battery has
    # been charged from the grid but before it is discharged into the peak
    restarted = _run(restart_at=22)

    # Then - every figure matches at full Decimal precision. A restart is an
    # implementation detail of the host, not an accounting event.
    assert restarted.whole_home == expected.whole_home
    assert restarted.untracked == expected.untracked
    assert restarted.devices == expected.devices
    assert restarted.unreconciled_kwh == expected.unreconciled_kwh


def test_snapshot_restore_reproduces_an_uninterrupted_run_at_every_split() -> None:
    # Given - the totals an uninterrupted run produces
    expected = _run(restart_at=None)

    # When / Then - no instant to restart at changes them. Restarting only on a
    # bucket boundary would miss the case the defect actually lives in, a restart
    # part-way through an interval nobody has finalised yet.
    for split in range(1, _LAST_MINUTE):
        assert _run(restart_at=split) == expected, (
            f"restarting at minute {split} changed the accounting"
        )


# Every attribute the accountant holds, sorted into what a snapshot does with
# it. Spelled out rather than derived so that adding state fails this test until
# somebody decides whether it has to survive a restart - which is exactly the
# decision that was never made for the battery ledger (HEA-112).
_PERSISTED = frozenset(
    {
        "_battery",
        "_debts",
        "_draws",
        "_held",
        "_house",
        "_implausible",
        "_pending_bounds",
        "_prices",
        "_raw",
        "_retained",
        "_running",
        "_sources",
        "_watermark",
        "_window",
    }
)
# Rebuilt from the config entry on every setup, so persisting them would let a
# stale snapshot silently override a household's reconfiguration.
_CONFIG_DERIVED = frozenset(
    {
        "_configured",
        "_device_of",
        "_entity_of",
        "_import_entity",
        "_lateness",
        "_max_quiet_span",
        "_retention",
        "_role_of",
        "_strategy",
        "_units",
        "_windows",
    }
)
# Deliberately allowed to reset. ``_unhealthy_roles`` is re-derived from live
# state within one poll, and a restored value would accuse a healthy meter that
# recovered while the host was down. ``_cold_start_logged`` only suppresses a
# duplicate log line.
_TRANSIENT = frozenset({"_cold_start_logged", "_unhealthy_roles"})


def test_snapshot_survives_a_json_round_trip_unchanged() -> None:
    # Given - a run with money and energy at full Decimal precision, and a
    # snapshot of it
    acc = _accountant()
    for when, price in _PRICES:
        acc.record_price(at(when), price)
    for entity, when, value in _READINGS:
        acc.observe(entity, at(when), Decimal(value))
    acc.finalize(at(_LAST_MINUTE))
    carried = acc.snapshot()

    # When - it makes the trip the integration layer's Store puts it through
    through_json = json.loads(json.dumps(carried))

    # Then - it arrives identical. Serialising a Decimal as a float would survive
    # this call and lose fractions of a cent per restart for ever after, so the
    # assertion is on equality of the whole structure, not on it merely encoding.
    assert through_json == carried

    # ...and an accountant restored from the decoded copy accounts identically to
    # one restored from the original, which is what the round trip is *for*.
    from_json = _accountant()
    from_json.restore(through_json)
    direct = _accountant()
    direct.restore(carried)
    assert from_json.totals() == direct.totals()


def _battery_run(*, restart_at: int | None, carry_state: bool) -> Totals:
    """The scenario, optionally restarting with or without carrying state."""
    acc = _accountant()
    for minute in range(_LAST_MINUTE + 1):
        if minute == restart_at:
            carried = acc.snapshot()
            acc = _accountant()
            if carry_state:
                acc.restore(carried)
        for when, price in _PRICES:
            if when == minute:
                acc.record_price(at(minute), price)
        for entity, when, value in _READINGS:
            if when == minute:
                acc.observe(entity, at(minute), Decimal(value))
        acc.finalize(at(minute))
    return acc.totals()


def test_battery_discharge_after_a_restart_is_priced_from_the_carried_ledger() -> None:
    # Given - a run that charges the battery from the grid at the off-peak rate
    # and discharges it into the peak, and the cost that run really incurs
    uninterrupted = _run(restart_at=None).whole_home.actual_cost

    # When - the process restarts between the charge and the discharge, once
    # carrying the stored-cost ledger and once with it empty
    carried = _battery_run(restart_at=25, carry_state=True).whole_home.actual_cost
    empty = _battery_run(restart_at=25, carry_state=False).whole_home.actual_cost

    # Then - carrying the ledger prices the discharge exactly as an uninterrupted
    # run does
    assert carried == uninterrupted

    # ...and an empty ledger charges *less*, because grid-bought energy is spent
    # as though generated. Asserted, not assumed: two paths that agreed here
    # would pass just as well if the ledger were never consulted.
    assert empty < uninterrupted


def test_restoring_into_a_reconfigured_home_forgets_a_removed_device() -> None:
    # Given - a snapshot taken while two devices were tracked
    acc = _accountant()
    for when, price in _PRICES:
        acc.record_price(at(when), price)
    for entity, when, value in _READINGS:
        acc.observe(entity, at(when), Decimal(value))
    acc.finalize(at(_LAST_MINUTE))
    carried = acc.snapshot()
    assert "steady_pump" in acc.totals().devices

    # When - the household removes one of them and the snapshot is restored into
    # the accountant the new configuration builds
    reconfigured = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.GENERATION: GENERATION,
            SourceRole.BATTERY_CHARGE: CHARGE,
            SourceRole.BATTERY_DISCHARGE: DISCHARGE,
        },
        device_energy_entities={"coarse_step_aircon": COARSE_AIRCON},
    )
    reconfigured.restore(carried)
    totals = reconfigured.totals()

    # Then - the removed device is gone rather than resurrected by its own
    # snapshot, which would put back a device the household deleted
    assert set(totals.devices) == {"coarse_step_aircon"}

    # ...and its energy stays with the home, falling to Untracked, so the split
    # still reconciles exactly (ADR-0002)
    assert (
        totals.untracked.energy_kwh + _sum_devices(totals, "energy_kwh")
        == totals.whole_home.energy_kwh
    )
    assert (
        totals.untracked.actual_cost + _sum_devices(totals, "actual_cost")
        == totals.whole_home.actual_cost
    )


def _sum_devices(totals: Totals, field: str) -> Decimal:
    return sum(
        (getattr(device, field) for device in totals.devices.values()), Decimal(0)
    )


def test_the_aggregate_invariant_holds_across_a_restart() -> None:
    # Given / When - a run interrupted by a restart
    totals = _run(restart_at=22)

    # Then - Σ devices + Untracked is still exactly the whole home. This is the
    # invariant the product's honesty rests on, so it is asserted after a restore
    # in its own right and not left to the equivalence test to imply.
    for figure in ("energy_kwh", "actual_cost", "naive_cost", "cost_savings"):
        assert getattr(totals.untracked, figure) + _sum_devices(totals, figure) == (
            getattr(totals.whole_home, figure)
        ), f"{figure} does not reconcile after a restart"


def test_every_accountant_field_is_classified_for_the_snapshot() -> None:
    # Given - a configured accountant that has seen traffic, so no field is still
    # unset
    acc = _accountant()
    for when, price in _PRICES:
        acc.record_price(at(when), price)
    for entity, when, value in _READINGS:
        acc.observe(entity, at(when), Decimal(value))
    acc.finalize(at(_LAST_MINUTE))

    # When / Then - every attribute it holds has a deliberate snapshot decision.
    # A new field lands in none of the three sets and fails here rather than
    # being quietly dropped on the next restart.
    assert set(vars(acc)) == _PERSISTED | _CONFIG_DERIVED | _TRANSIENT


def test_battery_diagnostics_report_the_ledger_behind_the_discharge_price() -> None:
    # Given - a run that force-charges the battery from the grid overnight
    acc = _accountant()
    for when, price in _PRICES:
        acc.record_price(at(when), price)
    for entity, when, value in _READINGS:
        if when <= 20:
            acc.observe(entity, at(when), Decimal(value))
    acc.finalize(at(60))

    # When - the battery diagnostics are read
    held = acc.battery_diagnostics()

    # Then - the ledger's contents are exposed, so a household reading the
    # download can see why the next discharge was priced as it was rather than
    # having to infer it from the totals
    assert Decimal(held["stored_kwh"]) > 0
    assert Decimal(held["stored_cost"]) > 0
