"""HA-free accounting runtime: readings in, per-device running cost out.

Wraps the engine primitives — the cumulative delta calculator, the interval
spreading, the battery stored-cost ledger, and the proportional allocation
strategy — and does the energy-balance decomposition (ADR-0005) that turns raw
meter deltas into the house-served sources the allocation model needs.

The Home Assistant coordinator (HEA-21 stage B) feeds this class state changes
and a wall-clock ``now``; the class itself holds no Home Assistant references and
is fully unit-testable. It keeps per-device *since-startup* running totals: the
sensors add a restored baseline on top, so restarts neither double-count nor need
the runtime to persist anything.

Completed intervals are finalised on a lateness margin, but not sealed: each
finalised bucket's context (its served sources, prices and draws) is retained in
a bounded ring (24 h by default). Energy that arrives late for a retained bucket
re-runs that bucket's allocation with its own retained prices and applies only the
difference — the late device gains, the Untracked remainder gives back, and no
already-published device figure is revised. This matters because the founding
devices (WF-RAC aircons) report in coarse steps every 15-90 min, so most deltas
span past the watermark; dropping them silently reattributed 30-50 % of their
energy to Untracked (ADR-0006, HEA-48). Only portions older than the ring are
dropped, and never silently — a ``DROPPED_LATE`` decision is logged.

The Untracked remainder is *derived*, not accumulated: whole-home totals minus
the tracked-device totals holds identically because every label shares each
bucket's blended price, so the engine tracks the whole home plus each device and
subtracts. A monotonic whole-home total falls out for free.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from .allocation import ProportionalAllocationStrategy
from .battery_ledger import BatteryLedger
from .energy_source import CumulativeEnergySource, EnergyUnit, Reading
from .interval_ledger import BUCKET, IntervalBucket, SourceKind, spread_energy

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from .allocation import DeviceAllocation
    from .energy_source import EnergyDelta, SourceSnapshot

_DEFAULT_LATENESS = 3 * BUCKET
# How long a finalised bucket's context stays available for late-arriving device
# energy to correct. A few KB per bucket, so 24 h is well under 1 MB and covers
# even twice-a-day counters; push-only sources that step more rarely lose the
# residue beyond it (logged as DROPPED_LATE). See ADR-0006 / HEA-48.
_DEFAULT_RETENTION = timedelta(hours=24)


class SourceRole(Enum):
    """A configured house-level meter, before decomposition into served sources."""

    GRID_IMPORT = "grid_import"
    GRID_EXPORT = "grid_export"
    SOLAR = "solar"
    BATTERY_CHARGE = "battery_charge"
    BATTERY_DISCHARGE = "battery_discharge"
    HOUSE_CONSUMPTION = "house_consumption"


@dataclass(frozen=True)
class DeviceTotals:
    """Running since-startup figures for one device or the Untracked remainder."""

    energy_kwh: Decimal
    actual_cost: Decimal
    naive_cost: Decimal
    cost_savings: Decimal


@dataclass(frozen=True)
class Totals:
    """A snapshot of every tracked device, the Untracked remainder, and the home.

    ``untracked`` is derived (``whole_home`` minus the tracked devices), so the
    three always reconcile exactly: Σ devices + untracked ≡ whole_home.
    """

    devices: Mapping[str, DeviceTotals]
    untracked: DeviceTotals
    whole_home: DeviceTotals


@dataclass
class _RetainedBucket:
    """A finalised bucket's context, kept so late device energy can correct it.

    Only the scalars a correction needs: the fixed consumption and blended unit
    price the bucket settled at, the import price its naive cost uses, and the
    running total device draw (which late arrivals grow). The whole-home and real
    cost are fixed once finalised, so a correction only moves value from the
    Untracked remainder to the late device — never between devices.
    """

    consumption: Decimal
    blended: Decimal
    import_price: Decimal
    draw: Decimal


@dataclass(frozen=True)
class _Served:
    """House-served energy for one interval, after decomposition."""

    grid: Decimal
    solar: Decimal
    battery: Decimal
    grid_charge: Decimal
    solar_charge: Decimal


@dataclass
class _Running:
    energy_kwh: Decimal = Decimal(0)
    actual_cost: Decimal = Decimal(0)
    naive_cost: Decimal = Decimal(0)
    cost_savings: Decimal = Decimal(0)

    def add(self, allocation: DeviceAllocation) -> None:
        self.energy_kwh += allocation.energy_kwh
        self.actual_cost += allocation.actual_cost
        self.naive_cost += allocation.naive_cost
        self.cost_savings += allocation.solar_saving

    def snapshot(self) -> DeviceTotals:
        return DeviceTotals(
            energy_kwh=self.energy_kwh,
            actual_cost=self.actual_cost,
            naive_cost=self.naive_cost,
            cost_savings=self.cost_savings,
        )


class Accountant:
    """Turns a stream of meter readings into per-device running cost."""

    def __init__(
        self,
        *,
        house_sources: Mapping[SourceRole, str],
        device_energy_entities: Mapping[str, str],
        units: Mapping[str, EnergyUnit] | None = None,
        lateness: timedelta = _DEFAULT_LATENESS,
        retention: timedelta = _DEFAULT_RETENTION,
    ) -> None:
        self._units = dict(units or {})
        self._lateness = lateness
        self._retention = retention
        self._role_of = {entity: role for role, entity in house_sources.items()}
        self._device_of = {
            entity: device for device, entity in device_energy_entities.items()
        }
        self._configured = set(house_sources)
        self._import_entity = house_sources.get(SourceRole.GRID_IMPORT)
        self._cold_start_logged = False
        self._sources: dict[str, CumulativeEnergySource] = {}
        self._raw: dict[datetime, dict[SourceRole, Decimal]] = {}
        self._draws: dict[datetime, dict[str, Decimal]] = {}
        self._prices: list[tuple[datetime, Decimal]] = []
        self._battery = BatteryLedger()
        self._strategy = ProportionalAllocationStrategy()
        self._running = {device: _Running() for device in device_energy_entities}
        self._house = _Running()
        self._retained: dict[datetime, _RetainedBucket] = {}
        self._watermark: datetime | None = None
        self._overdrawn_run = 0

    def record_price(self, at: datetime, price: Decimal) -> None:
        """Records the import price active from ``at``."""
        self._prices.append((at, price))

    def observe(self, entity_id: str, at: datetime, value: Decimal | None) -> None:
        """Records a meter reading, spreading its delta into the interval buckets."""
        source = self._sources.get(entity_id)
        if source is None:
            source = CumulativeEnergySource(
                unit=self._units.get(entity_id, EnergyUnit.KWH)
            )
            self._sources[entity_id] = source
        delta = source.observe(Reading(at=at, value=value))
        if delta is None:
            return
        if (role := self._role_of.get(entity_id)) is not None:
            self._spread_source(role, delta)
        elif (device := self._device_of.get(entity_id)) is not None:
            self._spread_device(device, delta, source)

    def finalize(self, now: datetime) -> None:
        """Finalises every interval that ended before the lateness margin."""
        cutoff = now - self._lateness - BUCKET
        for start in sorted(set(self._raw) | set(self._draws)):
            if start > cutoff:
                break
            self._finalize_bucket(start)
            self._watermark = start
        self._evict_stale()
        self._prune_prices()

    def flush(self, now: datetime) -> None:
        """Finalises all in-flight intervals, sealing the partial current bucket.

        Called on unload (restart or any options/config change): finalising past
        the lateness margin banks up to ~20 min of otherwise-discarded accounting
        so the sensors capture it into their restore baseline. The trade-off — a
        bucket sealed here can no longer receive late portions after the reload, and
        the rebuilt runtime's retention ring starts empty — is accepted in ADR-0006.
        """
        self.finalize(now + self._lateness + BUCKET)

    def totals(self) -> Totals:
        """Returns the since-startup running totals per device, home and Untracked.

        Untracked is derived from the whole-home total minus the tracked devices,
        so the split reconciles exactly however late corrections have moved value.
        """
        devices = {device: run.snapshot() for device, run in self._running.items()}
        whole_home = self._house.snapshot()
        return Totals(
            devices=devices,
            untracked=self._derive_untracked(whole_home, devices.values()),
            whole_home=whole_home,
        )

    @staticmethod
    def _derive_untracked(
        whole_home: DeviceTotals, devices: Iterable[DeviceTotals]
    ) -> DeviceTotals:
        tracked = list(devices)
        energy = _sum(d.energy_kwh for d in tracked)
        actual = _sum(d.actual_cost for d in tracked)
        naive = _sum(d.naive_cost for d in tracked)
        savings = _sum(d.cost_savings for d in tracked)
        return DeviceTotals(
            energy_kwh=whole_home.energy_kwh - energy,
            actual_cost=whole_home.actual_cost - actual,
            naive_cost=whole_home.naive_cost - naive,
            cost_savings=whole_home.cost_savings - savings,
        )

    def consecutive_overdrawn_buckets(self) -> int:
        """Consecutive finalised buckets whose device draw exceeded consumption.

        A device drawing more than the house was served means the Untracked
        remainder would be negative — the engine clamps it to zero (ADR-0002),
        but a *persistent* run signals double-counting or bad inputs, which the
        coordinator surfaces as a Repair (HEA-24 / HEA-36).
        """
        return self._overdrawn_run

    def source_diagnostics(self) -> dict[str, SourceSnapshot]:
        """Per-source accumulator state and decision log, keyed by entity id.

        Feeds the diagnostics download (HEA-24): every meter the runtime has
        observed — house-level and per-device — with its last reading and the
        gating decisions that explain its accounting.
        """
        return {entity: source.snapshot() for entity, source in self._sources.items()}

    def _spread_source(self, role: SourceRole, delta: EnergyDelta) -> None:
        for portion in spread_energy(delta):
            if self._is_finalised(portion.start):
                continue
            bucket = self._raw.setdefault(portion.start, {})
            bucket[role] = bucket.get(role, Decimal(0)) + portion.kwh

    def _spread_device(
        self, device: str, delta: EnergyDelta, source: CumulativeEnergySource
    ) -> None:
        for portion in spread_energy(delta):
            if not self._is_finalised(portion.start):
                bucket = self._draws.setdefault(portion.start, {})
                bucket[device] = bucket.get(device, Decimal(0)) + portion.kwh
            elif (retained := self._retained.get(portion.start)) is not None:
                self._correct(device, retained, portion.kwh)
            else:
                source.note_dropped_late(portion.start, portion.kwh)

    def _is_finalised(self, start: datetime) -> bool:
        return self._watermark is not None and start <= self._watermark

    def _correct(self, device: str, retained: _RetainedBucket, kwh: Decimal) -> None:
        """Reattribute late device energy within a finalised, still-retained bucket.

        The bucket's real cost and consumption are fixed, so the device is credited
        its full energy at the blended price, capped at the headroom the Untracked
        remainder still holds; the whole-home total absorbs any overdraw. Untracked
        is derived, so it gives back exactly what the device gains — no other device
        moves (ADR-0006, HEA-48).
        """
        headroom = max(Decimal(0), retained.consumption - retained.draw)
        priced = min(kwh, headroom)
        run = self._running.setdefault(device, _Running())
        run.energy_kwh += kwh
        run.naive_cost += kwh * retained.import_price
        run.actual_cost += priced * retained.blended
        run.cost_savings += kwh * retained.import_price - priced * retained.blended

        grew = max(retained.consumption, retained.draw + kwh) - max(
            retained.consumption, retained.draw
        )
        self._house.energy_kwh += grew
        self._house.naive_cost += grew * retained.import_price
        self._house.cost_savings += grew * retained.import_price
        retained.draw += kwh

    def _finalize_bucket(self, start: datetime) -> None:
        if not self._prices:
            self._note_zero_priced(start)
        raw = self._raw.pop(start, {})
        draws = self._draws.pop(start, {})
        served = self._decompose(raw)
        prices, sources = self._price_sources(served, self._price_at(start))
        bucket = IntervalBucket(start=start, sources=sources, device_draws=draws)
        allocation = self._strategy.allocate(bucket, prices)
        for device, share in allocation.devices.items():
            self._running.setdefault(device, _Running()).add(share)
        for share in allocation.devices.values():
            self._house.add(share)
        self._house.add(allocation.untracked)
        self._retain(start, sources, prices, draws)
        self._track_overdraw(served, draws)

    def _retain(
        self,
        start: datetime,
        sources: Mapping[SourceKind, Decimal],
        prices: Mapping[SourceKind, Decimal],
        draws: Mapping[str, Decimal],
    ) -> None:
        consumption = _sum(sources.values())
        total_cost = _sum(energy * prices[kind] for kind, energy in sources.items())
        self._retained[start] = _RetainedBucket(
            consumption=consumption,
            blended=total_cost / consumption if consumption > 0 else Decimal(0),
            import_price=prices[SourceKind.IMPORT],
            draw=_sum(draws.values()),
        )

    def _evict_stale(self) -> None:
        if self._watermark is None:
            return
        horizon = self._watermark - self._retention
        for start in [start for start in self._retained if start < horizon]:
            del self._retained[start]

    def _prune_prices(self) -> None:
        """Drops price entries a future bucket can no longer need (HEA-53).

        Every interval left to finalise starts after the watermark, so the only
        price at or before the watermark that can still apply is the newest one;
        anything older is superseded. Without this the list grows unbounded and is
        rescanned from index zero per bucket — pathological for a spot tariff.
        """
        if self._watermark is None:
            return
        keep_from = 0
        for index, (when, _price) in enumerate(self._prices):
            if when > self._watermark:
                break
            keep_from = index
        if keep_from > 0:
            del self._prices[:keep_from]

    def _note_zero_priced(self, start: datetime) -> None:
        """Log, once, that finalising began before any import price was known.

        Attached to the price-bearing import source's decision log so diagnostics
        can explain the zero-cost early buckets. Logged a single time per
        cold-start: once a price is recorded the list never empties again (pruning
        keeps at least one), so this cannot re-fire.
        """
        if self._cold_start_logged or self._import_entity is None:
            return
        source = self._sources.get(self._import_entity)
        if source is not None:
            source.note_zero_priced(start)
            self._cold_start_logged = True

    def _track_overdraw(self, served: _Served, draws: Mapping[str, Decimal]) -> None:
        consumption = served.grid + served.solar + served.battery
        total_draw = sum(draws.values(), Decimal(0))
        if total_draw > consumption:
            self._overdrawn_run += 1
        else:
            self._overdrawn_run = 0

    def _decompose(self, raw: Mapping[SourceRole, Decimal]) -> _Served:
        imp = raw.get(SourceRole.GRID_IMPORT, Decimal(0))
        exp = raw.get(SourceRole.GRID_EXPORT, Decimal(0))
        gen = raw.get(SourceRole.SOLAR, Decimal(0))
        charge = raw.get(SourceRole.BATTERY_CHARGE, Decimal(0))
        discharge = raw.get(SourceRole.BATTERY_DISCHARGE, Decimal(0))

        grid_charge = min(charge, imp)
        solar_charge = charge - grid_charge
        grid = imp - grid_charge

        if SourceRole.HOUSE_CONSUMPTION in self._configured:
            house = raw.get(SourceRole.HOUSE_CONSUMPTION, Decimal(0))
            solar = max(Decimal(0), house - grid - discharge)
        elif {SourceRole.SOLAR, SourceRole.GRID_EXPORT} <= self._configured:
            solar = max(Decimal(0), gen - solar_charge - exp)
        else:
            solar = Decimal(0)

        return _Served(
            grid=grid,
            solar=solar,
            battery=discharge,
            grid_charge=grid_charge,
            solar_charge=solar_charge,
        )

    def _price_sources(
        self, served: _Served, price: Decimal
    ) -> tuple[dict[SourceKind, Decimal], dict[SourceKind, Decimal]]:
        if served.grid_charge > 0:
            self._battery.charge_from_grid(served.grid_charge, price)
        if served.solar_charge > 0:
            self._battery.charge_from_solar(served.solar_charge)

        battery_price = Decimal(0)
        if served.battery > 0:
            battery_price = self._battery.discharge(served.battery) / served.battery

        prices = {
            SourceKind.IMPORT: price,
            SourceKind.SOLAR: Decimal(0),
            SourceKind.BATTERY: battery_price,
        }
        energies = {
            SourceKind.IMPORT: served.grid,
            SourceKind.SOLAR: served.solar,
            SourceKind.BATTERY: served.battery,
        }
        sources = {kind: kwh for kind, kwh in energies.items() if kwh > 0}
        return prices, sources

    def _price_at(self, when: datetime) -> Decimal:
        if not self._prices:
            return Decimal(0)
        applicable = self._prices[0][1]
        for at, price in self._prices:
            if at > when:
                break
            applicable = price
        return applicable


def _sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))
