from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from custom_components.home_energy_advisor.engine.allocation import (
    BucketAllocation,
    CostAllocationStrategy,
    ProportionalAllocationStrategy,
)
from custom_components.home_energy_advisor.engine.interval_ledger import (
    IntervalBucket,
    SourceKind,
)

# Import price windows observed on the reference instance; overnight is the
# rate Predbat force-charges the battery at.
PEAK = Decimal("0.234")
OVERNIGHT = Decimal("0.093")

# Allocation ignores the bucket's timestamp; any fixed instant serves.
A_MOMENT = datetime(2026, 7, 11, 20, 15, tzinfo=UTC)

STRATEGY = ProportionalAllocationStrategy()


def bucket(sources: dict[SourceKind, str], draws: dict[str, str]) -> IntervalBucket:
    return IntervalBucket(
        start=A_MOMENT,
        sources={kind: Decimal(v) for kind, v in sources.items()},
        device_draws={name: Decimal(v) for name, v in draws.items()},
    )


def prices(
    overrides: dict[SourceKind, Decimal] | None = None,
) -> dict[SourceKind, Decimal]:
    base = {SourceKind.IMPORT: PEAK, SourceKind.GENERATION: Decimal(0)}
    if overrides:
        base.update(overrides)
    return base


def total_actual(allocation: BucketAllocation) -> Decimal:
    return sum(
        (d.actual_cost for d in allocation.devices.values()),
        start=allocation.untracked.actual_cost,
    )


def test_proportional_strategy_is_a_cost_allocation_strategy() -> None:
    # Given / When / Then — the MVP strategy honours the pluggable contract so
    # deficit-capped and export-aware variants can replace it without touching
    # the sensor layer
    assert isinstance(STRATEGY, CostAllocationStrategy)


def test_all_import_bucket_prices_a_tracked_device_at_the_import_rate() -> None:
    # Given — 1 kWh drawn entirely from the grid by one device
    result = STRATEGY.allocate(
        bucket({SourceKind.IMPORT: "1.0"}, {"coarse_step_aircon": "1.0"}),
        prices(),
    )

    # Then — actual equals naive; with no solar or battery there is no saving
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("1.0")
    assert aircon.actual_cost == Decimal("0.234")
    assert aircon.naive_cost == Decimal("0.234")
    assert aircon.cost_savings == Decimal("0.000")


def test_solar_share_makes_actual_cheaper_than_naive() -> None:
    # Given — half the consumption is free solar
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "0.5", SourceKind.GENERATION: "0.5"},
            {"coarse_step_aircon": "1.0"},
        ),
        prices(),
    )

    # Then — the device is priced at the blended rate and solar is the saving
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.actual_cost == Decimal("0.117")
    assert aircon.naive_cost == Decimal("0.234")
    assert aircon.cost_savings == Decimal("0.117")


def test_battery_energy_is_priced_at_its_stored_cost_not_the_live_rate() -> None:
    # Given — consumption served entirely from the battery, charged overnight
    result = STRATEGY.allocate(
        bucket({SourceKind.BATTERY: "1.0"}, {"coarse_step_aircon": "1.0"}),
        prices({SourceKind.BATTERY: OVERNIGHT}),
    )

    # Then — it costs the overnight stored rate, and the saving is the gap to peak
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.actual_cost == Decimal("0.093")
    assert aircon.naive_cost == Decimal("0.234")
    assert aircon.cost_savings == Decimal("0.141")


def test_untracked_remainder_absorbs_consumption_no_device_explains() -> None:
    # Given — 3 kWh consumed from a mix, only 1.5 kWh explained by two devices
    result = STRATEGY.allocate(
        bucket(
            {
                SourceKind.IMPORT: "1.0",
                SourceKind.GENERATION: "1.0",
                SourceKind.BATTERY: "1.0",
            },
            {"coarse_step_aircon": "1.0", "fine_meter_aircon": "0.5"},
        ),
        prices({SourceKind.BATTERY: OVERNIGHT}),
    )

    # Then — the unexplained 1.5 kWh is the Untracked pseudo-device
    assert result.untracked.energy_kwh == Decimal("1.5")
    # blended = (0.234 + 0 + 0.093) / 3 = 0.109 per kWh
    assert result.devices["coarse_step_aircon"].actual_cost == Decimal("0.109")
    assert result.devices["fine_meter_aircon"].actual_cost == Decimal("0.0545")
    assert result.untracked.actual_cost == Decimal("0.1635")


def test_allocations_sum_exactly_to_the_bucket_cost() -> None:
    # Given — a blend whose per-kWh cost does not terminate: total €1.00 over
    # 3 kWh is €0.3333… each — the canary for rounding that breaks the invariant
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "1.0", SourceKind.BATTERY: "2.0"},
            {"a": "1.0", "b": "1.0", "c": "1.0"},
        ),
        prices(
            {SourceKind.IMPORT: Decimal("0.10"), SourceKind.BATTERY: Decimal("0.45")}
        ),
    )

    # Then — the parts still sum to exactly the real bucket cost
    assert total_actual(result) == Decimal("1.00")


def test_naive_cost_sums_to_consumption_at_the_import_rate() -> None:
    # Given — a mixed bucket with a remainder
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "1.0", SourceKind.GENERATION: "2.0"},
            {"coarse_step_aircon": "1.0"},
        ),
        prices(),
    )

    # Then — "cost without solar" values the whole 3 kWh at the import rate
    naive_total = result.untracked.naive_cost + sum(
        d.naive_cost for d in result.devices.values()
    )
    assert naive_total == Decimal("3.0") * PEAK


def test_over_draw_clamps_the_remainder_and_prices_the_excess_at_import() -> None:
    # Given — a device that measured more draw than the house consumed (coarse
    # sensor timing / a source unavailable while the device kept drawing)
    result = STRATEGY.allocate(
        bucket({SourceKind.IMPORT: "1.0"}, {"coarse_step_aircon": "1.5"}),
        prices(),
    )

    # Then — the remainder never goes negative, and the half kWh the meters had
    # not caught up with is charged at the marginal import rate rather than
    # diluting a fixed cost across inflated energy, which would price every kWh
    # in the bucket below what any of it could have been bought for (HEA-74)
    assert result.untracked.energy_kwh == Decimal(0)
    assert result.untracked.actual_cost == Decimal(0)
    assert total_actual(result) == Decimal("0.351")
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.actual_cost / aircon.energy_kwh == PEAK


def test_over_draw_against_free_generation_still_costs_the_excess() -> None:
    # Given — a bucket served entirely by generation, so its metered cost is zero,
    # with a coarse device claiming half a kWh more than the house was served
    result = STRATEGY.allocate(
        bucket({SourceKind.GENERATION: "1.0"}, {"coarse_step_aircon": "1.5"}),
        prices(),
    )

    # Then — the excess is bought energy, not free: diluting zero across 1.5 kWh
    # is what let a device drawing hard at peak be costed at nothing at all
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.actual_cost == Decimal("0.117")
    assert total_actual(result) == Decimal("0.117")


def test_draw_within_consumption_is_unaffected_by_the_overdraw_rule() -> None:
    # Given — devices drawing less than the house consumed, the ordinary case
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "1.0", SourceKind.GENERATION: "1.0"},
            {"coarse_step_aircon": "0.5", "pool_pump": "0.25"},
        ),
        prices(),
    )

    # Then — the bucket's real cost is split across the labels and nothing is
    # added: the marginal rule only ever engages when the meters disagree
    assert total_actual(result) == Decimal("0.234")
    assert result.untracked.energy_kwh == Decimal("1.25")


def test_zero_consumption_bucket_allocates_nothing() -> None:
    # Given — an interval with no energy at all
    result = STRATEGY.allocate(
        bucket({}, {"coarse_step_aircon": "0"}),
        prices(),
    )

    # Then — every figure is zero, with no division by zero
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal(0)
    assert aircon.actual_cost == Decimal(0)
    assert total_actual(result) == Decimal(0)


def test_cost_savings_is_negative_when_battery_cost_beats_the_current_rate() -> None:
    # Given — battery energy charged at a peak €0.30 discharged now when import is
    # cheap at €0.10: the stored-cost model honestly shows a loss, not a saving
    result = STRATEGY.allocate(
        bucket({SourceKind.BATTERY: "1.0"}, {"coarse_step_aircon": "1.0"}),
        prices(
            {SourceKind.IMPORT: Decimal("0.10"), SourceKind.BATTERY: Decimal("0.30")}
        ),
    )

    # Then — the saving is negative rather than floored, keeping naive - actual exact
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.actual_cost == Decimal("0.30")
    assert aircon.cost_savings == Decimal("-0.20")


def test_missing_price_for_a_present_source_is_rejected() -> None:
    # Given — a bucket with battery energy but no battery price supplied
    incomplete = {SourceKind.IMPORT: PEAK, SourceKind.GENERATION: Decimal(0)}

    # When / Then — pricing cannot silently guess a source's cost
    with pytest.raises(ValueError, match="battery"):
        STRATEGY.allocate(
            bucket({SourceKind.BATTERY: "1.0"}, {"coarse_step_aircon": "1.0"}),
            incomplete,
        )


def test_energy_is_split_across_the_sources_that_served_the_bucket() -> None:
    # Given — a bucket served 0.4 kWh from the grid and 0.3 kWh from solar, of
    # which one device drew 0.5 kWh
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "0.4", SourceKind.GENERATION: "0.3"},
            {"coarse_step_aircon": "0.5"},
        ),
        prices(),
    )

    # Then — the device's energy carries the bucket's source mix, exactly as its
    # cost carries the bucket's blended price (HEA-51)
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_by_source[SourceKind.IMPORT] == Decimal(
        "0.2857142857142857142857142857"
    )
    assert aircon.energy_by_source[SourceKind.GENERATION] == Decimal(
        "0.2142857142857142857142857143"
    )


def test_a_devices_source_energies_sum_to_its_energy_exactly() -> None:
    # Given — a three-source bucket whose proportions do not divide cleanly
    result = STRATEGY.allocate(
        bucket(
            {
                SourceKind.IMPORT: "0.4",
                SourceKind.GENERATION: "0.3",
                SourceKind.BATTERY: "0.3",
            },
            {"coarse_step_aircon": "0.5", "tumble_dryer": "0.2"},
        ),
        prices({SourceKind.BATTERY: OVERNIGHT}),
    )

    # Then — every label's source energies sum back to its energy at full Decimal
    # precision, so a self-sufficiency share always totals 100 % (the rounding
    # residue is folded into the largest source, as the cost split does)
    for allocation in (*result.devices.values(), result.untracked):
        assert (
            sum(allocation.energy_by_source.values(), start=Decimal(0))
            == allocation.energy_kwh
        )


def test_a_bucket_with_no_served_energy_attributes_no_source() -> None:
    # Given — a device drew while no house-level source reported anything, so the
    # engine genuinely does not know what served it
    result = STRATEGY.allocate(
        bucket({}, {"coarse_step_aircon": "0.5"}),
        prices(),
    )

    # Then — the energy is still counted, but no source is asserted. Booking it to
    # grid would label unknown energy as grid-supplied; the shortfall is visible
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.5")
    assert aircon.energy_by_source == {}


def test_overdrawn_bucket_keeps_each_device_summing_to_its_own_energy() -> None:
    # Given — tracked draw exceeding the energy the house-level meters accounted
    # for, which clamps the Untracked remainder to zero
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "0.4", SourceKind.GENERATION: "0.3"},
            {"coarse_step_aircon": "0.8", "tumble_dryer": "0.4"},
        ),
        prices(),
    )

    # Then — each device's split still sums to its own energy: the per-device
    # invariant is the one a self-sufficiency figure depends on, so it holds even
    # though the devices between them then exceed the metered source totals
    assert result.untracked.energy_kwh == Decimal(0)
    for name in ("coarse_step_aircon", "tumble_dryer"):
        allocation = result.devices[name]
        assert (
            sum(allocation.energy_by_source.values(), start=Decimal(0))
            == allocation.energy_kwh
        )
