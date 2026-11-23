"""Carrying the household's old price history into its new sensors (ADR-0048).

Decision 4: a household that opts into this integration's price sensors would
otherwise leave every hour before it without prices. So the price sensors and
the standing charge it used before are read, and their recorded history is
written behind the new sensors: each hour's mean price for the prices, each
hour's cost for the daily charge.

Only hours before the new sensor's first recorded one are written, so nothing it
recorded itself is overwritten. A running cost is written up from zero and the
live rows are lifted by what was carried in, so the total joins without a step,
as proven on the reference home (HEA-308). The join is found before anything is
written: once history exists, "the first row" no longer finds it.

An action rather than a step alone, so it can be aimed at spare statistics to
rehearse, and run again for a source that was missed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    statistics_during_period,
)
from homeassistant.core import (
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CURRENCY,
    CONF_PLAN_CARRY_IN,
    DEFAULT_CURRENCY,
    DOMAIN,
    SERVICE_CARRY_IN_HISTORY,
)
from .current_plan import current_plan_of, provides_prices
from .plan_comparison import price_per_kwh
from .price_sensors import (
    DAILY_CHARGE_COST,
    EXPORT_PRICE,
    IMPORT_PRICE,
    price_sensor_unique_id,
)
from .schemas import vol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_REGISTERED = f"{DOMAIN}_carry_in_registered"
# Before any statistic Home Assistant could have kept.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
# How much history is read and written at once (HEA-316).
_WINDOW = timedelta(days=31)
_PRICES = (IMPORT_PRICE, EXPORT_PRICE)
_KEYS = (*_PRICES, DAILY_CHARGE_COST)

_SCHEMA = vol.Schema(
    {
        **{vol.Optional(f"{key}_from"): cv.entity_id for key in _KEYS},
        **{vol.Optional(f"{key}_to"): cv.entity_id for key in _KEYS},
    }
)


def async_register(hass: HomeAssistant) -> None:
    """Offer the action, once, however many times the entry is set up."""
    if hass.data.get(_REGISTERED):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_CARRY_IN_HISTORY,
        _async_handle,
        schema=_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.data[_REGISTERED] = True


async def _async_handle(call: ServiceCall) -> ServiceResponse:
    """Carry each source named into its sensor, or the target named instead.

    Answers how many hours were written for each.
    """
    hass = call.hass
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    entry = entries[0] if entries else None
    sources = {
        key: call.data[f"{key}_from"] for key in _KEYS if call.data.get(f"{key}_from")
    }
    targets = {
        key: call.data[f"{key}_to"] for key in _KEYS if call.data.get(f"{key}_to")
    }
    return await async_carry(hass, entry, sources, targets)


async def async_carry(
    hass: HomeAssistant,
    entry: ConfigEntry | None,
    sources: Mapping[str, str],
    targets: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Carry each source into its target, or this integration's own sensor.

    Answers how many hours were written for each. Refused where a source has
    nothing to be written behind.
    """
    currency = str(entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)) if entry else ""
    answer: dict[str, Any] = {}
    for key in _KEYS:
        source = sources.get(key)
        if not source:
            continue
        target = (targets or {}).get(key) or _ours(hass, entry, key)
        if target is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="carry_in_no_target"
            )
        if key in _PRICES:
            answer[key] = await _carry_means(hass, source, target, currency)
        else:
            answer[key] = await _carry_costs(hass, source, target, currency)
    return answer


@callback
def async_carry_pending(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Run the carry-in chosen when the price sensors were asked for, once.

    Chosen in the current plan's form, before the sensors existed; run on the
    setup that made them, in the background so years of statistics never hold
    up Home Assistant's start, then forgotten, so it never runs twice. A
    carry-in that fails is logged, and can be run again with the action.
    """
    current = current_plan_of(entry)
    pending = current.data.get(CONF_PLAN_CARRY_IN) if current else None
    if current is None or not pending:
        return
    hass.config_entries.async_update_subentry(
        entry,
        current,
        data={k: v for k, v in current.data.items() if k != CONF_PLAN_CARRY_IN},
    )
    if provides_prices(entry):
        entry.async_create_background_task(
            hass, _carry_logged(hass, entry, dict(pending)), "carry in price history"
        )


async def _carry_logged(
    hass: HomeAssistant, entry: ConfigEntry, pending: Mapping[str, str]
) -> None:
    if RECORDER_DOMAIN not in hass.config.components:
        _LOGGER.warning("No recorder, so no price history to carry in")
        return
    try:
        written = await async_carry(hass, entry, pending)
    except HomeAssistantError:
        _LOGGER.exception("Carrying the old price history in failed")
        return
    _LOGGER.info("Carried the old price history in: %s hours", written)


def _ours(hass: HomeAssistant, entry: ConfigEntry | None, key: str) -> str | None:
    """This integration's sensor for `key`, where the household has it."""
    if entry is None:
        return None
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, price_sensor_unique_id(entry, key)
    )


async def _rows(
    hass: HomeAssistant,
    statistic_id: str,
    span: tuple[datetime, datetime],
    kind: str,
    period: Literal["hour", "month"] = "hour",
) -> list[dict[str, Any]]:
    """One statistic's rows over a span, read in the recorder's executor."""
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        span[0],
        span[1],
        {statistic_id},
        period,
        None,
        {kind},
    )
    return [dict(row) for row in rows.get(statistic_id, [])]


async def _first(
    hass: HomeAssistant, statistic_id: str, end: datetime, kind: str
) -> datetime | None:
    """A statistic's first recorded hour before `end`, if it has one.

    Found by its months first, a few dozen rows however many years it holds,
    then the hours of its first month alone: never every row it has.
    """
    months = await _rows(hass, statistic_id, (_EPOCH, end), kind, "month")
    if not months:
        return None
    start = _start(months[0])
    # Through that month, and a little past it in case the month row is
    # labelled by a zone other than the hours', a window at a time.
    last = min(start + timedelta(days=32), end)
    while start < last:
        stop = min(start + _WINDOW, last)
        if hours := await _rows(hass, statistic_id, (start, stop), kind):
            return _start(hours[0])
        start = stop
    return None


async def _windows(
    hass: HomeAssistant, statistic_id: str, end: datetime, kind: str
) -> AsyncIterator[list[dict[str, Any]]]:
    """A statistic's hourly rows before `end`, a window at a time.

    So years of history are never held, read or written at once (HEA-316).
    """
    start = await _first(hass, statistic_id, end, kind)
    while start is not None and start < end:
        stop = min(start + _WINDOW, end)
        yield await _rows(hass, statistic_id, (start, stop), kind)
        start = stop


def _this_hour() -> datetime:
    return dt_util.utcnow().replace(minute=0, second=0, microsecond=0)


def _start(row: dict[str, Any]) -> datetime:
    return datetime.fromtimestamp(row["start"], UTC)


async def _carry_means(
    hass: HomeAssistant, source: str, target: str, currency: str
) -> int:
    """Each hour's mean price before the target's first, per kWh, as it keeps it."""
    join = await _first(hass, target, _this_hour(), "mean") or _this_hour()
    per_kwh = float(price_per_kwh(hass, source))
    metadata = StatisticMetaData(
        has_sum=False,
        mean_type=StatisticMeanType.ARITHMETIC,
        name=None,
        source="recorder",
        statistic_id=target,
        unit_class=None,
        unit_of_measurement=f"{currency}/kWh",
    )
    written = 0
    async for window in _windows(hass, source, join, "mean"):
        rows = [
            StatisticData(
                start=_start(row),
                mean=row["mean"] * per_kwh,
                min=row["mean"] * per_kwh,
                max=row["mean"] * per_kwh,
            )
            for row in window
            if row.get("mean") is not None
        ]
        if rows:
            async_import_statistics(hass, metadata, rows)
        written += len(rows)
    return written


async def _carry_costs(
    hass: HomeAssistant, source: str, target: str, currency: str
) -> int:
    """Each hour's cost before the target's first, and the target lifted by it.

    Written up from zero, and the target's own rows lifted by the total. The
    source's first hour carries nothing: the running total before it is not
    known, and taking that whole total as one hour's cost is the step HEA-308
    found. Rows carry no state, so a sensor recording on from them carries on
    from their total rather than counting its own value as a change.
    """
    # The join, fixed before anything is written: once history exists, the
    # target's first row no longer finds it.
    recorded = await _first(hass, target, dt_util.utcnow(), "sum")
    join = recorded or _this_hour()
    metadata = StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=None,
        source="recorder",
        statistic_id=target,
        unit_class=None,
        unit_of_measurement=currency,
    )
    total = 0.0
    before: float | None = None
    written = 0
    async for window in _windows(hass, source, join, "sum"):
        rows = []
        for row in window:
            if row.get("sum") is None:
                continue
            if before is not None:
                total += max(row["sum"] - before, 0.0)
            before = row["sum"]
            rows.append(StatisticData(start=_start(row), sum=total))
        if rows:
            async_import_statistics(hass, metadata, rows)
        written += len(rows)
    if recorded is not None and total:
        get_instance(hass).async_adjust_statistics(target, join, total, currency)
    return written
