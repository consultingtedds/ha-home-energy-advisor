"""Every tariff plan priced against the household's recorded grid flows (ADR-0036).

Asked for by the plan comparison card, for whatever period its picker shows. The
hourly change of every grid import and export meter entered is read from Home
Assistant's long-term statistics and summed across registers; each plan's
holidays are read from the calendar it names; and the engine prices each plan
at the same hours. Nothing read here is a figure of this integration's own, so
any period the statistics reach can be compared, past months included.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.decorators import (
    async_response,
    websocket_command,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .engine.plan_pricing import HourOfEnergy, PlanCost, days_covered, price_plan
from .house_inputs import grid_meters_of
from .schemas import vol
from .tariff_plans import plans_of

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.components.websocket_api.connection import ActiveConnection
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

COMPARE_PLANS = f"{DOMAIN}/compare_plans"
_REGISTERED = f"{DOMAIN}_compare_plans_registered"
# Figures go to the card as numbers, to a ten-thousandth: finer than any
# currency shows, and the card rounds for display.
_SHOWN = Decimal("0.0001")


def async_register(hass: HomeAssistant) -> None:
    """Offer the comparison to the card, once however many times setup runs."""
    if hass.data.get(_REGISTERED):
        return
    async_register_command(hass, _websocket_compare_plans)
    hass.data[_REGISTERED] = True


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
    hours = await _hourly_flows(hass, imports, exports, start, end)
    days = days_covered(dt_util.as_local(start), dt_util.as_local(end))
    plans = []
    for plan_id, tariff in plans_of(entry).items():
        holidays = (
            await _holidays(hass, tariff.holidays, start, end)
            if tariff.holidays
            else frozenset()
        )
        try:
            cost = price_plan(tariff.plan, hours, days=days, holidays=holidays)
        except ValueError:
            # Only a plan edited outside its form can leave hours unpriced; it is
            # listed, not guessed at.
            plans.append(
                {
                    "id": plan_id,
                    "name": tariff.plan.name,
                    "current": tariff.current,
                    "incomplete": True,
                }
            )
            continue
        plans.append(
            {
                "id": plan_id,
                "name": tariff.plan.name,
                "current": tariff.current,
                **_figures(cost),
            }
        )
    return {
        "hours": len(hours),
        "days": float(days),
        "imported_kwh": _number(sum((hour.imported_kwh for hour in hours), Decimal(0))),
        "exported_kwh": _number(sum((hour.exported_kwh for hour in hours), Decimal(0))),
        "plans": plans,
    }


def _figures(cost: PlanCost) -> dict[str, float]:
    return {
        "energy": _number(cost.energy),
        "export_credit": _number(cost.export_credit),
        "daily_charges": _number(cost.daily_charges),
        "total": _number(cost.total),
    }


def _number(value: Decimal) -> float:
    return float(value.quantize(_SHOWN))


async def _hourly_flows(
    hass: HomeAssistant,
    imports: set[str],
    exports: set[str],
    start: datetime,
    end: datetime,
) -> list[HourOfEnergy]:
    """Each recorded hour's grid import and export, summed across meters.

    An hour none of the meters recorded is left out rather than priced as
    nothing; the caller says how many hours there were.
    """
    if RECORDER_DOMAIN not in hass.config.components or not imports | exports:
        return []
    changes = await get_instance(hass).async_add_executor_job(
        _hourly_changes, hass, imports | exports, start, end
    )
    imported = _summed(changes, imports)
    exported = _summed(changes, exports)
    return [
        HourOfEnergy(
            start=dt_util.as_local(moment),
            imported_kwh=imported.get(moment, Decimal(0)),
            exported_kwh=exported.get(moment, Decimal(0)),
        )
        for moment in sorted(imported.keys() | exported.keys())
    ]


def _hourly_changes(
    hass: HomeAssistant, statistic_ids: set[str], start: datetime, end: datetime
) -> Mapping[str, list[Any]]:
    """The recorder's hourly change for each meter, in kWh. A database read."""
    return statistics_during_period(
        hass, start, end, statistic_ids, "hour", {"energy": "kWh"}, {"change"}
    )


def _summed(
    changes: Mapping[str, Iterable[Mapping[str, Any]]], meters: set[str]
) -> dict[datetime, Decimal]:
    """Each hour's change, added up across these meters."""
    total: dict[datetime, Decimal] = defaultdict(Decimal)
    for meter in meters:
        for row in changes.get(meter, ()):
            change = row.get("change")
            if change is None:
                continue
            total[_moment(row["start"])] += Decimal(str(change))
    return dict(total)


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
