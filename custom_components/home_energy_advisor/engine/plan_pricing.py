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
plan importing at the market has no bands at all. A market price published
wholesale, as Nord Pool's is, is adjusted by each plan to what its supplier
charges: its charges added per kWh, then multiplied, as VAT is (HEA-273). The
adjustment belongs to the plan, so two suppliers on one wholesale price are two
plans reading the same entity.

An export price can pay only on the first kWh exported in a day, as some
feed-in offers do (ADR-0039). The plan's own export price can carry an
allowance, with a lower price for the rest; a band's export price can too, and
what it does not pay falls to the plan's. A band's allowance belongs to the
named price it charges, so it counts across every band charging that price, and
everything credited at the plan's price counts against the plan's. Each
allowance starts again at local midnight.

An import price can charge its rate only on the first kWh imported in a day,
week or month, as free hours capped at a few kWh do (HEA-264). Beyond the
allowance its hours are charged another price, the one the household would
otherwise pay then. Like an export allowance it belongs to the named price, so
it counts across every band charging that price; a week starts on Monday, and
every period at local midnight. One price within it and one beyond, so the
total does not depend on the order intervals are priced in.

What export earns in a month can be capped at what the month's energy cost, as
many plans cap it (HEA-258). The cap is on the energy
alone: daily charges are payable however much is exported. Whatever the cap
does not pay is lost, or, on a plan that carries it forward, offsets the next
month's energy, and whatever is still carried at the end of the period is said
rather than credited. Months are calendar months in local time, part-months
included, because a period picked on a dashboard need not be a billing period.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


class AllowancePeriod(StrEnum):
    """How long an import allowance lasts before it starts again (HEA-264)."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    def start(self, day: date) -> date:
        """The first day of the period `day` falls in."""
        if self is AllowancePeriod.WEEK:
            return day - timedelta(days=day.weekday())
        if self is AllowancePeriod.MONTH:
            return day.replace(day=1)
        return day


@dataclass(frozen=True)
class Band:
    """One price, for some hours of some days.

    Its days are the ones an offer names, or any it chooses (ADR-0038). Hours run
    from `start` up to but not including `end`, on a 0-24 clock, so a band from
    22 to 8 runs across midnight. Whole hours only: the statistics a plan is
    priced against are hourly (ADR-0036).

    `export_allowance` is how many kWh a day its export price pays on, shared
    with every band charging the same named price, `name` (ADR-0039).
    `import_allowance` is how many kWh each `import_allowance_period` its import
    price charges on, shared the same way, with `import_price_after` charged on
    the rest (HEA-264). `import_price_after_name` is the named price that is, so
    what it charges is counted on that price's row (HEA-300).
    """

    days: Days | frozenset[Day]
    start: int
    end: int
    import_price: Decimal
    export_price: Decimal | None = None
    export_allowance: Decimal | None = None
    import_allowance: Decimal | None = None
    import_allowance_period: AllowancePeriod = AllowancePeriod.DAY
    import_price_after: Decimal = Decimal(0)
    # Whose allowance it shares, not what it charges, so two bands at the same
    # prices are the same band whatever their price is called.
    name: str = field(default="", compare=False)
    import_price_after_name: str = field(default="", compare=False)

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
class MarketAdjustment:
    """What a plan makes of a market price: `(price + add) x multiply`.

    The supplier's charges and any energy tax per kWh are added first and VAT
    is a multiplier on all of it, as a dynamic contract's bill reads. Left as
    it is, it leaves the market's price unchanged.
    """

    add: Decimal = Decimal(0)
    multiply: Decimal = Decimal(1)

    def apply(self, price: Decimal) -> Decimal:
        """The price the plan charges or pays, for the market's `price`."""
        return (price + self.add) * self.multiply


class ExportCap(StrEnum):
    """How much of what export earns a month a plan pays (HEA-258)."""

    # Every kWh exported is paid at its price.
    NONE = "none"
    # Paid up to the month's energy cost, and the rest lost.
    MONTHLY = "monthly"
    # Paid up to the month's energy cost, and the rest offsets the next month's.
    CARRIED = "carried"


@dataclass(frozen=True)
class Plan:
    """A tariff plan as it is published: its bands, daily charge and export price.

    `import_per_interval` and `export_per_interval` say that the plan charges for
    import, or pays for export, at each interval's market price instead (ADR-0037),
    adjusted by `import_adjustment` and `export_adjustment` (HEA-273).
    `export_allowance` is how many kWh a day its export price pays on, with
    `export_price_after` paid on the rest (ADR-0039). `export_cap` is whether
    what export earns a month is capped at the month's energy cost (HEA-258).
    """

    name: str
    bands: tuple[Band, ...]
    daily_charge: Decimal = Decimal(0)
    export_price: Decimal = Decimal(0)
    import_per_interval: bool = False
    export_per_interval: bool = False
    export_allowance: Decimal | None = None
    export_price_after: Decimal = Decimal(0)
    import_adjustment: MarketAdjustment = field(default_factory=MarketAdjustment)
    export_adjustment: MarketAdjustment = field(default_factory=MarketAdjustment)
    export_cap: ExportCap = ExportCap.NONE

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
class PriceLine:
    """What one of a plan's prices charged or paid, as a bill's line reads.

    `name` is the named price, empty for the plan's own export price and for
    one a plan entered before prices had names. `rate` is per kWh, or `None`
    for a market price, which has no one rate. `beyond_allowance` marks the
    plan's export price after its allowance (ADR-0039).
    """

    name: str
    rate: Decimal | None
    kwh: Decimal
    amount: Decimal
    beyond_allowance: bool = False


@dataclass(frozen=True)
class PlanCost:
    """What a plan would have charged, in its three parts.

    `export_credit` is what export was paid, after any cap. `export_unpaid` is
    what the cap did not pay, and `export_carried` what it carried forward and
    was still unused when the period ended (HEA-258).

    `imports` and `exports` break the energy and the export down by price, so a
    household can match each line against a bill (HEA-300). The import lines
    add up to `energy`; the export lines are what export earned before any cap,
    so they add up to `export_credit` plus what the cap did not pay.
    `cheapest_import` and `dearest_import` are the ends the plan's average
    import price is read against: its own prices, or for a market price, the
    cheapest and dearest it charged.
    """

    energy: Decimal
    export_credit: Decimal
    daily_charges: Decimal
    export_unpaid: Decimal = Decimal(0)
    export_carried: Decimal = Decimal(0)
    imports: tuple[PriceLine, ...] = field(default=(), compare=False)
    exports: tuple[PriceLine, ...] = field(default=(), compare=False)
    cheapest_import: Decimal | None = field(default=None, compare=False)
    dearest_import: Decimal | None = field(default=None, compare=False)

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
    plan's holiday bands where it has them. An interval a market-priced plan
    needs a price for and that has none is refused: what to charge it is the
    caller's to decide, not a guess here.
    """
    if plan.gaps():
        msg = f"Plan {plan.name!r} does not cover every hour exactly once"
        raise ValueError(msg)
    months: dict[tuple[int, int], _Month] = {}
    allowances = _Allowances()
    # Counted apart from export's, since a price can carry both.
    import_allowances = _Allowances()
    lines = _Lines(plan)
    for recorded in intervals:
        month = months.setdefault((recorded.start.year, recorded.start.month), _Month())
        band = (
            None
            if plan.import_per_interval
            else plan.band_at(
                plan.day_of(recorded.start.date(), holidays), recorded.start.hour
            )
        )
        if band is None:
            price = plan.import_adjustment.apply(
                _market(recorded.import_price, recorded, plan)
            )
            month.energy += lines.charge_at_market(recorded.imported_kwh, price)
        else:
            month.energy += lines.charge(
                band, *import_allowances.charge(band, recorded)
            )
        if plan.export_per_interval:
            price = plan.export_adjustment.apply(
                _market(recorded.export_price, recorded, plan)
            )
            month.earned += lines.pay(
                [(_AT_MARKET, recorded.exported_kwh, recorded.exported_kwh * price)]
            )
        else:
            month.earned += lines.pay(allowances.credit(plan, band, recorded))
    return _capped(plan, [months[key] for key in sorted(months)], days, lines)


@dataclass
class _Month:
    """What a month's import cost, and what its export earned before any cap."""

    energy: Decimal = Decimal(0)
    earned: Decimal = Decimal(0)


def _capped(plan: Plan, months: list[_Month], days: Decimal, lines: _Lines) -> PlanCost:
    """The plan's cost, with export paid as its cap allows, month by month.

    With the lines it is made of, which no cap changes: they say what each price
    charged and earned, and the cap only what of the earnings was paid.

    A month's cap is its energy cost, never below nothing: a month the market
    paid the household to import has no energy cost for export to offset.
    """
    paid = Decimal(0)
    unpaid = Decimal(0)
    carried = Decimal(0)
    for month in months:
        if plan.export_cap is ExportCap.NONE:
            paid += month.earned
            continue
        earned = month.earned + carried
        within = min(earned, max(month.energy, Decimal(0)))
        paid += within
        if plan.export_cap is ExportCap.CARRIED:
            carried = earned - within
        else:
            unpaid += earned - within
    return PlanCost(
        energy=sum((month.energy for month in months), Decimal(0)),
        export_credit=paid,
        daily_charges=plan.daily_charge * days,
        export_unpaid=unpaid,
        export_carried=carried,
        imports=lines.imports(),
        exports=lines.exports(),
        cheapest_import=lines.cheapest_import(),
        dearest_import=lines.dearest_import(),
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


class _Allowances:
    """What export earns at a plan's and its bands' prices, allowances counted.

    Each allowance is counted by the day and by whose it is: a named price's, or
    the plan's own (`None`). Every kWh at a price meets the same allowance
    whatever order the intervals come in, so the total does not depend on it.
    """

    def __init__(self) -> None:
        self._used: dict[tuple[date, str | None], Decimal] = {}

    def credit(
        self, plan: Plan, band: Band | None, recorded: IntervalOfEnergy
    ) -> list[_Paid]:
        """What `recorded`'s export earns, at its band's price, then the plan's.

        Each part with the line it is paid on, the kWh and what they earned.
        """
        day = recorded.start.date()
        exported = recorded.exported_kwh
        parts: list[_Paid] = []
        if band is not None and band.export_price is not None:
            paid = self._within(day, band.name, band.export_allowance, exported)
            parts.append(
                (_band_export(band, band.export_price), paid, paid * band.export_price)
            )
            exported -= paid
        paid = self._within(day, None, plan.export_allowance, exported)
        parts.append((_plans_export(plan), paid, paid * plan.export_price))
        if plan.export_allowance is not None:
            beyond = exported - paid
            parts.append(
                (_beyond_export(plan), beyond, beyond * plan.export_price_after)
            )
        return parts

    def charge(self, band: Band, recorded: IntervalOfEnergy) -> tuple[Decimal, Decimal]:
        """`recorded`'s import within its band's allowance, and beyond it.

        The allowance is counted from the start of its period, a day, week or
        month (HEA-264), so `_within`'s day is that period's first.
        """
        imported = recorded.imported_kwh
        starts = band.import_allowance_period.start(recorded.start.date())
        within = self._within(starts, band.name, band.import_allowance, imported)
        return within, imported - within

    def _within(
        self, day: date, whose: str | None, allowance: Decimal | None, kwh: Decimal
    ) -> Decimal:
        """How much of `kwh` the day's allowance still has room for, now used."""
        if allowance is None:
            return kwh
        used = self._used.get((day, whose), Decimal(0))
        within = min(kwh, max(allowance - used, Decimal(0)))
        self._used[(day, whose)] = used + within
        return within


# A line of a plan's breakdown: its price's name, rate per kWh (none for a market
# price), and whether it is the plan's export price beyond its allowance.
_Line = tuple[str, Decimal | None, bool]
# What one part of an interval's flow came to: its line, kWh and money.
_Paid = tuple[_Line, Decimal, Decimal]

_AT_MARKET: _Line = ("", None, False)


def _band_import(name: str, rate: Decimal) -> _Line:
    return (name, rate, False)


def _band_export(band: Band, rate: Decimal) -> _Line:
    return (band.name, rate, False)


def _plans_export(plan: Plan) -> _Line:
    return ("", plan.export_price, False)


def _beyond_export(plan: Plan) -> _Line:
    return ("", plan.export_price_after, True)


class _Lines:
    """A plan's flows counted by the price that charged or paid them (HEA-300).

    Every price the plan has gets its line before anything is counted, in the
    order its bands first use it, so a price nothing was charged at still reads
    as a line of nothing, as a bill lists every period whether used or not.
    """

    def __init__(self, plan: Plan) -> None:
        self._imports: dict[_Line, list[Decimal]] = {}
        self._exports: dict[_Line, list[Decimal]] = {}
        self._charged: list[Decimal] = []
        if plan.import_per_interval:
            self._open(self._imports, _AT_MARKET)
        else:
            for band in plan.bands:
                self._open(self._imports, _band_import(band.name, band.import_price))
            for band in plan.bands:
                if band.import_allowance is not None:
                    self._open(
                        self._imports,
                        _band_import(
                            band.import_price_after_name, band.import_price_after
                        ),
                    )
        if plan.export_per_interval:
            self._open(self._exports, _AT_MARKET)
            return
        for band in plan.bands:
            if band.export_price is not None:
                self._open(self._exports, _band_export(band, band.export_price))
        self._open(self._exports, _plans_export(plan))
        if plan.export_allowance is not None:
            self._open(self._exports, _beyond_export(plan))

    @staticmethod
    def _open(lines: dict[_Line, list[Decimal]], line: _Line) -> None:
        lines.setdefault(line, [Decimal(0), Decimal(0)])

    @staticmethod
    def _add(
        lines: dict[_Line, list[Decimal]], line: _Line, kwh: Decimal, money: Decimal
    ) -> None:
        counted = lines.setdefault(line, [Decimal(0), Decimal(0)])
        counted[0] += kwh
        counted[1] += money

    def charge(self, band: Band, within: Decimal, beyond: Decimal) -> Decimal:
        """Count import at its band's price and beyond its allowance; the cost."""
        cost = within * band.import_price
        self._add(
            self._imports, _band_import(band.name, band.import_price), within, cost
        )
        if band.import_allowance is None:
            return cost
        after = beyond * band.import_price_after
        self._add(
            self._imports,
            _band_import(band.import_price_after_name, band.import_price_after),
            beyond,
            after,
        )
        return cost + after

    def charge_at_market(self, kwh: Decimal, price: Decimal) -> Decimal:
        """Count import at the market's price; what it cost."""
        cost = kwh * price
        self._add(self._imports, _AT_MARKET, kwh, cost)
        if kwh:
            self._charged.append(price)
        return cost

    def pay(self, parts: Iterable[_Paid]) -> Decimal:
        """Count each part of export on its line; what they earned."""
        earned = Decimal(0)
        for line, kwh, money in parts:
            self._add(self._exports, line, kwh, money)
            earned += money
        return earned

    def imports(self) -> tuple[PriceLine, ...]:
        """The import lines, in order."""
        return self._finished(self._imports)

    def exports(self) -> tuple[PriceLine, ...]:
        """The export lines, in order."""
        return self._finished(self._exports)

    def cheapest_import(self) -> Decimal | None:
        """The cheapest import price: the plan's own, or the market's charged."""
        return min(self._import_rates(), default=None)

    def dearest_import(self) -> Decimal | None:
        """The dearest import price: the plan's own, or the market's charged."""
        return max(self._import_rates(), default=None)

    def _import_rates(self) -> list[Decimal]:
        if _AT_MARKET in self._imports:
            return self._charged
        return [rate for _, rate, _ in self._imports if rate is not None]

    @staticmethod
    def _finished(lines: dict[_Line, list[Decimal]]) -> tuple[PriceLine, ...]:
        return tuple(
            PriceLine(name, rate, kwh, money, beyond_allowance=beyond)
            for (name, rate, beyond), (kwh, money) in lines.items()
        )


def _market(price: Decimal | None, recorded: IntervalOfEnergy, plan: Plan) -> Decimal:
    if price is None:
        msg = f"Plan {plan.name!r} has no market price for {recorded.start}"
        raise ValueError(msg)
    return price
