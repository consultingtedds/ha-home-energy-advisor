"""Spreads energy deltas into aligned 5-minute buckets — the interval ledger.

Allocation needs a common time grid so that, within one interval, each device's
draw lines up with the house-level sources serving it. This ledger provides that
grid: every :00/:05/:10 … boundary in UTC opens a bucket, and each energy delta
is spread across the buckets its span touches, in proportion to the real time
spent in each.

Working in UTC and by real elapsed time is what makes daylight-saving
transitions ordinary: a delta crossing Europe/Madrid's spring-forward hour
spreads over the one real hour that elapsed, not the two the wall clock skipped.

All time arithmetic is done in integer microseconds, never
``timedelta.total_seconds()`` (a float), so no binary-float error contaminates
the Decimal energy values — the parts of a spread delta sum back to it exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .energy_source import EnergyDelta

BUCKET = timedelta(minutes=5)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)


class SourceKind(Enum):
    """A house-level energy source that serves consumption within a bucket.

    Solar and battery are optional per household; a balance built from imports
    alone simply never carries their kinds.
    """

    IMPORT = "import"
    SOLAR = "solar"
    BATTERY = "battery"


@dataclass(frozen=True)
class BucketPortion:
    """The share of one delta's energy attributed to one bucket."""

    start: datetime
    kwh: Decimal


@dataclass(frozen=True)
class IntervalBucket:
    """A 5-minute interval's energy: house sources and per-device draws."""

    start: datetime
    sources: Mapping[SourceKind, Decimal]
    device_draws: Mapping[str, Decimal]


def _bucket_start(moment: datetime) -> datetime:
    index = (moment.astimezone(UTC) - _EPOCH) // BUCKET
    return _EPOCH + index * BUCKET


def _micros(span: timedelta) -> int:
    return span // _MICROSECOND


def spread_energy(delta: EnergyDelta) -> list[BucketPortion]:
    """Splits a delta across the buckets it spans, in proportion to time.

    The returned portions always sum to exactly ``delta.kwh``: shares are taken
    at full Decimal precision and the rounding residue is folded into the
    largest-overlap bucket, so the aggregate invariant holds without imposing any
    presentation-level rounding here. Portions come out in chronological order.
    """
    total = _micros(delta.end - delta.start)
    portions: list[BucketPortion] = []
    widest_index = 0
    widest_overlap = -1

    start = _bucket_start(delta.start)
    while start < delta.end:
        end = start + BUCKET
        overlap = _micros(min(end, delta.end) - max(start, delta.start))
        portions.append(BucketPortion(start=start, kwh=delta.kwh * overlap / total))
        if overlap > widest_overlap:
            widest_overlap = overlap
            widest_index = len(portions) - 1
        start = end

    _absorb_residue(portions, delta.kwh, widest_index)
    return portions


def _absorb_residue(portions: list[BucketPortion], target: Decimal, index: int) -> None:
    residue = target - sum((p.kwh for p in portions), start=Decimal(0))
    if residue != 0:
        widest = portions[index]
        portions[index] = BucketPortion(start=widest.start, kwh=widest.kwh + residue)


@dataclass
class _Accumulator:
    sources: dict[SourceKind, Decimal] = field(default_factory=dict)
    device_draws: dict[str, Decimal] = field(default_factory=dict)


class IntervalLedger:
    """Accumulates house-source and device energy into aligned 5-minute buckets."""

    def __init__(self) -> None:
        self._buckets: dict[datetime, _Accumulator] = {}

    def add_source(self, kind: SourceKind, delta: EnergyDelta) -> None:
        """Spreads a house-level source delta across the buckets it spans."""
        for portion in spread_energy(delta):
            tally = self._at(portion.start).sources
            tally[kind] = tally.get(kind, Decimal(0)) + portion.kwh

    def add_device(self, device_id: str, delta: EnergyDelta) -> None:
        """Spreads a tracked device's delta across the buckets it spans."""
        for portion in spread_energy(delta):
            tally = self._at(portion.start).device_draws
            tally[device_id] = tally.get(device_id, Decimal(0)) + portion.kwh

    def buckets(self) -> list[IntervalBucket]:
        """Returns the accumulated buckets in chronological order."""
        return [
            IntervalBucket(
                start=start,
                sources=dict(self._buckets[start].sources),
                device_draws=dict(self._buckets[start].device_draws),
            )
            for start in sorted(self._buckets)
        ]

    def _at(self, start: datetime) -> _Accumulator:
        return self._buckets.setdefault(start, _Accumulator())
