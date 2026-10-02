"""What the battery saved, separated from what the sun saved (HEA-173).

Asked for by a household running Predbat: *"my main goal is to see how many
money I save using my home battery (or lose due incorrect behavior)"*. Cost
Savings already contains the answer and buries it, because it compares every kWh
against the import price whether a battery was involved or not - so a house with
panels and no battery shows a large saving.

The figure is a **decomposition rather than a new claim**, and that is what these
tests hold. Cost Savings is the sum over sources of `energy x (import price -
source price)`, which expands to exactly

    generation x import price  +  battery x (import price - stored cost)

so the battery's half and the sun's half add back to the figure already
published. A number that did not reconcile with Cost Savings would be a second
opinion about the same money, which is the one thing this project does not ship.

It can be negative, and the household who asked said so first: a battery charged
dear and discharged cheap costs money. Nothing special-cases that.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.allocation import (
    BucketAllocation,
    ProportionalAllocationStrategy,
)
from custom_components.home_energy_advisor.engine.interval_ledger import (
    IntervalBucket,
    SourceKind,
)

# Import price windows observed on the reference instance; overnight is the rate
# Predbat force-charges the battery at.
PEAK = Decimal("0.234")
OVERNIGHT = Decimal("0.093")

A_MOMENT = datetime(2026, 7, 11, 20, 15, tzinfo=UTC)
BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
STRATEGY = ProportionalAllocationStrategy()


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def bucket(sources: dict[SourceKind, str], draws: dict[str, str]) -> IntervalBucket:
    return IntervalBucket(
        start=A_MOMENT,
        sources={kind: Decimal(v) for kind, v in sources.items()},
        device_draws={name: Decimal(v) for name, v in draws.items()},
    )


def prices(battery: Decimal) -> dict[SourceKind, Decimal]:
    """Peak import, free generation, and whatever the battery's store cost."""
    return {
        SourceKind.IMPORT: PEAK,
        SourceKind.GENERATION: Decimal(0),
        SourceKind.BATTERY: battery,
    }


def battery_saved(allocation: BucketAllocation) -> Decimal:
    """The battery's saving across every device and the remainder."""
    return sum(
        (device.battery_savings for device in allocation.devices.values()),
        start=allocation.untracked.battery_savings,
    )


def saved(allocation: BucketAllocation) -> Decimal:
    """Cost Savings across the house - the whole the battery's saving is half of."""
    return sum(
        (device.cost_savings for device in allocation.devices.values()),
        start=allocation.untracked.cost_savings,
    )


def test_a_cheap_charge_discharged_at_peak_saves_the_difference() -> None:
    # Given - 2 kWh served from a battery filled overnight, used at peak
    served = bucket({SourceKind.BATTERY: "2.0"}, {"coarse_step_aircon": "2.0"})

    # When
    allocation = STRATEGY.allocate(served, prices(OVERNIGHT))

    # Then - the saving is what the household did not pay the grid for it
    assert battery_saved(allocation) == Decimal("2.0") * (PEAK - OVERNIGHT)


def test_a_battery_charged_dear_and_discharged_cheap_loses_money() -> None:
    # Given - the case the household who asked for this named first: the battery
    # filled at peak and discharged into a cheap window, which an automation
    # getting its forecast wrong really does
    served = bucket({SourceKind.BATTERY: "2.0"}, {"coarse_step_aircon": "2.0"})
    cheap_now = {**prices(PEAK), SourceKind.IMPORT: OVERNIGHT}

    # When
    allocation = STRATEGY.allocate(served, cheap_now)

    # Then - negative, and not clamped. A figure that could only rise would say
    # the battery never costs anything, which is the opposite of what he asked to
    # be able to see
    assert battery_saved(allocation) == Decimal("2.0") * (OVERNIGHT - PEAK)


def test_the_battery_and_generation_savings_sum_to_cost_savings() -> None:
    # Given - an evening bucket served by all three at once: some grid, some
    # sun still on the roof, and the battery covering the rest
    served = bucket(
        {
            SourceKind.IMPORT: "1.0",
            SourceKind.GENERATION: "0.5",
            SourceKind.BATTERY: "2.5",
        },
        {"coarse_step_aircon": "3.0", "steady_pump": "1.0"},
    )

    # When
    allocation = STRATEGY.allocate(served, prices(OVERNIGHT))

    # Then - the two halves are the whole. This is the obligation: the figure is
    # a decomposition of money already published, so it has to add up to it
    # exactly rather than approximately. The sun's half is not published - it is
    # this subtraction - and that is the point being pinned.
    generation_savings = Decimal("0.5") * PEAK
    assert battery_saved(allocation) + generation_savings == saved(allocation)


def test_a_bucket_with_no_battery_saves_nothing_through_one() -> None:
    # Given - a house with panels and no battery at all, which is the household
    # Cost Savings on its own misleads
    served = bucket(
        {SourceKind.IMPORT: "1.0", SourceKind.GENERATION: "2.0"},
        {"coarse_step_aircon": "3.0"},
    )

    # When
    allocation = STRATEGY.allocate(served, prices(Decimal(0)))

    # Then - zero from the battery, while Cost Savings is substantial: 2 of the
    # 3 kWh came free from the panels, so the house saved two peak units.
    # Telling those apart is the whole request
    assert battery_saved(allocation) == Decimal(0)
    assert saved(allocation) == 2 * PEAK


def test_energy_the_sun_put_in_the_battery_is_credited_to_the_battery() -> None:
    """Deliberate, and the one debatable line in this figure.

    Surplus generation stored at midday and drawn at peak cost nothing to store,
    so the whole peak price is counted as the battery's saving. The alternative
    reading - that it is the sun's saving, and the battery merely held it - was
    rejected: without the battery that energy would have been exported and the
    evening's kWh bought at peak instead. The battery is what made it available
    then, and "what did having a battery do for me" is the question asked.

    It inherits ADR-0002's documented optimism about forgone export revenue,
    which HEA-38 tracks and which is unchanged by anything here.
    """
    # Given - 2 kWh of stored sunshine, drawn at peak
    served = bucket({SourceKind.BATTERY: "2.0"}, {"coarse_step_aircon": "2.0"})

    # When - the ledger says that energy cost nothing to store
    allocation = STRATEGY.allocate(served, prices(Decimal(0)))

    # Then - the full peak price is the saving
    assert battery_saved(allocation) == Decimal("2.0") * PEAK


def test_an_overdrawn_bucket_withholds_the_battery_saving_in_step() -> None:
    # Given - device counters claiming more than the house meters accounted for,
    # which a coarse counter does in any single bucket (ADR-0015)
    served = bucket({SourceKind.BATTERY: "2.0"}, {"coarse_step_aircon": "3.0"})

    # When
    allocation = STRATEGY.allocate(served, prices(OVERNIGHT))

    # Then - the saving is withheld exactly as its two parents are, so the
    # identity survives the overdraw. A figure that ignored the clamp would drift
    # away from Cost Savings by the amount of every overdraw, for ever
    assert battery_saved(allocation) == Decimal("2.0") * (PEAK - OVERNIGHT)
    assert battery_saved(allocation) == saved(allocation)


def _home_that_stores_cheap_and_spends_at_peak() -> Accountant:
    """The reference home's overnight-charge, evening-discharge cycle."""
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        # Isolate the ledger from quiet-run spreading, as the sibling battery
        # tests do: these meters sit still and then jump by design.
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # Overnight: 2 kWh imported, all of it into the battery
    acc.observe("sensor.grid_import", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal(0))

    # Evening: the battery serves the whole 2 kWh, at peak prices
    acc.record_price(at(5), PEAK)
    acc.observe("sensor.grid_import", at(10), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(10), Decimal("2.0"))
    acc.observe("sensor.house_load", at(10), Decimal("2.0"))
    acc.observe("sensor.coarse_step_energy", at(10), Decimal("2.0"))
    return acc


def test_the_home_accumulates_what_its_battery_saved() -> None:
    # Given / When - a full cheap-charge, peak-discharge cycle
    acc = _home_that_stores_cheap_and_spends_at_peak()
    acc.finalize(at(40))

    # Then - the household's figure is the gap between what the stored energy
    # cost and what the same energy would have cost at the moment they used it
    home = acc.totals().whole_home
    assert home.battery_savings == Decimal("2.0") * (PEAK - OVERNIGHT)
    # ...and with no generation involved, that is the whole of Cost Savings
    assert home.battery_savings == home.cost_savings


def test_a_late_arrival_keeps_the_two_halves_together() -> None:
    """The correction path, which is how most of a coarse counter's energy lands.

    A device that reports every half hour has most of its energy reallocated into
    already-finalised buckets (ADR-0006). If those corrections moved Cost Savings
    and left this figure behind, the two halves would drift apart by the size of
    every late arrival - quietly, and for ever, on exactly the households that
    have coarse counters.

    Asserted as the invariant rather than as an arithmetic result: with no
    generation anywhere, every saving this house makes is its battery's, so the
    two figures must be equal whatever route the energy took to get here.
    """
    # Given - a grid-and-battery house that charged cheap and discharged at peak
    # while its coarse device said nothing, so the whole draw went to Untracked
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    # Every meter is read at each boundary, including the ones that have not
    # moved: a delta spanning two buckets is spread across both, and this test is
    # about which bucket a *late* one lands in.
    acc.observe("sensor.grid_import", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal(0))
    acc.record_price(at(5), PEAK)
    acc.observe("sensor.grid_import", at(10), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(10), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(10), Decimal("2.0"))
    acc.observe("sensor.house_load", at(10), Decimal("2.0"))
    acc.finalize(at(40))
    assert acc.totals().devices["coarse_step_aircon"].battery_savings == Decimal(0)

    # When - the counter finally reports, into that finalised bucket
    acc.observe("sensor.coarse_step_energy", at(10), Decimal("2.0"))
    acc.finalize(at(45))

    # Then - the device is credited with the saving, Untracked gives up exactly
    # that much, and the household's two halves are still one figure
    result = acc.totals()
    # 2 kWh bought overnight and spent at peak, so the household saved the
    # difference twice over. The *household* figure is exact; the device's share
    # of it is not, because a funded correction is handed over as later buckets
    # earn it rather than all at once (HEA-85), and the schedule for that is
    # another test's subject
    assert result.whole_home.battery_savings == 2 * (PEAK - OVERNIGHT)
    assert result.devices["coarse_step_aircon"].battery_savings > 0
    assert result.whole_home.battery_savings == result.whole_home.cost_savings
    assert (
        result.devices["coarse_step_aircon"].battery_savings
        + result.untracked.battery_savings
        == result.whole_home.battery_savings
    )


def test_a_settled_debt_publishes_its_battery_half_too() -> None:
    """The carry, which is the last path money reaches a device by (ADR-0015).

    A bucket whose devices claim more than its meters accounted for publishes no
    money for the excess; a later bucket's surplus repays it, at *that* bucket's
    blend. So the saving arrives after the energy did, through `_release` rather
    than through an allocation - and a figure that is not published there sheds
    the whole of every settlement while Cost Savings keeps it.

    Found by probing rather than by reading: the first build of this figure passed
    every other test in this file and lost EUR 0.0705 here, which is exactly one
    settlement's saving.
    """
    # Given - a battery filled cheaply, a bucket the device overdraws, and later
    # buckets with the surplus to repay it
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    readings = (
        # charge 4 kWh overnight, nothing consumed
        (5, "4.0", "4.0", "0", "0", "0"),
        # the battery serves 1 kWh; the device claims 2, so 1 is owed
        (10, "4.0", "4.0", "1.0", "1.0", "2.0"),
        # two quiet buckets whose surplus the ledger can repay out of
        (15, "4.0", "4.0", "3.0", "3.0", "2.0"),
        (20, "4.0", "4.0", "4.0", "4.0", "2.0"),
    )
    acc.record_price(at(5), PEAK)
    for minute, grid, charge, discharge, load, device in readings:
        for entity, value in (
            ("sensor.grid_import", grid),
            ("sensor.battery_charge", charge),
            ("sensor.battery_discharge", discharge),
            ("sensor.house_load", load),
            ("sensor.coarse_step_energy", device),
        ):
            acc.observe(entity, at(minute), Decimal(value))

    # When - the debt is repaid rather than forgiven
    acc.finalize(at(60))
    assert acc.totals().unreconciled_kwh == Decimal(0)

    # Then - the household's two halves are still one figure. With no generation
    # anywhere, every saving this house made was its battery's
    home = acc.totals().whole_home
    assert home.battery_savings == home.cost_savings


def test_the_battery_saving_survives_a_restart() -> None:
    # Given - a home with the figure accumulated, snapshotted
    acc = _home_that_stores_cheap_and_spends_at_peak()
    acc.finalize(at(40))
    before = acc.totals().whole_home.battery_savings
    assert before > 0
    snapshot = acc.snapshot()

    # When - the accountant is rebuilt from it, as a restart does
    resumed = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    resumed.restore(snapshot)

    # Then - it is carried, not restarted. A money figure that reset at every
    # restart would be read as the battery having saved nothing since lunchtime
    assert resumed.totals().whole_home.battery_savings == before


def test_a_snapshot_written_before_this_figure_existed_still_restores() -> None:
    """The upgrade path, and the reason it is not left to the generic fallback.

    A snapshot this engine cannot read is answered by starting cold, which is
    safe and deliberate (ADR-0021) - but it also discards the battery's
    stored-cost ledger, so the household's next discharge is priced at zero and
    their figures are wrong for a cycle. Every installed household would take
    that on upgrading, to gain a field whose absence means zero.
    """
    # Given - a snapshot as the released version wrote it, with no such figure
    acc = _home_that_stores_cheap_and_spends_at_peak()
    acc.finalize(at(40))
    snapshot = acc.snapshot()
    for running in (*snapshot["running"].values(), snapshot["house"]):
        del running["battery_savings"]
    for held in snapshot["held"]:
        held.pop("battery_savings", None)

    # When - this engine restores it
    resumed = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    resumed.restore(snapshot)

    # Then - it restores, reading the absent figure as nothing, and the battery
    # ledger comes through intact so the next discharge is still priced
    assert resumed.totals().whole_home.battery_savings == Decimal(0)
    assert resumed.battery_diagnostics()["stored_kwh"] == "0"
    assert resumed.totals().whole_home.actual_cost > 0
