"""HA-free accounting runtime: readings in, per-device running cost out.

Wraps the engine primitives - the cumulative delta calculator, the interval
spreading, the battery stored-cost ledger, and the proportional allocation
strategy - and does the energy-balance decomposition (ADR-0005) that turns raw
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
difference - the late device gains, the Untracked remainder gives back, and no
already-published device figure is revised. The giving back is *gradual*: the
remainder is a published figure too, and taking it where the correction was
discovered printed an hour that went backwards (ADR-0006, 2026-08-17 update).

This matters because the founding devices (cycle-resetting aircons) report in
coarse steps every 15-90 min, so most deltas
span past the watermark; dropping them silently reattributed 30-50 % of their
energy to Untracked (ADR-0006, HEA-48). Only portions older than the ring are
dropped, and never silently - a ``DROPPED_LATE`` decision is logged.

The Untracked remainder is *derived*, not accumulated: whole-home totals minus
the tracked-device totals holds identically because every label shares each
bucket's blended price, so the engine tracks the whole home plus each device and
subtracts. A monotonic whole-home total falls out for free.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from .allocation import (
    DeviceAllocation,
    ProportionalAllocationStrategy,
    split_by_source,
)
from .battery_ledger import BatteryLedger
from .debt_ledger import DebtLedger, Settlement
from .energy_source import (
    MAX_QUIET_SPAN,
    CumulativeEnergySource,
    EnergyUnit,
    Reading,
)
from .interval_ledger import BUCKET, IntervalBucket, SourceKind, spread_energy

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

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
# what the house was served in it - that is the spreading approximation ADR-0006
# is built around, not a fault. Over an hour those artefacts cancel; a counter
# that is lying does not. The window must be *full* before anything is judged,
# so a fresh start never condemns a device on one interval's evidence.
_PLAUSIBILITY_WINDOW = 12


@dataclass(frozen=True)
class AccountingWindows:
    """How long the accountant waits, remembers, and reaches back.

    Three spans that all answer "how far from now does this reading belong",
    grouped so they can be tuned together and so the constructor keeps one
    parameter for timing policy rather than three.
    """

    # How long an interval stays open for late readings before it is finalised.
    lateness: timedelta = _DEFAULT_LATENESS
    # How long a finalised bucket's context survives so late energy can correct it.
    retention: timedelta = _DEFAULT_RETENTION
    # How far back into a quiet run a coarse counter's step may be spread.
    max_quiet_span: timedelta = MAX_QUIET_SPAN


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
    # What ``actual_cost`` would have been had every kWh landed in the cheapest,
    # then the dearest, 5-minute slice of the span its counter revealed it over.
    # Outer bounds on the spreading approximation, not a confidence interval, and
    # on a house with generation they are far apart: a span can hold a slice
    # served by the sun and one served entirely by the meter (ADR-0016).
    cost_floor: Decimal
    cost_ceiling: Decimal


@dataclass(frozen=True)
class Totals:
    """A snapshot of every tracked device, the Untracked remainder, and the home.

    ``untracked`` is derived (``whole_home`` minus the tracked devices), so the
    three always reconcile exactly: Σ devices + untracked ≡ whole_home.

    ``unreconciled_kwh`` is the one figure that does *not* reconcile, and says so:
    debt the house meters never accounted for, forgiven at the expiry. Since the
    carry landed it is the only thing that can lift ``whole_home`` above metered
    consumption, so it is exactly the gap a household would find checking these
    totals against their own meter (ADR-0015, HEA-82).
    """

    devices: Mapping[str, DeviceTotals]
    untracked: DeviceTotals
    whole_home: DeviceTotals
    unreconciled_kwh: Decimal = Decimal(0)


@dataclass
class _RetainedBucket:
    """A finalised bucket's context, kept so late device energy can correct it.

    Only what a correction needs: the fixed consumption and blended unit price the
    bucket settled at, the import price its naive cost uses, the running total
    device draw (which late arrivals grow), and the source mix that served it, so
    reclaimed energy is attributed to the sources of *its own* interval rather
    than whichever ones happen to be running when it finally arrives. The
    whole-home and real cost are fixed once finalised, so a correction only moves
    value from the Untracked remainder to the late device - never between devices.
    """

    consumption: Decimal
    blended: Decimal
    import_price: Decimal
    draw: Decimal
    sources: Mapping[SourceKind, Decimal]


@dataclass(frozen=True)
class _PendingBound:
    """One delta's energy, waiting for the slices it spans to be priced.

    A delta's bound needs the blended price of every slice it touched, and those
    are only known as each is finalised. So the bound is held until the last of
    them closes, then resolved from the retained ring (ADR-0016).
    """

    device: str
    kwh: Decimal
    buckets: tuple[datetime, ...]


@dataclass
class _HeldCorrection:
    """Value a late delta earned from a finalised bucket, waiting to be handed over.

    The bucket's metered consumption is fixed, so a device reporting late claims
    energy the Untracked remainder was already credited with. Moving it at the
    moment of discovery takes it out of whichever hour the counter happened to
    report in, and a cumulative sensor can only be corrected in its current
    bucket - so the remainder publishes an hour that went backwards. That is the
    wrong-hour retraction HEA-85 removed from the overdraw charge, reaching the
    same figures by the other path.

    So the transfer waits, and each finalisation hands over only as much as the
    remainder has just earned. Both sides stay honest: no published total ever
    falls, and because the money moves device-ward without the house total
    changing, the split reconciles to the whole home at every instant rather than
    only once the transfer completes.

    Held in proportion, never field by field. Releasing energy faster than cost
    would price a device wrongly in the meantime, and releasing the by-source
    split out of step would stop a device's grid/generation/battery shares
    summing to its energy (HEA-51).

    It expires, on the same span a suspended charge does. A household whose
    remainder never earns again would otherwise hold this for ever, and a device
    that permanently under-reports is a worse answer than one dip in a figure -
    which is the trade ADR-0015 already made when it gave the debt ledger an
    expiry rather than letting a deficit outlive its meaning.
    """

    device: str
    at: datetime
    energy_kwh: Decimal
    actual_cost: Decimal
    naive_cost: Decimal
    cost_savings: Decimal
    by_source: dict[SourceKind, Decimal]

    def scaled(self, fraction: Decimal) -> _HeldCorrection:
        return _HeldCorrection(
            device=self.device,
            at=self.at,
            energy_kwh=self.energy_kwh * fraction,
            actual_cost=self.actual_cost * fraction,
            naive_cost=self.naive_cost * fraction,
            cost_savings=self.cost_savings * fraction,
            by_source={kind: kwh * fraction for kind, kwh in self.by_source.items()},
        )

    def less(self, taken: _HeldCorrection) -> _HeldCorrection:
        return _HeldCorrection(
            device=self.device,
            at=self.at,
            energy_kwh=self.energy_kwh - taken.energy_kwh,
            actual_cost=self.actual_cost - taken.actual_cost,
            naive_cost=self.naive_cost - taken.naive_cost,
            cost_savings=self.cost_savings - taken.cost_savings,
            by_source={
                kind: kwh - taken.by_source.get(kind, Decimal(0))
                for kind, kwh in self.by_source.items()
            },
        )


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
    # Deliberately not touched by ``add``: a bucket's allocation cannot bound a
    # figure whose uncertainty spans the buckets *around* it. Bounds accrue when
    # the span of the delta that revealed the energy has finished finalising.
    cost_floor: Decimal = Decimal(0)
    cost_ceiling: Decimal = Decimal(0)
    by_source: dict[SourceKind, Decimal] = field(default_factory=dict)

    def bound(self, floor: Decimal, ceiling: Decimal) -> None:
        self.cost_floor += floor
        self.cost_ceiling += ceiling

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
            cost_floor=self.cost_floor,
            cost_ceiling=self.cost_ceiling,
        )


class Accountant:
    """Turns a stream of meter readings into per-device running cost."""

    def __init__(
        self,
        *,
        house_sources: Mapping[SourceRole, str],
        device_energy_entities: Mapping[str, str],
        units: Mapping[str, EnergyUnit] | None = None,
        windows: AccountingWindows | None = None,
    ) -> None:
        self._units = dict(units or {})
        self._windows = windows or AccountingWindows()
        self._lateness = self._windows.lateness
        self._retention = self._windows.retention
        self._max_quiet_span = self._windows.max_quiet_span
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
        # Energy charged before its meter reading arrived, awaiting the surplus
        # that repays it. Expiring at the span a coarse step is spread over is a
        # derivation, not a second knob: a deficit created by that spreading
        # clears within it, and one that does not is a meter disagreement rather
        # than late reporting (ADR-0015).
        self._debts = DebtLedger(expiry=self._max_quiet_span)
        self._pending_bounds: list[_PendingBound] = []
        # Late corrections awaiting a remainder that can afford to hand them over,
        # oldest first so a device that has waited longest is paid first.
        self._held: list[_HeldCorrection] = []
        self._strategy = ProportionalAllocationStrategy()
        self._running = {device: _Running() for device in device_energy_entities}
        self._house = _Running()
        self._retained: dict[datetime, _RetainedBucket] = {}
        self._watermark: datetime | None = None
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
                unit=self._units.get(entity_id, EnergyUnit.KWH),
                max_quiet_span=self._max_quiet_span,
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
        ``unavailable`` or ``unknown`` - a genuinely silent meter. A meter that
        reports an unchanged reading is healthy and has simply not moved, and the
        two must never be conflated: on a coarse counter a quiet house yields
        unchanged readings for many buckets, so treating that as a failure would
        swap the decomposition model back and forth during normal running.

        This is why the bucket's contents cannot be the signal - a no-movement
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
        # Expiry is a function of time, not of activity. Each closing bucket
        # checks it too - that keeps the ordering right while buckets are being
        # settled - but a household whose meters have gone quiet closes no
        # buckets at all, and a suspended charge must still fall due (HEA-85).
        self._release(self._debts.expire(cutoff))
        self._expire_held(cutoff)
        self._evict_stale()
        self._prune_prices()

    def flush(self, now: datetime) -> None:
        """Finalises all in-flight intervals, sealing the partial current bucket.

        Called on unload (restart or any options/config change): finalising past
        the lateness margin banks up to ~20 min of otherwise-discarded accounting
        so the sensors capture it into their restore baseline. The trade-off - a
        bucket sealed here can no longer receive late portions after the reload, and
        the rebuilt runtime's retention ring starts empty - is accepted in ADR-0006.
        """
        self.finalize(now + self._lateness + BUCKET)

    def reset_totals(self) -> None:
        """Rebases every running total to zero, as a hard accounting boundary.

        Backs the supported reset of a household's accumulated figures. Alongside
        the totals it drops the in-flight buckets and the retained ring, so no
        energy earned before the rebase can land after it - including as a late
        correction to a bucket that no longer contributes to any total.

        Two kinds of state deliberately survive. Each meter's last reading stays,
        so a climbing counter is read neither as a fresh start (dropping the next
        delta) nor as a climb from zero (re-counting everything before the
        rebase). And the battery's stored-cost ledger stays, because it records
        physical fact - the battery still holds energy bought at a known price,
        and discharging it after a rebase is not free.
        """
        self._running = {device: _Running() for device in self._running}
        self._house = _Running()
        self._raw.clear()
        self._draws.clear()
        self._retained.clear()
        # Debt outlives nothing: it is a claim against buckets that no longer
        # contribute to any total, and repaying it after the rebase would move
        # value between figures that no longer share a baseline.
        self._debts = DebtLedger(expiry=self._max_quiet_span)

    def totals(self) -> Totals:
        """Returns the since-startup running totals per device, home and Untracked.

        Untracked is derived from the whole-home total minus the tracked devices,
        so the split reconciles exactly however late corrections have moved value.
        """
        devices = {device: run.snapshot() for device, run in self._running.items()}
        whole_home = self._house.snapshot()
        untracked = self._derive_untracked(whole_home, devices.values())
        # Bounds are the one figure the household total does not accumulate. The
        # remainder is priced within its own slice, so it carries no doubt, and a
        # late correction moves value out of it long after the slice closed -
        # accumulating a bound alongside would drift from the figure it bounds.
        # Composing it from the parts keeps it exact however value has moved.
        bounded = _sum(d.cost_floor for d in devices.values()) + untracked.actual_cost
        capped = _sum(d.cost_ceiling for d in devices.values()) + untracked.actual_cost
        return Totals(
            devices=devices,
            untracked=untracked,
            whole_home=replace(whole_home, cost_floor=bounded, cost_ceiling=capped),
            unreconciled_kwh=self.unreconciled_energy(),
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
        generation = _sum(d.energy_from_generation for d in tracked)
        battery = _sum(d.energy_from_battery for d in tracked)
        return DeviceTotals(
            energy_kwh=whole_home.energy_kwh - energy,
            actual_cost=whole_home.actual_cost - actual,
            naive_cost=whole_home.naive_cost - naive,
            cost_savings=whole_home.cost_savings - savings,
            energy_from_grid=whole_home.energy_from_grid - grid,
            energy_from_generation=whole_home.energy_from_generation - generation,
            energy_from_battery=whole_home.energy_from_battery - battery,
            # The remainder is derived slice by slice from meters that reported
            # for that slice, so unlike a coarse counter it has no span to be
            # uncertain about: its cost is its own bound.
            cost_floor=whole_home.actual_cost - actual,
            cost_ceiling=whole_home.actual_cost - actual,
        )

    def source_diagnostics(self) -> dict[str, SourceSnapshot]:
        """Per-source accumulator state and decision log, keyed by entity id.

        Feeds the diagnostics download (HEA-24): every meter the runtime has
        observed - house-level and per-device - with its last reading and the
        gating decisions that explain its accounting.
        """
        return {entity: source.snapshot() for entity, source in self._sources.items()}

    def has_finalised(self) -> bool:
        """Whether any interval has closed, and so whether a figure exists at all.

        Costs lag real time by the lateness margin plus the bucket - around twenty
        minutes - because that margin is what lets a coarse device's delta land
        before its bucket seals (ADR-0006). It buys correctness, so it is not a
        knob to turn down; what it costs is a first install that reads as broken
        while it is in fact counting. This says which of the two is happening
        (HEA-47).

        A rebase deliberately does not reset it. `reset_totals` zeroes the figures
        but leaves the watermark, because an engine that has closed an interval
        has proved it works, and saying otherwise would flag a household that has
        just reset as one that has just installed.
        """
        return self._watermark is not None

    def _spread_source(self, role: SourceRole, delta: EnergyDelta) -> None:
        for portion in spread_energy(delta):
            if self._is_finalised(portion.start):
                continue
            bucket = self._raw.setdefault(portion.start, {})
            bucket[role] = bucket.get(role, Decimal(0)) + portion.kwh

    def _spread_device(
        self, device: str, delta: EnergyDelta, source: CumulativeEnergySource
    ) -> None:
        portions = spread_energy(delta)
        # The whole delta is one question - "where in this span did the energy
        # happen" - so it is bounded as a whole, over every slice it touched,
        # rather than portion by portion.
        self._pending_bounds.append(
            _PendingBound(
                device=device,
                kwh=delta.kwh,
                buckets=tuple(portion.start for portion in portions),
            )
        )
        for portion in portions:
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

        The bucket's metered consumption is fixed, so the device takes what the
        Untracked remainder can still fund at the bucket's blended price, and
        *buys* the rest at the import price - energy the house drew that its
        meters had not yet reported can only have come off the grid. Leaving that
        excess free, as this path first did, published device costs far below the
        tariff whenever a coarse counter overshot a bucket (HEA-74, ADR-0014).
        Untracked is derived, so it gives back exactly what the device gains from
        the funded part - no other device moves (ADR-0006, HEA-48). That giving
        back is *held* rather than done here: taking it at the moment of discovery
        published a remainder that went backwards in whichever hour the counter
        reported. See `_HeldCorrection`.

        This is also the path a lying cloud-polled counter mostly arrives by - the
        utility plug reported every ~30 minutes, so most of each delta fell past the
        watermark - so the plausibility guard has to cover it too, or it would have
        missed the very case it exists for (HEA-60).
        """
        self._claim(device, kwh)
        if device in self._implausible:
            self._note_implausible(device, start, kwh)
            return

        headroom = max(Decimal(0), retained.consumption - retained.draw)
        funded = min(kwh, headroom)
        # Only the part the bucket's meters can still fund is priced. The rest is
        # the same overdraw the live path suspends, arriving later - and this is
        # the path most of a coarse counter's energy takes, so charging it here
        # would leave the symptom untouched (HEA-85).
        cost = funded * retained.blended
        grew = max(retained.consumption, retained.draw + kwh) - max(
            retained.consumption, retained.draw
        )
        run = self._running.setdefault(device, _Running())
        # The unfunded excess is the device's outright: no other figure holds it,
        # so handing it over now takes nothing from anyone. Only the funded part
        # comes out of the remainder, and only that part waits.
        run.energy_kwh += grew
        run.add_by_source(split_by_source(grew, retained.sources, retained.consumption))
        self._hold(
            _HeldCorrection(
                device=device,
                at=start,
                energy_kwh=funded,
                actual_cost=cost,
                naive_cost=funded * retained.import_price,
                cost_savings=funded * retained.import_price - cost,
                by_source=split_by_source(
                    funded, retained.sources, retained.consumption
                ),
            )
        )

        # `grew` is exactly the unfunded excess (`kwh - funded`), owed on the one
        # ledger both paths share. Its energy is published so the period still
        # reconciles; its money waits there until the debt settles.
        self._debts.owe(start, grew, grew * retained.import_price, {device: kwh})
        self._house.energy_kwh += grew
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
        remainder = self._settle(start, allocation.untracked, draws, sources, prices)
        for device, share in allocation.devices.items():
            self._running.setdefault(device, _Running()).add(share)
        for share in allocation.devices.values():
            self._house.add(share)
        self._house.add(remainder)
        # After the remainder has been banked, so the budget it funds is real.
        self._release_held(remainder, start)
        self._retain(start, sources, prices, draws)
        self._resolve_bounds(start)

    def _hold(self, correction: _HeldCorrection) -> None:
        """Queue a correction until the remainder can afford to hand it over."""
        if correction.energy_kwh > 0 or correction.actual_cost != 0:
            self._held.append(correction)

    def _release_held(self, remainder: DeviceAllocation, start: datetime) -> None:
        """Hand over as much held correction as this bucket's remainder just earned.

        The budget is the remainder itself, because that is precisely what has
        been added to the household total and not yet claimed by any device.
        Spending it moves value device-ward while the house total stands still,
        so the split still sums to the whole home - exactly, at this instant and
        every other. Spending more than it would push the remainder's published
        figure below what it printed an hour ago, which is the whole point.

        Oldest first: a device that has waited longest is paid first, so no
        correction can be starved by a livelier one behind it.
        """
        budget = _HeldCorrection(
            device="",
            at=start,
            energy_kwh=remainder.energy_kwh,
            actual_cost=remainder.actual_cost,
            naive_cost=remainder.naive_cost,
            cost_savings=Decimal(0),
            by_source={},
        )
        outstanding: list[_HeldCorrection] = []
        for held in self._held:
            fraction = _affordable(held, budget)
            if fraction <= 0:
                outstanding.append(held)
                continue
            paid = held.scaled(fraction)
            run = self._running.setdefault(held.device, _Running())
            run.energy_kwh += paid.energy_kwh
            run.actual_cost += paid.actual_cost
            run.naive_cost += paid.naive_cost
            run.cost_savings += paid.cost_savings
            run.add_by_source(paid.by_source)
            budget = budget.less(paid)
            if fraction < 1:
                outstanding.append(held.less(paid))
        self._held = outstanding

    def _expire_held(self, cutoff: datetime) -> None:
        """Hand over a correction the remainder never found the room for.

        Expiry is a function of time, not of activity, so it lives here beside the
        debt ledger's rather than in the bucket path: a household whose meters go
        quiet closes no buckets, and a device left short would stay short for ever
        (the same reasoning HEA-85 applied to a suspended charge).

        Two other ways the budget never comes. A bucket's surplus repays debt
        before any remainder is published, so a large outstanding overdraw
        crowds this out for as long as it lasts. And a remainder that is
        persistently zero - a house whose tracked devices account for everything -
        has nothing to give. Both end here, at the one price the wait was ever
        worth paying to avoid.
        """
        due = [held for held in self._held if cutoff - held.at >= self._max_quiet_span]
        if not due:
            return
        self._held = [held for held in self._held if held not in due]
        for held in due:
            run = self._running.setdefault(held.device, _Running())
            run.energy_kwh += held.energy_kwh
            run.actual_cost += held.actual_cost
            run.naive_cost += held.naive_cost
            run.cost_savings += held.cost_savings
            run.add_by_source(held.by_source)

    def _resolve_bounds(self, start: datetime) -> None:
        """Price every waiting delta whose last slice has now closed.

        Buckets finalise in order, so a delta is resolvable once the newest slice
        it touched is retained. Both paths arrive here: energy accounted live
        resolves at its own last slice, and energy arriving late for slices
        already closed resolves at the next finalisation - which matters, because
        that is the path most of a coarse counter's energy takes (ADR-0006).
        """
        waiting: list[_PendingBound] = []
        for pending in self._pending_bounds:
            if pending.buckets[-1] > start:
                waiting.append(pending)
                continue
            blends = [
                retained.blended
                for at in pending.buckets
                if (retained := self._retained.get(at)) is not None
            ]
            if not blends:
                continue
            floor = pending.kwh * min(blends)
            ceiling = pending.kwh * max(blends)
            self._running.setdefault(pending.device, _Running()).bound(floor, ceiling)
        self._pending_bounds = waiting

    def _settle(
        self,
        start: datetime,
        remainder: DeviceAllocation,
        draws: Mapping[str, Decimal],
        sources: Mapping[SourceKind, Decimal],
        prices: Mapping[SourceKind, Decimal],
    ) -> DeviceAllocation:
        """Owes this bucket's overdraw, or spends its surplus repaying an older one.

        A bucket whose tracked draw exceeds metered consumption publishes no
        remainder and records the excess as debt; one with a surplus offers it to
        the ledger before publishing what is left. Over the pair the published
        figures reconcile to the meter, which neither does alone (ADR-0015).
        """
        consumption = _sum(sources.values())
        import_price = prices[SourceKind.IMPORT]
        self._release(self._debts.expire(start))
        overdraw = _sum(draws.values()) - consumption
        if overdraw > 0:
            self._debts.owe(start, overdraw, overdraw * import_price, draws)
            return remainder
        if remainder.energy_kwh <= 0:
            return remainder
        blended = remainder.actual_cost / remainder.energy_kwh
        settlement = self._debts.repay(remainder.energy_kwh, blended)
        self._release(settlement)
        return _withhold(remainder, settlement.kwh, blended, import_price, sources)

    def _release(self, settlement: Settlement) -> None:
        """Publishes a suspended charge, now that its real price is known.

        The overdraw was never charged when it happened: pricing it at import was
        a guess, and publishing a guess means taking it back, which reads as an
        hour that cost less than nothing (HEA-85, ADR-0015 decision 5). It arrives
        here instead - at the repaying interval's blend, or at import if the debt
        expired unpaid.

        Actual and counterfactual move together. On expiry they are equal and the
        saving is untouched; on repayment their difference is the real saving the
        household made by having been served more cheaply than the grid.
        """
        for device, amount in settlement.actual.items():
            self._running.setdefault(device, _Running()).actual_cost += amount
            self._house.actual_cost += amount
        for device, amount in settlement.naive.items():
            run = self._running.setdefault(device, _Running())
            run.naive_cost += amount
            run.cost_savings += amount - settlement.actual.get(device, Decimal(0))
            self._house.naive_cost += amount
            self._house.cost_savings += amount - settlement.actual.get(
                device, Decimal(0)
            )

    def unreconciled_energy(self) -> Decimal:
        """Energy charged that the house meters never went on to account for.

        Debt forgiven at the expiry rather than repaid. Reporting latency clears
        within that window; what survives it is the household's own meters
        disagreeing, which is surfaced rather than absorbed (HEA-82).
        """
        return self._debts.forgiven_kwh()

    def unreconciled_share(self) -> Decimal:
        """Unreconciled energy as a fraction of everything published.

        The same gap the ``unreconciled_energy`` figure carries, expressed the way
        a household would check it - "my totals sit this far above my meter". A
        fraction rather than a quantity because that is what survives comparison
        between a flat and a farmhouse, and what a threshold can be set on.

        It decays on its own: a fault that is fixed stops adding to the numerator
        while good energy keeps growing the denominator, so a Repair raised on it
        clears without anyone resetting anything.
        """
        published = self._house.energy_kwh
        if published <= 0:
            return Decimal(0)
        return self._debts.forgiven_kwh() / published

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
        recorded and nothing is condemned - the fault is the meter's, and it is
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
        house total of zero judges nothing either - a silent house meter is its
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
        rescanned from index zero per bucket - pathological for a spot tariff.
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
        # to grid + battery and discarding generation entirely - while the
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


def _withhold(
    remainder: DeviceAllocation,
    repaid: Decimal,
    blended: Decimal,
    import_price: Decimal,
    sources: Mapping[SourceKind, Decimal],
) -> DeviceAllocation:
    """The remainder less the energy that settled a debt, and less its cost.

    Withheld rather than published because the devices were already credited
    with this energy in the bucket that overdrew; publishing it again is the
    double-count the carry exists to remove. The sources are re-split over what
    is kept, so the by-source figures still sum to the energy they explain.
    """
    if repaid <= 0:
        return remainder
    kept = remainder.energy_kwh - repaid
    actual = remainder.actual_cost - repaid * blended
    naive = kept * import_price
    return DeviceAllocation(
        energy_kwh=kept,
        actual_cost=actual,
        naive_cost=naive,
        cost_savings=naive - actual,
        energy_by_source=split_by_source(kept, sources, _sum(sources.values())),
    )


def _sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))


def _affordable(held: _HeldCorrection, budget: _HeldCorrection) -> Decimal:
    """What share of a held correction this budget can pay for, from 0 to 1.

    The tightest field decides, and the whole correction moves at that one share.
    Paying each field to its own limit would let a device's energy outrun its
    cost, pricing it wrongly until the rest caught up, and would break the
    identity that a device's grid, generation and battery shares sum to its
    energy (HEA-51).

    A field the correction does not want cannot constrain it; a field the budget
    cannot cover at all stops the payment outright, which is how a bucket with no
    remainder to spare hands over nothing rather than borrowing against itself.
    """
    fraction = Decimal(1)
    for wanted, available in (
        (held.energy_kwh, budget.energy_kwh),
        (held.actual_cost, budget.actual_cost),
        (held.naive_cost, budget.naive_cost),
    ):
        if wanted <= 0:
            continue
        if available <= 0:
            return Decimal(0)
        fraction = min(fraction, available / wanted)
    return fraction
