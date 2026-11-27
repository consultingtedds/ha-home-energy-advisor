"""Clearing a household's figures for a chosen period (HEA-272).

The full reset (HEA-57) is the only other way out of a bad stretch of figures,
and it takes the whole history with it. This clears whole hours instead: every
HEA figure for the household over the period, so they still add up.

Three things move, all measured from the long-term statistics before anything
is written:

1. **The history.** Each figure's hours in the period are written flat, so the
   period shows no change, and every later hour drops by what the period added.
2. **The money figures' lifetime totals.** A `total` figure's restore baseline
   drops by the same amount. Its zero point does not move: for a `total` figure
   the compiler would start a new accumulation at the lowered value and book all
   of it as a change. The fall is booked as an ordinary negative change instead,
   so for these figures the later hours are rewritten only up to the last one
   compiled, and the compiler's own booking carries the drop from there on.
3. **The money cycle meters' current value.** A cost meter subtracts its
   source's fall. Where the period lies wholly or partly before the meter's
   current cycle, it is calibrated back up by the part that does.

Energy figures are `total_increasing`, which the compiler reads as a loss or a
meter reset if they ever fall, so their lifetime totals keep the period: only
their history is cleared. The history of the cycle meters is not changed; a cost
meter's history shows the clear in the hour it was made.

Only the hourly statistics are rewritten through Home Assistant's public
interface. The five-minute statistics, kept for about ten days, still show the
period, with the correction where the hourly ones carry it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    statistics_during_period,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END,
    ATTR_START,
    CONF_CURRENCY,
    CONF_CYCLE_METERS,
    DEFAULT_CURRENCY,
    DOMAIN,
    SERVICE_CLEAR_PERIOD,
    SIGNAL_CLEAR_PERIOD,
    WHOLE_HOME_KEY,
)
from .cycle_meter import utility_meter_output_sensor
from .helper_ownership import helper_entry_id, helper_was_created
from .schemas import vol

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.components.recorder.models import StatisticMetaData
    from homeassistant.core import HomeAssistant, ServiceResponse

    from .coordinator import HeaConfigEntry

_HOUR = timedelta(hours=1)
# How many hours of rows are read and written at once (HEA-316).
_WINDOW = timedelta(days=31)
_CALIBRATE = "calibrate"
_UTILITY_METER = "utility_meter"
# The figures a household is shown before it clears a period.
_SUMMARY = ("energy_used", "actual_cost", "cost_savings")

_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_START): cv.datetime,
        vol.Required(ATTR_END): cv.datetime,
    }
)


@dataclass(frozen=True)
class Period:
    """Whole hours, start inclusive and end exclusive, in UTC."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class _Measured:
    """One statistic's hours in the period and what they added."""

    before: float
    added: float
    rows: list[dict[str, Any]]


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the action, administrators only, as the reset is."""
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_PERIOD,
        _async_handle,
        schema=_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_handle(call: ServiceCall) -> ServiceResponse:
    """Clear the period the call names, answering what was removed."""
    entry = _target_entry(call)
    period = whole_hours(call.data[ATTR_START], call.data[ATTR_END])
    removed = await async_clear_period(call.hass, entry, period)
    shown: dict[str, Any] = dict(summary(call.hass, entry, removed))
    return {"removed": shown}


def _target_entry(call: ServiceCall) -> HeaConfigEntry:
    """The loaded HEA config entry the call names, or a translated refusal."""
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = call.hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="reset_unknown_entry",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="reset_entry_not_loaded"
        )
    return entry


def whole_hours(start: datetime, end: datetime) -> Period:
    """The whole hours covering start to end, or a translated refusal.

    A time without a zone is the household's own. The start is taken back to
    its hour and the end on to the next, so nothing asked for is left out. The
    period has to have finished: an hour still being counted has nothing
    settled to clear.
    """
    first = _floor(_utc(start))
    last = _floor(_utc(end))
    if last < _utc(end):
        last += _HOUR
    if first >= last:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="clear_period_order"
        )
    if last > _floor(dt_util.utcnow()):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="clear_period_unfinished"
        )
    return Period(first, last)


def _utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_utc(moment)


def _floor(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


async def async_measure(
    hass: HomeAssistant, entry: HeaConfigEntry, period: Period
) -> dict[str, Decimal]:
    """What the period added to each of the household's figures, by entity id."""
    measured = await _measure(hass, _figures(hass, entry), period)
    return {
        statistic_id: Decimal(str(round(one.added, 9)))
        for statistic_id, one in measured.items()
    }


def summary(
    hass: HomeAssistant, entry: HeaConfigEntry, removed: Mapping[str, Decimal]
) -> dict[str, float]:
    """The whole-home energy, cost and savings among what a clear removes."""
    registry = er.async_get(hass)
    answer: dict[str, float] = {}
    for key in _SUMMARY:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{WHOLE_HOME_KEY}_{key}"
        )
        answer[key] = float(removed.get(entity_id, Decimal(0))) if entity_id else 0.0
    return answer


async def async_clear_period(
    hass: HomeAssistant, entry: HeaConfigEntry, period: Period
) -> dict[str, Decimal]:
    """Clear every HEA figure for the household over the period.

    Answers what was removed from each figure, by entity id.
    """
    figures = _figures(hass, entry)
    measured = await _measure(hass, figures, period)
    meters = _money_meters(hass, entry)
    partial = await _measure_from_cycles(hass, meters, period)
    falling = {
        statistic_id
        for statistic_id in measured
        if _state_class(hass, statistic_id) == SensorStateClass.TOTAL
    }
    metadata = await get_instance(hass).async_add_executor_job(
        lambda: get_metadata(hass, statistic_ids=set(measured))
    )
    for statistic_id, one in measured.items():
        meta = metadata[statistic_id][1]
        _flatten(hass, meta, one)
        if statistic_id in falling:
            await _lower_compiled(hass, meta, period.end, one.added)
        else:
            get_instance(hass).async_adjust_statistics(
                statistic_id,
                period.end,
                -one.added,
                meta["unit_of_measurement"] or "",
            )
    removed = {
        statistic_id: Decimal(str(round(one.added, 9)))
        for statistic_id, one in measured.items()
    }
    before = {meter.output: _value(hass, meter.output) for meter in meters}
    async_dispatcher_send(
        hass,
        SIGNAL_CLEAR_PERIOD.format(entry_id=entry.entry_id),
        {key: value for key, value in removed.items() if key in falling},
    )
    for meter in meters:
        held = before[meter.output]
        if held is None or meter.source not in falling:
            continue
        in_cycle = partial.get(meter.output, Decimal(0))
        await hass.services.async_call(
            _UTILITY_METER,
            _CALIBRATE,
            {ATTR_ENTITY_ID: meter.output, "value": str(held - in_cycle)},
            blocking=True,
        )
    return removed


def _figures(hass: HomeAssistant, entry: HeaConfigEntry) -> list[str]:
    """The household's own running figures, by entity id.

    The current plan's price sensors are left out: they follow the plan the
    household is on, not anything this integration counted.
    """
    plan_prefix = f"{entry.entry_id}_current_plan_"
    registry = er.async_get(hass)
    return [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == "sensor"
        and not entity.unique_id.startswith(plan_prefix)
        and _state_class(hass, entity.entity_id)
        in (SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING)
    ]


def _state_class(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    return state.attributes.get(ATTR_STATE_CLASS) if state else None


def _value(hass: HomeAssistant, entity_id: str) -> Decimal | None:
    state = hass.states.get(entity_id)
    try:
        return Decimal(state.state) if state else None
    except ArithmeticError:
        return None


async def _rows(
    hass: HomeAssistant, statistic_ids: set[str], start: datetime, end: datetime
) -> dict[str, list[dict[str, Any]]]:
    """Hourly rows over a span, read in the recorder's executor, a window at a time."""
    answer: dict[str, list[dict[str, Any]]] = {key: [] for key in statistic_ids}
    while start < end:
        stop = min(start + _WINDOW, end)
        rows = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass,
            start,
            stop,
            statistic_ids,
            "hour",
            None,
            {"sum", "state", "last_reset"},
        )
        for statistic_id, found in rows.items():
            answer[statistic_id].extend(dict(row) for row in found)
        start = stop
    return answer


async def _measure(
    hass: HomeAssistant, statistic_ids: list[str], period: Period
) -> dict[str, _Measured]:
    """Each statistic's hours in the period and what they added, where anything.

    The sum before the period is the hour before it; a statistic that began
    inside the period is measured from its first hour, which carries none of
    the change that started it.
    """
    if not statistic_ids:
        return {}
    found = await _rows(hass, set(statistic_ids), period.start - _HOUR, period.end)
    measured: dict[str, _Measured] = {}
    for statistic_id, rows in found.items():
        summed = [row for row in rows if row.get("sum") is not None]
        if not summed:
            continue
        before = float(summed[0]["sum"])
        inside = summed[1:] if _start(summed[0]) < period.start else summed
        if not inside:
            continue
        added = float(inside[-1]["sum"]) - before
        if added:
            measured[statistic_id] = _Measured(before, added, inside)
    return measured


def _start(row: Mapping[str, Any]) -> datetime:
    return datetime.fromtimestamp(row["start"], UTC)


def _flatten(hass: HomeAssistant, meta: StatisticMetaData, one: _Measured) -> None:
    """Write the period's hours at the sum it began with: no change in any."""
    async_import_statistics(
        hass,
        meta,
        [_row(row, one.before) for row in one.rows],
    )


def _row(row: Mapping[str, Any], total: float) -> StatisticData:
    data = StatisticData(start=_start(row), sum=total)
    if row.get("state") is not None:
        data["state"] = row["state"]
    if row.get("last_reset") is not None:
        data["last_reset"] = datetime.fromtimestamp(row["last_reset"], UTC)
    return data


async def _lower_compiled(
    hass: HomeAssistant, meta: StatisticMetaData, end: datetime, added: float
) -> None:
    """Lower every compiled hour after the period, up to the last.

    Not by the recorder's adjustment, which would also lower the five-minute
    statistics the next compile starts from, and so lower the hours to come a
    second time once the figure's own fall is booked.
    """
    statistic_id = meta["statistic_id"]
    found = await _rows(hass, {statistic_id}, end, _floor(dt_util.utcnow()) + _HOUR)
    rows = [row for row in found[statistic_id] if row.get("sum") is not None]
    if rows:
        async_import_statistics(
            hass, meta, [_row(row, float(row["sum"]) - added) for row in rows]
        )


@dataclass(frozen=True)
class _Meter:
    output: str
    source: str
    cycle_start: datetime | None


def _money_meters(hass: HomeAssistant, entry: HeaConfigEntry) -> list[_Meter]:
    """The cost cycle meters HEA created, with their source and current cycle."""
    meters: list[_Meter] = []
    for record in entry.data.get(CONF_CYCLE_METERS, {}).values():
        if not helper_was_created(record):
            continue
        meter_entry = hass.config_entries.async_get_entry(helper_entry_id(record))
        output = utility_meter_output_sensor(hass, helper_entry_id(record))
        if meter_entry is None or output is None:
            continue
        if _state_class(hass, output) != SensorStateClass.TOTAL:
            continue
        state = hass.states.get(output)
        stamp = state.attributes.get("last_reset") if state else None
        meters.append(
            _Meter(
                output=output,
                source=str(meter_entry.options.get("source", "")),
                cycle_start=dt_util.parse_datetime(stamp)
                if isinstance(stamp, str)
                else None,
            )
        )
    return meters


async def _measure_from_cycles(
    hass: HomeAssistant, meters: list[_Meter], period: Period
) -> dict[str, Decimal]:
    """What the period added inside each meter's current cycle, by meter."""
    answer: dict[str, Decimal] = {}
    for meter in meters:
        start = max(period.start, _floor(meter.cycle_start or period.start))
        if start >= period.end:
            answer[meter.output] = Decimal(0)
            continue
        measured = await _measure(hass, [meter.source], Period(start, period.end))
        one = measured.get(meter.source)
        answer[meter.output] = Decimal(str(round(one.added, 9))) if one else Decimal(0)
    return answer


def currency_of(entry: HeaConfigEntry) -> str:
    """The household's currency, as its money figures carry it."""
    return str(entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY))
