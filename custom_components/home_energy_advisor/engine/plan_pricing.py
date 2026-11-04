"""What a tariff plan would have charged for the grid flows actually recorded.

A plan is a typed schedule, as offers are published: time bands with an import
price and optionally an export price of their own, a flat export price for the
rest, and a daily charge (ADR-0036). It is priced against the household's
recorded hourly import and export, so the figure re-prices what really happened.
Nothing is modelled; the one assumption, said wherever the figure is shown, is
that the household would have run its battery the same way.

Bands are in local time. A band applies to any days of the week, and to public
holidays as a day of their own, so a weekend that starts on Friday evening, or a
holiday priced unlike either a weekday or a weekend, is a band like any other
(ADR-0038). Most time-of-use offers price a holiday as a weekend, which the
weekends-and-holidays band says; a plan with no band for holidays at all prices
each as the day of the week it falls on. Every hour of every day falls in exactly
one band: a plan that leaves an hour uncovered, or covers one twice, is refused
rather than priced, because either way the price of that hour would be a guess.

A plan's import, and separately its export, can instead follow a market price
that changes through the day (ADR-0037). Each recorded interval then carries the
price the market set for it, at whatever resolution the recorder kept, and a
plan importing at the market has no bands at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

_HOURS_IN_A_DAY = 24


class Day(StrEnum):
    """A day a band can price: one of the week's, or a public holiday."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    HOLIDAY = "holiday"


# The days of the week, by `date.weekday()`.
_WEEK = tuple(day for day in Day if day is not Day.HOLIDAY)


class Days(StrEnum):
    """The days most bands apply to, as offers name them."""

    WEEKDAYS = "weekdays"
    REST_DAYS = "rest_days"
    EVERY_DAY = "every_day"

    @property
    def days(self) -> frozenset[Day]:
        """The days it names."""
        return _DAYS_OF[self]


_DAYS_OF = {
    Days.WEEKDAYS: frozenset(_WEEK[:5]),
    Days.REST_DAYS: frozenset({*_WEEK[5:], Day.HOLIDAY}),
    Days.EVERY_DAY: frozenset(Day),
}


@dataclass(frozen=True)
class Band:
    """One price, for some hours of some days.

    Its days are the ones an offer names, or any it chooses (ADR-0038). Hours run
    from `start` up to but not including `end`, on a 0-24 clock, so a band from
    22 to 8 runs across midnight. Whole hours only: the statistics a plan is
    priced against are hourly (ADR-0036).
    """

    days: Days | frozenset[Day]
    start: int
    end: int
    import_price: Decimal
    export_price: Decimal | None = None

    def __post_init__(self) -> None:
        """Refuse a band of no days, or hours that are not whole hours of one."""
        if not self.covers:
            msg = "A band applies to at least one day"
            raise ValueError(msg)
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

    @property
    def covers(self) -> frozenset[Day]:
        """The days it prices."""
        return self.days.days if isinstance(self.days, Days) else self.days

    def applies_to(self, day: Day) -> bool:
        """Whether it prices that day."""
        return day in self.covers


@dataclass(frozen=True)
class PlanGap:
    """Hours that a plan prices not exactly once, on each of some days."""

    days: tuple[Day, ...]
    hours: tuple[int, ...]
    covered_by: int


@dataclass(frozen=True)
class Plan:
    """A tariff plan as it is published: its bands, daily charge and export price.

    `import_per_interval` and `export_per_interval` say that the plan charges for
    import, or pays for export, at each interval's market price instead (ADR-0037).
    """

    name: str
    bands: tuple[Band, ...]
    daily_charge: Decimal = Decimal(0)
    export_price: Decimal = Decimal(0)
    import_per_interval: bool = False
    export_per_interval: bool = False

    @property
    def prices_holidays(self) -> bool:
        """Whether a holiday is a day of its own, rather than its day of the week."""
        return any(band.applies_to(Day.HOLIDAY) for band in self.bands)

    def gaps(self) -> tuple[PlanGap, ...]:
        """Every hour of every day that no band, or more than one, covers.

        Days missing the same hours are grouped, and uncovered hours come first,
        so a form can say exactly what is missing or doubled: "weekdays from
        22:00", not five lines. Holidays are a day to cover only when a band
        prices them. A plan importing at the market prices every hour from it,
        so has none.
        """
        if self.import_per_interval:
            return ()
        priced = (*_WEEK, Day.HOLIDAY) if self.prices_holidays else _WEEK
        grouped: dict[tuple[int, tuple[int, ...]], list[Day]] = {}
        for day in priced:
            covering = {
                hour: sum(
                    1
                    for band in self.bands
                    if band.applies_to(day) and hour in band.hours
                )
                for hour in range(_HOURS_IN_A_DAY)
            }
            for count in sorted({count for count in covering.values() if count != 1}):
                hours = tuple(hour for hour, n in covering.items() if n == count)
                grouped.setdefault((count, hours), []).append(day)
        return tuple(
            PlanGap(tuple(days), hours, covered_by=count)
            for (count, hours), days in sorted(
                grouped.items(), key=lambda group: group[0][0]
            )
        )

    def day_of(self, day: date, holidays: Collection[date]) -> Day:
        """Which of its days the plan prices `day` as."""
        if day in holidays and self.prices_holidays:
            return Day.HOLIDAY
        return _WEEK[day.weekday()]

    def band_at(self, day: Day, hour: int) -> Band:
        """The one band pricing that hour of that day."""
        return next(
            band for band in self.bands if band.applies_to(day) and hour in band.hours
        )


@dataclass(frozen=True)
class IntervalOfEnergy:
    """One recorded interval of grid flow, by the local time it started.

    An hour, or five minutes where the recorder still keeps them, with the market
    prices of the interval where a plan follows the market (ADR-0037).
    """

    start: datetime
    imported_kwh: Decimal
    exported_kwh: Decimal
    import_price: Decimal | None = None
    export_price: Decimal | None = None


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
    intervals: Iterable[IntervalOfEnergy],
    *,
    days: Decimal,
    holidays: Collection[date],
) -> PlanCost:
    """What `plan` would have charged for these intervals, over `days` of charges.

    `days` is how many days of daily charge the period carries, which
    `days_covered` measures. `holidays` are the public holidays, priced at the
    plan's holiday bands where it has them. An
    interval a market-priced plan needs a price for and that has none is
    refused: what to charge it is the caller's to decide, not a guess here.
    """
    if plan.gaps():
        msg = f"Plan {plan.name!r} does not cover every hour exactly once"
        raise ValueError(msg)
    energy = Decimal(0)
    export_credit = Decimal(0)
    for recorded in intervals:
        band = (
            None
            if plan.import_per_interval
            else plan.band_at(
                plan.day_of(recorded.start.date(), holidays), recorded.start.hour
            )
        )
        energy += recorded.imported_kwh * (
            _market(recorded.import_price, recorded, plan)
            if band is None
            else band.import_price
        )
        if plan.export_per_interval:
            export_price = _market(recorded.export_price, recorded, plan)
        elif band is None or band.export_price is None:
            export_price = plan.export_price
        else:
            export_price = band.export_price
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


def _market(price: Decimal | None, recorded: IntervalOfEnergy, plan: Plan) -> Decimal:
    if price is None:
        msg = f"Plan {plan.name!r} has no market price for {recorded.start}"
        raise ValueError(msg)
    return price
