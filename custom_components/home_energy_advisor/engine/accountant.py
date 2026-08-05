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
devices (a cycle-resetting counter aircons) report in coarse steps every 15-90 min, so most deltas
span past the watermark; dropping them silently reattributed 30-50 % of their
energy to Untracked (ADR-0006, HEA-48). Only portions older than the ring are
dropped, and never silently — a ``DROPPED_LATE`` decision is logged.

The Untracked remainder is *derived*, not accumulated: whole-home totals minus
the tracked-device totals holds identically because every label shares each
bucket's blended price, so the engine tracks the whole home plus each device and
subtracts. A monotonic whole-home total falls out for free.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from .allocation import ProportionalAllocationStrategy, split_by_source
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

# How many finalised buckets the plausibility guard weighs a device against the
# whole house over (HEA-60). One hour, and deliberately not one bucket: a coarse
# device's step legitimately lands entirely inside a single interval and exceeds
# what the house was served in it — that is the spreading approximation ADR-0006
# is built around, not a fault. Over an hour those artefacts cancel; a counter
# that is lying does not. The window must be *full* before anything is judged,
# so a fresh start never condemns a device on one interval's evidence.
_PLAUSIBILITY_WINDOW = 12


class SourceRole(Enum):
    """A configured house-level meter, before decomposition into served sources."""

    GRID_IMPORT = "grid_import"
    GRID_EXPORT = "grid_export"
    GENERATION = "generation"
    BATTERY_CHARGE = "battery_charge"
    BATTERY_DISCHARGE = "battery_discharge"
    HOUSE_CONSUMPTION = "house_consumption"


@dataclass(frozen=True)
class DeviceTotals:
    """Running since-startup figures for one device or the Untracked remainder.

    The three ``energy_from_*`` figures split ``energy_kwh`` across the sources
    that served it, for energy self-sufficiency (HEA-51). They sum to
    ``energy_kwh`` for every bucket the house-level meters accounted for; a bucket
    with draw but no readings at all contributes to the energy and to no source,
    so over such an interval the split falls short rather than claiming a supply
    nobody measured.
    """

    energy_kwh: Decimal
    actual_cost: Decimal
    naive_cost: Decimal
    cost_savings: Decimal
    energy_from_grid: Decimal
    energy_from_generation: Decimal
    energy_from_battery: Decimal


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

    Only what a correction needs: the fixed consumption and blended unit price the
    bucket settled at, the import price its naive cost uses, the running total
    device draw (which late arrivals grow), and the source mix that served it, so
    reclaimed energy is attributed to the sources of *its own* interval rather
    than whichever ones happen to be running when it finally arrives. The
    whole-home and real cost are fixed once finalised, so a correction only moves
    value from the Untracked remainder to the late device — never between devices.
    """

    consumption: Decimal
    blended: Decimal
    import_price: Decimal
    draw: Decimal
    sources: Mapping[SourceKind, Decimal]


@dataclass
class _WindowBucket:
    """One finalised interval's evidence for the plausibility guard (HEA-60).

    ``claimed`` is what each device's source *said* it drew, not what was booked.
    Judging on the claim is what lets a condemned device recover: its readings
    keep being weighed, so an honest source is believed again as soon as it is
    honest.
    """

    consumption: Decimal
    claimed: dict[str, Decimal]


@dataclass(frozen=True)
class _Served:
    """House-served energy for one interval, after decomposition."""

    grid: Decimal
    generation: Decimal
    battery: Decimal
    grid_charge: Decimal
    generation_charge: Decimal


@dataclass
class _Running:
    energy_kwh: Decimal = Decimal(0)
    actual_cost: Decimal = Decimal(0)
    naive_cost: Decimal = Decimal(0)
    cost_savings: Decimal = Decimal(0)
    by_source: dict[SourceKind, Decimal] = field(default_factory=dict)

    def add(self, allocation: DeviceAllocation) -> None:
        self.energy_kwh += allocation.energy_kwh
        self.actual_cost += allocation.actual_cost
        self.naive_cost += allocation.naive_cost
        self.cost_savings += allocation.cost_savings
        self.add_by_source(allocation.energy_by_source)

    def add_by_source(self, shares: Mapping[SourceKind, Decimal]) -> None:
        for kind, kwh in shares.items():
            self.by_source[kind] = self.by_source.get(kind, Decimal(0)) + kwh

    def snapshot(self) -> DeviceTotals:
        return DeviceTotals(
            energy_kwh=self.energy_kwh,
            actual_cost=self.actual_cost,
            naive_cost=self.naive_cost,
            cost_savings=self.cost_savings,
            energy_from_grid=self.by_source.get(SourceKind.IMPORT, Decimal(0)),
            energy_from_generation=self.by_source.get(
                SourceKind.GENERATION, Decimal(0)
            ),
            energy_from_battery=self.by_source.get(SourceKind.BATTERY, Decimal(0)),
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
        self._entity_of = dict(device_energy_entities)
        self._window: deque[_WindowBucket] = deque(maxlen=_PLAUSIBILITY_WINDOW)
        self._implausible: frozenset[str] = frozenset()
        # House inputs that are currently silent. Distinct from configured-but-
        # still: a meter that reports an unchanged reading is healthy (HEA-67).
        self._unhealthy_roles: set[SourceRole] = set()

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
        role = self._role_of.get(entity_id)
        if role is not None:
            self._note_role_health(role, reporting=value is not None)
        if delta is None:
            return
        if role is not None:
            self._spread_source(role, delta)
        elif (device := self._device_of.get(entity_id)) is not None:
            self._spread_device(device, delta, source)

    def _note_role_health(self, role: SourceRole, *, reporting: bool) -> None:
        """Track which house-level inputs are currently readable at all.

        ``value is None`` is the integration layer's signal that the state is
        ``unavailable`` or ``unknown`` — a genuinely silent meter. A meter that
        reports an unchanged reading is healthy and has simply not moved, and the
        two must never be conflated: on a coarse counter a quiet house yields
        unchanged readings for many buckets, so treating that as a failure would
        swap the decomposition model back and forth during normal running.

        This is why the bucket's contents cannot be the signal — a no-movement
        reading produces no delta, so it leaves no trace there either (HEA-67).
        """
        if reporting:
            self._unhealthy_roles.discard(role)
        else:
            self._unhealthy_roles.add(role)

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

    def reset_totals(self) -> None:
        """Rebases every running total to zero, as a hard accounting boundary.

        Backs the supported reset of a household's accumulated figures. Alongside
        the totals it drops the in-flight buckets and the retained ring, so no
        energy earned before the rebase can land after it — including as a late
        correction to a bucket that no longer contributes to any total.

        Two kinds of state deliberately survive. Each meter's last reading stays,
        so a climbing counter is read neither as a fresh start (dropping the next
        delta) nor as a climb from zero (re-counting everything before the
        rebase). And the battery's stored-cost ledger stays, because it records
        physical fact — the battery still holds energy bought at a known price,
        and discharging it after a rebase is not free.
        """
        self._running = {device: _Running() for device in self._running}
        self._house = _Running()
        self._raw.clear()
        self._draws.clear()
        self._retained.clear()

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
        grid = _sum(d.energy_from_grid for d in tracked)
        solar = _sum(d.energy_from_generation for d in tracked)
        battery = _sum(d.energy_from_battery for d in tracked)
        return DeviceTotals(
            energy_kwh=whole_home.energy_kwh - energy,
            actual_cost=whole_home.actual_cost - actual,
            naive_cost=whole_home.naive_cost - naive,
            cost_savings=whole_home.cost_savings - savings,
            energy_from_grid=whole_home.energy_from_grid - grid,
            energy_from_generation=whole_home.energy_from_generation - solar,
            energy_from_battery=whole_home.energy_from_battery - battery,
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
                self._correct(device, retained, portion.kwh, portion.start)
            else:
                source.note_dropped_late(portion.start, portion.kwh)

    def _is_finalised(self, start: datetime) -> bool:
        return self._watermark is not None and start <= self._watermark

    def _correct(
        self, device: str, retained: _RetainedBucket, kwh: Decimal, start: datetime
    ) -> None:
        """Reattribute late device energy within a finalised, still-retained bucket.

        The bucket's real cost and consumption are fixed, so the device is credited
        its full energy at the blended price, capped at the headroom the Untracked
        remainder still holds; the whole-home total absorbs any overdraw. Untracked
        is derived, so it gives back exactly what the device gains — no other device
        moves (ADR-0006, HEA-48).

        This is also the path a lying cloud-polled counter mostly arrives by — the
        utility plug reported every ~30 minutes, so most of each delta fell past the
        watermark — so the plausibility guard has to cover it too, or it would have
        missed the very case it exists for (HEA-60).
        """
        self._claim(device, kwh)
        if device in self._implausible:
            self._note_implausible(device, start, kwh)
            return

        headroom = max(Decimal(0), retained.consumption - retained.draw)
        priced = min(kwh, headroom)
        run = self._running.setdefault(device, _Running())
        run.energy_kwh += kwh
        run.naive_cost += kwh * retained.import_price
        run.actual_cost += priced * retained.blended
        run.cost_savings += kwh * retained.import_price - priced * retained.blended
        run.add_by_source(split_by_source(kwh, retained.sources, retained.consumption))

        grew = max(retained.consumption, retained.draw + kwh) - max(
            retained.consumption, retained.draw
        )
        self._house.energy_kwh += grew
        self._house.naive_cost += grew * retained.import_price
        self._house.cost_savings += grew * retained.import_price
        self._house.add_by_source(
            split_by_source(grew, retained.sources, retained.consumption)
        )
        retained.draw += kwh

    def _finalize_bucket(self, start: datetime) -> None:
        if not self._prices:
            self._note_zero_priced(start)
        raw = self._raw.pop(start, {})
        claimed = self._draws.pop(start, {})
        served = self._decompose(raw)
        self._weigh_plausibility(served, claimed)
        draws = self._believable(claimed, start)
        prices, sources = self._price_sources(served, self._price_at(start))
        bucket = IntervalBucket(start=start, sources=sources, device_draws=draws)
        allocation = self._strategy.allocate(bucket, prices)
        for device, share in allocation.devices.items():
            self._running.setdefault(device, _Running()).add(share)
        for share in allocation.devices.values():
            self._house.add(share)
        self._house.add(allocation.untracked)
        self._retain(start, sources, prices, draws)
        # Overdraw is judged on what the sources *claimed*, not on what survived the
        # plausibility guard. "Your tracked devices report drawing more than the
        # house" stays true whether or not the engine refused to book it, and
        # quarantining a lying device must not silently retire the broader Repair
        # that first tells a user something is wrong (HEA-36).
        self._track_overdraw(served, claimed)

    def implausible_devices(self) -> frozenset[str]:
        """Devices whose source is claiming more energy than the whole house.

        No real load can exceed the house it sits in, so a device that does over a
        full window is being lied to about (HEA-60). The coordinator turns this
        into a Repair; the engine has already stopped booking the energy, because
        allocation is proportional and one inflated device silently under-reports
        every other one.
        """
        return self._implausible

    def _claim(self, device: str, kwh: Decimal) -> None:
        """Add late-arriving energy to the newest window entry, as evidence.

        Attributed to the current window rather than the bucket it belongs to:
        the guard asks "is this source telling the truth *now*", and a claim is
        evidence whenever it lands. Recording it even while the device is
        condemned is what lets an honest source earn its way back.
        """
        if not self._window:
            return
        newest = self._window[-1].claimed
        newest[device] = newest.get(device, Decimal(0)) + kwh

    def _weigh_plausibility(
        self, served: _Served, claimed: Mapping[str, Decimal]
    ) -> None:
        """Record this interval's evidence and re-judge every device against it.

        While any house-level input is silent the house total is not evidence of
        anything: an unavailable meter reads as a zero, shrinking consumption
        until honest devices appear to exceed the house they sit in. Nothing is
        recorded and nothing is condemned — the fault is the meter's, and it is
        reported as such elsewhere.

        This protects the figures, not just the message. A condemned device has
        its energy refused by ``_believable``, so blaming devices for a house
        failure would quietly move real consumption into Untracked (HEA-67).
        """
        if self._unhealthy_roles:
            self._implausible = frozenset()
            return
        consumption = served.grid + served.generation + served.battery
        self._window.append(
            _WindowBucket(consumption=consumption, claimed=dict(claimed))
        )
        self._implausible = self._judge()

    def _judge(self) -> frozenset[str]:
        """Devices claiming more than the house across a *full* window.

        A part-filled window judges nothing: with one interval's evidence this
        would be the per-bucket test that coarse devices legitimately fail. A
        house total of zero judges nothing either — a silent house meter is its
        own fault, reported elsewhere, and is no evidence against a device.
        """
        if len(self._window) < _PLAUSIBILITY_WINDOW:
            return frozenset()
        house = _sum(bucket.consumption for bucket in self._window)
        if house <= 0:
            return frozenset()
        totals: dict[str, Decimal] = {}
        for bucket in self._window:
            for device, kwh in bucket.claimed.items():
                totals[device] = totals.get(device, Decimal(0)) + kwh
        return frozenset(device for device, drawn in totals.items() if drawn > house)

    def _believable(
        self, claimed: Mapping[str, Decimal], start: datetime
    ) -> dict[str, Decimal]:
        """The draws worth booking, logging each refusal on its own source."""
        believable = {}
        for device, kwh in claimed.items():
            if device in self._implausible:
                self._note_implausible(device, start, kwh)
            else:
                believable[device] = kwh
        return believable

    def _note_implausible(self, device: str, at: datetime, kwh: Decimal) -> None:
        entity = self._entity_of.get(device)
        source = self._sources.get(entity) if entity is not None else None
        if source is not None:
            source.note_implausible(at, kwh)

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
            sources=dict(sources),
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
        consumption = served.grid + served.generation + served.battery
        total_draw = sum(draws.values(), Decimal(0))
        if total_draw > consumption:
            self._overdrawn_run += 1
        else:
            self._overdrawn_run = 0

    def _is_readable(self, *roles: SourceRole) -> bool:
        """Whether every named house input is both configured and reporting."""
        return all(
            role in self._configured and role not in self._unhealthy_roles
            for role in roles
        )

    def _decompose(self, raw: Mapping[SourceRole, Decimal]) -> _Served:
        imp = raw.get(SourceRole.GRID_IMPORT, Decimal(0))
        exp = raw.get(SourceRole.GRID_EXPORT, Decimal(0))
        gen = raw.get(SourceRole.GENERATION, Decimal(0))
        charge = raw.get(SourceRole.BATTERY_CHARGE, Decimal(0))
        discharge = raw.get(SourceRole.BATTERY_DISCHARGE, Decimal(0))

        grid_charge = min(charge, imp)
        generation_charge = charge - grid_charge
        grid = imp - grid_charge

        # The branch follows what is *readable*, not merely what is configured.
        # A failed house meter otherwise reads as a zero, collapsing consumption
        # to grid + battery and discarding generation entirely — while the
        # household may well have the meters for the full-balance model (HEA-67).
        if self._is_readable(SourceRole.HOUSE_CONSUMPTION):
            house = raw.get(SourceRole.HOUSE_CONSUMPTION, Decimal(0))
            generation = max(Decimal(0), house - grid - discharge)
        elif self._is_readable(SourceRole.GENERATION, SourceRole.GRID_EXPORT):
            generation = max(Decimal(0), gen - generation_charge - exp)
        else:
            generation = Decimal(0)

        return _Served(
            grid=grid,
            generation=generation,
            battery=discharge,
            grid_charge=grid_charge,
            generation_charge=generation_charge,
        )

    def _price_sources(
        self, served: _Served, price: Decimal
    ) -> tuple[dict[SourceKind, Decimal], dict[SourceKind, Decimal]]:
        if served.grid_charge > 0:
            self._battery.charge_from_grid(served.grid_charge, price)
        if served.generation_charge > 0:
            self._battery.charge_from_generation(served.generation_charge)

        battery_price = Decimal(0)
        if served.battery > 0:
            battery_price = self._battery.discharge(served.battery) / served.battery

        prices = {
            SourceKind.IMPORT: price,
            SourceKind.GENERATION: Decimal(0),
            SourceKind.BATTERY: battery_price,
        }
        energies = {
            SourceKind.IMPORT: served.grid,
            SourceKind.GENERATION: served.generation,
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
