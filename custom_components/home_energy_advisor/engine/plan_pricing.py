"""What a tariff plan would have charged for the grid flows actually recorded.

A plan is a typed schedule, as offers are published: time bands with an import
price and optionally an export price of their own, a flat export price for the
rest, and a daily charge (ADR-0036). It is priced against the household's
recorded hourly import and export, so the figure re-prices what really happened.
Nothing is modelled; the one assumption, said wherever the figure is shown, is
that the household would have run its battery the same way.

Bands are in local time. Weekends and holidays share the rest-day bands, which
is how time-of-use offers treat a public holiday. Every hour of both kinds of day
falls in exactly one band: a plan that leaves an hour uncovered, or covers one
twice, is refused rather than priced, because either way the price of that hour
would be a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping

_HOURS_IN_A_DAY = 24
_SATURDAY = 5


class Days(StrEnum):
    """Which days a band applies to."""

    WEEKDAYS = "weekdays"
    REST_DAYS = "rest_days"
    EVERY_DAY = "every_day"


class DayKind(StrEnum):
    """The two kinds of day a plan prices differently: working and rest days."""

    WEEKDAY = "weekday"
    REST_DAY = "rest_day"


_KINDS_OF = {
    Days.WEEKDAYS: (DayKind.WEEKDAY,),
    Days.REST_DAYS: (DayKind.REST_DAY,),
    Days.EVERY_DAY: (DayKind.WEEKDAY, DayKind.REST_DAY),
}


@dataclass(frozen=True)
class Band:
    """One price, for some hours of some days.

    Hours run from `start` up to but not including `end`, on a 0-24 clock, so a
    band from 22 to 8 runs across midnight. Whole hours only: the statistics a
    plan is priced against are hourly (ADR-0036).
    """

    days: Days
    start: int
    end: int
    import_price: Decimal
    export_price: Decimal | None = None

    def __post_init__(self) -> None:
        """Refuse hours that are not whole hours of one day, or that cover none."""
        if not 0 <= self.start < _HOURS_IN_A_DAY:
            msg = f"A band's hours start between 0 and 23, not {self.start}"
            raise ValueError(msg)
        if not 0 < self.end <= _HOURS_IN_A_DAY:
            msg = f"A band's hours end between 1 and 24, not {self.end}"
            raise ValueError(msg)
        if self.start == self.end:
            msg = f"A band's hours must cover at least one hour, not {self.start}"
            raise ValueError(msg)

    @property
    def hours(self) -> frozenset[int]:
        """The hours of the day it covers, each by the hour it starts at."""
        if self.start < self.end:
            return frozenset(range(self.start, self.end))
        return frozenset(range(self.start, _HOURS_IN_A_DAY)) | frozenset(
            range(self.end)
        )

    def applies_to(self, kind: DayKind) -> bool:
        """Whether it prices that kind of day."""
        return kind in _KINDS_OF[self.days]


@dataclass(frozen=True)
class PlanGap:
    """Hours of one kind of day that a plan prices not exactly once."""

    kind: DayKind
    hours: tuple[int, ...]
    covered_by: int


@dataclass(frozen=True)
class Plan:
    """A tariff plan as it is published: its bands, daily charge and export price."""

    name: str
    bands: tuple[Band, ...]
    daily_charge: Decimal = Decimal(0)
    export_price: Decimal = Decimal(0)

    def gaps(self) -> tuple[PlanGap, ...]:
        """Every hour of either kind of day that no band, or more than one, covers.

        Grouped by kind of day and by how many bands cover the hours, uncovered
        hours first, so a form can say exactly what is missing or doubled.
        """
        gaps: list[PlanGap] = []
        for kind in DayKind:
            covering = {
                hour: sum(
                    1
                    for band in self.bands
                    if band.applies_to(kind) and hour in band.hours
                )
                for hour in range(_HOURS_IN_A_DAY)
            }
            for count in sorted({count for count in covering.values() if count != 1}):
                hours = tuple(hour for hour, n in covering.items() if n == count)
                gaps.append(PlanGap(kind, hours, covered_by=count))
        return tuple(gaps)

    def band_at(self, kind: DayKind, hour: int) -> Band:
        """The one band pricing that hour of that kind of day."""
        return next(
            band for band in self.bands if band.applies_to(kind) and hour in band.hours
        )


@dataclass(frozen=True)
class PriceGroup:
    """One price a plan charges, and every band that charges it (HEA-259).

    What a household types when copying a plan: an offer that shares a plan's
    bands differs from it in a handful of prices, not in its bands, so each
    distinct price is asked for once however many bands carry it.
    """

    price: Decimal
    bands: tuple[Band, ...]


def import_price_groups(plan: Plan) -> tuple[PriceGroup, ...]:
    """The plan's distinct import prices, in the order its bands first use them."""
    return _grouped(plan.bands, lambda band: band.import_price)


def export_price_groups(plan: Plan) -> tuple[PriceGroup, ...]:
    """The distinct export prices bands carry of their own.

    A band without one pays the plan's export price, which is a figure of the
    plan's already, so it forms no group.
    """
    return _grouped(
        tuple(band for band in plan.bands if band.export_price is not None),
        lambda band: band.export_price,
    )


def repriced(
    plan: Plan,
    *,
    imports: Mapping[Decimal, Decimal],
    exports: Mapping[Decimal, Decimal],
) -> Plan:
    """The plan with each old price replaced by its new one, bands unchanged.

    A price not in the maps is kept, so a copy changes only what was given.
    """
    return Plan(
        name=plan.name,
        daily_charge=plan.daily_charge,
        export_price=plan.export_price,
        bands=tuple(
            replace(
                band,
                import_price=imports.get(band.import_price, band.import_price),
                export_price=(
                    None
                    if band.export_price is None
                    else exports.get(band.export_price, band.export_price)
                ),
            )
            for band in plan.bands
        ),
    )


def _grouped(
    bands: tuple[Band, ...], price_of: Callable[[Band], Decimal | None]
) -> tuple[PriceGroup, ...]:
    grouped: dict[Decimal, list[Band]] = {}
    for band in bands:
        price = price_of(band)
        if price is not None:
            grouped.setdefault(price, []).append(band)
    return tuple(
        PriceGroup(price, tuple(members)) for price, members in grouped.items()
    )


@dataclass(frozen=True)
class HourOfEnergy:
    """One recorded hour of grid flow, by the local time it started."""

    start: datetime
    imported_kwh: Decimal
    exported_kwh: Decimal


@dataclass(frozen=True)
class PlanCost:
    """What a plan would have charged, in its three parts."""

    energy: Decimal
    export_credit: Decimal
    daily_charges: Decimal

    @property
    def total(self) -> Decimal:
        """What the household would have paid: energy and charges, less export."""
        return self.energy - self.export_credit + self.daily_charges


def price_plan(
    plan: Plan,
    hours: Iterable[HourOfEnergy],
    *,
    days: Decimal,
    holidays: Collection[date],
) -> PlanCost:
    """What `plan` would have charged for these hours, over `days` of charges.

    `days` is how many days of daily charge the period carries, which
    `days_covered` measures. `holidays` are dates priced as rest days.
    """
    if plan.gaps():
        msg = f"Plan {plan.name!r} does not cover every hour exactly once"
        raise ValueError(msg)
    energy = Decimal(0)
    export_credit = Decimal(0)
    for recorded in hours:
        band = plan.band_at(
            _kind_of(recorded.start.date(), holidays), recorded.start.hour
        )
        energy += recorded.imported_kwh * band.import_price
        export_price = (
            plan.export_price if band.export_price is None else band.export_price
        )
        export_credit += recorded.exported_kwh * export_price
    return PlanCost(
        energy=energy,
        export_credit=export_credit,
        daily_charges=plan.daily_charge * days,
    )


def days_covered(start: datetime, end: datetime) -> Decimal:
    """How many days of daily charge run from `start` to `end`, in local time.

    Each local day counts the share of it the period covers, measured against
    that day's own length, so the 23- and 25-hour days daylight saving makes are
    each one day, as a bill counts them.
    """
    total = Decimal(0)
    day = start.date()
    while (midnight := _midnight(day, start)) < end:
        following = _midnight(day + timedelta(days=1), start)
        covered = min(end, following) - max(start, midnight)
        if covered > timedelta(0):
            total += Decimal(covered.total_seconds()) / Decimal(
                (following - midnight).total_seconds()
            )
        day += timedelta(days=1)
    return total


def _midnight(day: date, zoned: datetime) -> datetime:
    """The start of `day` in the time zone `zoned` carries."""
    return datetime(day.year, day.month, day.day, tzinfo=zoned.tzinfo)


def _kind_of(day: date, holidays: Collection[date]) -> DayKind:
    if day.weekday() >= _SATURDAY or day in holidays:
        return DayKind.REST_DAY
    return DayKind.WEEKDAY
