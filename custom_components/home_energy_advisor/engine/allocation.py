"""Splits each interval's real cost across the devices that drew it.

This is the accounting model's payoff. Within a 5-minute bucket the house is
served by a blend of sources — grid import at the live rate, local generation at
zero, battery at its stored cost — and every kWh consumed, by a tracked device or
by the unexplained "Untracked" remainder, is priced at that same blend. The
grid-price figure values the same energy as if every kWh had been bought off the
meter as it was used, so the gap between them is what the household saved.

The contract is a pluggable strategy so the recorded fallbacks — a deficit-capped
model, an export-aware variant that prices generation at the export rate — can replace
the MVP proportional split without the sensor layer noticing.

Two invariants hold on every bucket (see docs/CRITICAL_INSTRUCTIONS.md):

- Σ device + remainder actual costs equal the bucket's real cost, exactly at
  Decimal precision — the rounding residue is folded into the largest allocation.
- No allocation is negative.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, override

from .interval_ledger import SourceKind

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .interval_ledger import IntervalBucket

# The remainder rides through the same proportional maths as the real devices,
# keyed by a sentinel no entity id can collide with.
_UNTRACKED = "\x00untracked"


@dataclass(frozen=True)
class DeviceAllocation:
    """One device's share of a bucket: the four figures the sensors publish.

    ``energy_by_source`` splits ``energy_kwh`` across the sources that served the
    bucket, for the self-sufficiency figures (HEA-51). It carries only the kinds
    the bucket was actually served by, so a bucket with no house-level readings
    leaves it empty rather than asserting a source nobody measured.
    """

    energy_kwh: Decimal
    actual_cost: Decimal
    naive_cost: Decimal
    cost_savings: Decimal
    energy_by_source: Mapping[SourceKind, Decimal]


@dataclass(frozen=True)
class BucketAllocation:
    """A bucket's cost split across tracked devices and the Untracked remainder."""

    devices: Mapping[str, DeviceAllocation]
    untracked: DeviceAllocation


class CostAllocationStrategy(ABC):
    """Prices a bucket's energy and splits it across devices plus the remainder."""

    @abstractmethod
    def allocate(
        self, bucket: IntervalBucket, prices: Mapping[SourceKind, Decimal]
    ) -> BucketAllocation:
        """Allocates one bucket's cost; ``prices`` gives each source's €/kWh."""


class ProportionalAllocationStrategy(CostAllocationStrategy):
    """Splits each bucket by share of draw — the MVP model.

    Because every source is allocated by the same draw share, a device's actual
    cost is simply its share of the blended bucket cost. When measured device
    draw exceeds the consumption the sources account for — coarse sensor timing,
    or a source unavailable while a device kept drawing — the remainder clamps to
    zero rather than going negative, and the excess is priced at the **import**
    rate: it is energy the house drew that its meters have not yet reported, and
    the grid is the only place it can have come from.

    Costing that excess is what the shipped model got wrong. Holding the bucket's
    cost fixed and dividing it across the inflated energy priced *every* label
    below what any kWh could have been bought for — 3-6x below the tariff on a
    coarse device, and near zero when generation dominated the blend. The energy
    mismatch itself is what Repairs surfaces (HEA-74, ADR-0014).

    A small overdraw is expected and is not a fault. A coarse counter's step is
    spread evenly across a span whose true accrual profile cannot be known, and an
    even estimate can exceed what the house really drew in one five-minute slice
    while reconciling exactly over the whole span. Measured on the reference
    instance it inflates published whole-home energy by ~1 %, in ~2 % of buckets.
    Cost Savings is unaffected: the excess is charged at the import rate and the
    counterfactual values it at the import rate, so it nets to zero saving
    (HEA-77, ADR-0014).
    """

    @override
    def allocate(
        self, bucket: IntervalBucket, prices: Mapping[SourceKind, Decimal]
    ) -> BucketAllocation:
        import_price = _price(prices, SourceKind.IMPORT)
        consumption = _sum(bucket.sources.values())
        metered_cost = _sum(
            energy * _price(prices, kind) for kind, energy in bucket.sources.items()
        )

        energies = _energies(bucket, consumption)
        overdraw = _sum(energies.values()) - consumption
        total_cost = metered_cost + overdraw * import_price
        actuals = _proportional(energies, total_cost)

        allocations = {
            label: DeviceAllocation(
                energy_kwh=energy,
                actual_cost=actuals[label],
                naive_cost=energy * import_price,
                cost_savings=energy * import_price - actuals[label],
                energy_by_source=split_by_source(energy, bucket.sources, consumption),
            )
            for label, energy in energies.items()
        }
        untracked = allocations.pop(_UNTRACKED)
        return BucketAllocation(devices=allocations, untracked=untracked)


def split_by_source(
    energy: Decimal, sources: Mapping[SourceKind, Decimal], consumption: Decimal
) -> dict[SourceKind, Decimal]:
    """Splits one label's energy across the sources, in the bucket's own mix.

    The counterpart of the blended price: every label consumes the same mixture of
    grid, solar and battery that served the bucket, just as every label pays the
    same blended rate for it. Shares are taken at full Decimal precision with the
    residue folded into the largest source, so they sum back to ``energy`` exactly
    — the invariant a self-sufficiency percentage depends on.

    That per-label exactness is deliberately the invariant that holds. When
    tracked draw exceeds the metered consumption the labels between them then
    account for more of a source than the meters recorded, exactly as their
    energies already exceed consumption; the alternative would leave a device's
    own sources summing to less than its energy, which no share can be read from.

    A bucket with no served energy yields an empty mapping: the honest answer is
    that nothing is known about what supplied it (HEA-51).
    """
    if consumption <= 0:
        return {}
    shares = {
        kind: energy * kwh / consumption for kind, kwh in sources.items() if kwh > 0
    }
    if not shares:
        return {}
    residue = energy - _sum(shares.values())
    if residue != 0:
        largest = max(shares, key=lambda kind: shares[kind])
        shares[largest] += residue
    return shares


def _energies(bucket: IntervalBucket, consumption: Decimal) -> dict[str, Decimal]:
    draws = dict(bucket.device_draws)
    total_draw = _sum(draws.values())
    remainder = max(consumption, total_draw) - total_draw
    return {**draws, _UNTRACKED: remainder}


def _proportional(
    energies: Mapping[str, Decimal], total_cost: Decimal
) -> dict[str, Decimal]:
    """Splits ``total_cost`` across the energies, residue to the largest share."""
    total_energy = _sum(energies.values())
    if total_energy == 0:
        return dict.fromkeys(energies, Decimal(0))

    shares = {
        label: energy * total_cost / total_energy for label, energy in energies.items()
    }
    residue = total_cost - _sum(shares.values())
    if residue != 0:
        largest = max(energies, key=lambda label: energies[label])
        shares[largest] += residue
    return shares


def _price(prices: Mapping[SourceKind, Decimal], kind: SourceKind) -> Decimal:
    price = prices.get(kind)
    if price is None:
        msg = f"no price supplied for source: {kind.value}"
        raise ValueError(msg)
    return price


def _sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))
