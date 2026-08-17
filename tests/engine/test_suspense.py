"""A published cost never comes back down (HEA-85).

A bucket whose tracked draw exceeds metered consumption is charged for energy the
house meters have not reported yet. ADR-0014 prices that at the import rate,
because unmetered energy can only have come off the grid - and then the bucket
that repays the debt discovers the interval was served by the sun, and hands most
of it back.

Both steps are right and the totals reconcile. But the correction can only land
in the bucket that discovered it: the sensors are cumulative running totals and
Home Assistant derives each bucket's change from their value at the boundaries,
so a refund shows up as an hour that cost *less than nothing*. On the reference
instance two adjacent hours of near identical draw published +EUR0.105 and
-EUR0.118.

So the charge is not published until it is known. The overdraw's money waits -
released at the repaying interval's real blend, or at the import rate if the debt
expires unpaid. Same money, and it only ever arrives.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
TARIFF = Decimal("0.30")

GRID = "sensor.grid_import"
GENERATION = "sensor.generation"
HOUSE = "sensor.house_consumption"
COARSE_STEP_AIRCON = "sensor.coarse_step_energy"
DEVICE = "coarse_step_aircon"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_home(**sources: str) -> Accountant:
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            **{SourceRole(role): entity for role, entity in sources.items()},
        },
        device_energy_entities={DEVICE: COARSE_STEP_AIRCON},
    )
    acc.record_price(at(0), TARIFF)
    return acc


def published(acc: Accountant) -> dict[str, Decimal]:
    """Every money figure a household can see, right now."""
    totals = acc.totals()
    device = totals.devices[DEVICE]
    return {
        "house_cost": totals.whole_home.actual_cost,
        "house_naive": totals.whole_home.naive_cost,
        "device_cost": device.actual_cost,
        "device_naive": device.naive_cost,
        "device_savings": device.cost_savings,
        "untracked_cost": totals.untracked.actual_cost,
    }


def overdraw_then_repay(acc: Accountant) -> list[dict[str, Decimal]]:
    """The pair from `test_reconciliation`, finalised one bucket at a time.

    The house draws 0.1 kWh then 0.5 kWh. The device's counter reveals a 0.4 kWh
    step in the first bucket and holds still through the second - a counter that
    reports every half hour, against a meter that reports every few seconds.
    Nothing is faulty. Snapshots are taken after each bucket closes, because a
    single finalise at the end would hide the very thing under test.
    """
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))
    acc.observe(GRID, at(10), Decimal("0.6"))
    acc.observe(COARSE_STEP_AIRCON, at(10), Decimal("0.4"))

    # The watermark is now - lateness(15) - BUCKET(5), so at(20) closes the
    # overdrawing bucket and nothing else; a later first call would close both
    # and hide the intermediate state entirely.
    snapshots = []
    for minute in (20, 25, 40):
        acc.finalize(at(minute))
        snapshots.append(published(acc))
    return snapshots


def test_no_published_figure_ever_falls_while_a_debt_settles() -> None:
    # Given / When - the overdraw is charged in one bucket and found to have been
    # cheaper in the next, which is the whole mechanism
    acc = a_home()
    snapshots = overdraw_then_repay(acc)

    # Then - every figure a household reads only ever rises. A single fall here
    # is an hour that published a negative cost.
    for figure in snapshots[0]:
        series = [snapshot[figure] for snapshot in snapshots]
        assert series == sorted(series), f"{figure} fell: {series}"


def test_the_overdrawing_bucket_publishes_only_what_the_meters_back() -> None:
    # Given / When - the first bucket metered 0.1 kWh while the device claimed
    # 0.4, so 0.3 kWh has no meter reading behind it yet
    acc = a_home()
    first, *_ = overdraw_then_repay(acc)

    # Then - the household is charged for the 0.1 kWh its meter actually saw, and
    # nothing for the 0.3 kWh still unaccounted. Charging that at import would
    # publish 0.12 and then take 0.09 of it back.
    assert first["house_cost"] == Decimal("0.03")
    assert first["device_cost"] == Decimal("0.03")


def test_the_charge_arrives_in_full_once_the_meter_catches_up() -> None:
    # Given / When
    acc = a_home()
    *_, last = overdraw_then_repay(acc)

    # Then - the same totals reconciliation has always guaranteed: 0.6 kWh at the
    # 0.30 tariff, and the device paying the tariff for its own 0.4 kWh
    assert last["house_cost"] == Decimal("0.18")
    assert last["device_cost"] == Decimal("0.12")


def test_cost_savings_does_not_spike_while_a_charge_waits() -> None:
    # Given - a home with no generation, so there is no saving to be had at all
    acc = a_home()

    # When
    snapshots = overdraw_then_repay(acc)

    # Then - suspending the charge must withhold the counterfactual with it.
    # Holding back actual cost alone would inflate the saving and then correct it
    # downwards, which is the same artefact moved onto a different sensor
    # (ADR-0014's invariance, measured in HEA-77).
    assert [snapshot["device_savings"] for snapshot in snapshots] == [Decimal(0)] * 3


def test_a_debt_nobody_repays_is_charged_at_the_import_rate() -> None:
    # Given - an overdraw whose surplus never arrives. Nothing better than the
    # import rate is ever learned about it, so that is what it costs (ADR-0014).
    acc = a_home()
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))
    acc.finalize(at(20))
    held = published(acc)

    # When - the quiet span passes with the house drawing nothing, so no surplus
    # ever arrives to settle the debt against. The meter keeps reporting: expiry
    # is checked as buckets close, and a house with no readings closes none.
    for minute in range(10, 205, 5):
        acc.observe(GRID, at(minute), Decimal("0.1"))
    acc.finalize(at(200))
    settled = published(acc)

    # Then - the 0.3 kWh unaccounted energy is charged at 0.30, and the
    # counterfactual with it, so the saving stays zero
    assert held["device_cost"] == Decimal("0.03")
    assert settled["device_cost"] == Decimal("0.12")
    assert settled["device_savings"] == Decimal(0)


def test_a_late_arrival_suspends_its_overdraw_too() -> None:
    # Given - a counter reporting every 40 minutes, so most of its step lands in
    # buckets already finalised. That path carries the bulk of a coarse counter's
    # energy, and leaving it charging at import would keep the symptom.
    acc = a_home()
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    for minute in range(5, 45, 5):
        acc.observe(GRID, at(minute), Decimal("0.05") * (minute // 5))
    acc.finalize(at(40))
    before = published(acc)

    # When - the device reveals far more than those buckets had headroom for
    acc.observe(COARSE_STEP_AIRCON, at(40), Decimal("1.2"))
    acc.finalize(at(60))
    after = published(acc)

    # Then - the late energy is published, but the part with no meter reading
    # behind it is not charged yet, so nothing has to be taken back later
    assert after["device_cost"] >= before["device_cost"]
    assert after["device_cost"] < Decimal("1.2") * TARIFF

    # The 0.95 kWh no meter backs is the device's outright and lands at once. The
    # rest was metered, so it belongs to the remainder until a bucket earns enough
    # to hand it over - taking it here would print a remainder that went backwards
    assert acc.totals().devices[DEVICE].energy_kwh == Decimal("0.95")

    # When - time runs on. A bucket's surplus repays the suspended overdraw before
    # it publishes any remainder, so with a debt this size there is nothing spare
    # to hand the held part over with, however long the house consumes for
    acc.finalize(at(400))

    # Then - the wait expires and the device ends up with every kWh its counter
    # revealed. A device short for good is the one outcome worse than a figure
    # that dips once
    assert acc.totals().devices[DEVICE].energy_kwh == Decimal("1.2")


def test_the_household_total_is_still_the_sum_of_its_parts() -> None:
    # Given / When - suspending money must not break the invariant every card
    # and every ADR leans on
    acc = a_home(generation=GENERATION, house_consumption=HOUSE)
    for entity in (GRID, GENERATION, HOUSE, COARSE_STEP_AIRCON):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(GENERATION, at(5), Decimal("0.2"))
    acc.observe(HOUSE, at(5), Decimal("0.3"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.5"))
    acc.observe(GRID, at(10), Decimal("0.4"))
    acc.observe(GENERATION, at(10), Decimal("0.6"))
    acc.observe(HOUSE, at(10), Decimal("1.0"))
    acc.observe(COARSE_STEP_AIRCON, at(10), Decimal("0.5"))
    acc.finalize(at(40))

    # Then
    totals = acc.totals()
    parts = sum(
        (device.actual_cost for device in totals.devices.values()),
        totals.untracked.actual_cost,
    )
    assert parts == totals.whole_home.actual_cost
    assert totals.untracked.actual_cost >= 0
