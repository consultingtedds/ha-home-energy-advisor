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
for, and hour by hour before it.

A stretch with no data - no grid statistics, or no price for a market price a
plan follows - is bridged where it is two hours or less, a missing price
carrying the last one. A longer one is left out for every plan, its daily
charges with it, and said (ADR-0043). A price sensor only the current plan
follows is the exception: its gaps are the current plan's alone, each hour
priced at the plan the household was on that day, or leaving it unpriced
(HEA-311, HEA-307). The same plans price a shared sensor that recorded nothing
in the period.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field, replace
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
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import (
    CONF_GENERATION_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PERIOD_FROM,
    CONF_PERIOD_PLAN,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PLAN_PERIODS,
    DOMAIN,
    IMPOSSIBLE_KWH_PER_HOUR,
    SERVICE_COMPARE_PLANS,
    SUBENTRY_TYPE_PLAN,
)
from .current_plan import current_plan_of
from .energy_dashboard import async_energy_prefs, export_price_in, grid_import_costs
from .engine.plan_pricing import (
    ExportCap,
    IntervalOfEnergy,
    Plan,
    PlanCost,
    PriceLine,
    days_covered,
    price_plan,
)
from .engine.plan_schedule import export_price_at, follows_the_clock, import_price_at
from .house_inputs import GridMeter, batteries_of, grid_meters_of, house_entities
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
# The longest stretch with no data that is bridged rather than left out: a
# restart, a late publish, a missed statistics hour (ADR-0043). A market price
# is looked for this far before the period too, to carry into its start.
_BRIDGE = timedelta(hours=2)
# What a stretch with no grid statistics is left out for, beside a price entity.
_GRID_METERS = "grid"
# Not an entity: the current plan's import price per interval, every grid meter
# at its own, worked out here (ADR-0042).
_PAID_IMPORT = f"{DOMAIN}.paid_import"
# Nor this: its export price per interval, where a price sensor gives it.
_PAID_EXPORT = f"{DOMAIN}.paid_export"
# A change beyond it, either way, is a fault in the statistics, and its interval
# is left out (ADR-0044).
_CEILING_PER_HOUR = Decimal(IMPOSSIBLE_KWH_PER_HOUR)
# Before anything the recorder can hold, for asking when a statistic begins.
_EVER = datetime(2000, 1, 1, tzinfo=UTC)
_ENERGY_UNITS = {str(unit) for unit in UnitOfEnergy}
# The two resolutions the recorder keeps that a comparison reads.
_Period = Literal["5minute", "hour"]


@dataclass(frozen=True)
class _Recorded:
    """The grid flows of a period, and from when they are five minutes apart.

    With the intervals a grid meter recorded more than a home could use in, and
    each import meter's own change per interval, which the current plan prices
    at that meter's own price (ADR-0042).
    """

    intervals: list[IntervalOfEnergy]
    five_minute_from: datetime | None = None
    impossible: tuple[_Stretch, ...] = ()
    imported_by_meter: Mapping[str, Mapping[datetime, Decimal]] = field(
        default_factory=dict
    )

    def length_at(self, moment: datetime) -> timedelta:
        """How long a statistic starting at `moment` covers: an hour, or 5 minutes."""
        fine = self.five_minute_from is not None and moment >= self.five_minute_from
        return _FIVE_MINUTES if fine else _HOUR


@dataclass(frozen=True)
class _Stretch:
    """A stretch left out of every plan, and what had no data for it.

    Or, with `kwh`, the meter that recorded that much in it: more than a home
    could use (ADR-0044).
    """

    start: datetime
    end: datetime
    source: str
    kwh: Decimal | None = None

    def overlaps(self, start: datetime, length: timedelta) -> bool:
        return start < self.end and start + length > self.start


@dataclass(frozen=True)
class _Paid:
    """The prices Paid is priced at, which the current plan follows (ADR-0042).

    Each grid meter's own import price, the Energy Dashboard's export price, and
    the current plan's billing rules: its daily charge, typed or the recorded
    cost of the Energy Dashboard grid source the household enters it as, and its
    export cap.
    """

    plan_id: str
    name: str
    rules: Mapping[str, Any]
    meters: tuple[GridMeter, ...]
    export_entity: str | None
    export_number: Decimal | None
    # The statistic the followed grid source's cost is recorded in, if it has one.
    daily_statistic: str | None = None
    # The plans the household has been on, whose prices stand in where the
    # price sensors have no statistics: each from its local day, or from always,
    # by subentry id, earliest first (HEA-311, HEA-307).
    periods: tuple[tuple[date | None, str], ...] = ()

    @property
    def entities(self) -> set[str]:
        """Every price entity it follows, each read from its statistics."""
        followed = {meter.price_entity for meter in self.meters if meter.price_entity}
        return followed | ({self.export_entity} if self.export_entity else set())

    async def daily_charge(self, hass: HomeAssistant, basis: _Basis) -> Decimal | None:
        """Its daily charge: as typed, or what its source cost a day, compared.

        A followed source's recorded cost in the hours compared, over the days
        they make, so the hours left out take their share with them.
        """
        if (typed := self.rules.get(CONF_PLAN_DAILY_CHARGE)) is not None:
            return Decimal(str(typed))
        if self.daily_statistic is None or not basis.days:
            return None
        rows = await get_instance(hass).async_add_executor_job(
            _changes, hass, {self.daily_statistic}, basis.start, basis.end, "hour"
        )
        hours = {
            interval.start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            for interval in basis.intervals
        }
        costs = [
            Decimal(str(row["change"]))
            for row in rows.get(self.daily_statistic, ())
            if row.get("change") is not None and _moment(row["start"]) in hours
        ]
        return sum(costs, Decimal(0)) / basis.days if costs else None

    def tariff(self, daily_charge: Decimal | None) -> TariffPlan:
        """The current plan as the engine prices it: every interval at its price."""
        return TariffPlan(
            plan=Plan(
                name=self.name,
                bands=(),
                daily_charge=daily_charge or Decimal(0),
                export_price=self.export_number or Decimal(0),
                import_per_interval=True,
                export_per_interval=self.export_entity is not None,
                export_cap=ExportCap(
                    self.rules.get(CONF_PLAN_EXPORT_CAP, ExportCap.NONE)
                ),
            ),
            current=True,
            holidays=None,
            import_entity=_PAID_IMPORT,
            export_entity=_PAID_EXPORT if self.export_entity else None,
        )


async def _paid_prices(hass: HomeAssistant, entry: ConfigEntry) -> _Paid | None:
    """What the current plan follows, where the household has one."""
    current = current_plan_of(entry)
    if current is None:
        return None
    prefs = await async_energy_prefs(hass)
    entity, number = export_price_in(prefs)
    costs = grid_import_costs(
        prefs, hass.data.get("energy", {}).get("cost_sensors", {})
    )
    source = current.data.get(CONF_PLAN_DAILY_CHARGE_SOURCE)
    return _Paid(
        current.subentry_id,
        current.title,
        current.data,
        tuple(grid_meters_of(entry).values()),
        entity,
        number,
        costs[source][0] if source in costs else None,
        tuple(
            (
                date.fromisoformat(start)
                if (start := period.get(CONF_PERIOD_FROM))
                else None,
                period[CONF_PERIOD_PLAN],
            )
            for period in current.data.get(CONF_PLAN_PERIODS) or ()
        ),
    )


# Told apart by identity: two periods on the same plan are two stands.
@dataclass(frozen=True, eq=False)
class _Stand:
    """A plan the household was on, from its day, priced as it priced an hour.

    By the clock alone, so an hour's price is its band's at that local hour, or
    its market price's, adjusted as the plan adjusts it (HEA-311). With no
    tariff, the plan is gone or cannot price an hour, and its days go unpriced.
    """

    start: date | None
    tariff: TariffPlan | None
    holidays: frozenset[date]

    def import_at(
        self, start: datetime, prices: Mapping[str, _Series]
    ) -> Decimal | None:
        if self.tariff is None:
            return None
        plan = self.tariff.plan
        if self.tariff.import_entity:
            price = prices[self.tariff.import_entity].at(start.astimezone(UTC))
            return None if price is None else plan.import_adjustment.apply(price)
        return import_price_at(plan, start, self.holidays)

    def export_at(
        self, start: datetime, prices: Mapping[str, _Series]
    ) -> Decimal | None:
        if self.tariff is None:
            return None
        plan = self.tariff.plan
        if self.tariff.export_entity:
            price = prices[self.tariff.export_entity].at(start.astimezone(UTC))
            return None if price is None else plan.export_adjustment.apply(price)
        return export_price_at(plan, start, self.holidays)


@dataclass(frozen=True)
class _History:
    """The plans the household has been on, which stand in for the price sensors.

    An hour is priced at the plan of the period its local day falls in; an hour
    before the first dated period, with none from always, at none (HEA-307).
    """

    stands: tuple[_Stand, ...]
    prices: Mapping[str, _Series]

    def stand_at(self, start: datetime) -> _Stand | None:
        day = dt_util.as_local(start).date()
        return next(
            (
                stand
                for stand in reversed(self.stands)
                if stand.start is None or stand.start <= day
            ),
            None,
        )


async def _history_of(
    basis: _Basis, paid: _Paid, tariffs: Mapping[str, TariffPlan]
) -> _History | None:
    """The plans the household has been on, as each prices an hour."""
    stands = []
    entities: set[str] = set()
    for start, plan_id in paid.periods:
        tariff = tariffs.get(plan_id)
        if tariff is None or not follows_the_clock(tariff.plan):
            stands.append(_Stand(start, None, frozenset()))
            continue
        holidays = (
            await async_holidays(basis.hass, tariff.holidays, basis.start, basis.end)
            if tariff.holidays
            else frozenset()
        )
        stands.append(_Stand(start, tariff, holidays))
        entities |= {e for e in (tariff.import_entity, tariff.export_entity) if e}
    if not stands:
        return None
    return _History(
        tuple(stands),
        {entity: _Series(basis.prices.get(entity, {})) for entity in entities},
    )


class _PaidPrices:
    """Each interval's prices as Paid prices it, which the current plan follows.

    Import at one price per interval, the meters' own weighted by what each
    imported, so the interval's import at it costs exactly what Paid charges;
    export at the Energy Dashboard's price sensor where it has one.

    Where a price sensor no other plan follows has no statistics, its interval
    is priced at the plan the household was on that day, and `stood_in` names
    each plan that did; with none to read, the sensor is `lacking`, and the
    current plan cannot be priced (HEA-311, HEA-307). Any other price is carried
    as a market price is, and an interval it has no price before yet is left for
    the engine to refuse.
    """

    def __init__(
        self,
        basis: _Basis,
        paid: _Paid,
        gaps: Mapping[str, list[_Stretch]],
        history: _History | None,
    ) -> None:
        self._recorded = basis.recorded
        self._kept = {interval.start for interval in basis.intervals}
        self._series = {
            entity: _Series(basis.prices.get(entity, {})) for entity in paid.entities
        }
        self._gaps = gaps
        self._history = history
        self.lacking: set[str] = set()
        self.stood_in: set[_Stand] = set()
        self.imported = self._imported(paid)
        self.exported = self._exported(paid.export_entity)

    def _exported(self, entity: str | None) -> dict[datetime, Decimal]:
        if entity is None:
            return {}
        exported: dict[datetime, Decimal] = {}
        for interval in self._recorded.intervals:
            rate = self._rate(entity, interval, exported=True)
            if rate is not None:
                exported[interval.start.astimezone(UTC)] = rate
        return exported

    def _imported(self, paid: _Paid) -> dict[datetime, Decimal]:
        blended: dict[datetime, Decimal] = {}
        for interval in self._recorded.intervals:
            moment = interval.start.astimezone(UTC)
            rates = {
                meter.imported: (
                    self._rate(meter.price_entity, interval, exported=False)
                    if meter.price_entity
                    else meter.fixed_price
                )
                for meter in paid.meters
            }
            known = {meter: rate for meter, rate in rates.items() if rate is not None}
            if not known or len(known) < len(rates):
                continue
            kwh = {
                meter: self._recorded.imported_by_meter.get(meter, {}).get(
                    moment, Decimal(0)
                )
                for meter in known
            }
            total = sum(kwh.values(), Decimal(0))
            blended[moment] = (
                sum((kwh[meter] * rate for meter, rate in known.items()), Decimal(0))
                / total
                if total
                else sum(known.values(), Decimal(0)) / len(known)
            )
        return blended

    def _rate(
        self, entity: str, interval: IntervalOfEnergy, *, exported: bool
    ) -> Decimal | None:
        moment = interval.start.astimezone(UTC)
        length = self._recorded.length_at(moment)
        if not any(gap.overlaps(moment, length) for gap in self._gaps.get(entity, ())):
            return self._series[entity].at(moment)
        stand = self._history.stand_at(interval.start) if self._history else None
        stood: Decimal | None = None
        if stand is not None and self._history is not None:
            prices = self._history.prices
            stood = (
                stand.export_at(interval.start, prices)
                if exported
                else stand.import_at(interval.start, prices)
            )
        if interval.start in self._kept:
            if stood is None or stand is None:
                self.lacking.add(entity)
            else:
                self.stood_in.add(stand)
        return stood


def _gaps(
    recorded: _Recorded,
    prices: Mapping[str, Mapping[datetime, Decimal]],
    entities: Iterable[str],
    span: tuple[datetime, datetime],
) -> dict[str, list[_Stretch]]:
    """Each price entity's stretches with no statistics, too long to bridge."""
    start, end = span
    return {
        entity: [
            _Stretch(max(gap_start, start), gap_end, entity)
            for gap_start, gap_end in _uncovered(
                list(prices.get(entity, {})),
                recorded,
                (start - _BRIDGE, end),
                counted=False,
            )
            if gap_end > start
        ]
        for entity in entities
    }


class _Series:
    """A price entity's prices in time order, for the last one at a moment."""

    def __init__(self, prices: Mapping[datetime, Decimal]) -> None:
        ordered = sorted(prices.items())
        self._times = [moment for moment, _ in ordered]
        self._prices = [price for _, price in ordered]

    def at(self, moment: datetime) -> Decimal | None:
        """The last price recorded at or before `moment`, if any."""
        index = bisect_right(self._times, moment)
        return self._prices[index - 1] if index else None


def async_register(hass: HomeAssistant) -> None:
    """Offer the comparison, once however many times setup runs.

    To the card, over the websocket, and as an action returning the same
    result, for scripts, automations and other tools to read (HEA-302): a
    comparison is worked out for a period asked, so it is answered on demand
    rather than kept in a sensor, as `weather.get_forecasts` answers.
    """
    if hass.data.get(_REGISTERED):
        return
    async_register_command(hass, _websocket_compare_plans)
    async_register_command(hass, _websocket_list_plans)
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPARE_PLANS,
        _async_handle_compare,
        schema=_ACTION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.data[_REGISTERED] = True


_ACTION_SCHEMA = vol.Schema(
    {vol.Required("start"): cv.datetime, vol.Required("end"): cv.datetime}
)


async def _async_handle_compare(call: ServiceCall) -> ServiceResponse:
    """Price every plan over the period the action names.

    A time without a zone is the household's own, as a script's is. A period
    the meters have not reached yet has nothing to compare, so it is refused
    rather than answered with nothing.
    """
    start = dt_util.as_utc(call.data["start"])
    end = dt_util.as_utc(call.data["end"])
    if end <= start:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="compare_end_before_start"
        )
    if start >= dt_util.utcnow():
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="compare_not_started"
        )
    entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="compare_not_loaded"
        )
    return await async_compare_plans(call.hass, entries[0], start, end)


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
    current = current_plan_of(entries[0]) if entries else None
    connection.send_result(
        msg["id"],
        {
            "plans": [
                {"id": plan_id, "name": tariff.plan.name, "current": False}
                for plan_id, tariff in plans.items()
            ]
            + (
                [{"id": current.subentry_id, "name": current.title, "current": True}]
                if current
                else []
            )
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
    paid = await _paid_prices(hass, entry)
    typed = {
        entity
        for tariff in tariffs.values()
        for entity in (tariff.import_entity, tariff.export_entity)
        if entity
    }
    # A price sensor only the current plan follows leaves no hour out for the
    # plans that do not: its gaps are the current plan's alone (HEA-311).
    own = paid.entities - typed if paid else set()
    markets = typed | own
    # Five minutes at a time only where a market price changes within the hour:
    # a band prices five minutes exactly as it prices their hour.
    recorded = await _recorded_flows(
        hass, imports, exports, start, end, five_minutes=bool(markets)
    )
    prices = await _market_prices(hass, markets, start, end, recorded.five_minute_from)
    # Charged up to now at most: the picker's Today runs to midnight, and a whole
    # day's charge against half a day's energy would make every total read high.
    charged_until = max(start, min(end, dt_util.utcnow()))
    # A price with nothing in the period leaves only its own plans unpriced:
    # left out for everyone, it would leave nothing to compare.
    silent = {e for e in markets if not _any_within(prices, e, start, end)}
    used, use_impossible = await _recorded_use(hass, entry, recorded, start, end)
    left_out = _with_impossible(
        _left_out(recorded, prices, typed - silent, start, charged_until),
        [*recorded.impossible, *use_impossible],
    )
    intervals = _kept(recorded, left_out)
    missing = sum(
        (
            days_covered(dt_util.as_local(stretch.start), dt_util.as_local(stretch.end))
            for stretch in _merged(left_out)
        ),
        Decimal(0),
    )
    period = days_covered(dt_util.as_local(start), dt_util.as_local(charged_until))
    days = period - missing
    basis = _Basis(hass, start, end, recorded, intervals, prices, used, silent, days)
    flags: dict[str, Any] = {}
    lacking: list[str] = []
    # Where the plan named for the current plan's price history can stand in:
    # a sensor only it follows, and one a typed plan shares that recorded
    # nothing in the period, which leaves no hour out for anyone (HEA-311).
    stand_in = own | (paid.entities & silent) if paid else set()
    if paid:
        gaps = _gaps(recorded, prices, stand_in, (start, charged_until))
        current, flags, lacking = await _current_plan(
            basis, paid, tariffs, gaps, prices
        )
        tariffs = {**tariffs, paid.plan_id: current}
    plans = []
    for plan_id, tariff in tariffs.items():
        is_paid = paid is not None and plan_id == paid.plan_id
        named = {
            "id": plan_id,
            "name": tariff.plan.name,
            "current": tariff.current,
            "rates": _rates(tariff),
            **(flags if is_paid else {}),
        }
        if is_paid and lacking:
            plans.append({**named, "no_price": True, "no_price_entities": lacking})
            continue
        followed = (
            sorted(paid.entities - stand_in)
            if paid is not None and is_paid
            else [e for e in (tariff.import_entity, tariff.export_entity) if e]
        )
        plans.append(await _plan_row(basis, tariff, named, followed))
    return {
        "hours": len(intervals),
        "days": float(days),
        "imported_kwh": _number(sum((i.imported_kwh for i in intervals), Decimal(0))),
        "exported_kwh": _number(sum((i.exported_kwh for i in intervals), Decimal(0))),
        "five_minute_from": _when(recorded.five_minute_from),
        "left_out": [
            {
                "from": _when(stretch.start),
                "to": _when(stretch.end),
                "source": stretch.source,
                **({} if stretch.kwh is None else {"kwh": _number(stretch.kwh)}),
            }
            for stretch in left_out
        ],
        "plans": plans,
    }


async def _current_plan(
    basis: _Basis,
    paid: _Paid,
    tariffs: Mapping[str, TariffPlan],
    gaps: Mapping[str, list[_Stretch]],
    prices: dict[str, dict[datetime, Decimal]],
) -> tuple[TariffPlan, dict[str, Any], list[str]]:
    """The current plan as priced, what its row says, and the sensors it lacks.

    Its prices per interval go into `prices`, the comparison's market prices,
    where the engine reads them. Without a daily charge it would read cheaper
    than every plan with one, so the card holds each plan's difference from it
    (ADR-0042); and its row names the plans that priced the hours its sensors
    had no statistics for, in the order the household was on them (HEA-311).
    """
    history = await _history_of(basis, paid, tariffs)
    paid_prices = _PaidPrices(basis, paid, gaps, history)
    prices[_PAID_IMPORT] = paid_prices.imported
    prices[_PAID_EXPORT] = paid_prices.exported
    daily_charge = await paid.daily_charge(basis.hass, basis)
    stood = [
        stand.tariff.plan.name
        for stand in (history.stands if history else ())
        if stand in paid_prices.stood_in and stand.tariff is not None
    ]
    flags = (
        {"follows_prices": True}
        | ({"daily_charge_missing": True} if daily_charge is None else {})
        | ({"history_from": stood} if stood else {})
    )
    return paid.tariff(daily_charge), flags, sorted(paid_prices.lacking)


@dataclass(frozen=True)
class _Basis:
    """What every plan in one comparison is priced against."""

    hass: HomeAssistant
    start: datetime
    end: datetime
    recorded: _Recorded
    intervals: list[IntervalOfEnergy]
    prices: Mapping[str, Mapping[datetime, Decimal]]
    used: Mapping[datetime, Decimal] | None
    silent: set[str]
    days: Decimal


async def _plan_row(
    basis: _Basis,
    tariff: TariffPlan,
    named: dict[str, Any],
    followed: list[str],
) -> dict[str, Any]:
    """One plan's row: its figures, or why it has none."""
    if quiet := [entity for entity in followed if entity in basis.silent]:
        return {**named, "no_price": True, "no_price_entities": quiet}
    holidays = (
        await async_holidays(basis.hass, tariff.holidays, basis.start, basis.end)
        if tariff.holidays
        else frozenset()
    )
    priced = _at_market_prices(basis.recorded, basis.intervals, tariff, basis.prices)
    try:
        cost = price_plan(tariff.plan, priced, days=basis.days, holidays=holidays)
        without = _without_installation(
            tariff, priced, basis.used, days=basis.days, holidays=holidays
        )
    except ValueError:
        # Only a plan edited outside its form can leave hours unpriced; it is
        # listed, not guessed at.
        return {**named, "incomplete": True}
    return {
        **named,
        **_figures(cost),
        **without,
        "breakdown": _breakdown(tariff.plan, cost, basis.days),
    }


def _left_out(
    recorded: _Recorded,
    prices: Mapping[str, Mapping[datetime, Decimal]],
    entities: Iterable[str],
    start: datetime,
    end: datetime,
) -> list[_Stretch]:
    """The stretches every plan leaves out, each with what had no data for it.

    Priced each over what it could be, a year's comparison charged one plan 315
    days of daily charges and another two, and the cheapest was whichever had
    the least data (HEA-294, discussion 58). So a stretch any source has no data
    for is left out of every plan (ADR-0043).

    The grid meters' counters carry a gap's energy into the next row, so one at
    the period's start is bridged as any other, and the row that ends a gap too
    long to bridge is left out with it: its change is the gap's, and would
    otherwise be priced as one interval (ADR-0046). A price is carried only from
    one recorded before the gap, so a gap a price starts the period with, with
    none in the `_BRIDGE` before it, is never bridged; a price is no counter,
    so the price after a gap is its own.
    """
    stretches = [
        _Stretch(gap_start, gap_end, _GRID_METERS)
        for gap_start, gap_end in _uncovered(
            [interval.start for interval in recorded.intervals],
            recorded,
            (start, end),
            counted=True,
        )
    ]
    for gaps in _gaps(recorded, prices, entities, (start, end)).values():
        stretches += gaps
    return sorted(stretches, key=lambda stretch: (stretch.start, stretch.source))


def _uncovered(
    moments: Iterable[datetime],
    recorded: _Recorded,
    span: tuple[datetime, datetime],
    *,
    counted: bool,
) -> list[tuple[datetime, datetime]]:
    """The stretches of `span` no statistic covers, too long to bridge.

    Each statistic covers its hour, or its five minutes where they are kept. A
    stretch of `_BRIDGE` or less is bridged. Meters are `counted`: a counter
    carries a gap's energy into its next row, so even a short gap they start
    `span` with is bridged, and a stretch too long to bridge runs on to the end
    of the row that ends it, unless it runs from the start of `span`: what is
    read begins there, so whether that row ends a gap or is the meter's first is
    not known. A price is no counter, so a gap it starts `span` with is never
    bridged, and the price after a gap is its own.
    """
    start, end = span
    gaps: list[tuple[datetime, datetime, datetime]] = []
    reached = start
    for moment in sorted(moment for moment in moments if moment < end):
        covered = moment + recorded.length_at(moment)
        if moment > reached:
            gaps.append((reached, moment, covered))
        reached = max(reached, covered)
    if reached < end:
        gaps.append((reached, end, end))
    return [
        (gap_start, min(row_end, end) if counted and gap_start > start else gap_end)
        for gap_start, gap_end, row_end in gaps
        if gap_end - gap_start > _BRIDGE or (gap_start == start and not counted)
    ]


def _with_impossible(
    left_out: list[_Stretch], impossible: Iterable[_Stretch]
) -> list[_Stretch]:
    """The stretches left out, with each interval a meter could not have recorded.

    Once each: a balance-read house reads the grid meters too, so the same
    interval can be found twice.
    """
    seen = {(stretch.start, stretch.source) for stretch in left_out}
    found = list(left_out)
    for stretch in impossible:
        if (stretch.start, stretch.source) not in seen:
            seen.add((stretch.start, stretch.source))
            found.append(stretch)
    return sorted(found, key=lambda stretch: (stretch.start, stretch.source))


def _impossible(
    changes: Mapping[str, Iterable[Mapping[str, Any]]],
    meters: Iterable[str],
    kept: Any,  # noqa: ANN401 - the caller's choice of interval
    *,
    is_fine: bool,
) -> list[_Stretch]:
    """Each interval a meter changed by more than a home could use (ADR-0044).

    Held to the hourly ceiling's rate, so five minutes may change by a twelfth
    of it, and a row that ends a gap may rise by the rate across the gap, since
    the gap's energy arrives in it (ADR-0046). A fall is held to its own
    interval: a counter that fell by as much is as wrong, after a gap or not.

    A row after a gap short enough to bridge carries the gap's energy too
    (ADR-0043), so it is left out from the gap's start: otherwise the gap would
    be bridged and its hours charged daily charges for energy left out with
    the row.
    """
    length = _FIVE_MINUTES if is_fine else _HOUR
    ceiling = _CEILING_PER_HOUR * Decimal(length.total_seconds()) / Decimal(3600)
    return [
        stretch
        for meter in sorted(meters)
        for stretch in _impossible_of(
            meter,
            _kept_changes(changes.get(meter, ()), kept, is_fine=is_fine),
            length,
            ceiling,
        )
    ]


def _kept_changes(
    rows: Iterable[Mapping[str, Any]],
    kept: Any,  # noqa: ANN401 - the caller's choice of interval
    *,
    is_fine: bool,
) -> list[tuple[datetime, Decimal]]:
    """A meter's changes at the resolution read, in time order."""
    changes = []
    for row in rows:
        moment = _moment(row["start"])
        if row.get("change") is not None and kept(moment, is_fine=is_fine):
            changes.append((moment, Decimal(str(row["change"]))))
    return sorted(changes)


def _impossible_of(
    meter: str,
    rows: list[tuple[datetime, Decimal]],
    length: timedelta,
    ceiling: Decimal,
) -> list[_Stretch]:
    """One meter's impossible intervals, each from the start of a gap it ends."""
    found: list[_Stretch] = []
    recorded_to: datetime | None = None
    for moment, kwh in rows:
        covered = moment + length - (recorded_to or moment)
        allowed = ceiling * Decimal(covered / length) if kwh > 0 else ceiling
        if abs(kwh) > allowed:
            bridged = recorded_to is not None and moment - recorded_to <= _BRIDGE
            start = recorded_to if bridged and recorded_to else moment
            found.append(_Stretch(start, moment + length, meter, kwh))
        recorded_to = moment + length
    return found


def _merged(stretches: Iterable[_Stretch]) -> list[_Stretch]:
    """The stretches as one set of times, overlaps counted once."""
    merged: list[_Stretch] = []
    for stretch in sorted(stretches, key=lambda stretch: stretch.start):
        if merged and stretch.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = replace(last, end=max(last.end, stretch.end))
        else:
            merged.append(stretch)
    return merged


def _kept(recorded: _Recorded, left_out: list[_Stretch]) -> list[IntervalOfEnergy]:
    """The recorded intervals no stretch left out touches."""
    return [
        interval
        for interval in recorded.intervals
        if not any(
            stretch.overlaps(interval.start, recorded.length_at(interval.start))
            for stretch in left_out
        )
    ]


def _any_within(
    prices: Mapping[str, Mapping[datetime, Decimal]],
    entity: str,
    start: datetime,
    end: datetime,
) -> bool:
    """Whether the entity recorded any price within the period itself."""
    return any(start <= moment < end for moment in prices.get(entity, {}))


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


def _breakdown(plan: Plan, cost: PlanCost, days: Decimal) -> dict[str, Any]:
    """A plan's cost line by line, as a bill lists it (HEA-300).

    The daily charge, each price's kWh and what they cost, and what export was
    paid on, so a household can match each line against a bill. The average
    import rate is what each kWh cost on average, with the plan's cheapest and
    dearest import prices for the card to read it between.
    """
    imported = sum((line.kwh for line in cost.imports), Decimal(0))
    return {
        "daily": {
            "rate": _number(plan.daily_charge),
            "days": _number(days),
            "amount": _number(cost.daily_charges),
        },
        "imports": [_line(line) for line in cost.imports],
        "exports": [
            {**_line(line), "beyond_allowance": line.beyond_allowance}
            for line in cost.exports
        ],
        "average_import_rate": _number(cost.energy / imported) if imported else None,
        "cheapest_import_rate": _optional_number(cost.cheapest_import),
        "dearest_import_rate": _optional_number(cost.dearest_import),
    }


def _line(line: PriceLine) -> dict[str, Any]:
    return {
        "name": line.name,
        "rate": _optional_number(line.rate),
        "kwh": _number(line.kwh),
        "amount": _number(line.amount),
    }


def _optional_number(value: Decimal | None) -> float | None:
    return None if value is None else _number(value)


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
    kept = _kept_from(five_minute_from)
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
        (
            *_impossible(hourly, meters, kept, is_fine=False),
            *_impossible(fine, meters, kept, is_fine=True),
        ),
        {
            meter: _summed(hourly, {meter}, kept, is_fine=False)
            | _summed(fine, {meter}, kept, is_fine=True)
            for meter in imports
        },
    )


def _kept_from(five_minute_from: datetime | None) -> Any:  # noqa: ANN401 - a predicate
    """Which resolution an interval is read at: hourly, then 5-minute from then."""

    def kept(moment: datetime, *, is_fine: bool) -> bool:
        if five_minute_from is None:
            return not is_fine
        return (moment >= five_minute_from) is is_fine

    return kept


async def _recorded_use(
    hass: HomeAssistant,
    entry: ConfigEntry,
    recorded: _Recorded,
    start: datetime,
    end: datetime,
) -> tuple[dict[datetime, Decimal] | None, list[_Stretch]]:
    """What the house used in each interval, from its own meters (HEA-293).

    With each interval one of those meters recorded more than a home could use
    in (ADR-0044).

    ``None`` for a household with no generation and no battery: what it used is
    what it imported, so pricing it again as if it had neither says nothing.

    Read at the grid flows' own resolution. A balance can read below nothing in
    an interval whose counters tick at different moments - a charge before the
    import that supplied it - and that is carried into the intervals after it
    rather than dropped, so the period adds up to what the meters say.
    """
    signs = _use_meters(entry)
    if signs is None or RECORDER_DOMAIN not in hass.config.components:
        return None, []
    meters = set(signs)
    recorder = get_instance(hass)
    hourly = await recorder.async_add_executor_job(
        _changes, hass, meters, start, end, "hour"
    )
    fine = (
        await recorder.async_add_executor_job(
            _changes, hass, meters, start, end, "5minute"
        )
        if recorded.five_minute_from is not None
        else {}
    )
    kept = _kept_from(recorded.five_minute_from)
    used: dict[datetime, Decimal] = defaultdict(Decimal)
    for sign in (1, -1):
        group = {meter for meter, its in signs.items() if its == sign}
        read = _summed(hourly, group, kept, is_fine=False) | _summed(
            fine, group, kept, is_fine=True
        )
        for moment, kwh in read.items():
            used[moment] += sign * kwh
    impossible = [
        *_impossible(hourly, meters, kept, is_fine=False),
        *_impossible(fine, meters, kept, is_fine=True),
    ]
    return _carried_forward(used), impossible


def _use_meters(entry: ConfigEntry) -> dict[str, int] | None:
    """The meters what the house used is read from, each with its sign.

    The house's own consumption meter where it has one. Otherwise the balance
    the accounting is built from: import and generation and discharge in, export
    and charge out, so what is lost inside the battery is never counted as used.
    """
    generation = house_entities(entry.data, CONF_GENERATION_ENTITY)
    batteries = list(batteries_of(entry).values())
    if not generation and not batteries:
        return None
    house = house_entities(entry.data, CONF_HOUSE_CONSUMPTION_ENTITY)
    if house:
        return dict.fromkeys(house, 1)
    grids = list(grid_meters_of(entry).values())
    signs = {grid.imported: 1 for grid in grids}
    signs |= {grid.exported: -1 for grid in grids if grid.exported}
    signs |= dict.fromkeys(generation, 1)
    signs |= {battery.discharge: 1 for battery in batteries if battery.discharge}
    signs |= {battery.charge: -1 for battery in batteries if battery.charge}
    return signs


def _carried_forward(used: Mapping[datetime, Decimal]) -> dict[datetime, Decimal]:
    """Each interval's use, an interval below nothing taken off those after it."""
    owed = Decimal(0)
    carried: dict[datetime, Decimal] = {}
    for moment in sorted(used):
        kwh = used[moment] - owed
        owed = max(Decimal(0), -kwh)
        carried[dt_util.as_local(moment)] = max(Decimal(0), kwh)
    return carried


def _without_installation(
    tariff: TariffPlan,
    intervals: list[IntervalOfEnergy],
    used: Mapping[datetime, Decimal] | None,
    *,
    days: Decimal,
    holidays: frozenset[date],
) -> dict[str, float]:
    """What the plan would have cost with no generation or battery, where it differs.

    Everything the house used, bought at the plan's prices, with its daily
    charges: beside the plan's own total it reads as what the installation saved
    on that plan (HEA-293, discussion 58). Nothing for a household with neither.
    """
    if used is None:
        return {}
    cost = price_plan(
        tariff.plan, _as_if_without(intervals, used), days=days, holidays=holidays
    )
    return {"without_installation": _number(cost.total)}


def _as_if_without(
    intervals: list[IntervalOfEnergy], used: Mapping[datetime, Decimal]
) -> list[IntervalOfEnergy]:
    """The plan's intervals as a house with no generation or battery would have them.

    Everything used bought from the grid, nothing exported; a market plan keeps
    each interval's price.
    """
    return [
        replace(
            interval,
            imported_kwh=used.get(interval.start, Decimal(0)),
            exported_kwh=Decimal(0),
        )
        for interval in intervals
    ]


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

    Hourly means before `five_minute_from` (from `_BRIDGE` before the period, so
    a short gap at its start carries the price before it) and 5-minute means
    from it.
    """
    if RECORDER_DOMAIN not in hass.config.components or not entities:
        return {}
    recorder = get_instance(hass)
    hourly = await recorder.async_add_executor_job(
        _means, hass, entities, start - _BRIDGE, five_minute_from or end, "hour"
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
        per_kwh = price_per_kwh(hass, entity)
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


def price_per_kwh(hass: HomeAssistant, entity: str) -> Decimal:
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
    intervals: list[IntervalOfEnergy],
    tariff: TariffPlan,
    prices: Mapping[str, Mapping[datetime, Decimal]],
) -> list[IntervalOfEnergy]:
    """The intervals compared, each with the market prices the plan follows.

    An interval with no price of its own carries the last one before it: the
    gaps left among the intervals compared are the short ones `_left_out`
    bridges. One with nothing to carry keeps no price, and the engine refuses
    the plan rather than guess.
    """
    entities = [e for e in (tariff.import_entity, tariff.export_entity) if e]
    if not entities:
        return intervals
    first = recorded.intervals[0].start if recorded.intervals else None
    last = {e: _last_before(prices.get(e, {}), first) for e in entities}
    priced: list[IntervalOfEnergy] = []
    kept = {interval.start for interval in intervals}
    for interval in recorded.intervals:
        moment = interval.start.astimezone(UTC)
        last |= {
            entity: price
            for entity in entities
            if (price := prices.get(entity, {}).get(moment)) is not None
        }
        if interval.start not in kept:
            continue
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
    return priced


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


async def async_holidays(
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
