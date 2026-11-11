"""Every tariff plan priced against the household's recorded grid flows (ADR-0036).

Asked for by the plan comparison card, for whatever period its picker shows. The
hourly change of every grid import and export meter entered is read from Home
Assistant's long-term statistics and summed across registers; each plan's
holidays are read from the calendar it names; and the engine prices each plan
at the same hours. Nothing read here is a figure of this integration's own, so
any period the statistics reach can be compared, past months included.

A plan importing or exporting at a market price is priced from that price
entity's own statistics (ADR-0037). Every plan is then priced five minutes at a
time from the first whole hour the recorder still keeps 5-minute statistics
for, and hour by hour before it; an interval with no price carries the last one,
and a plan is priced only from the market's first recorded price.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.decorators import (
    async_response,
    websocket_command,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfEnergy
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import (
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)
from .engine.plan_pricing import IntervalOfEnergy, PlanCost, days_covered, price_plan
from .house_inputs import grid_meters_of
from .schemas import vol
from .tariff_plans import TariffPlan, plans_of

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.components.websocket_api.connection import ActiveConnection
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

COMPARE_PLANS = f"{DOMAIN}/compare_plans"
LIST_PLANS = f"{DOMAIN}/list_plans"
_REGISTERED = f"{DOMAIN}_compare_plans_registered"
# Figures go to the card as numbers, to a ten-thousandth: finer than any
# currency shows, and the card rounds for display.
_SHOWN = Decimal("0.0001")
_HOUR = timedelta(hours=1)
_FIVE_MINUTES = timedelta(minutes=5)
# How far before the period a market price is looked for, so a gap at its very
# start carries the price before it rather than leaving the plan unpriced.
_LOOKBACK = timedelta(days=1)
# Before anything the recorder can hold, for asking when a statistic begins.
_EVER = datetime(2000, 1, 1, tzinfo=UTC)
_ENERGY_UNITS = {str(unit) for unit in UnitOfEnergy}
# The two resolutions the recorder keeps that a comparison reads.
_Period = Literal["5minute", "hour"]


@dataclass(frozen=True)
class _Recorded:
    """The grid flows of a period, and from when they are five minutes apart."""

    intervals: list[IntervalOfEnergy]
    five_minute_from: datetime | None = None

    def length_of(self, interval: IntervalOfEnergy) -> timedelta:
        fine = self.five_minute_from is not None and interval.start >= (
            self.five_minute_from
        )
        return _FIVE_MINUTES if fine else _HOUR


@dataclass(frozen=True)
class _AtMarket:
    """A plan's intervals with the market prices it is charged at.

    `priced_from` is where the market's prices began, when that was after the
    first interval; `carried` is how long was priced at a price carried over a
    gap. `unpriced` is a plan needing a market price no interval had.
    """

    intervals: list[IntervalOfEnergy]
    priced_from: datetime | None = None
    carried: timedelta = timedelta(0)
    unpriced: bool = False


def async_register(hass: HomeAssistant) -> None:
    """Offer the comparison to the card, once however many times setup runs."""
    if hass.data.get(_REGISTERED):
        return
    async_register_command(hass, _websocket_compare_plans)
    async_register_command(hass, _websocket_list_plans)
    hass.data[_REGISTERED] = True


@websocket_command({vol.Required("type"): LIST_PLANS})
@callback
def _websocket_list_plans(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """The plans entered, without pricing them.

    For the dashboard, which shows the comparison only where there is a plan to
    compare and must not read a year of statistics to find that out. Plans are
    entries rather than entities, and reading entries through Home Assistant's
    own commands needs an administrator, which a household member opening the
    dashboard need not be.
    """
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    plans = plans_of(entries[0]) if entries else {}
    connection.send_result(
        msg["id"],
        {
            "plans": [
                {"id": plan_id, "name": tariff.plan.name, "current": tariff.current}
                for plan_id, tariff in plans.items()
            ]
        },
    )


@websocket_command(
    {
        vol.Required("type"): COMPARE_PLANS,
        vol.Required("start_time"): str,
        vol.Required("end_time"): str,
    }
)
@async_response
async def _websocket_compare_plans(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Price every plan over the period the card asks about."""
    start = dt_util.parse_datetime(msg["start_time"])
    end = dt_util.parse_datetime(msg["end_time"])
    if start is None or end is None or end <= start:
        connection.send_error(
            msg["id"],
            "invalid_format",
            "start_time and end_time must be times, in order",
        )
        return
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        connection.send_error(
            msg["id"], "not_loaded", "Home Energy Advisor is not set up"
        )
        return
    connection.send_result(
        msg["id"], await async_compare_plans(hass, entries[0], start, end)
    )


async def async_compare_plans(
    hass: HomeAssistant, entry: ConfigEntry, start: datetime, end: datetime
) -> dict[str, Any]:
    """Every plan's cost over the period, beside what the meters recorded."""
    meters = grid_meters_of(entry).values()
    imports = {grid.imported for grid in meters}
    exports = {grid.exported for grid in meters if grid.exported}
    tariffs = plans_of(entry)
    markets = {
        entity
        for tariff in tariffs.values()
        for entity in (tariff.import_entity, tariff.export_entity)
        if entity
    }
    # Five minutes at a time only where a market price changes within the hour:
    # a band prices five minutes exactly as it prices their hour.
    recorded = await _recorded_flows(
        hass, imports, exports, start, end, five_minutes=bool(markets)
    )
    prices = await _market_prices(hass, markets, start, end, recorded.five_minute_from)
    at_market = {
        plan_id: _at_market_prices(recorded, tariff, prices)
        for plan_id, tariff in tariffs.items()
    }
    span = _common_span(start, recorded, tariffs, at_market)
    intervals = span.of(recorded.intervals)
    # Charged up to now at most: the picker's Today runs to midnight, and a whole
    # day's charge against half a day's energy would make every total read high.
    charged_until = max(span.start, min(end, dt_util.utcnow()))
    days = days_covered(dt_util.as_local(span.start), dt_util.as_local(charged_until))
    plans = []
    for plan_id, tariff in tariffs.items():
        named = {
            "id": plan_id,
            "name": tariff.plan.name,
            "current": tariff.current,
            "rates": _rates(tariff),
        }
        holidays = (
            await _holidays(hass, tariff.holidays, start, end)
            if tariff.holidays
            else frozenset()
        )
        market = at_market[plan_id]
        if market.unpriced:
            plans.append({**named, "no_price": True})
            continue
        try:
            cost = price_plan(
                tariff.plan, span.of(market.intervals), days=days, holidays=holidays
            )
        except ValueError:
            # Only a plan edited outside its form can leave hours unpriced; it is
            # listed, not guessed at.
            plans.append({**named, "incomplete": True})
            continue
        plans.append({**named, **_figures(cost), **_market_notes(tariff, market)})
    return {
        "hours": len(intervals),
        "days": float(days),
        "imported_kwh": _number(sum((i.imported_kwh for i in intervals), Decimal(0))),
        "exported_kwh": _number(sum((i.exported_kwh for i in intervals), Decimal(0))),
        "five_minute_from": _when(recorded.five_minute_from),
        "compared_from": _when(span.start) if span.start > start else None,
        "compared_from_plan": span.set_by,
        "plans": plans,
    }


@dataclass(frozen=True)
class _Span:
    """From when every plan is compared, and which plan's prices set it, if one did."""

    start: datetime
    set_by: str | None = None

    def of(self, intervals: list[IntervalOfEnergy]) -> list[IntervalOfEnergy]:
        """The intervals that fall within the span."""
        return [interval for interval in intervals if interval.start >= self.start]


def _common_span(
    start: datetime,
    recorded: _Recorded,
    tariffs: Mapping[str, TariffPlan],
    at_market: Mapping[str, _AtMarket],
) -> _Span:
    """From when all the plans can be priced: the one span every plan is priced over.

    A plan at a market price can only be priced from its price's first recorded
    hour, and no plan from before the grid meters' first. Priced each from its
    own start, a year's comparison charged one plan 315 days of daily charges
    and another two, and the cheapest was whichever had the least history
    (HEA-294, discussion 58). So the latest of those starts holds for every plan.

    A plan with no price at all in the period does not shorten it for the others:
    it is listed without a total.
    """
    span = _Span(start)
    if recorded.intervals and recorded.intervals[0].start > start:
        span = _Span(recorded.intervals[0].start)
    for plan_id, market in at_market.items():
        begins = market.priced_from
        if begins is not None and not market.unpriced and begins > span.start:
            span = _Span(begins, tariffs[plan_id].plan.name)
    return span


async def async_plan_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Every plan as entered, and what its market prices are, for the download.

    A comparison could not be checked without them (HEA-276, discussion 58).
    The settings are carried exactly as the household entered them rather than
    as read: with the recorded statistics they reproduce every figure the card
    shows, and a plan that cannot be read at all still appears. Its figures are
    left out, because they depend on the period the card asks about.

    Each market price entity says what it is and the first hour its mean was
    recorded at - the one statistic a plan is priced from - so a feed the
    recorder keeps nothing for shows up at once.
    """
    entered = {
        subentry_id: subentry
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_PLAN
    }
    entities = sorted(
        {
            entity
            for subentry in entered.values()
            for key in (CONF_PLAN_IMPORT_PRICE_ENTITY, CONF_PLAN_EXPORT_PRICE_ENTITY)
            if (entity := subentry.data.get(key))
        }
    )
    first = await _first_means(hass, set(entities))
    return {
        "plans": [
            {
                "id": subentry_id,
                "title": subentry.title,
                "settings": dict(subentry.data),
            }
            for subentry_id, subentry in entered.items()
        ],
        "market_entities": {
            entity: _market_entity(hass, entity, first.get(entity))
            for entity in entities
        },
    }


def _market_entity(
    hass: HomeAssistant, entity: str, first_mean: datetime | None
) -> dict[str, Any]:
    """What a market price entity reads, in what, and since when it is priced."""
    state = hass.states.get(entity)
    attributes = state.attributes if state else {}
    return {
        "state": state.state if state else None,
        "unit": attributes.get(ATTR_UNIT_OF_MEASUREMENT),
        "state_class": attributes.get("state_class"),
        "mean_statistics_from": _when(first_mean),
    }


async def _first_means(hass: HomeAssistant, entities: set[str]) -> dict[str, datetime]:
    """The first hour each entity's mean was recorded at, where it ever was."""
    if RECORDER_DOMAIN not in hass.config.components or not entities:
        return {}
    means = await get_instance(hass).async_add_executor_job(
        _means, hass, entities, _EVER, dt_util.utcnow(), "hour"
    )
    return {entity: _moment(rows[0]["start"]) for entity, rows in means.items() if rows}


def _rates(tariff: TariffPlan) -> dict[str, Any]:
    """A plan's own prices, for the card to list beside what it cost (HEA-280).

    Each named price once, in the order its bands first use it, as an offer
    lists its periods. Per kWh, and the daily charge per day, as entered. A plan
    entered before prices had names carries its figures on each band, so an
    unnamed price is told apart by its figures rather than all read as one.
    """
    prices: dict[object, dict[str, Any]] = {}
    for band in tariff.plan.bands:
        prices.setdefault(
            band.name or (band.import_price, band.export_price),
            {
                "name": band.name,
                "import": _number(band.import_price),
                "export": None
                if band.export_price is None
                else _number(band.export_price),
            },
        )
    return {
        "prices": list(prices.values()),
        "export": _number(tariff.plan.export_price),
        "daily_charge": _number(tariff.plan.daily_charge),
        "import_market": tariff.import_entity is not None,
        "export_market": tariff.export_entity is not None,
    }


def _market_notes(tariff: TariffPlan, market: _AtMarket) -> dict[str, Any]:
    """What a market-priced plan's figures rest on, for the card to say.

    Where its prices start is the comparison's, not the plan's: every plan is
    priced from the same hour (`_common_span`, HEA-294).
    """
    if not (tariff.import_entity or tariff.export_entity):
        return {}
    return {"carried_hours": round(market.carried / _HOUR, 2)}


def _when(moment: datetime | None) -> str | None:
    return None if moment is None else moment.astimezone(UTC).isoformat()


def _figures(cost: PlanCost) -> dict[str, float]:
    return {
        "energy": _number(cost.energy),
        "export_credit": _number(cost.export_credit),
        "daily_charges": _number(cost.daily_charges),
        "total": _number(cost.total),
        # What a capped plan did not pay for export, or carried and left unused,
        # so the card can say why a high export price helped less (HEA-258).
        "export_unpaid": _number(cost.export_unpaid),
        "export_carried": _number(cost.export_carried),
    }


def _number(value: Decimal) -> float:
    return float(value.quantize(_SHOWN))


async def _recorded_flows(  # noqa: PLR0913 - the meters and period and how finely to read them
    hass: HomeAssistant,
    imports: set[str],
    exports: set[str],
    start: datetime,
    end: datetime,
    *,
    five_minutes: bool,
) -> _Recorded:
    """Each recorded interval's grid import and export, summed across meters.

    Hourly, unless `five_minutes`: then five minutes at a time from the first
    whole hour the recorder still holds 5-minute statistics for. An interval
    none of the meters recorded is left out rather than priced as nothing; the
    caller says how many there were.
    """
    if RECORDER_DOMAIN not in hass.config.components or not imports | exports:
        return _Recorded([])
    meters = imports | exports
    recorder = get_instance(hass)
    hourly = await recorder.async_add_executor_job(
        _changes, hass, meters, start, end, "hour"
    )
    fine = (
        await recorder.async_add_executor_job(
            _changes, hass, meters, start, end, "5minute"
        )
        if five_minutes
        else {}
    )
    five_minute_from = _first_whole_hour(fine)

    def kept(moment: datetime, *, is_fine: bool) -> bool:
        if five_minute_from is None:
            return not is_fine
        return (moment >= five_minute_from) is is_fine

    imported = _summed(hourly, imports, kept, is_fine=False) | _summed(
        fine, imports, kept, is_fine=True
    )
    exported = _summed(hourly, exports, kept, is_fine=False) | _summed(
        fine, exports, kept, is_fine=True
    )
    return _Recorded(
        [
            IntervalOfEnergy(
                start=dt_util.as_local(moment),
                imported_kwh=imported.get(moment, Decimal(0)),
                exported_kwh=exported.get(moment, Decimal(0)),
            )
            for moment in sorted(imported.keys() | exported.keys())
        ],
        five_minute_from,
    )


def _changes(
    hass: HomeAssistant,
    statistic_ids: set[str],
    start: datetime,
    end: datetime,
    period: _Period,
) -> Mapping[str, list[Any]]:
    """The recorder's change per `period` for each meter, in kWh. A database read."""
    return statistics_during_period(
        hass,
        start,
        end,
        statistic_ids,
        period,
        {"energy": "kWh"},
        {"change"},
    )


def _first_whole_hour(
    changes: Mapping[str, Iterable[Mapping[str, Any]]],
) -> datetime | None:
    """The first whole hour these 5-minute statistics cover, if any."""
    starts = [_moment(row["start"]) for rows in changes.values() for row in rows]
    if not starts:
        return None
    earliest = min(starts)
    hour = earliest.replace(minute=0, second=0, microsecond=0)
    return hour if hour == earliest else hour + _HOUR


def _summed(
    changes: Mapping[str, Iterable[Mapping[str, Any]]],
    meters: set[str],
    kept: Any,  # noqa: ANN401 - the caller's choice of interval
    *,
    is_fine: bool,
) -> dict[datetime, Decimal]:
    """Each interval's change, added up across these meters, where `kept`."""
    total: dict[datetime, Decimal] = defaultdict(Decimal)
    for meter in meters:
        for row in changes.get(meter, ()):
            change = row.get("change")
            moment = _moment(row["start"])
            if change is None or not kept(moment, is_fine=is_fine):
                continue
            total[moment] += Decimal(str(change))
    return dict(total)


async def _market_prices(
    hass: HomeAssistant,
    entities: set[str],
    start: datetime,
    end: datetime,
    five_minute_from: datetime | None,
) -> dict[str, dict[datetime, Decimal]]:
    """Each market price entity's mean price per interval, per kWh.

    Hourly means before `five_minute_from` (from a day before the period, so a
    gap at its start carries the price before it) and 5-minute means from it.
    """
    if RECORDER_DOMAIN not in hass.config.components or not entities:
        return {}
    recorder = get_instance(hass)
    hourly = await recorder.async_add_executor_job(
        _means, hass, entities, start - _LOOKBACK, five_minute_from or end, "hour"
    )
    fine = (
        await recorder.async_add_executor_job(
            _means, hass, entities, five_minute_from, end, "5minute"
        )
        if five_minute_from is not None
        else {}
    )
    prices: dict[str, dict[datetime, Decimal]] = {}
    for entity in entities:
        per_kwh = _per_kwh(hass, entity)
        prices[entity] = {
            _moment(row["start"]): Decimal(str(row["mean"])) * per_kwh
            for rows in (hourly.get(entity, ()), fine.get(entity, ()))
            for row in rows
            if row.get("mean") is not None
        }
    return prices


def _means(
    hass: HomeAssistant,
    statistic_ids: set[str],
    start: datetime,
    end: datetime,
    period: _Period,
) -> Mapping[str, list[Any]]:
    """The recorder's mean per `period` for each price entity. A database read."""
    return statistics_during_period(
        hass,
        start,
        end,
        statistic_ids,
        period,
        None,
        {"mean"},
    )


def _per_kwh(hass: HomeAssistant, entity: str) -> Decimal:
    """What a price entity's figure is multiplied by to be per kWh.

    As the Energy Dashboard reads a price: the unit after the `/` is the energy
    it is per, and anything else (no unit, or one that is not energy) is taken
    as per kWh.
    """
    state = hass.states.get(entity)
    unit = str(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, "")) if state else ""
    energy = unit.partition("/")[2]
    if energy not in _ENERGY_UNITS:
        return Decimal(1)
    return Decimal(
        str(EnergyConverter.convert(1.0, UnitOfEnergy.KILO_WATT_HOUR, energy))
    )


def _at_market_prices(
    recorded: _Recorded,
    tariff: TariffPlan,
    prices: Mapping[str, Mapping[datetime, Decimal]],
) -> _AtMarket:
    """The plan's intervals, each with the market prices the plan follows.

    An interval with no price of its own carries the last one before it. Until
    every price the plan follows has been recorded once there is nothing to
    carry, so those intervals are left out and the plan priced from then.
    """
    entities = [e for e in (tariff.import_entity, tariff.export_entity) if e]
    if not entities:
        return _AtMarket(recorded.intervals)
    first = recorded.intervals[0].start if recorded.intervals else None
    last = {e: _last_before(prices.get(e, {}), first) for e in entities}
    priced: list[IntervalOfEnergy] = []
    carried = timedelta(0)
    left_out = False
    for interval in recorded.intervals:
        moment = interval.start.astimezone(UTC)
        own = {e: prices.get(e, {}).get(moment) for e in entities}
        last |= {entity: price for entity, price in own.items() if price is not None}
        if any(last[entity] is None for entity in entities):
            left_out = True
            continue
        if any(price is None for price in own.values()):
            carried += recorded.length_of(interval)
        priced.append(
            replace(
                interval,
                import_price=last[tariff.import_entity]
                if tariff.import_entity
                else None,
                export_price=last[tariff.export_entity]
                if tariff.export_entity
                else None,
            )
        )
    return _AtMarket(
        priced,
        priced_from=priced[0].start if priced and left_out else None,
        carried=carried,
        unpriced=left_out and not priced,
    )


def _last_before(
    prices: Mapping[datetime, Decimal], moment: datetime | None
) -> Decimal | None:
    """The latest price recorded before `moment`, if any."""
    if moment is None:
        return None
    earlier = [at for at in prices if at < moment.astimezone(UTC)]
    return prices[max(earlier)] if earlier else None


def _moment(start: float | datetime) -> datetime:
    """A statistics row's start, which the recorder gives as a UTC timestamp."""
    if isinstance(start, datetime):
        return start.astimezone(UTC)
    return datetime.fromtimestamp(start, UTC)


async def _holidays(
    hass: HomeAssistant, calendar: str, start: datetime, end: datetime
) -> frozenset[date]:
    """Every date an all-day event in `calendar` covers within the period.

    Read through the calendar's own action, which answers for past dates. A
    calendar that is gone or cannot answer leaves the plan with no holidays,
    so its holidays are priced as the weekdays they fall on, as without one.
    """
    try:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": calendar,
                "start_date_time": start.isoformat(),
                "end_date_time": end.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError:
        return frozenset()
    answer = (response or {}).get(calendar)
    events = answer.get("events") if isinstance(answer, dict) else None
    if not isinstance(events, list):
        return frozenset()
    return frozenset(
        day
        for event in events
        if isinstance(event, dict)
        for day in _all_day_dates(event)
    )


def _all_day_dates(event: Mapping[str, Any]) -> list[date]:
    """The dates an all-day event covers, its end exclusive; none for a timed one."""
    start, end = str(event.get("start", "")), str(event.get("end", ""))
    if "T" in start or "T" in end:
        return []
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return []
    return [first + timedelta(days=n) for n in range((last - first).days)]
