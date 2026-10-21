"""HA-free accounting runtime: readings in, per-device running cost out.

Wraps the engine primitives - the cumulative delta calculator, the interval
spreading, the battery stored-cost ledger, and the proportional allocation
strategy - and does the energy-balance decomposition (ADR-0005) that turns raw
meter deltas into the house-served sources the allocation model needs.

The Home Assistant coordinator (HEA-21 stage B) feeds this class state changes
and a wall-clock ``now``; the class itself holds no Home Assistant references and
is fully unit-testable. Its runtime state is serialisable (:meth:`Accountant.
snapshot` / :meth:`Accountant.restore`), so accounting continues across a restart
rather than resuming from nothing; the integration layer owns where that state is
kept.

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
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from .allocation import (
    DeviceAllocation,
    ProportionalAllocationStrategy,
    split_by_source,
)
from .battery_ledger import BatteryLedger
from .battery_shares import BatteryLoss, BatteryMeters, BatteryShares
from .debt_ledger import DebtLedger, Settlement
from .energy_source import (
    MAX_QUIET_SPAN,
    CumulativeEnergySource,
    DecisionReason,
    EnergyUnit,
    Reading,
    ScaleChange,
)
from .house_balance import ChargeSource, HouseBalance, HouseReadings, Served
from .interval_ledger import (
    BUCKET,
    IntervalBucket,
    SourceKind,
    bucket_start,
    spread_energy,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

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

# How long the battery's meters must have allowed a loss, without a break, before
# it is published (HEA-213, ADR-0028). A battery's level is an estimate that
# drifts through an evening and corrects itself at the next charge - a reference
# household's runs about 1 kWh either side of its meters over a day - and a loss
# figure only counts upwards, so anything published at the peak of that drift
# stays there. A day covers the cycle the drift follows, and depends on nothing
# but time, so it serves a battery that never reaches full as well as one that
# does.
_LOSS_HOLD = timedelta(hours=24)

# Printed beside the figure in the diagnostics download, because it is the only
# place a household's meter disagreement is visible at all (HEA-200, HEA-212).
_METER_DISAGREEMENT_MEANS = (
    "How far the house meters claim more battery loss than the battery's own "
    "meters allow, since measuring began. Non-zero only where a household's "
    "meters disagree with each other; it never reaches a published figure."
)


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


type HouseMeters = str | tuple[str, ...]
"""The meter, or meters, filling one role.

Generation can come from several - Home Assistant's Energy Dashboard takes any
number of solar sources (HEA-219) - and each is counted on its own and added, so
one resetting never re-counts another's lifetime.
"""


def meters_of(meters: HouseMeters) -> tuple[str, ...]:
    """Every meter filling a role, however it was given."""
    return (meters,) if isinstance(meters, str) else meters


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
    # The share of ``cost_savings`` that came from time-shifting rather than from
    # the sun, so a household can tell what their battery did for them from what
    # their panels did (HEA-173). The two halves sum to ``cost_savings`` exactly;
    # generation's is left as that subtraction.
    battery_savings: Decimal
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
    # What the generation this device consumed would have earned had it been
    # exported instead, at the export rate in force at the time. Published
    # *beside* the cost and never inside it, so `actual_cost` stays what the
    # household paid and ADR-0002's reconciliation keeps meaning what it says
    # (ADR-0026). Zero for a household who declare no export price.
    forgone_export: Decimal


#: Every figure at zero, for a household whose battery has lost nothing - or has
#: no battery at all.
_ZERO_TOTALS = DeviceTotals(
    energy_kwh=Decimal(0),
    actual_cost=Decimal(0),
    naive_cost=Decimal(0),
    cost_savings=Decimal(0),
    battery_savings=Decimal(0),
    energy_from_grid=Decimal(0),
    energy_from_generation=Decimal(0),
    energy_from_battery=Decimal(0),
    cost_floor=Decimal(0),
    cost_ceiling=Decimal(0),
    forgone_export=Decimal(0),
)


@dataclass(frozen=True)
class Totals:
    """A snapshot of every tracked device, the Untracked remainder, and the home.

    ``untracked`` is derived - ``whole_home`` less the tracked devices *and* less
    the battery's own consumption - so the terms always reconcile exactly:
    Σ devices + untracked + battery ≡ whole_home. The battery is zero throughout
    for a household who has not said how full theirs is, which is what leaves
    that identity reading as it always did for them (ADR-0002, HEA-174).

    ``unreconciled_kwh`` is the one figure that does *not* reconcile, and says so:
    debt the house meters never accounted for, forgiven at the expiry. Since the
    carry landed it is the only thing that can lift ``whole_home`` above metered
    consumption, so it is exactly the gap a household would find checking these
    totals against their own meter (ADR-0015, HEA-82).
    """

    devices: Mapping[str, DeviceTotals]
    untracked: DeviceTotals
    whole_home: DeviceTotals
    # Energy the battery took in and never gave back, and what it cost. A third
    # term in the identity rather than part of the remainder: it is real imported
    # energy really used, so it belongs in the house total, but it is not
    # *untracked* - Untracked is what a household shrinks by tracking more
    # devices, and nothing they track will ever shrink this (HEA-174).
    battery: DeviceTotals = field(default_factory=lambda: _ZERO_TOTALS)
    unreconciled_kwh: Decimal = Decimal(0)
    # Each battery's share of `battery`, keyed by battery, where there are two or
    # more. Not a fourth term: the shares add up to `battery` and sit beside it
    # (ADR-0031). Empty for a household with one battery, whose pool is it.
    batteries: Mapping[str, DeviceTotals] = field(default_factory=dict)


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
    # What a kWh out of the battery cost in *this* bucket, so a late arrival's
    # share of the battery saving is priced against the charge that really served
    # it rather than against whatever the ledger holds when it turns up (HEA-173).
    battery_price: Decimal
    # What exporting a kWh earned in *this* bucket, so late generation is valued
    # against the rate that really applied rather than whatever is current when
    # it turns up (ADR-0026). Kept here for the same reason `import_price` is:
    # the rate series is pruned against the watermark, so an old bucket's rate
    # is not necessarily still in it.
    forgone_prices: Mapping[SourceKind, Decimal]
    draw: Decimal
    sources: Mapping[SourceKind, Decimal]


# House roles whose energy *adds* to what the house consumed, and which can
# therefore still correct a bucket that has closed. Their counterparts - export
# and battery charge - subtract, so a late one would pull a published figure
# down, and `HouseBalance` already carries both forward instead (ADR-0015's
# 2026-09-16 and 2026-09-18 amendments).
_RAISES_CONSUMPTION = {
    SourceRole.GRID_IMPORT: SourceKind.IMPORT,
    SourceRole.GENERATION: SourceKind.GENERATION,
    SourceRole.BATTERY_DISCHARGE: SourceKind.BATTERY,
}

# What a kilowatt-hour from each source cost the household in the interval that
# used it. Generation is free at the margin (ADR-0002), grid is the import price
# the bucket settled at, and a discharge is what that bucket's battery energy had
# been bought for.
_MARGINAL_PRICE_OF: dict[SourceKind, Callable[[_RetainedBucket], Decimal]] = {
    SourceKind.IMPORT: lambda retained: retained.import_price,
    SourceKind.GENERATION: lambda _: Decimal(0),
    SourceKind.BATTERY: lambda retained: retained.battery_price,
}


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


@dataclass(frozen=True)
class _LossAnchor:
    """Where everything the battery's loss is read from stood when measuring began.

    The loss is read from two running totals and both are taken from here: what
    the house's meters cannot explain, and what the battery's own meters carried,
    each less what the level gained since (HEA-213).
    """

    headroom: Decimal
    available: Decimal
    charged: Decimal
    discharged: Decimal


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
    battery_savings: Decimal
    # What each source in this correction's bucket gave up per kWh. Rates, not
    # amounts, so they are carried through a split unchanged while the energy
    # beside them is scaled (ADR-0026, ADR-0027).
    forgone_prices: Mapping[SourceKind, Decimal]
    by_source: dict[SourceKind, Decimal]

    def scaled(self, fraction: Decimal) -> _HeldCorrection:
        return _HeldCorrection(
            device=self.device,
            at=self.at,
            energy_kwh=self.energy_kwh * fraction,
            actual_cost=self.actual_cost * fraction,
            naive_cost=self.naive_cost * fraction,
            cost_savings=self.cost_savings * fraction,
            battery_savings=self.battery_savings * fraction,
            forgone_prices=self.forgone_prices,
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
            battery_savings=self.battery_savings - taken.battery_savings,
            forgone_prices=self.forgone_prices,
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

    ``start`` is the interval it is evidence for, so energy that arrives late can
    be weighed against the house in the interval it belongs to (HEA-225). ``None``
    only for an entry restored from a snapshot written before it was kept.
    """

    consumption: Decimal
    claimed: dict[str, Decimal]
    start: datetime | None = None


@dataclass
class _Running:
    energy_kwh: Decimal = Decimal(0)
    actual_cost: Decimal = Decimal(0)
    naive_cost: Decimal = Decimal(0)
    cost_savings: Decimal = Decimal(0)
    battery_savings: Decimal = Decimal(0)
    # Deliberately not touched by ``add``: a bucket's allocation cannot bound a
    # figure whose uncertainty spans the buckets *around* it. Bounds accrue when
    # the span of the delta that revealed the energy has finished finalising.
    cost_floor: Decimal = Decimal(0)
    cost_ceiling: Decimal = Decimal(0)
    # What this device's share of self-consumed generation would have earned had
    # it been exported instead (ADR-0026). Accumulated here rather than carried
    # on the allocation, because `add_by_source` is the one funnel every path
    # attributes energy through - so a path that books generation cannot fail to
    # book what it gave up. ADR-0025 threaded a money figure through each path by
    # hand and silently missed one of the four.
    forgone_export: Decimal = Decimal(0)
    by_source: dict[SourceKind, Decimal] = field(default_factory=dict)

    def bound(self, floor: Decimal, ceiling: Decimal) -> None:
        self.cost_floor += floor
        self.cost_ceiling += ceiling

    def add(
        self,
        allocation: DeviceAllocation,
        forgone_per_kwh: Mapping[SourceKind, Decimal],
    ) -> None:
        self.energy_kwh += allocation.energy_kwh
        self.actual_cost += allocation.actual_cost
        self.naive_cost += allocation.naive_cost
        self.cost_savings += allocation.cost_savings
        self.battery_savings += allocation.battery_savings
        self.add_by_source(allocation.energy_by_source, forgone_per_kwh)

    def add_by_source(
        self,
        shares: Mapping[SourceKind, Decimal],
        forgone_per_kwh: Mapping[SourceKind, Decimal],
    ) -> None:
        """Attribute energy to its sources, and what each source gave up.

        Generation gives up the export it was not paid for, at the rate in force
        when it was used. A battery discharge gives up what the sunshine inside
        it gave up when it was *stored*, which the ledger carries (ADR-0027).
        Grid energy gives up nothing: it was bought.

        The rates belong to the interval the energy belongs to, not to the moment
        it was booked - a late arrival is attributed to the sources of its own
        bucket, so it is valued at that bucket's rates too.

        A mapping rather than one rate per source in turn, so a source nobody has
        priced simply contributes nothing and adding another needs no new
        argument. Required rather than defaulted, so a new caller cannot quietly
        book generation at nothing.
        """
        for kind, kwh in shares.items():
            self.by_source[kind] = self.by_source.get(kind, Decimal(0)) + kwh
            self.forgone_export += kwh * forgone_per_kwh.get(kind, Decimal(0))

    def snapshot(self) -> DeviceTotals:
        return DeviceTotals(
            energy_kwh=self.energy_kwh,
            actual_cost=self.actual_cost,
            naive_cost=self.naive_cost,
            cost_savings=self.cost_savings,
            battery_savings=self.battery_savings,
            energy_from_grid=self.by_source.get(SourceKind.IMPORT, Decimal(0)),
            energy_from_generation=self.by_source.get(
                SourceKind.GENERATION, Decimal(0)
            ),
            energy_from_battery=self.by_source.get(SourceKind.BATTERY, Decimal(0)),
            cost_floor=self.cost_floor,
            cost_ceiling=self.cost_ceiling,
            forgone_export=self.forgone_export,
        )


class Accountant:
    """Turns a stream of meter readings into per-device running cost."""

    def __init__(  # noqa: PLR0913 - every argument is a keyword-only fact about the house
        self,
        *,
        house_sources: Mapping[SourceRole, HouseMeters],
        device_energy_entities: Mapping[str, str],
        nested_devices: Mapping[str, str] | None = None,
        windows: AccountingWindows | None = None,
        charge_source: ChargeSource = ChargeSource.SPARE_SOLAR,
        batteries: Mapping[str, BatteryMeters] | None = None,
    ) -> None:
        self._windows = windows or AccountingWindows()
        # Which battery each battery meter belongs to, so the pool's loss can be
        # shared out among them (ADR-0031). The pool itself is accounted from the
        # house's battery roles, which hold every battery's meters.
        self._shares = BatteryShares(dict(batteries or {}))
        # The levels the last reconcile was given, battery by battery, which the
        # share of a loss is measured against.
        self._levels: Mapping[str, Decimal] = {}
        # How the household's battery charges, which decides what charged it
        # where import, generation and charging coincide (HEA-233). The meters
        # cannot see it, so the household says.
        self._charge_source = charge_source
        self._lateness = self._windows.lateness
        self._retention = self._windows.retention
        self._max_quiet_span = self._windows.max_quiet_span
        self._meters_of = {role: meters_of(m) for role, m in house_sources.items()}
        self._role_of = {
            entity: role
            for role, entities in self._meters_of.items()
            for entity in entities
        }
        self._device_of = {
            entity: device for device, entity in device_energy_entities.items()
        }
        # Which device physically contains which, child -> its direct parent.
        # A clamp on a breaker measures everything downstream of it, so a
        # tracked appliance on a tracked circuit is inside both counters and
        # would otherwise be booked twice (HEA-151).
        self._upstream = dict(nested_devices or {})
        self._children: dict[str, list[str]] = {}
        for child, parent in self._upstream.items():
            self._children.setdefault(parent, []).append(child)
        # What a parent's children reported ahead of the parent itself, waiting
        # for the bucket its own counter catches up in. Keyed by parent, held as
        # the amount still owed and the instant it was first owed (HEA-169).
        self._nesting_carry: dict[str, tuple[Decimal, datetime]] = {}
        self._configured = set(house_sources)
        self._import_entity = next(
            iter(self._meters_of.get(SourceRole.GRID_IMPORT, ())), None
        )
        # The import meters that have been told no price has arrived for them yet.
        self._cold_start_logged: set[str] = set()
        self._sources: dict[str, CumulativeEnergySource] = {}
        self._raw: dict[datetime, dict[SourceRole, Decimal]] = {}
        # Each interval's import again, meter by meter, because each register is
        # priced at its own rate (ADR-0032). `_raw` holds the same energy summed.
        self._raw_import: dict[datetime, dict[str, Decimal]] = {}
        self._draws: dict[datetime, dict[str, Decimal]] = {}
        # The import price of each import meter. Keyed `None` only where a
        # household has no import meter at all, which leaves the rate pricing
        # what the grid would have cost and nothing else.
        self._prices: dict[str | None, list[tuple[datetime, Decimal]]] = {}
        # What the household is paid for exporting, kept the same way the import
        # price is because the forgone-export figure is accumulated against the
        # rate in force at the time rather than an average over a period
        # (ADR-0026). Empty on every household who export nothing, and then
        # nothing is published - which is today's behaviour and the right one,
        # since for them self-consumed generation really is free.
        self._export_prices: list[tuple[datetime, Decimal]] = []
        self._battery = BatteryLedger()
        # What the house's own meters leave unexplained, which by physics is what
        # the battery gained plus what it lost - and so a ceiling on the loss we
        # will publish. ``None`` until a household meters enough to ask (HEA-174).
        self._balance_headroom: Decimal | None = None
        # Where the loss is measured from. `None` until the household first tells
        # us how full the battery is.
        self._loss_anchor: _LossAnchor | None = None
        # How much of the loss measured since the anchor has been published. Not
        # the published figure itself: a reset rebases that and must not make the
        # same loss publishable twice.
        self._loss_published = Decimal(0)
        # The lower of the two running totals over the last `_LOSS_HOLD`, as a
        # sliding minimum: each entry is a value and the moment it took effect,
        # values strictly rising, so the first entry is the least the totals have
        # read across the window. Rarely more than a handful of entries.
        self._loss_window: deque[tuple[datetime, Decimal]] = deque()
        self._battery_loss_kwh = Decimal(0)
        self._battery_loss_cost = Decimal(0)
        self._battery_loss_forgone = Decimal(0)
        # What the battery's own meters have carried, which bounds the loss the
        # house balance infers (HEA-196). Running totals of the *metered* charge
        # and discharge: the ledger's own write-down cannot serve here, because
        # `_loss_ceiling` already caps that against this same house balance, so it
        # is not independent of the figure it would be bounding.
        self._metered_charge = Decimal(0)
        self._metered_discharge = Decimal(0)
        # How far the house balance currently claims more than the battery's meters
        # allow, for the diagnostics. A household seeing this grow has meters that
        # disagree with each other, which is worth knowing and is not something
        # the figures can fix.
        self._loss_refused_kwh = Decimal(0)
        # What each side of the measurement said at the last tick - the house
        # meters' claim and the battery meters' allowance since the anchor - for
        # the diagnostics (HEA-212). Recomputed every tick, so not persisted.
        self._loss_last_totals: tuple[Decimal, Decimal] | None = None
        # Energy charged before its meter reading arrived, awaiting the surplus
        # that repays it. Expiring at the span a coarse step is spread over is a
        # derivation, not a second knob: a deficit created by that spreading
        # clears within it, and one that does not is a meter disagreement rather
        # than late reporting (ADR-0015).
        self._debts = DebtLedger(expiry=self._max_quiet_span)
        # House meters that tick a whole unit at a time leave each interval's
        # balance half told; what is left over waits here for its counterpart
        # rather than being floored away (HEA-133).
        self._balance = HouseBalance(
            expiry=self._max_quiet_span, charge_source=self._charge_source
        )
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
        # House meters that are currently silent. Distinct from configured-but-
        # still: a meter that reports an unchanged reading is healthy (HEA-67).
        # Kept per meter, not per role: where a role has several, one reporting
        # must not vouch for another that has gone quiet (HEA-219).
        self._silent_meters: set[str] = set()

    def record_price(
        self, at: datetime, price: Decimal, meter: str | None = None
    ) -> None:
        """Records the import price active from ``at`` on one import meter.

        ``meter`` defaults to the household's first import meter, which is the
        only one a household with a single register has.
        """
        key = self._import_entity if meter is None else meter
        self._prices.setdefault(key, []).append((at, price))

    def record_export_price(self, at: datetime, price: Decimal) -> None:
        """Records the export price active from ``at`` (ADR-0026).

        Read from the Energy Dashboard rather than configured here, because a
        household who exports has already declared what they are paid for it and
        a second copy would be a second source of truth. A household who records
        none is one who exports nothing, and forgoes nothing by using their own
        generation.
        """
        self._export_prices.append((at, price))

    def rates_in_force(self, now: datetime) -> dict[str, object]:
        """The import and export rate the engine holds at ``now``, and since when.

        For the diagnostics (HEA-210). A forgone figure only moves when
        generation is used, so on a dull morning a rate that took and a rate the
        engine never saw look the same; the rate held and the moment it took
        effect tell them apart. ``None`` where no rate has been received, which
        is a different answer from a rate of zero. Import is given per import
        meter, since each register has its own (ADR-0032).
        """
        return {
            "import": {
                str(meter): _in_force(series, now)
                for meter, series in self._prices.items()
            },
            "export": _in_force(self._export_prices, now),
        }

    def observe(
        self,
        entity_id: str,
        at: datetime,
        value: Decimal | None,
        unit: EnergyUnit = EnergyUnit.KWH,
    ) -> None:
        """Records a meter reading, spreading its delta into the interval buckets.

        The unit belongs to the reading rather than to the source, so a sensor
        that was not readable when this accountant was built is still counted in
        its own unit once it reports, and one that changes unit is not counted
        across the change (HEA-149).

        It defaults to kWh for a caller whose counters simply are kilowatt hours.
        The integration layer never relies on that: it reads the unit off each
        state, and says ``UNKNOWN`` where the state does not carry one - which is
        a different instruction from this default, and the distinction is the
        whole of GitHub #24.
        """
        source = self._sources.get(entity_id)
        if source is None:
            source = CumulativeEnergySource(max_quiet_span=self._max_quiet_span)
            self._sources[entity_id] = source
        delta = source.observe(Reading(at=at, value=value, unit=unit))
        role = self._role_of.get(entity_id)
        if role is not None:
            self._note_meter_health(entity_id, reporting=value is not None)
        if delta is None:
            return
        if role is not None:
            self._shares.carried(entity_id, delta.kwh)
            self._spread_source(entity_id, role, delta, source)
        elif (device := self._device_of.get(entity_id)) is not None:
            self._spread_device(device, delta, source)

    def _note_meter_health(self, entity_id: str, *, reporting: bool) -> None:
        """Track which house-level meters are currently readable at all.

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
            self._silent_meters.discard(entity_id)
        else:
            self._silent_meters.add(entity_id)

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
        rebase). And the battery's stored *inventory* stays, because it records
        physical fact - the battery still holds energy bought at a known price,
        and discharging it after a rebase is not free.

        What the battery has *lost* is not physical fact about the present but a
        running total of the past, and it is published as one (HEA-174). So it
        rebases with every other figure, or a household who asked to start again
        would find one sensor still carrying the whole history.
        """
        self._running = {device: _Running() for device in self._running}
        self._house = _Running()
        self._battery.forget_losses()
        # The figure a household actually sees. `forget_losses` rebases the
        # ledger's write-down, which was the same figure until HEA-182 split the
        # measured loss from it - and the reset was left pointing at the old one
        # while this docstring was updated to describe the new behaviour. So a
        # household who reset everything found this one sensor carrying its whole
        # history, which is what they reported (HEA-207, GitHub 34).
        self._battery_loss_kwh = Decimal(0)
        self._battery_loss_cost = Decimal(0)
        self._battery_loss_forgone = Decimal(0)
        self._shares.forget_losses()
        # The measurement underneath carries on - anchor, published amount and the
        # hold's window alike. Re-anchoring would publish nothing for a day, and
        # forgetting what was published would publish the same loss twice.
        self._raw.clear()
        self._raw_import.clear()
        self._draws.clear()
        self._retained.clear()
        # Debt outlives nothing: it is a claim against buckets that no longer
        # contribute to any total, and repaying it after the rebase would move
        # value between figures that no longer share a baseline. A carried
        # balance is a claim on the same buckets, and goes for the same reason.
        self._debts = DebtLedger(expiry=self._max_quiet_span)
        self._balance = HouseBalance(
            expiry=self._max_quiet_span, charge_source=self._charge_source
        )

    @property
    def nesting(self) -> Mapping[str, str]:
        """Which device sits inside which, child to parent, as it was last set.

        Readable because the hierarchy decides more than the arithmetic: a circuit
        published at what it used *itself* reads lower than the clamp measuring it,
        and whatever shows that figure has to be able to say why.

        Returned as a mapping rather than the dictionary itself, so a reader
        cannot rewrite the hierarchy the netting depends on.
        """
        return MappingProxyType(self._upstream)

    def set_nesting(self, nested_devices: Mapping[str, str]) -> None:
        """Replaces which device contains which, without disturbing anything else.

        A household can re-wire their hierarchy in the Energy Dashboard at any
        moment, and the mirror tells the engine as soon as they do. Rebuilding
        the accountant to take the new map would be the easy way and the wrong
        one: it would discard the battery's stored-cost ledger, the open buckets
        and the retained ring along with the old hierarchy, turning a config
        edit into lost accounting (ADR-0021).

        Netting is applied per bucket at finalise time rather than held as
        state, so the map is all there is to replace.

        A carry belongs to a link that existed. Dropping the carries of devices
        that are no longer parents is what stops a hierarchy the household has
        deleted from going on suppressing a device - the orphan state this must
        not be able to leave behind (HEA-168).
        """
        self._upstream = dict(nested_devices)
        self._children = {}
        for child, parent in self._upstream.items():
            self._children.setdefault(parent, []).append(child)
        self._nesting_carry = {
            device: owed
            for device, owed in self._nesting_carry.items()
            if device in self._children
        }

    def snapshot(self) -> dict[str, Any]:
        """Everything the engine has learned, for carrying across a restart.

        Where each counter stands, what the battery holds, which buckets are
        open, and what is owed to whom. Anything derivable from the config entry
        is absent: it is rebuilt on every setup, and restoring it would let a
        stale snapshot override a household's reconfiguration.

        Plain JSON-safe primitives, every ``Decimal`` a string. The integration
        layer owns the file and the staleness rule.
        """
        return {
            "sources": {
                entity: source.persisted_state()
                for entity, source in self._sources.items()
            },
            "raw": [
                {
                    "at": start.isoformat(),
                    "roles": {role.value: str(kwh) for role, kwh in roles.items()},
                }
                for start, roles in self._raw.items()
            ],
            "raw_import": [
                {
                    "at": start.isoformat(),
                    "meters": {meter: str(kwh) for meter, kwh in meters.items()},
                }
                for start, meters in self._raw_import.items()
            ],
            "draws": [
                {
                    "at": start.isoformat(),
                    "devices": {device: str(kwh) for device, kwh in devices.items()},
                }
                for start, devices in self._draws.items()
            ],
            "import_prices": [
                {
                    "meter": meter,
                    "prices": [
                        {"at": when.isoformat(), "price": str(price)}
                        for when, price in series
                    ],
                }
                for meter, series in self._prices.items()
            ],
            # Persisted for the same reason the import price is: a restart that
            # lost it would value the generation served before the household's
            # export sensor next reports at nothing, and book a forgone figure
            # of zero against energy that really gave something up (ADR-0026).
            "export_prices": [
                {"at": when.isoformat(), "price": str(price)}
                for when, price in self._export_prices
            ],
            "battery": self._battery.snapshot(),
            "balance_headroom": (
                None if self._balance_headroom is None else str(self._balance_headroom)
            ),
            # The loss measurement's own state. All of it persists: an anchor that
            # restarted would forgive whatever the level had not yet caught up, a
            # window that restarted would publish a peak it had kept out, and the
            # totals are published figures that cannot go backwards (ADR-0021).
            "battery_loss": {
                "anchor": (
                    None
                    if self._loss_anchor is None
                    else [
                        str(self._loss_anchor.headroom),
                        str(self._loss_anchor.available),
                        str(self._loss_anchor.charged),
                        str(self._loss_anchor.discharged),
                    ]
                ),
                "published": str(self._loss_published),
                "window": [
                    [moment.isoformat(), str(value)]
                    for moment, value in self._loss_window
                ],
                "kwh": str(self._battery_loss_kwh),
                "cost": str(self._battery_loss_cost),
                "forgone": str(self._battery_loss_forgone),
                "metered": [str(self._metered_charge), str(self._metered_discharge)],
                "refused": str(self._loss_refused_kwh),
            },
            # Each battery's meters, anchor and share, for the same reason: a share
            # is a published figure, and the split's anchor is the measurement's.
            "battery_shares": self._shares.snapshot(),
            "balance": self._balance.snapshot(),
            "debts": self._debts.snapshot(),
            # What a parent still owes its children. Carried for the same reason
            # the debts are: losing it would let the first buckets after a
            # restart book a double count the carry exists to remove (HEA-169).
            "nesting_carry": [
                {"device": device, "kwh": str(owed), "since": since.isoformat()}
                for device, (owed, since) in self._nesting_carry.items()
            ],
            "pending_bounds": [
                {
                    "device": bound.device,
                    "kwh": str(bound.kwh),
                    "buckets": [start.isoformat() for start in bound.buckets],
                }
                for bound in self._pending_bounds
            ],
            "held": [
                {
                    "device": held.device,
                    "at": held.at.isoformat(),
                    "energy_kwh": str(held.energy_kwh),
                    "actual_cost": str(held.actual_cost),
                    "naive_cost": str(held.naive_cost),
                    "cost_savings": str(held.cost_savings),
                    "battery_savings": str(held.battery_savings),
                    "forgone_prices": _dump_by_source(held.forgone_prices),
                    "by_source": _dump_by_source(held.by_source),
                }
                for held in self._held
            ],
            "running": {
                device: _dump_running(running)
                for device, running in self._running.items()
            },
            "house": _dump_running(self._house),
            "retained": [
                {
                    "at": start.isoformat(),
                    "consumption": str(bucket.consumption),
                    "blended": str(bucket.blended),
                    "import_price": str(bucket.import_price),
                    "battery_price": str(bucket.battery_price),
                    "forgone_prices": _dump_by_source(bucket.forgone_prices),
                    "draw": str(bucket.draw),
                    "sources": _dump_by_source(bucket.sources),
                }
                for start, bucket in self._retained.items()
            ],
            "watermark": (
                None if self._watermark is None else self._watermark.isoformat()
            ),
            "window": [
                {
                    "consumption": str(bucket.consumption),
                    "claimed": {
                        device: str(kwh) for device, kwh in bucket.claimed.items()
                    },
                    "start": None if bucket.start is None else bucket.start.isoformat(),
                }
                for bucket in self._window
            ],
            "implausible": sorted(self._implausible),
        }

    def restore(self, data: Mapping[str, Any]) -> None:
        """Reinstates a snapshot taken by :meth:`snapshot`.

        Applied to a freshly configured accountant, so only what the engine
        learned is written over.

        Anything held for a device no longer configured is dropped: its counter
        position, running totals, share of an open bucket, and any correction it
        was owed. The device stays deleted, and its energy stays with the
        Untracked remainder, which keeps the split reconciling.
        """
        tracked = set(self._entity_of)
        known = set(self._role_of) | set(self._device_of)
        for entity, source_data in data["sources"].items():
            if entity not in known:
                continue
            source = CumulativeEnergySource(max_quiet_span=self._max_quiet_span)
            source.restore(source_data)
            self._sources[entity] = source

        self._raw = {
            datetime.fromisoformat(bucket["at"]): {
                SourceRole(role): Decimal(kwh) for role, kwh in bucket["roles"].items()
            }
            for bucket in data["raw"]
        }
        # Absent before import was kept meter by meter. An interval left open
        # then has nothing to weight its registers by, and is priced at their
        # average, which for a single register is its own rate.
        self._raw_import = {
            datetime.fromisoformat(bucket["at"]): {
                meter: Decimal(kwh) for meter, kwh in bucket["meters"].items()
            }
            for bucket in data.get("raw_import", [])
        }
        self._draws = {
            datetime.fromisoformat(bucket["at"]): {
                device: Decimal(kwh)
                for device, kwh in bucket["devices"].items()
                if device in tracked
            }
            for bucket in data["draws"]
        }
        # One list before each register had its own, and every household then had
        # one register, so the list is that register's.
        registers = data.get("import_prices") or [
            {"meter": self._import_entity, "prices": data["prices"]}
        ]
        importing = set(self._meters_of.get(SourceRole.GRID_IMPORT, ()))
        self._prices = {
            register["meter"]: [
                (datetime.fromisoformat(entry["at"]), Decimal(entry["price"]))
                for entry in register["prices"]
            ]
            for register in registers
            if register["meter"] in importing or register["meter"] is None
        }
        # Absent from a snapshot written before this existed, which is every
        # installed household's on the release that adds it - see `_load_running`.
        self._export_prices = [
            (datetime.fromisoformat(entry["at"]), Decimal(entry["price"]))
            for entry in data.get("export_prices", [])
        ]
        self._battery.restore(data["battery"])
        # Absent before this ceiling existed - see the ledger's own restore.
        headroom = data.get("balance_headroom")
        self._balance_headroom = None if headroom is None else Decimal(headroom)
        loss = data.get("battery_loss", {})
        self._battery_loss_kwh = Decimal(loss.get("kwh", "0"))
        self._battery_loss_cost = Decimal(loss.get("cost", "0"))
        # Absent before a loss published what it could have earned (HEA-229).
        self._battery_loss_forgone = Decimal(loss.get("forgone", "0"))
        metered = loss.get("metered")
        if metered is not None:
            self._metered_charge = Decimal(metered[0])
            self._metered_discharge = Decimal(metered[1])
        # Absent where measuring never began, and from a snapshot that measured
        # span by span, whose state cannot be turned into a running total. Either
        # way the anchor is taken at the next tick, which the coordinator runs
        # within seconds of startup, so nobody waits for a starting point they
        # are never given (HEA-206) - the cost is a day's hold before anything is
        # published.
        anchor = loss.get("anchor")
        self._loss_anchor = (
            None if anchor is None else _LossAnchor(*(Decimal(part) for part in anchor))
        )
        # Absent from a snapshot written before batteries were told apart. The
        # pool's measurement above carries on regardless, and the split anchors at
        # the next tick (ADR-0031).
        self._shares.restore(data.get("battery_shares", {}))
        self._loss_published = Decimal(loss.get("published", "0"))
        self._loss_window = deque(
            (datetime.fromisoformat(moment), Decimal(value))
            for moment, value in loss.get("window", [])
        )
        self._loss_refused_kwh = Decimal(loss.get("refused", "0"))
        # A snapshot taken before the carries existed simply has none to restore.
        self._balance.restore(data.get("balance", {}))
        self._debts.restore(data["debts"])
        # Filtered by `tracked` like every other per-device figure here: a
        # device the household removed while the host was down must not have a
        # carry restored against it.
        self._nesting_carry = {
            entry["device"]: (
                Decimal(entry["kwh"]),
                datetime.fromisoformat(entry["since"]),
            )
            for entry in data.get("nesting_carry", [])
            if entry["device"] in tracked
        }
        self._pending_bounds = [
            _PendingBound(
                device=bound["device"],
                kwh=Decimal(bound["kwh"]),
                buckets=tuple(
                    datetime.fromisoformat(start) for start in bound["buckets"]
                ),
            )
            for bound in data["pending_bounds"]
            if bound["device"] in tracked
        ]
        self._held = [
            _HeldCorrection(
                device=held["device"],
                at=datetime.fromisoformat(held["at"]),
                energy_kwh=Decimal(held["energy_kwh"]),
                actual_cost=Decimal(held["actual_cost"]),
                naive_cost=Decimal(held["naive_cost"]),
                cost_savings=Decimal(held["cost_savings"]),
                # Absent before this figure existed - see `_load_running`.
                battery_savings=Decimal(held.get("battery_savings", 0)),
                # Empty on a snapshot written before these were tracked, which
                # values that correction's generation at nothing - the honest
                # answer, since nobody recorded what it gave up.
                forgone_prices=_load_by_source(held.get("forgone_prices", {})),
                by_source=_load_by_source(held["by_source"]),
            )
            for held in data["held"]
            if held["device"] in tracked
        ]
        self._running = {
            device: _load_running(running)
            for device, running in data["running"].items()
            if device in tracked
        }
        self._house = _load_running(data["house"])
        self._retained = {
            datetime.fromisoformat(bucket["at"]): _RetainedBucket(
                consumption=Decimal(bucket["consumption"]),
                blended=Decimal(bucket["blended"]),
                import_price=Decimal(bucket["import_price"]),
                # Absent before this figure existed - see `_load_running`.
                battery_price=Decimal(bucket.get("battery_price", 0)),
                forgone_prices=_load_by_source(bucket.get("forgone_prices", {})),
                draw=Decimal(bucket["draw"]),
                sources=_load_by_source(bucket["sources"]),
            )
            for bucket in data["retained"]
        }
        watermark = data["watermark"]
        self._watermark = (
            None if watermark is None else datetime.fromisoformat(watermark)
        )
        self._window = deque(
            (
                _WindowBucket(
                    consumption=Decimal(bucket["consumption"]),
                    claimed={
                        device: Decimal(kwh)
                        for device, kwh in bucket["claimed"].items()
                    },
                    # Absent from a snapshot written before HEA-225; such a
                    # window falls back to the newest entry until it refreshes.
                    start=(
                        None
                        if bucket.get("start") is None
                        else datetime.fromisoformat(bucket["start"])
                    ),
                )
                for bucket in data["window"]
            ),
            maxlen=_PLAUSIBILITY_WINDOW,
        )
        self._implausible = frozenset(data["implausible"])

    def totals(self) -> Totals:
        """Returns the since-startup running totals per device, home and Untracked.

        Untracked is derived from the whole-home total minus the tracked devices,
        so the split reconciles exactly however late corrections have moved value.
        """
        devices = {device: run.snapshot() for device, run in self._running.items()}
        whole_home = self._house.snapshot()
        battery = self._battery_totals()
        untracked = self._derive_untracked(whole_home, [*devices.values(), battery])
        # Bounds are the one figure the household total does not accumulate. The
        # remainder is priced within its own slice, so it carries no doubt, and a
        # late correction moves value out of it long after the slice closed -
        # accumulating a bound alongside would drift from the figure it bounds.
        # Composing it from the parts keeps it exact however value has moved.
        bounded = _sum(d.cost_floor for d in devices.values()) + untracked.actual_cost
        capped = _sum(d.cost_ceiling for d in devices.values()) + untracked.actual_cost
        # The battery's losses hang off the house and off nothing else: they are
        # a property of the household's storage, not a share of any bucket, so
        # they are attached here rather than accumulated through the allocation
        # (HEA-174). Untracked is derived before this and so carries zero, which
        # is right - it is a remainder of allocated energy, and this was never
        # allocated.
        return Totals(
            devices=devices,
            untracked=untracked,
            battery=battery,
            whole_home=replace(whole_home, cost_floor=bounded, cost_ceiling=capped),
            unreconciled_kwh=self.unreconciled_energy(),
            batteries=self._battery_shares(),
        )

    def _battery_totals(self) -> DeviceTotals:
        """The battery as the consumer it is: what it lost, and what that cost.

        Measured against what the battery's level actually did, so this is a
        round-trip loss rather than the ledger's write-down - the two are not the
        same thing, and reporting the second as the first is what HEA-182 was
        raised about.
        """
        return _loss_totals(
            BatteryLoss(
                self._battery_loss_kwh,
                self._battery_loss_cost,
                self._battery_loss_forgone,
            )
        )

    def _battery_shares(self) -> dict[str, DeviceTotals]:
        """Each battery's share of that, built the same way (ADR-0031)."""
        return {
            battery: _loss_totals(loss)
            for battery, loss in self._shares.losses().items()
        }

    @staticmethod
    def _derive_untracked(
        whole_home: DeviceTotals, devices: Iterable[DeviceTotals]
    ) -> DeviceTotals:
        tracked = list(devices)
        energy = _sum(d.energy_kwh for d in tracked)
        actual = _sum(d.actual_cost for d in tracked)
        naive = _sum(d.naive_cost for d in tracked)
        savings = _sum(d.cost_savings for d in tracked)
        battery_savings = _sum(d.battery_savings for d in tracked)
        grid = _sum(d.energy_from_grid for d in tracked)
        generation = _sum(d.energy_from_generation for d in tracked)
        battery = _sum(d.energy_from_battery for d in tracked)
        forgone = _sum(d.forgone_export for d in tracked)
        return DeviceTotals(
            energy_kwh=whole_home.energy_kwh - energy,
            actual_cost=whole_home.actual_cost - actual,
            naive_cost=whole_home.naive_cost - naive,
            cost_savings=whole_home.cost_savings - savings,
            battery_savings=whole_home.battery_savings - battery_savings,
            energy_from_grid=whole_home.energy_from_grid - grid,
            energy_from_generation=whole_home.energy_from_generation - generation,
            energy_from_battery=whole_home.energy_from_battery - battery,
            # The remainder is derived slice by slice from meters that reported
            # for that slice, so unlike a coarse counter it has no span to be
            # uncertain about: its cost is its own bound.
            cost_floor=whole_home.actual_cost - actual,
            cost_ceiling=whole_home.actual_cost - actual,
            forgone_export=whole_home.forgone_export - forgone,
        )

    def balance_diagnostics(self) -> dict[str, str]:
        """House energy still waiting for the counterpart that explains it.

        A household whose figures run above their own meter is either being
        told the truth about coarse counters or is meeting a bug; without these
        two, the download cannot tell one from the other (HEA-133).
        """
        return self._balance.diagnostics()

    def reconcile_battery(
        self,
        available_kwh: Decimal,
        now: datetime,
        levels: Mapping[str, Decimal] | None = None,
    ) -> None:
        """Write the ledger down to what the battery holds.

        `available_kwh` is the pool's contents. `levels` is each battery's own,
        which adds up to it, and is what each battery's share of a loss is
        measured against (ADR-0031); a caller with one battery may leave it out.

        The inventory is inferred from the charge and discharge meters, so
        anything that leaves the battery another way - round-trip losses, a
        discharge the configured meter does not count - stays on the books for
        ever and stops the drain-to-empty that is its only self-correction
        (HEA-178). Correcting it is what keeps discharge priced against energy
        the battery really holds.

        **Nothing here reaches the household's totals.** The write-down says what
        was wrongly on the books; it cannot say why. Two causes reach it and they
        want opposite treatment: a round-trip loss is energy the household paid
        for and never got back, while a discharge the meter missed reached the
        house and was billed there already. Publishing both as consumption
        double-counts the second, and on a battery carrying months of drift it
        does so all at once - the reference instance ran at four times its own
        house meter for hours (HEA-182).

        So the correction stays inside the ledger, where it fixes pricing without
        inventing energy. What the battery *lost* is a separate figure, measured
        here against what its level actually did (HEA-182).
        """
        self._levels = dict(levels or {})
        self._battery.reconcile(available_kwh, ceiling=self._loss_ceiling())
        self._measure_the_batterys_loss(available_kwh, now)

    def _measure_the_batterys_loss(self, available_kwh: Decimal, now: datetime) -> None:
        """Book what the battery took in and never gave back.

        `import + generation - export - house` is, by physics, whatever the
        battery gained plus whatever was lost inside it - which is why
        `_balance_headroom` accumulates it. Knowing how full the battery is
        supplies the gain, so the remainder is the loss. Both halves come from
        meters, so nothing here assumes an efficiency.

        **The first call only anchors, against what has accumulated so far.** On
        a household who fill their battery level in after the integration has
        been running, the headroom behind them is history nobody measured, and
        publishing it as one loss is the fault HEA-182 was raised to stop arriving
        by the other door. On a fresh install nothing has accumulated, so the
        anchor is zero and the first interval is measurable like any other.

        **Running totals, not spans.** Meters tick at different moments and a
        level is a coarse percentage, so any one span can measure less loss than
        nothing, or more than there was. Totals from a fixed anchor let that noise
        cancel instead of rectifying into a standing overstatement, which is the
        whole subject of ADR-0015 - and the one place it went wrong, a bound
        floored span by span, let through three times what the meters allowed
        (HEA-211).

        **Published a day late, and only what held all day.** Both totals
        subtract the level's gain, and the level is an estimate that drifts and
        corrects itself. Published as soon as the meters allowed it, the peak of
        that drift stayed in a figure that only counts upwards (HEA-213). So the
        figure published is the least the lower total has read over the last
        `_LOSS_HOLD`, which a drift lasting less than that cannot reach.

        Measurable only where the household meters enough for the headroom to
        exist at all - a house-consumption meter and metered generation. Without
        those there is no gain to subtract and no figure is published.
        """
        if self._balance_headroom is None:
            # Nothing has been priced yet, so there is nothing accumulated to
            # measure against - and zero is what the anchor should hold rather
            # than nothing at all. The headroom is set per priced interval and an
            # interval where nothing moved is never priced, so it does not exist
            # until something moves, and the interval that brings it into
            # existence is already inside it. Waiting for it meant the anchor
            # landed one interval late and that interval's loss was never
            # published (HEA-199). Kept current while the headroom is still
            # absent, so the anchor holds the level just before the first one.
            self._anchor_the_loss(Decimal(0), available_kwh, now)
            return
        if self._loss_anchor is None:
            self._anchor_the_loss(self._balance_headroom, available_kwh, now)
            return
        if not self._shares.anchored:
            # A snapshot from before batteries were told apart: the pool's
            # measurement carries on, and the split starts from here.
            self._shares.anchor(self._levels)

        claimed, allowed = self._loss_since_the_anchor(
            self._loss_anchor, self._balance_headroom, available_kwh
        )
        self._loss_refused_kwh = max(Decimal(0), claimed - allowed)
        self._loss_last_totals = (claimed, allowed)
        held = self._held_through_the_hold(min(claimed, allowed), now)
        if held > self._loss_published:
            self._publish_the_loss(held - self._loss_published)

    def _anchor_the_loss(
        self, headroom: Decimal, available_kwh: Decimal, now: datetime
    ) -> None:
        self._loss_anchor = _LossAnchor(
            headroom=headroom,
            available=available_kwh,
            charged=self._metered_charge,
            discharged=self._metered_discharge,
        )
        self._loss_published = Decimal(0)
        self._loss_last_totals = (Decimal(0), Decimal(0))
        self._shares.anchor(self._levels)
        # Nothing measured yet reads as zero, so the hold starts here: a total
        # cannot have stood above zero for a day until a day has passed.
        self._loss_window = deque([(now, Decimal(0))])

    def _loss_since_the_anchor(
        self, anchor: _LossAnchor, headroom: Decimal, available_kwh: Decimal
    ) -> tuple[Decimal, Decimal]:
        """What the house's meters claim was lost, and what the battery's allow.

        The claim is what the house's meters cannot explain, less what the level
        gained. It is a residual of four meters and inherits every disagreement
        between them - a household whose generation is metered on the far side of
        their inverter saw four times what their battery could have lost
        (HEA-196, GitHub 34).

        The allowance is the battery's own: energy in has to go somewhere, so
        `charge = discharge + gain + loss` and the loss cannot exceed
        `charge - discharge - gain`. Every term is metered, so it assumes nothing
        about the hardware.

        **Each is a bound on the other, not the figure itself.** Where a discharge
        meter counts only what reached the house, the allowance is loose by
        whatever it missed - the fault HEA-182 exists for. Taking the lower of the
        two keeps both faults out: the claim refuses a discharge the meter missed,
        and the allowance refuses a disagreement between the house's own meters.
        """
        gained = available_kwh - anchor.available
        claimed = headroom - anchor.headroom - gained
        carried = (self._metered_charge - anchor.charged) - (
            self._metered_discharge - anchor.discharged
        )
        return claimed, carried - gained

    def _held_through_the_hold(self, total: Decimal, now: datetime) -> Decimal:
        """The least `total` has read since `_LOSS_HOLD` ago.

        A sliding minimum. An entry the new value is no higher than can never be
        the least again, so it goes - and the new value takes its moment, because
        over any window reaching back past that moment the new value is the lower.
        Entries that have left the window go too, keeping the last one that took
        effect before it opened: that value held at the window's start.
        """
        since = now
        while self._loss_window and self._loss_window[-1][1] >= total:
            since = self._loss_window.pop()[0]
        self._loss_window.append((since, total))
        opened = now - _LOSS_HOLD
        while len(self._loss_window) > 1 and self._loss_window[1][0] <= opened:
            self._loss_window.popleft()
        return self._loss_window[0][1]

    def _publish_the_loss(self, lost: Decimal) -> None:
        """Take `lost` out of the ledger and into the household's figures.

        Taken out of the ledger because it really has left the battery, and
        priced at what it cost to put there - the blend of every charge still on
        the books, which is the only price this energy ever had.

        What it could have earned comes out at the same blend: sunshine stored
        instead of exported carried the export it gave up, and lost to heat it
        was given up for nothing. Grid charge carried none (ADR-0027, HEA-229).
        Added to the whole home beside the loss's energy and cost, so the parts
        still add up to it with Untracked unmoved.
        """
        self._loss_published += lost
        withdrawn = self._battery.discharge(lost)
        loss = BatteryLoss(lost, withdrawn.cost, withdrawn.forgone)
        self._battery_loss_kwh += loss.kwh
        self._battery_loss_cost += loss.cost
        self._battery_loss_forgone += loss.forgone
        self._shares.apportion(loss, self._levels)
        self._house.energy_kwh += loss.kwh
        self._house.actual_cost += loss.cost
        self._house.naive_cost += loss.cost
        self._house.forgone_export += loss.forgone

    @staticmethod
    def _cheapest_spread(
        kwh: Decimal,
        slices: list[tuple[Decimal, Decimal]],
        *,
        dearest: bool,
    ) -> Decimal:
        """The cheapest - or dearest - way this energy can have been spread.

        Each slice is its blended price and what the house consumed in it, and a
        slice cannot have supplied more than that. So the bound is over *feasible*
        distributions rather than over slices: filling the cheapest slices first,
        to their capacity, is the cheapest arrangement there is, and filling the
        dearest first is the most expensive (HEA-197).

        Pricing the whole step at one slice's blend, as this did before, claims a
        distribution the allocation itself excludes - it spreads a step in
        proportion to what each slice consumed, so a thin slice never receives the
        lot. Measured on a counter reporting hourly, so twelve slices to a step,
        the old floor came to 6% of the figure it bracketed.

        Where the slices cannot hold it all, the excess is priced at the extreme,
        which is what this did throughout before. A household whose devices report
        more energy than their house meter is in that position by metering
        disagreement rather than by physics (ADR-0015), and a bound is the wrong
        place to adjudicate it.
        """
        ordered = sorted(slices, key=lambda entry: entry[0], reverse=dearest)
        total = Decimal(0)
        remaining = kwh
        for blended, capacity in ordered:
            took = min(remaining, max(Decimal(0), capacity))
            total += took * blended
            remaining -= took
            if remaining <= 0:
                return total
        # Still energy to place, so every slice is full. The favourable extreme is
        # the first in this order, which keeps the figure a bound either way.
        return total + remaining * ordered[0][0]

    def _loss_ceiling(self) -> Decimal | None:
        """The most the battery can still honestly be said to have lost.

        What the house's own meters cannot account for, less what has already
        been written off against it. ``None`` where the household does not meter
        enough for the question to be asked, in which case nothing is capped.
        """
        if self._balance_headroom is None:
            return None
        written_off, _ = self._battery.losses
        return max(Decimal(0), self._balance_headroom - written_off)

    def battery_losses(self) -> tuple[Decimal, Decimal]:
        """Energy the battery never gave back, and what it cost (HEA-174)."""
        return self._battery.losses

    def battery_diagnostics(self) -> dict[str, Any]:
        """What the stored-cost ledger holds, for the diagnostics download.

        Discharge is priced from this and from nothing else, so without it a
        discharge costed below the import rate cannot be explained from the
        download alone.

        `meter_disagreement` carries the sentence that says what it is beside the
        figure, because it is the only place a household's meter disagreement is
        visible at all (HEA-200) and a bare number named for a mechanism told
        nobody what it meant. `loss` is where the battery's loss measurement
        stands, or ``None`` where nothing is being measured (HEA-212).
        `batteries`, where there are two or more, is each battery's own meters,
        bound and share of that loss (ADR-0031).
        """
        diagnostics = self._battery.diagnostics() | {
            "meter_disagreement": {
                "kwh": str(self._loss_refused_kwh),
                "means": _METER_DISAGREEMENT_MEANS,
            },
            "loss": self._loss_diagnostics(),
        }
        if self._shares.splits:
            diagnostics["batteries"] = self._shares.diagnostics(self._levels)
        return diagnostics

    def _loss_diagnostics(self) -> dict[str, Any] | None:
        """Every figure the published loss is read from, in one place.

        Where measuring began, what the house meters claim and the battery's
        meters allow since, what has been published, and the least the lower of
        the two has read across the hold - which is what the next publication
        can reach - with the moment it took that value.
        """
        anchor = self._loss_anchor
        if anchor is None:
            return None
        claimed, allowed = self._loss_last_totals or (None, None)
        held_since, held = self._loss_window[0] if self._loss_window else (None, None)
        return {
            "anchor": {
                "headroom_kwh": str(anchor.headroom),
                "available_kwh": str(anchor.available),
                "charged_kwh": str(anchor.charged),
                "discharged_kwh": str(anchor.discharged),
            },
            "claimed_kwh": None if claimed is None else str(claimed),
            "allowed_kwh": None if allowed is None else str(allowed),
            "published_kwh": str(self._loss_published),
            "held_kwh": None if held is None else str(held),
            "held_since": None if held_since is None else held_since.isoformat(),
        }

    def source_diagnostics(self) -> dict[str, SourceSnapshot]:
        """Per-source accumulator state and decision log, keyed by entity id.

        Feeds the diagnostics download (HEA-24): every meter the runtime has
        observed - house-level and per-device - with its last reading and the
        gating decisions that explain its accounting.
        """
        return {entity: source.snapshot() for entity, source in self._sources.items()}

    def settled_until(self) -> datetime | None:
        """The instant up to which every figure is complete, or ``None``.

        An interval closes on the lateness margin, so at any moment the most
        recent twenty minutes or so are still accruing: energy for them has been
        counted, and more of it is still expected. A card drawing that alongside
        Home Assistant's own hourly figures shows a short bar with nothing to
        say why, which is how it reached us (HEA-140, GitHub #20).

        The *end* of the last closed interval, not its start: the household's
        figures are complete up to that instant and provisional after it.
        """
        if self._watermark is None:
            return None
        return self._watermark + BUCKET

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

    def _spread_source(
        self,
        entity_id: str,
        role: SourceRole,
        delta: EnergyDelta,
        source: CumulativeEnergySource,
    ) -> None:
        """Place a house meter's energy in the intervals it accrued across.

        A portion for an interval still open joins it. One for an interval that
        has closed corrects it where the retained ring still holds it, exactly as
        a late device portion does - the ring is 24 hours deep and a house meter
        that goes quiet for a night falls well inside it.

        ADR-0006 recorded dropping these silently, on the grounds that house
        meters report too often for a delta to cross the watermark. A cloud-polled
        inverter breaks that: one household's generation meter revealed seventeen
        hours at once and 2.17 kWh of 2.2 was discarded, in the direction that
        puts a household's total *below* their own meter (HEA-186). That ADR set
        "revisit if evidence shows otherwise" as the trigger, and this is it.
        """
        for portion in spread_energy(delta):
            if not self._is_finalised(portion.start):
                bucket = self._raw.setdefault(portion.start, {})
                bucket[role] = bucket.get(role, Decimal(0)) + portion.kwh
                if role is SourceRole.GRID_IMPORT:
                    meters = self._raw_import.setdefault(portion.start, {})
                    meters[entity_id] = meters.get(entity_id, Decimal(0)) + portion.kwh
            elif (kind := _RAISES_CONSUMPTION.get(role)) is None:
                # Export and charge subtract, and a finalised bucket's published
                # figure never falls. Their carries settle them forward instead.
                continue
            elif (retained := self._retained.get(portion.start)) is not None:
                self._correct_house(kind, retained, portion.kwh)
            else:
                source.note_dropped_late(portion.start, portion.kwh)

    def _correct_house(
        self, kind: SourceKind, retained: _RetainedBucket, kwh: Decimal
    ) -> None:
        """Add energy a house meter reported late to the interval it served.

        The household really used it, so the whole-home total rises. No device
        claimed it, and Untracked is derived by subtraction (ADR-0006 decision 3),
        so the remainder absorbs exactly this much and no device's published
        figure moves - which is what lets this be a closed form rather than a
        re-run of the bucket's allocation.

        What it *cost* follows the source, not the bucket's blend. Energy off the
        grid is charged at the import price the bucket settled at; generation was
        free then and is free now; a discharge is charged what that interval's
        battery energy cost. The counterfactual is the import price either way,
        so late generation shows up as saving rather than as spending.
        """
        actual = kwh * _MARGINAL_PRICE_OF[kind](retained)
        naive = kwh * retained.import_price
        self._house.energy_kwh += kwh
        self._house.add_by_source({kind: kwh}, retained.forgone_prices)
        self._house.actual_cost += actual
        self._house.naive_cost += naive
        self._house.cost_savings += naive - actual
        # So a further late portion for the same interval sees the headroom this
        # one created, rather than funding itself against a stale figure.
        retained.consumption += kwh

    def _spread_device(
        self, device: str, delta: EnergyDelta, source: CumulativeEnergySource
    ) -> None:
        if not self._within_the_house(delta):
            # Refused, but still *claimed*. What the source said is evidence
            # whether or not it was booked, and `_judge` is what turns a run of
            # these into a Repair that names the device (HEA-60). Dropping the
            # claim here would make a counter that lies steadily silently
            # uncounted instead of reported - the failure this guard exists to
            # prevent, reintroduced one layer down.
            self._claim(device, delta.kwh)
            source.note_beyond_the_house(delta.end, delta.kwh)
            return
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

    def _within_the_house(self, delta: EnergyDelta) -> bool:
        """Whether one delta claims less energy than the house was served.

        A device cannot draw more than the whole house, which is ADR-0002's
        invariant - but `_judge` can only apply it to a device's *total* across a
        full window, so a single enormous delta lands long before that verdict
        arrives. That is how a rescaled counter's reset credit booked 119 kWh to
        a water heater (HEA-157).

        The span is floored at one plausibility window, and that floor is the
        whole design rather than a detail. A coarse counter's step legitimately
        exceeds what the house was metered in the seconds it was reported over -
        the spreading approximation ADR-0006 is built on - so judged over its own
        span every ordinary reading would be refused. Over an hour the artefact
        cancels; a rescale does not. It is the same reasoning, and the same
        constant, as `_PLAUSIBILITY_WINDOW`.

        Measured over the span rather than extrapolated from a rate: an EV
        charger quiet while the house drew heavily, then honest about all of it
        at once, would be refused if it were judged against an idle hour. The
        house meter saw the same span the device did, so it is asked about that
        span.

        Three ways it declines to judge, each erring towards booking:
        before the window has filled, because a fresh start condemns nothing on
        one interval's evidence; where the house metered nothing, because a
        silent meter is its own fault and no evidence against a device; and
        where the span reaches past what is still retained, because a source
        silent for three days really did meter those three days and there is
        nothing left to compare it with. In that last case `CREDIBLE_POWER_KW`
        stands alone, which is the case it was written for.
        """
        if len(self._window) < _PLAUSIBILITY_WINDOW:
            return True
        served = self._served_between(delta.start, delta.end)
        return served is None or delta.kwh <= served

    def _served_between(self, start: datetime, end: datetime) -> Decimal | None:
        """What the house was metered as consuming over a span, or ``None``.

        ``None`` where the question cannot be answered: a bucket the span covers
        that is no longer retained, or a house that metered nothing at all.

        The span is widened to a full window before it is measured, never
        narrowed - a delta covering three hours is judged over its own three
        hours, and one covering twenty seconds over the hour ending when it did.
        """
        first = bucket_start(min(start, end - _PLAUSIBILITY_WINDOW * BUCKET))
        served = Decimal(0)
        moment = first
        last = bucket_start(end)
        while moment <= last:
            bucket = self._retained.get(moment)
            if bucket is None:
                # Either older than retention, or not yet finalised. Neither is
                # evidence, and neither may be read as the house using nothing.
                return None if moment < (self._watermark or moment) else served
            served += bucket.consumption
            moment += BUCKET
        return served or None

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
        self._claim(device, kwh, start)
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
        run.add_by_source(
            split_by_source(grew, retained.sources, retained.consumption),
            retained.forgone_prices,
        )
        funded_by_source = split_by_source(
            funded, retained.sources, retained.consumption
        )
        self._hold(
            _HeldCorrection(
                device=device,
                at=start,
                energy_kwh=funded,
                actual_cost=cost,
                naive_cost=funded * retained.import_price,
                cost_savings=funded * retained.import_price - cost,
                # Priced against *its own* bucket's battery, which is why the
                # retained bucket keeps that price. A correction settled at
                # today's stored cost would credit last night's cheap charge with
                # whatever the battery happens to hold now, and would drift the
                # two halves of Cost Savings apart by the size of every late
                # arrival - which on a coarse counter is most of its energy.
                battery_savings=funded_by_source.get(SourceKind.BATTERY, Decimal(0))
                * (retained.import_price - retained.battery_price),
                forgone_prices=retained.forgone_prices,
                by_source=funded_by_source,
            )
        )

        # `grew` is exactly the unfunded excess (`kwh - funded`), owed on the one
        # ledger both paths share. Its energy is published so the period still
        # reconciles; its money waits there until the debt settles.
        self._debts.owe(start, grew, grew * retained.import_price, {device: kwh})
        self._house.energy_kwh += grew
        self._house.add_by_source(
            split_by_source(grew, retained.sources, retained.consumption),
            retained.forgone_prices,
        )
        retained.draw += kwh

    def _finalize_bucket(self, start: datetime) -> None:
        self._note_zero_priced(start)
        raw = self._raw.pop(start, {})
        imported = self._raw_import.pop(start, {})
        claimed = self._draws.pop(start, {})
        served = self._decompose(raw, start)
        self._weigh_plausibility(served, claimed, start)
        draws = self._own_draws(self._believable(claimed, start), start)
        prices, sources, forgone_prices = self._price_sources(
            served, self._import_price(start, imported), start
        )
        bucket = IntervalBucket(start=start, sources=sources, device_draws=draws)
        allocation = self._strategy.allocate(bucket, prices)
        remainder = self._settle(start, allocation.untracked, draws, sources, prices)
        for device, share in allocation.devices.items():
            self._running.setdefault(device, _Running()).add(share, forgone_prices)
        for share in allocation.devices.values():
            self._house.add(share, forgone_prices)
        self._house.add(remainder, forgone_prices)
        # After the remainder has been banked, so the budget it funds is real.
        self._release_held(remainder, start)
        self._retain(start, sources, prices, draws, forgone_prices)
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
            # Neither saving constrains what a correction can afford: both are
            # derived from the money above, and `_affordable` weighs only what a
            # bucket actually has to hand over.
            cost_savings=Decimal(0),
            battery_savings=Decimal(0),
            # The budget is weighed, never attributed, so no rate applies to it.
            forgone_prices={},
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
            run.battery_savings += paid.battery_savings
            run.add_by_source(paid.by_source, paid.forgone_prices)
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
            run.battery_savings += held.battery_savings
            run.add_by_source(held.by_source, held.forgone_prices)

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
            slices = [
                (retained.blended, retained.consumption)
                for at in pending.buckets
                if (retained := self._retained.get(at)) is not None
            ]
            if not slices:
                continue
            floor = self._cheapest_spread(pending.kwh, slices, dearest=False)
            ceiling = self._cheapest_spread(pending.kwh, slices, dearest=True)
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
        self._release(settlement, _battery_share(sources, prices))
        return _withhold(remainder, settlement.kwh, blended, import_price, sources)

    def _release(
        self, settlement: Settlement, battery_share: Decimal = Decimal(0)
    ) -> None:
        """Publishes a suspended charge, now that its real price is known.

        The overdraw was never charged when it happened: pricing it at import was
        a guess, and publishing a guess means taking it back, which reads as an
        hour that cost less than nothing (HEA-85, ADR-0015 decision 5). It arrives
        here instead - at the repaying interval's blend, or at import if the debt
        expired unpaid.

        Actual and counterfactual move together. On expiry they are equal and the
        saving is untouched; on repayment their difference is the real saving the
        household made by having been served more cheaply than the grid.

        ``battery_share`` splits that saving the way the repaying bucket's own was
        split, because that is the bucket whose blend priced it - the same
        reasoning that makes the repayment happen at this blend rather than at the
        overdrawing bucket's. It defaults to nothing for the expiry paths, where
        actual and counterfactual are equal and there is no saving to divide. The
        withheld remainder gave its share up in ``_withhold``, so without this the
        household's battery saving would quietly shed the whole of every
        settlement while Cost Savings kept it (HEA-173).
        """
        for device, amount in settlement.actual.items():
            self._running.setdefault(device, _Running()).actual_cost += amount
            self._house.actual_cost += amount
        for device, amount in settlement.naive.items():
            run = self._running.setdefault(device, _Running())
            saving = amount - settlement.actual.get(device, Decimal(0))
            run.naive_cost += amount
            run.cost_savings += saving
            run.battery_savings += saving * battery_share
            self._house.naive_cost += amount
            self._house.cost_savings += saving
            self._house.battery_savings += saving * battery_share

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

    def refused_steps(self) -> frozenset[str]:
        """Inputs whose counter leapt, and whose step was refused (HEA-137).

        Read from each source's own decision log, so it says what the diagnostics
        download says. It clears itself once the refusal has aged out of that
        log: the energy was never booked, so nothing is left to put right, and
        what the household needs is to be told rather than chased.
        """
        return frozenset(
            entity
            for entity, source in self._sources.items()
            if any(
                decision.reason is DecisionReason.IMPLAUSIBLE_STEP
                for decision in source.snapshot().recent_decisions
            )
        )

    def last_reading_at(self) -> dict[str, datetime]:
        """When each input last produced a reading this engine could count.

        The question a household asks of a figure that has stopped moving, and the
        only one this engine can answer on its own: a counter it cannot count -
        unavailable, unit-less, refused - leaves no reading here, whatever its
        sensor is doing. That is the right reading of the word, because it is
        exactly the moment after which the figure could not have moved.

        Read straight from each source, so it says what the diagnostics download
        says, and it survives a restart because the position it comes from does.
        """
        return {
            entity: snapshot.last_at
            for entity, source in self._sources.items()
            if (snapshot := source.snapshot()).last_at is not None
        }

    def rescaled_sources(self) -> dict[str, ScaleChange]:
        """Inputs whose refused step looked like their scale moving (HEA-159).

        Read straight from each source, so it says what the diagnostics download
        says, and it empties itself the moment a counter reports something the
        house can account for again.
        """
        return {
            entity: snapshot.scale_change
            for entity, source in self._sources.items()
            if (snapshot := source.snapshot()).scale_change is not None
        }

    def _claim(self, device: str, kwh: Decimal, start: datetime | None = None) -> None:
        """Add late-arriving energy to the window, as evidence.

        Against the interval it belongs to, where that interval is still in the
        window, so the guard weighs a device against the house over the same
        stretch of time. Piling it all onto the newest interval instead weighed a
        two-hour step from a sparse counter against one hour of house, and
        condemned a pump that never drew more than the house did (HEA-225).

        A portion from before the window is left out of it: the window cannot
        weigh it against the house it was used in, and the step it came in has
        already been weighed over its whole span by `_within_the_house`. With no
        interval named - a step refused whole for leaving the house - it is
        evidence about the source now, and lands on the newest interval.

        Recorded even while the device is condemned, which is what lets an
        honest source earn its way back.
        """
        if not self._window:
            return
        entry = self._window_entry(start)
        if entry is None:
            return
        entry.claimed[device] = entry.claimed.get(device, Decimal(0)) + kwh

    def _window_entry(self, start: datetime | None) -> _WindowBucket | None:
        """The window entry for the interval at ``start``, if it is in the window.

        The newest entry where no interval is named, or where the window holds
        entries restored without one: the behaviour before intervals were kept,
        for the hour it takes such a window to refresh.
        """
        newest = self._window[-1]
        if start is None or self._window[0].start is None:
            return newest
        for entry in self._window:
            if entry.start == start:
                return entry
        return None if start < self._window[0].start else newest

    def _weigh_plausibility(
        self, served: Served, claimed: Mapping[str, Decimal], start: datetime
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
        if self._silent_meters:
            self._implausible = frozenset()
            return
        consumption = served.grid + served.generation + served.battery
        self._window.append(
            _WindowBucket(consumption=consumption, claimed=dict(claimed), start=start)
        )
        self._implausible = self._judge()

    def plausibility_evidence(self, device: str) -> tuple[Decimal, Decimal]:
        """What ``device`` claimed and what the house used, over the window weighed.

        The two figures the guard compared, for the Repair that names a device
        it set aside: concrete enough for a household to check against the
        sensor's own history, and to quote in a report (HEA-226).
        """
        claimed = _sum(
            bucket.claimed.get(device, Decimal(0)) for bucket in self._window
        )
        house = _sum(bucket.consumption for bucket in self._window)
        return claimed, house

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

    def _own_draws(
        self, draws: dict[str, Decimal], start: datetime
    ) -> dict[str, Decimal]:
        """Each device's draw less its direct children's, for a nested fleet.

        A clamp on a circuit measures everything downstream of it, so a tracked
        appliance on a tracked circuit sits inside both counters. Left alone the
        pair claims its energy twice, which inflates their share of every bucket
        and shrinks the remainder that is derived by subtracting them - the
        double count Home Assistant's own `included_in_stat` exists to remove.

        Each parent subtracts its **direct children's gross**, never their net.
        That is what makes it telescope: on breaker -> fuse -> plug -> appliance
        the intermediate terms cancel in pairs, so however deep the chain runs
        the devices still sum to the roots' own readings. Subtracting a child's
        *net* instead would leave the grandchild's energy counted twice, which
        looks almost right and is not, so the whole map is read before anything
        is written - no parent is ever netted against an already-netted child.

        Only children that were **booked** are subtracted. One condemned by the
        plausibility guard is absent from `draws`, and its energy really is in
        its parent's counter, so removing it would take away energy nobody
        counted. Skipping it keeps the two consistent.
        """
        if not self._children:
            return draws
        gross = dict(draws)
        return {
            device: self._own_draw(gross, device, kwh, start)
            for device, kwh in gross.items()
        }

    def _own_draw(
        self,
        gross: Mapping[str, Decimal],
        device: str,
        kwh: Decimal,
        start: datetime,
    ) -> Decimal:
        """One device's own draw, clamped at zero, carrying what it still owes.

        Over any span both meters have reported, a parent's counter is at least
        the sum of its children's - it physically contains them. **Inside one
        bucket it need not be.** A coarse child's step is spread evenly across
        the buckets it covered (ADR-0006) while the parent's own reading is not,
        so a bucket where the child's share exceeds the parent's is ordinary.

        Publishing the difference would put a *negative* draw into the
        allocation, and a negative draw takes a negative share of the bucket's
        cost - a household shown a circuit breaker that was paid to run. That is
        HEA-85's lesson, and it is why this clamps rather than subtracts freely.

        So the excess is carried and taken out of the bucket where the parent's
        counter catches up, which is ADR-0015's answer to the same disagreement
        between two streams sampled thousands of times apart. It expires on the
        same span for the same reason: a deficit caused by spreading clears
        within it, and one that does not is a hierarchy that is wrong rather
        than a reading that is late.

        The clock is deliberately **not** reset while a carry persists. A
        parent outrun every bucket is not catching up, and renewing its clock
        would let one wrong upstream link suppress a device indefinitely.
        """
        owed = self._owed_by(device, start)
        net = kwh - self._booked_children(gross, device) - owed
        if net < 0:
            since = self._nesting_carry.get(device, (Decimal(0), start))[1]
            self._nesting_carry[device] = (-net, since)
            return Decimal(0)
        self._nesting_carry.pop(device, None)
        return net

    def _owed_by(self, device: str, start: datetime) -> Decimal:
        """What this parent still owes its children, or zero once that expired."""
        carried = self._nesting_carry.get(device)
        if carried is None:
            return Decimal(0)
        owed, since = carried
        if start - since > self._max_quiet_span:
            del self._nesting_carry[device]
            return Decimal(0)
        return owed

    def _booked_children(self, gross: Mapping[str, Decimal], device: str) -> Decimal:
        """What this device's direct children drew, of those actually booked."""
        children = self._children.get(device, ())
        return sum(
            (gross[child] for child in children if child in gross),
            start=Decimal(0),
        )

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
        forgone_prices: Mapping[SourceKind, Decimal],
    ) -> None:
        consumption = _sum(sources.values())
        total_cost = _sum(energy * prices[kind] for kind, energy in sources.items())
        self._retained[start] = _RetainedBucket(
            consumption=consumption,
            blended=total_cost / consumption if consumption > 0 else Decimal(0),
            import_price=prices[SourceKind.IMPORT],
            battery_price=prices.get(SourceKind.BATTERY, Decimal(0)),
            forgone_prices=dict(forgone_prices),
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
        for series in self._prices.values():
            keep_from = 0
            for index, (when, _price) in enumerate(series):
                if when > self._watermark:
                    break
                keep_from = index
            if keep_from > 0:
                del series[:keep_from]

    def _note_zero_priced(self, start: datetime) -> None:
        """Log, once per import meter, that it closed an interval with no price.

        Attached to that meter's own decision log so diagnostics can explain the
        zero-cost early buckets, register by register. Logged a single time per
        cold-start: once a price is recorded the list never empties again (pruning
        keeps at least one), so this cannot re-fire.
        """
        for meter in self._meters_of.get(SourceRole.GRID_IMPORT, ()):
            if meter in self._cold_start_logged or self._prices.get(meter):
                continue
            source = self._sources.get(meter)
            if source is not None:
                source.note_zero_priced(start)
                self._cold_start_logged.add(meter)

    def _is_readable(self, *roles: SourceRole) -> bool:
        """Whether every named house input is configured and all its meters report.

        A role with several meters is readable only while every one of them is:
        half a household's generation booked as though it were all of it is
        worse than none, which is how a single silent meter is already treated.
        """
        return all(
            role in self._configured
            and self._silent_meters.isdisjoint(self._meters_of[role])
            for role in roles
        )

    def _decompose(self, raw: Mapping[SourceRole, Decimal], at: datetime) -> Served:
        # The branch follows what is *readable*, not merely what is configured.
        # A failed house meter otherwise reads as a zero, collapsing consumption
        # to grid + battery and discarding generation entirely - while the
        # household may well have the meters for the full-balance model (HEA-67).
        metered = self._is_readable(SourceRole.HOUSE_CONSUMPTION)
        readings = HouseReadings(
            imported=raw.get(SourceRole.GRID_IMPORT, Decimal(0)),
            exported=raw.get(SourceRole.GRID_EXPORT, Decimal(0)),
            generated=raw.get(SourceRole.GENERATION, Decimal(0)),
            charged=raw.get(SourceRole.BATTERY_CHARGE, Decimal(0)),
            discharged=raw.get(SourceRole.BATTERY_DISCHARGE, Decimal(0)),
            # Zero, not absent, when a readable house meter simply did not move:
            # a quiet house is a reading, and treating it as no meter at all
            # hands the interval to the full-balance branch, which books
            # generation the household in fact exported (HEA-67).
            house=raw.get(SourceRole.HOUSE_CONSUMPTION, Decimal(0))
            if metered
            else None,
            generation_metered=self._is_readable(
                SourceRole.GENERATION, SourceRole.GRID_EXPORT
            ),
        )
        self._account_for_the_balance(readings)
        return self._balance.decompose(readings, at)

    def _account_for_the_balance(self, readings: HouseReadings) -> None:
        """Keep what the house's own meters leave unexplained, as a ceiling.

        `import + generation - export - house` is, by physics, whatever the
        battery gained plus whatever was lost in it. So it is the most energy the
        battery can honestly be said to have lost, and it comes from meters that
        have nothing to do with the battery's own.

        That makes it the check on a discharge meter we cannot otherwise verify:
        one that counts only what reached the house leaves the battery's exports
        looking like losses, and this is what refuses to publish them as energy
        the household used. Only computable where the household meters all four,
        and skipped where they do not - a ceiling nobody can calculate is not a
        reason to refuse the figure underneath it.
        """
        if readings.house is None or not readings.generation_metered:
            return
        unexplained = (
            readings.imported + readings.generated - readings.exported - readings.house
        )
        self._balance_headroom = (self._balance_headroom or Decimal(0)) + unexplained

    def _price_sources(
        self, served: Served, price: Decimal, start: datetime
    ) -> tuple[
        dict[SourceKind, Decimal],
        dict[SourceKind, Decimal],
        dict[SourceKind, Decimal],
    ]:
        if served.grid_charge > 0:
            self._battery.charge_from_grid(served.grid_charge, price)
        if served.generation_charge > 0:
            # Stored with what it gave up, at the rate in force now rather than
            # whenever the battery is next emptied: that is the revenue actually
            # forgone (ADR-0027).
            self._battery.charge_from_generation(
                served.generation_charge, self._export_price_at(start)
            )
        # The metered totals, kept here rather than in the ledger because the
        # ledger's own discharge is also called to remove a measured loss, which
        # would make it count what it is meant to bound (HEA-196).
        self._metered_charge += served.grid_charge + served.generation_charge
        self._metered_discharge += served.discharged

        # The ledger falls by the full physical discharge - `served.discharged`,
        # not `served.battery` - whether or not the house is the one billed for
        # it: energy that left the battery straight to export is gone from the
        # battery's inventory regardless of who paid for it. Pricing the
        # house-billed share off the same withdrawal keeps its cost anchored to
        # what was actually taken out, not to a share the house happened to keep.
        battery_price = Decimal(0)
        battery_forgone = Decimal(0)
        if served.discharged > 0:
            withdrawn = self._battery.discharge(served.discharged)
            battery_price = withdrawn.cost / served.discharged
            # What the sunshine inside this discharge gave up when it was
            # stored, per kWh taken out. Priced off the same withdrawal as the
            # cost, so the two cannot disagree about what left (ADR-0027).
            battery_forgone = withdrawn.forgone / served.discharged

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
        forgone = {
            SourceKind.GENERATION: self._export_price_at(start),
            SourceKind.BATTERY: battery_forgone,
        }
        return prices, sources, forgone

    def _import_price(self, when: datetime, imported: Mapping[str, Decimal]) -> Decimal:
        """The grid price of the interval at ``when``, blended over its registers.

        Each register's import at its own rate, summed and divided by the total
        (ADR-0032). Where every register that imported shares one rate, that
        rate is the answer outright, so a single register is priced at exactly
        its rate rather than at a quotient that can land a digit off.

        Where nothing was imported there is nothing to weight by, and the price
        is the plain average of the registers' rates: no register has a better
        claim on what the grid would have cost. A register with no rate yet is
        priced at zero, as a household with none at all is.
        """
        rates = {
            meter: _rate_at(series, when) for meter, series in self._prices.items()
        }
        weights = {meter: kwh for meter, kwh in imported.items() if kwh > 0}
        carried = {rates.get(meter, Decimal(0)) for meter in weights}
        if len(carried) == 1:
            return carried.pop()
        if weights:
            cost = _sum(
                kwh * rates.get(meter, Decimal(0)) for meter, kwh in weights.items()
            )
            return cost / _sum(weights.values())
        if not rates:
            return Decimal(0)
        distinct = set(rates.values())
        if len(distinct) == 1:
            return distinct.pop()
        return _sum(rates.values()) / len(rates)

    def _export_price_at(self, when: datetime) -> Decimal:
        """What a kWh exported at ``when`` would have earned, or zero if unknown.

        Zero for a household who have declared no export price, which makes the
        forgone figure zero too - the honest answer rather than a guessed rate.
        """
        return _rate_at(self._export_prices, when)


def _entry_at(
    series: list[tuple[datetime, Decimal]], when: datetime
) -> tuple[datetime, Decimal] | None:
    """The newest entry in ``series`` at or before ``when``, stepwise.

    The earliest recorded rate applies to anything before it, so a household
    whose first reading arrives a moment after the first interval is priced at
    the rate they were on rather than at nothing.
    """
    if not series:
        return None
    applicable = series[0]
    for entry in series:
        if entry[0] > when:
            break
        applicable = entry
    return applicable


def _rate_at(series: list[tuple[datetime, Decimal]], when: datetime) -> Decimal:
    """The rate in ``series`` at ``when``, or zero where none was ever recorded."""
    entry = _entry_at(series, when)
    return Decimal(0) if entry is None else entry[1]


def _in_force(
    series: list[tuple[datetime, Decimal]], when: datetime
) -> dict[str, str] | None:
    """The rate at ``when`` and the moment it began, for the diagnostics.

    Through the same lookup the figures are priced with, so the download cannot
    report a different rate from the one that was applied.
    """
    entry = _entry_at(series, when)
    if entry is None:
        return None
    since, rate = entry
    return {"rate": str(rate), "since": since.isoformat()}


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
        # Scaled by what is kept rather than recomputed, and exactly rather than
        # approximately: the source split is linear in energy, so the battery's
        # share of `kept` is its share of the whole in the same ratio. That also
        # spares this the bucket's battery price, which it has no other reason to
        # know.
        battery_savings=_scaled(remainder.battery_savings, kept, remainder.energy_kwh),
        energy_by_source=split_by_source(kept, sources, _sum(sources.values())),
    )


def _loss_totals(loss: BatteryLoss) -> DeviceTotals:
    """A battery's loss as the consumer it is.

    Its counterfactual equals its cost, so it shows no saving: this energy really
    was bought, and what it would have cost is what it cost. Nothing is
    attributed by source, because the split is the blend of every charge that
    ever went in rather than anything one interval can say. What it could have
    earned is the export its stored sunshine gave up, at that same blend
    (ADR-0027, HEA-229).
    """
    # Spelled out rather than `replace`d from the zero constant, which types as a
    # bare dataclass and loses what this returns.
    return DeviceTotals(
        energy_kwh=loss.kwh,
        actual_cost=loss.cost,
        naive_cost=loss.cost,
        cost_savings=Decimal(0),
        battery_savings=Decimal(0),
        energy_from_grid=Decimal(0),
        energy_from_generation=Decimal(0),
        energy_from_battery=Decimal(0),
        cost_floor=Decimal(0),
        cost_ceiling=Decimal(0),
        forgone_export=loss.forgone,
    )


def _battery_share(
    sources: Mapping[SourceKind, Decimal], prices: Mapping[SourceKind, Decimal]
) -> Decimal:
    """How much of a bucket's saving the battery accounts for, from 0 to 1.

    A bucket is cheaper than the grid only through the sources priced below it -
    generation at nothing, the battery at whatever its charge cost - so the gap
    between blended and import divides exactly between those two. This is the
    battery's part of it, which is the share a late settlement of this bucket's
    surplus carries with it.

    Zero where the bucket made no saving at all, which is every all-grid bucket:
    there is nothing to divide, and dividing by the gap would ask what fraction of
    nothing the battery earned.
    """
    import_price = prices[SourceKind.IMPORT]
    gap = _sum(
        energy * (import_price - prices[kind]) for kind, energy in sources.items()
    )
    battery = sources.get(SourceKind.BATTERY, Decimal(0))
    if gap == 0 or battery == 0:
        return Decimal(0)
    return battery * (import_price - prices[SourceKind.BATTERY]) / gap


def _scaled(value: Decimal, kept: Decimal, whole: Decimal) -> Decimal:
    """``value`` in the ratio ``kept`` bears to ``whole``, and zero if there is none."""
    return value * kept / whole if whole else Decimal(0)


def _sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))


def _dump_by_source(by_source: Mapping[SourceKind, Decimal]) -> dict[str, str]:
    """A source split as JSON-safe pairs, keyed by the enum's stable value."""
    return {kind.value: str(kwh) for kind, kwh in by_source.items()}


def _load_by_source(data: Mapping[str, str]) -> dict[SourceKind, Decimal]:
    return {SourceKind(kind): Decimal(kwh) for kind, kwh in data.items()}


def _dump_running(running: _Running) -> dict[str, Any]:
    """One accumulator's six figures and its source split.

    Listed field by field rather than walked, so adding a figure to ``_Running``
    fails the round-trip test until it is carried here too.
    """
    return {
        "energy_kwh": str(running.energy_kwh),
        "actual_cost": str(running.actual_cost),
        "naive_cost": str(running.naive_cost),
        "cost_savings": str(running.cost_savings),
        "battery_savings": str(running.battery_savings),
        "cost_floor": str(running.cost_floor),
        "cost_ceiling": str(running.cost_ceiling),
        "by_source": _dump_by_source(running.by_source),
    }


def _load_running(data: Mapping[str, Any]) -> _Running:
    return _Running(
        energy_kwh=Decimal(data["energy_kwh"]),
        actual_cost=Decimal(data["actual_cost"]),
        naive_cost=Decimal(data["naive_cost"]),
        cost_savings=Decimal(data["cost_savings"]),
        # Absent from every snapshot written before this figure existed, and read
        # as nothing rather than refused. Refusing is the general rule and it is
        # right for a snapshot this engine cannot make sense of - but here the
        # shape is understood and one field is simply missing, so insisting would
        # send every installed household through a cold start and take the
        # battery's stored-cost ledger with it. Their next discharge would be
        # priced at zero to gain a figure whose absence means zero (ADR-0021).
        battery_savings=Decimal(data.get("battery_savings", 0)),
        cost_floor=Decimal(data["cost_floor"]),
        cost_ceiling=Decimal(data["cost_ceiling"]),
        by_source=_load_by_source(data["by_source"]),
    )


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
