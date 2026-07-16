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
    base = {SourceKind.IMPORT: PEAK, SourceKind.SOLAR: Decimal(0)}
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
        bucket({SourceKind.IMPORT: "1.0"}, {"guest_bedroom_aircon": "1.0"}),
        prices(),
    )

    # Then — actual equals naive; with no solar or battery there is no saving
    guest = result.devices["guest_bedroom_aircon"]
    assert guest.energy_kwh == Decimal("1.0")
    assert guest.actual_cost == Decimal("0.234")
    assert guest.naive_cost == Decimal("0.234")
    assert guest.solar_saving == Decimal("0.000")


def test_solar_share_makes_actual_cheaper_than_naive() -> None:
    # Given — half the consumption is free solar
    result = STRATEGY.allocate(
        bucket(
            {SourceKind.IMPORT: "0.5", SourceKind.SOLAR: "0.5"},
            {"guest_bedroom_aircon": "1.0"},
        ),
        prices(),
    )

    # Then — the device is priced at the blended rate and solar is the saving
    guest = result.devices["guest_bedroom_aircon"]
    assert guest.actual_cost == Decimal("0.117")
    assert guest.naive_cost == Decimal("0.234")
    assert guest.solar_saving == Decimal("0.117")


def test_battery_energy_is_priced_at_its_stored_cost_not_the_live_rate() -> None:
    # Given — consumption served entirely from the battery, charged overnight
    result = STRATEGY.allocate(
        bucket({SourceKind.BATTERY: "1.0"}, {"guest_bedroom_aircon": "1.0"}),
        prices({SourceKind.BATTERY: OVERNIGHT}),
    )

    # Then — it costs the overnight stored rate, and the saving is the gap to peak
    guest = result.devices["guest_bedroom_aircon"]
    assert guest.actual_cost == Decimal("0.093")
    assert guest.naive_cost == Decimal("0.234")
    assert guest.solar_saving == Decimal("0.141")


def test_untracked_remainder_absorbs_consumption_no_device_explains() -> None:
    # Given — 3 kWh consumed from a mix, only 1.5 kWh explained by two devices
    result = STRATEGY.allocate(
        bucket(
            {
                SourceKind.IMPORT: "1.0",
                SourceKind.SOLAR: "1.0",
                SourceKind.BATTERY: "1.0",
            },
            {"guest_bedroom_aircon": "1.0", "kitchen_aircon": "0.5"},
        ),
        prices({SourceKind.BATTERY: OVERNIGHT}),
    )

    # Then — the unexplained 1.5 kWh is the Untracked pseudo-device
    assert result.untracked.energy_kwh == Decimal("1.5")
    # blended = (0.234 + 0 + 0.093) / 3 = 0.109 per kWh
    assert result.devices["guest_bedroom_aircon"].actual_cost == Decimal("0.109")
    assert result.devices["kitchen_aircon"].actual_cost == Decimal("0.0545")
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
            {SourceKind.IMPORT: "1.0", SourceKind.SOLAR: "2.0"},
            {"guest_bedroom_aircon": "1.0"},
        ),
        prices(),
    )

    # Then — "cost without solar" values the whole 3 kWh at the import rate
    naive_total = result.untracked.naive_cost + sum(
        d.naive_cost for d in result.devices.values()
    )
    assert naive_total == Decimal("3.0") * PEAK


def test_over_draw_clamps_the_remainder_and_keeps_the_cost_invariant() -> None:
    # Given — a device that measured more draw than the house consumed (coarse
    # sensor timing / a source unavailable while the device kept drawing)
    result = STRATEGY.allocate(
        bucket({SourceKind.IMPORT: "1.0"}, {"guest_bedroom_aircon": "1.5"}),
        prices(),
    )

    # Then — the remainder never goes negative, and the real cost is still fully
    # allocated across the devices
    assert result.untracked.energy_kwh == Decimal(0)
    assert result.untracked.actual_cost == Decimal(0)
    assert total_actual(result) == Decimal("0.234")


def test_zero_consumption_bucket_allocates_nothing() -> None:
    # Given — an interval with no energy at all
    result = STRATEGY.allocate(
        bucket({}, {"guest_bedroom_aircon": "0"}),
        prices(),
    )

    # Then — every figure is zero, with no division by zero
    guest = result.devices["guest_bedroom_aircon"]
    assert guest.energy_kwh == Decimal(0)
    assert guest.actual_cost == Decimal(0)
    assert total_actual(result) == Decimal(0)


def test_solar_saving_is_negative_when_battery_cost_beats_the_current_rate() -> None:
    # Given — battery energy charged at a peak €0.30 discharged now when import is
    # cheap at €0.10: the stored-cost model honestly shows a loss, not a saving
    result = STRATEGY.allocate(
        bucket({SourceKind.BATTERY: "1.0"}, {"guest_bedroom_aircon": "1.0"}),
        prices(
            {SourceKind.IMPORT: Decimal("0.10"), SourceKind.BATTERY: Decimal("0.30")}
        ),
    )

    # Then — the saving is negative rather than floored, keeping naive - actual exact
    guest = result.devices["guest_bedroom_aircon"]
    assert guest.actual_cost == Decimal("0.30")
    assert guest.solar_saving == Decimal("-0.20")


def test_missing_price_for_a_present_source_is_rejected() -> None:
    # Given — a bucket with battery energy but no battery price supplied
    incomplete = {SourceKind.IMPORT: PEAK, SourceKind.SOLAR: Decimal(0)}

    # When / Then — pricing cannot silently guess a source's cost
    with pytest.raises(ValueError, match="battery"):
        STRATEGY.allocate(
            bucket({SourceKind.BATTERY: "1.0"}, {"guest_bedroom_aircon": "1.0"}),
            incomplete,
        )
