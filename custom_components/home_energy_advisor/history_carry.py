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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_REGISTERED = f"{DOMAIN}_carry_in_registered"
# Before any statistic Home Assistant could have kept.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
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
    hass: HomeAssistant, statistic_id: str, end: datetime, kind: str
) -> list[dict[str, Any]]:
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        _EPOCH,
        end,
        {statistic_id},
        "hour",
        None,
        {kind},
    )
    return [dict(row) for row in rows.get(statistic_id, [])]


async def _join(hass: HomeAssistant, target: str, kind: str) -> datetime:
    """The target's first recorded hour, or this hour where it has none yet."""
    now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    rows = await _rows(hass, target, now, kind)
    return _start(rows[0]) if rows else now


def _start(row: dict[str, Any]) -> datetime:
    return datetime.fromtimestamp(row["start"], UTC)


async def _carry_means(
    hass: HomeAssistant, source: str, target: str, currency: str
) -> int:
    """Each hour's mean price before the target's first, per kWh, as it keeps it."""
    join = await _join(hass, target, "mean")
    per_kwh = float(price_per_kwh(hass, source))
    rows = [
        StatisticData(
            start=_start(row),
            mean=row["mean"] * per_kwh,
            min=row["mean"] * per_kwh,
            max=row["mean"] * per_kwh,
        )
        for row in await _rows(hass, source, join, "mean")
        if row.get("mean") is not None
    ]
    if rows:
        async_import_statistics(
            hass,
            StatisticMetaData(
                has_sum=False,
                mean_type=StatisticMeanType.ARITHMETIC,
                name=None,
                source="recorder",
                statistic_id=target,
                unit_class=None,
                unit_of_measurement=f"{currency}/kWh",
            ),
            rows,
        )
    return len(rows)


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
    target_rows = await _rows(hass, target, dt_util.utcnow(), "sum")
    join = (
        _start(target_rows[0])
        if target_rows
        else dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    )
    sums = [
        (_start(row), row["sum"])
        for row in await _rows(hass, source, join, "sum")
        if row.get("sum") is not None
    ]
    total = 0.0
    rows = []
    for index, (start, running) in enumerate(sums):
        if index:
            total += max(running - sums[index - 1][1], 0.0)
        rows.append(StatisticData(start=start, sum=total))
    if not rows:
        return 0
    async_import_statistics(
        hass,
        StatisticMetaData(
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=None,
            source="recorder",
            statistic_id=target,
            unit_class=None,
            unit_of_measurement=currency,
        ),
        rows,
    )
    if target_rows and total:
        get_instance(hass).async_adjust_statistics(target, join, total, currency)
    return len(rows)
