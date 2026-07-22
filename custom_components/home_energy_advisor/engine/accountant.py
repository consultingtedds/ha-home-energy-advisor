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

Completed intervals are finalised on a lateness margin. Energy that arrives for
an interval already finalised is dropped rather than reopening it — the amounts
are tiny and the alternative is materially more complex (ADR-0005, HEA-17).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from .allocation import ProportionalAllocationStrategy
from .battery_ledger import BatteryLedger
from .energy_source import CumulativeEnergySource, EnergyUnit, Reading
from .interval_ledger import BUCKET, IntervalBucket, SourceKind, spread_energy

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime, timedelta

    from .allocation import DeviceAllocation
    from .energy_source import EnergyDelta, SourceSnapshot

_DEFAULT_LATENESS = 3 * BUCKET


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
    """A snapshot of every tracked device plus the Untracked remainder."""

    devices: Mapping[str, DeviceTotals]
    untracked: DeviceTotals


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
    ) -> None:
        self._units = dict(units or {})
        self._lateness = lateness
        self._role_of = {entity: role for role, entity in house_sources.items()}
        self._device_of = {
            entity: device for device, entity in device_energy_entities.items()
        }
        self._configured = set(house_sources)
        self._sources: dict[str, CumulativeEnergySource] = {}
        self._raw: dict[datetime, dict[SourceRole, Decimal]] = {}
        self._draws: dict[datetime, dict[str, Decimal]] = {}
        self._prices: list[tuple[datetime, Decimal]] = []
        self._battery = BatteryLedger()
        self._strategy = ProportionalAllocationStrategy()
        self._running = {device: _Running() for device in device_energy_entities}
        self._untracked = _Running()
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
            self._spread_device(device, delta)

    def finalize(self, now: datetime) -> None:
        """Finalises every interval that ended before the lateness margin."""
        cutoff = now - self._lateness - BUCKET
        for start in sorted(set(self._raw) | set(self._draws)):
            if start > cutoff:
                break
            self._finalize_bucket(start)
            self._watermark = start

    def totals(self) -> Totals:
        """Returns the since-startup running totals per device and Untracked."""
        return Totals(
            devices={device: run.snapshot() for device, run in self._running.items()},
            untracked=self._untracked.snapshot(),
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

    def _spread_device(self, device: str, delta: EnergyDelta) -> None:
        for portion in spread_energy(delta):
            if self._is_finalised(portion.start):
                continue
            bucket = self._draws.setdefault(portion.start, {})
            bucket[device] = bucket.get(device, Decimal(0)) + portion.kwh

    def _is_finalised(self, start: datetime) -> bool:
        return self._watermark is not None and start <= self._watermark

    def _finalize_bucket(self, start: datetime) -> None:
        raw = self._raw.pop(start, {})
        draws = self._draws.pop(start, {})
        served = self._decompose(raw)
        prices, sources = self._price_sources(served, self._price_at(start))
        bucket = IntervalBucket(start=start, sources=sources, device_draws=draws)
        allocation = self._strategy.allocate(bucket, prices)
        for device, share in allocation.devices.items():
            self._running.setdefault(device, _Running()).add(share)
        self._untracked.add(allocation.untracked)
        self._track_overdraw(served, draws)

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
