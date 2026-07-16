"""Splits each interval's real cost across the devices that drew it.

This is the accounting model's payoff. Within a 5-minute bucket the house is
served by a blend of sources — grid import at the live rate, solar at zero,
battery at its stored cost — and every kWh consumed, by a tracked device or by
the unexplained "Untracked" remainder, is priced at that same blend. Naive cost
values the same energy as if it had all come from the grid, so the gap between
them is what local generation saved.

The contract is a pluggable strategy so the recorded fallbacks — a deficit-capped
model, an export-aware variant that prices solar at the export rate — can replace
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
    """One device's share of a bucket: the four figures the sensors publish."""

    energy_kwh: Decimal
    actual_cost: Decimal
    naive_cost: Decimal
    solar_saving: Decimal


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
    zero rather than going negative; the real cost is still fully split across the
    devices, and the leftover energy mismatch is what Repairs surfaces.
    """

    @override
    def allocate(
        self, bucket: IntervalBucket, prices: Mapping[SourceKind, Decimal]
    ) -> BucketAllocation:
        import_price = _price(prices, SourceKind.IMPORT)
        consumption = _sum(bucket.sources.values())
        total_cost = _sum(
            energy * _price(prices, kind) for kind, energy in bucket.sources.items()
        )

        energies = _energies(bucket, consumption)
        actuals = _proportional(energies, total_cost)

        allocations = {
            label: DeviceAllocation(
                energy_kwh=energy,
                actual_cost=actuals[label],
                naive_cost=energy * import_price,
                solar_saving=energy * import_price - actuals[label],
            )
            for label, energy in energies.items()
        }
        untracked = allocations.pop(_UNTRACKED)
        return BucketAllocation(devices=allocations, untracked=untracked)


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
