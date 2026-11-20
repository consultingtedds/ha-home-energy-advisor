"""Hours no home could use in a meter's statistics, raised as Repairs (ADR-0045).

The plan comparison leaves such an hour out and names it (ADR-0044), but only
for the period a household is looking at, and the same hour is wrong in the
Energy Dashboard and every chart too. So once a day every meter the comparison
reads, and every meter in the Energy Dashboard, is checked over all of its
history, and each impossible hour is raised as a Repair that says what was
recorded, what probably happened, and what the hour most likely should have
been. The household corrects it from there (``repairs.py``), or in Developer
Tools, or not at all; whichever, the Repair clears once the hour is no longer
impossible.

A meter's glitch is usually priced into the Energy Dashboard's cost for the
same hour too. That cost is a statistic of its own, with a Repair of its own,
found on its own: a household may want one corrected and not the other.

The suggestion is worked out from the readings, never guessed: from the five
minutes the jump happened in, where Home Assistant still keeps them, otherwise
from the hour's own price, otherwise from the same hour of the day over the
week either side.
"""

from __future__ import annotations

import logging
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from statistics import median
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.statistics import (
    get_metadata,
    statistics_during_period,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from . import issues
from .const import (
    CONF_GENERATION_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    IMPOSSIBLE_KWH_PER_HOUR,
)
from .energy_dashboard import async_energy_prefs, dashboard_meters, dashboard_money
from .house_inputs import batteries_of, grid_meters_of, house_entities

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)
_FIVE_MINUTES = timedelta(minutes=5)
# How far either side the same hour of the day is looked for.
_EITHER_SIDE = timedelta(days=7)
# Fewer similar hours than this say too little to suggest a value from.
_FEWEST_SIMILAR_HOURS = 3
# A change this close to the meter's own reading is its whole total counted
# again: a sensor that read zero for a moment and came back.
_COUNTED_AGAIN = 0.01
# Less energy than this in an hour says too little about its price.
_PRICED_FROM_KWH = 0.05
# Long enough after a start for the recorder to be settled; then once a day.
_FIRST_CHECK = timedelta(minutes=5)
_EVERY = timedelta(days=1)
# Before anything the recorder can hold.
_EVER = datetime(2000, 1, 1, tzinfo=UTC)
_IN_KWH = {"energy": "kWh"}
_KWH = "kWh"

ENERGY = "energy"
MONEY = "money"

CAUSE_COUNTED_AGAIN = "counted_again"
CAUSE_FELL = "fell"
CAUSE_JUMPED = "jumped"
CAUSE_RESTARTED = "restarted"
# A running total this close to zero is a statistic starting again.
_ZERO_TOTAL = 1e-9


@dataclass(frozen=True)
class Checked:
    """A statistic the check reads: energy or money, and the one it pairs with.

    An energy meter's partner is the Energy Dashboard's cost for it, and a
    cost's partner is the meter it prices.
    """

    statistic_id: str
    kind: str = ENERGY
    partner: str | None = None


@dataclass(frozen=True)
class Suggestion:
    """What an impossible hour most likely should have recorded, and why.

    From the five minutes it jumped in (`window`, `jump`, `rest`), from the
    hour's energy at its price (`energy`, `price`), or from the same hour on
    the days either side (`low`, `high`).
    """

    value: float
    low: float | None = None
    high: float | None = None
    window: datetime | None = None
    jump: float | None = None
    rest: float | None = None
    energy: float | None = None
    price: float | None = None


@dataclass(frozen=True)
class ImpossibleHour:
    """One hour of one statistic no home could use, or be charged for."""

    statistic_id: str
    start: datetime
    change: float
    reading: float | None
    suggestion: Suggestion | None = None
    kind: str = ENERGY
    unit: str = _KWH
    partner: str | None = None
    ceiling: float = IMPOSSIBLE_KWH_PER_HOUR
    restarted: bool = False

    @property
    def translation_key(self) -> str:
        """The Repair it raises: an impossible hour of energy, or of cost."""
        if self.kind == MONEY:
            return issues.ISSUE_IMPOSSIBLE_COST
        return issues.ISSUE_IMPOSSIBLE_HOUR

    @property
    def issue_id(self) -> str:
        """The Repair raised for it."""
        return issues.impossible_issue_id(
            self.translation_key, self.statistic_id, self.start
        )

    @property
    def cause(self) -> str:
        """What probably happened: ADR-0045's three causes, and ADR-0046's restart."""
        if self.restarted:
            return CAUSE_RESTARTED
        if self.change < 0:
            return CAUSE_FELL
        if self.reading and abs(self.change - self.reading) <= _COUNTED_AGAIN * abs(
            self.reading
        ):
            return CAUSE_COUNTED_AGAIN
        return CAUSE_JUMPED

    @property
    def corrected_at(self) -> datetime:
        """Where a correction is made: the five minutes it jumped in, or the hour."""
        if self.suggestion and self.suggestion.window:
            return self.suggestion.window
        return self.start

    def fix_data(self) -> dict[str, str | int | float | None]:
        """What the Repair's correction starts from (``repairs.py``)."""
        suggestion = self.suggestion or Suggestion(value=0.0)
        return {
            "statistic_id": self.statistic_id,
            "kind": self.kind,
            "unit": self.unit,
            "partner": self.partner,
            "start": self.start.isoformat(),
            "change": self.change,
            "ceiling": self.ceiling,
            "cause": self.cause,
            "corrected_at": self.corrected_at.isoformat(),
            "suggestion": self.suggestion.value if self.suggestion else None,
            "low": suggestion.low,
            "high": suggestion.high,
            "window": suggestion.window.isoformat() if suggestion.window else None,
            "jump": suggestion.jump,
            "rest": suggestion.rest,
            "energy": suggestion.energy,
            "price": suggestion.price,
        }


def checked_meters(entry: ConfigEntry) -> set[str]:
    """The meters the comparison reads (ADR-0044)."""
    grids = grid_meters_of(entry).values()
    meters = {grid.imported for grid in grids}
    meters |= {grid.exported for grid in grids if grid.exported}
    meters |= set(house_entities(entry.data, CONF_HOUSE_CONSUMPTION_ENTITY))
    meters |= set(house_entities(entry.data, CONF_GENERATION_ENTITY))
    for battery in batteries_of(entry).values():
        meters |= {meter for meter in (battery.charge, battery.discharge) if meter}
    return meters


def checked_statistics(
    entry: ConfigEntry,
    prefs: Any,  # noqa: ANN401 - untyped HA prefs
    cost_sensors: Mapping[str, str],
) -> dict[str, Checked]:
    """Every statistic the check reads (ADR-0045).

    The comparison's meters and the Energy Dashboard's, each once, and the
    Energy Dashboard's cost or compensation for each of its grid meters.
    """
    money = dashboard_money(prefs, cost_sensors)
    priced = {meter: statistic for statistic, meter in money.items()}
    meters = checked_meters(entry)
    for used in dashboard_meters(prefs).values():
        meters |= used
    checked = {
        meter: Checked(meter, ENERGY, priced.get(meter)) for meter in sorted(meters)
    }
    checked |= {
        statistic: Checked(statistic, MONEY, meter)
        for statistic, meter in money.items()
    }
    return checked


def impossible_hours(
    rows_by_statistic: Mapping[str, Iterable[Mapping[str, Any]]],
    checked: Mapping[str, Checked] | None = None,
    units: Mapping[str, str] | None = None,
) -> list[ImpossibleHour]:
    """Every hour a statistic changed by more than a home could use, or pay.

    Energy against the 100 kWh ceiling. Money against what 100 kWh could have
    cost at its meter's dearest real price that week, so it is found whether or
    not the meter's own hour has been corrected. A statistic's first row is
    never one: with nothing before it, the recorder gives its whole total as
    its change.
    """
    checked = checked or {meter: Checked(meter) for meter in rows_by_statistic}
    changes = {
        statistic: _changes(rows) for statistic, rows in rows_by_statistic.items()
    }
    found: list[ImpossibleHour] = []
    for statistic, what in sorted(checked.items()):
        rows = changes.get(statistic, [])
        if what.kind == ENERGY:
            found += _impossible_energy(statistic, rows, what.partner)
        elif what.partner is not None:
            found += _impossible_money(
                statistic,
                rows,
                changes.get(what.partner, []),
                what.partner,
                (units or {}).get(statistic, ""),
            )
    return found


@dataclass(frozen=True)
class _Row:
    """One row of a statistic: its change, reading and running total.

    `hours` is how long since the statistic's previous row began: 1 for an
    ordinary hour, more for the row that ends a gap, whose change covers all of
    it (ADR-0046).
    """

    moment: datetime
    change: float
    reading: float | None
    total: float | None
    hours: float

    @property
    def restarted(self) -> bool:
        """A fall to a running total of zero: the statistic starting again."""
        return (
            self.change < 0 and self.total is not None and abs(self.total) < _ZERO_TOTAL
        )

    def beyond(self, ceiling_per_hour: float) -> bool:
        """Whether the change is more than the ceiling allows (ADR-0046).

        A rise across the time since the previous row, since a gap's energy
        arrives in the row that ends it. A fall within its own hour: a counter
        never runs backwards, so a fall is never energy recorded late.
        """
        if self.change < 0:
            return -self.change > ceiling_per_hour
        return self.change > ceiling_per_hour * self.hours


def _changes(rows: Iterable[Mapping[str, Any]]) -> list[_Row]:
    """A statistic's rows in order, its first row left out.

    With nothing before it, the recorder gives the first row's whole total as
    its change.
    """
    ordered = sorted(rows, key=lambda row: _moment(row["start"]))
    found: list[_Row] = []
    for before, row in pairwise(ordered):
        if row.get("change") is None:
            continue
        moment = _moment(row["start"])
        found.append(
            _Row(
                moment,
                float(row["change"]),
                _optional(row.get("state")),
                _optional(row.get("sum")),
                (moment - _moment(before["start"])) / _HOUR,
            )
        )
    return found


def _optional(value: Any) -> float | None:  # noqa: ANN401 - a recorder field
    return None if value is None else float(value)


class _Hours:
    """A statistic's hours in time order, read a week either side at a time.

    Built once per statistic, so each hour's week is found by bisection rather
    than by scanning the whole history: a home with years of statistics was
    checked in billions of steps, on the event loop, and froze (GitHub #64).
    """

    def __init__(self, pairs: Iterable[tuple[datetime, float]]) -> None:
        ordered = sorted(pairs)
        self._moments = [moment for moment, _ in ordered]
        self._values = [value for _, value in ordered]
        self._dearest: list[list[float]] = []

    def _week(self, moment: datetime) -> tuple[int, int]:
        """The index range of the week either side of `moment`, both ends in."""
        return (
            bisect_left(self._moments, moment - _EITHER_SIDE),
            bisect_right(self._moments, moment + _EITHER_SIDE),
        )

    def around(self, moment: datetime) -> list[tuple[datetime, float]]:
        """Every hour of the week either side of `moment`, the hour itself left out."""
        low, high = self._week(moment)
        return [
            (self._moments[index], self._values[index])
            for index in range(low, high)
            if self._moments[index] != moment
        ]

    def dearest_around(self, moment: datetime) -> float | None:
        """The highest value in the week either side, the hour itself left out.

        From a sparse table built once: each look-up is two comparisons, so the
        whole history is checked in time linear in its hours.
        """
        low, high = self._week(moment)
        own = bisect_left(self._moments, moment, low, high)
        if own < high and self._moments[own] == moment:
            parts = [self._max(low, own), self._max(own + 1, high)]
        else:
            parts = [self._max(low, high)]
        found = [part for part in parts if part is not None]
        return max(found) if found else None

    def _max(self, low: int, high: int) -> float | None:
        """The highest value from `low` up to, not including, `high`."""
        if low >= high:
            return None
        if not self._dearest:
            self._dearest = [self._values]
            width = 1
            while width * 2 <= len(self._values):
                last = self._dearest[-1]
                self._dearest.append(
                    [
                        max(last[index], last[index + width])
                        for index in range(len(last) - width)
                    ]
                )
                width *= 2
        level = (high - low).bit_length() - 1
        row = self._dearest[level]
        return max(row[low], row[high - (1 << level)])


def _ordinary(rows: list[_Row], impossible: set[datetime]) -> _Hours:
    """The hours a typical hour is read from: whole hours, none impossible."""
    return _Hours(
        (row.moment, row.change)
        for row in rows
        if row.hours == 1 and row.moment not in impossible
    )


def _impossible_energy(
    meter: str, rows: list[_Row], partner: str | None
) -> list[ImpossibleHour]:
    impossible = {row.moment for row in rows if row.beyond(IMPOSSIBLE_KWH_PER_HOUR)}
    ordinary = _ordinary(rows, impossible)
    return [
        ImpossibleHour(
            meter,
            row.moment,
            row.change,
            row.reading,
            Suggestion(value=0.0)
            if row.restarted
            else suggestion_from_days(row.moment, ordinary),
            partner=partner,
            restarted=row.restarted,
        )
        for row in rows
        if row.moment in impossible
    ]


def _impossible_money(
    statistic: str,
    rows: list[_Row],
    meter_rows: list[_Row],
    meter: str,
    unit: str,
) -> list[ImpossibleHour]:
    """A cost's impossible hours, each judged against its meter's prices."""
    energy = {row.moment: row for row in meter_rows}
    meter_ordinary = _ordinary(
        meter_rows,
        {row.moment for row in meter_rows if row.beyond(IMPOSSIBLE_KWH_PER_HOUR)},
    )
    prices = _Hours(
        (row.moment, row.change / energy[row.moment].change)
        for row in rows
        if row.hours == 1
        and row.moment in energy
        and energy[row.moment].hours == 1
        and not energy[row.moment].beyond(IMPOSSIBLE_KWH_PER_HOUR)
        and abs(energy[row.moment].change) >= _PRICED_FROM_KWH
    )
    kwh = {moment: each.change for moment, each in energy.items()}
    whole_hours = _Hours((row.moment, row.change) for row in rows if row.hours == 1)
    found: list[ImpossibleHour] = []
    for row in rows:
        dearest = prices.dearest_around(row.moment)
        if dearest is None or dearest <= 0:
            continue
        ceiling = IMPOSSIBLE_KWH_PER_HOUR * dearest
        if not row.beyond(ceiling):
            continue
        suggestion = (
            Suggestion(value=0.0)
            if row.restarted
            else _suggested_cost(
                row.moment,
                row.change,
                energy=kwh,
                meter_ordinary=meter_ordinary,
                prices=prices,
                ordinary=whole_hours,
            )
        )
        found.append(
            ImpossibleHour(
                statistic,
                row.moment,
                row.change,
                row.reading,
                suggestion,
                kind=MONEY,
                unit=unit,
                partner=meter,
                ceiling=ceiling,
                restarted=row.restarted,
            )
        )
    return found


def _suggested_cost(  # noqa: PLR0913 - the hour with its meter and the prices around it
    moment: datetime,
    change: float,
    *,
    energy: Mapping[datetime, float],
    meter_ordinary: _Hours,
    prices: _Hours,
    ordinary: _Hours,
) -> Suggestion | None:
    """The hour's energy as it now stands, at the hour's price (ADR-0045).

    While the meter's hour is still impossible, its own suggestion is the
    energy, and the price is the faulty hour's own: a glitch is priced at the
    hour's real price. Once the meter's hour is corrected, the price is the
    median of the same hour's prices either side. Failing both, the same hour's
    cost on the days either side.
    """
    kwh_now = energy.get(moment)
    if kwh_now is not None and _beyond(kwh_now):
        fixed = suggestion_from_days(moment, meter_ordinary)
        if fixed is not None and kwh_now:
            price = change / kwh_now
            return Suggestion(
                value=_rounded(fixed.value * price), energy=fixed.value, price=price
            )
    elif kwh_now is not None:
        hour = dt_util.as_local(moment).hour
        same_hour = [
            price
            for other, price in prices.around(moment)
            if dt_util.as_local(other).hour == hour
        ]
        if len(same_hour) >= _FEWEST_SIMILAR_HOURS:
            price = median(same_hour)
            return Suggestion(
                value=_rounded(kwh_now * price), energy=kwh_now, price=price
            )
    return suggestion_from_days(moment, ordinary)


def suggestion_from_days(moment: datetime, ordinary: _Hours) -> Suggestion | None:
    """The same hour of the day over the week either side: its median and range.

    In local time, so the hour is the household's own routine across a change of
    the clocks. Nothing where there are too few such hours to go on.
    """
    local = dt_util.as_local(moment)
    similar = [
        change
        for other, change in ordinary.around(moment)
        if dt_util.as_local(other).hour == local.hour
    ]
    if len(similar) < _FEWEST_SIMILAR_HOURS:
        return None
    return Suggestion(
        value=_rounded(median(similar)),
        low=_rounded(min(similar)),
        high=_rounded(max(similar)),
    )


def suggestion_from_window(
    rows: Iterable[Mapping[str, Any]],
    ceiling: float = IMPOSSIBLE_KWH_PER_HOUR,
) -> Suggestion | None:
    """The hour as its five-minute statistics show it, without the jump.

    A fault is one big jump in a small window. The rest of the hour is taken as
    recorded, and the window as a typical one of the others: their median.
    Nothing where no window is beyond the hourly ceiling's rate, or none is
    kept.
    """
    windows = [
        (_moment(row["start"]), float(row["change"]))
        for row in rows
        if row.get("change") is not None
    ]
    if not windows:
        return None
    window, jump = max(windows, key=lambda each: abs(each[1]))
    if abs(jump) <= ceiling * (_FIVE_MINUTES / _HOUR):
        return None
    others = [change for moment, change in windows if moment != window]
    rest = sum(others)
    typical = median(others) if others else 0.0
    return Suggestion(
        value=_rounded(rest + typical),
        window=window,
        jump=round(jump, 3),
        rest=_rounded(rest),
    )


async def async_check(hass: HomeAssistant, entry: ConfigEntry) -> list[ImpossibleHour]:
    """Raise a Repair for every impossible hour, and clear those no longer found."""
    if RECORDER_DOMAIN not in hass.config.components:
        return []
    prefs = await async_energy_prefs(hass)
    cost_sensors = hass.data.get("energy", {}).get("cost_sensors", {})
    checked = checked_statistics(entry, prefs, cost_sensors)
    recorder = get_instance(hass)
    rows = await recorder.async_add_executor_job(_hourly_history, hass, set(checked))
    units = await recorder.async_add_executor_job(
        _money_units, hass, {s for s, what in checked.items() if what.kind == MONEY}
    )
    # Worked out in an executor job: years of history is real work, and on the
    # event loop it froze Home Assistant (GitHub #64).
    hours = await hass.async_add_executor_job(impossible_hours, rows, checked, units)
    found = []
    for hour in hours:
        windows = await recorder.async_add_executor_job(
            _five_minutes_of, hass, hour.statistic_id, hour.start, hour.kind
        )
        precise = suggestion_from_window(windows, hour.ceiling)
        found.append(hour if precise is None else replace(hour, suggestion=precise))
    _clear_answered(hass, {hour.issue_id for hour in found})
    for hour in found:
        issues.async_ask(
            hass,
            hour.issue_id,
            hour.translation_key,
            {
                "sensor": sensor_name(hass, hour.statistic_id),
                "when": when(hour.start),
                "recorded": amount(hour.change, hour.unit),
            },
            hour.fix_data(),
        )
    return found


def _clear_answered(hass: HomeAssistant, raised: set[str]) -> None:
    """Withdraw every Repair from an earlier check whose hour is no longer found."""
    for key in (issues.ISSUE_IMPOSSIBLE_HOUR, issues.ISSUE_IMPOSSIBLE_COST):
        for subject in issues.async_raised_subjects(hass, key):
            if (issue_id := f"{key}_{subject}") not in raised:
                issues.async_clear(hass, issue_id)


@callback
def async_start(hass: HomeAssistant, entry: ConfigEntry) -> Callable[[], None]:
    """Check a few minutes after setup, then once a day. Returns the cancel."""

    async def check(_now: datetime) -> None:
        await async_check(hass, entry)

    first = async_call_later(hass, _FIRST_CHECK, check)
    daily = async_track_time_interval(hass, check, _EVERY)

    @callback
    def cancel() -> None:
        first()
        daily()

    return cancel


def sensor_name(hass: HomeAssistant, entity_id: str) -> str:
    """A statistic as a household finds it: its name, and its entity ID."""
    state = hass.states.get(entity_id)
    name = state.name if state else None
    return f"{name} ({entity_id})" if name and name != entity_id else entity_id


def when(start: datetime) -> str:
    """An hour as the household's clock gives it, unambiguous in any language."""
    return dt_util.as_local(start).strftime("%Y-%m-%d %H:%M")


def amount(value: float, unit: str = _KWH) -> str:
    """A figure as the Repair states it: kWh, or the statistic's currency."""
    return f"{value:.2f} {unit}".rstrip()


def kwh(value: float) -> str:
    """Energy as the Repair states it."""
    return amount(value, _KWH)


def _beyond(kwh_change: float) -> bool:
    return abs(kwh_change) > IMPOSSIBLE_KWH_PER_HOUR


def _rounded(value: float) -> float:
    """A suggested figure to three places, never below nothing.

    Rounded because it is typed into a form: sums of readings carry float noise
    a household should not be asked to read.
    """
    return max(0.0, round(value, 3))


def _hourly_history(hass: HomeAssistant, statistics: set[str]) -> Mapping[str, Any]:
    """Each statistic's hourly change and reading over all its history. A read."""
    return statistics_during_period(
        hass,
        _EVER,
        dt_util.utcnow(),
        statistics,
        "hour",
        _IN_KWH,
        {"change", "state", "sum"},
    )


def _money_units(hass: HomeAssistant, statistics: set[str]) -> dict[str, str]:
    """Each money statistic's currency, as its metadata names it. A read."""
    if not statistics:
        return {}
    metadata = get_metadata(hass, statistic_ids=statistics)
    return {
        statistic: meta.get("unit_of_measurement") or ""
        for statistic, (_, meta) in metadata.items()
    }


def _five_minutes_of(
    hass: HomeAssistant, statistic_id: str, start: datetime, kind: str
) -> list[Mapping[str, Any]]:
    """A statistic's five-minute changes within one hour, where still kept."""
    rows = statistics_during_period(
        hass,
        start,
        start + _HOUR,
        {statistic_id},
        "5minute",
        _IN_KWH if kind == ENERGY else None,
        {"change"},
    )
    return list(rows.get(statistic_id, []))


def _moment(start: float | datetime) -> datetime:
    """A statistics row's start, which the recorder gives as a UTC timestamp."""
    if isinstance(start, datetime):
        return start.astimezone(UTC)
    return datetime.fromtimestamp(start, UTC)
