"""Every tariff plan priced against the household's recorded grid flows (ADR-0036).

The comparison reads the hourly change of every grid import and export meter
entered, summed across registers, for the period asked, and prices each plan at
it: its bands by local hour, rest days for weekends and the holidays in its
calendar, and its daily charge for the days the period covers. Nothing it reads
is a figure of this integration's own; the statistics are Home Assistant's.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_HOLIDAYS,
    DOMAIN,
    SUBENTRY_TYPE_GRID,
    SUBENTRY_TYPE_PLAN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

LOCAL = ZoneInfo("Europe/Madrid")
# Wednesday 4 November 2026, a whole local day.
DAY_START = datetime(2026, 11, 4, tzinfo=LOCAL)
DAY_END = DAY_START + timedelta(days=1)

_GRID = {
    CONF_NAME: "Grid",
    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
    CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
    CONF_FIXED_PRICE: 0.2,
}
# The household's current plan: one price all day.
_FLAT: dict[str, Any] = {
    CONF_NAME: "Flat rate",
    CONF_PLAN_CURRENT: True,
    CONF_PLAN_DAILY_CHARGE: 0.45,
    CONF_PLAN_EXPORT_PRICE: 0.05,
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.234,
        }
    ],
}
# An offer: dear from 08:00 to 22:00 on weekdays, cheap otherwise.
_OFFER = {
    CONF_NAME: "Night saver",
    CONF_PLAN_CURRENT: False,
    CONF_PLAN_DAILY_CHARGE: 0.30,
    CONF_PLAN_EXPORT_PRICE: 0.04,
    CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "weekdays",
            CONF_BAND_START: 8,
            CONF_BAND_END: 22,
            CONF_BAND_IMPORT_PRICE: 0.31,
        },
        {
            CONF_BAND_DAYS: "weekdays",
            CONF_BAND_START: 22,
            CONF_BAND_END: 8,
            CONF_BAND_IMPORT_PRICE: 0.09,
        },
        {
            CONF_BAND_DAYS: "rest_days",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.09,
        },
    ],
}


def _house(*subentries: tuple[str, dict[str, Any]]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=kind, title=data[CONF_NAME], data=data, unique_id=None
            )
            for kind, data in subentries
        ],
    )


def _record(hass: HomeAssistant, statistic_id: str, hours: dict[int, float]) -> None:
    """Hourly statistics for a meter: kWh in each local hour of the day, else 0."""
    total = 0.0
    rows = []
    for hour in range(24):
        total += hours.get(hour, 0.0)
        start = (DAY_START + timedelta(hours=hour)).astimezone(UTC)
        rows.append(StatisticData(start=start, state=total, sum=total))
    metadata = StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=None,
        source="recorder",
        statistic_id=statistic_id,
        unit_class="energy",
        unit_of_measurement="kWh",
    )
    async_import_statistics(hass, metadata, rows)


def _calendar(hass: HomeAssistant, holidays: list[date]) -> None:
    """A calendar answering `calendar.get_events` with these all-day holidays.

    In the shape Home Assistant's action returns: per calendar, its events, an
    all-day event's start and end as dates, the end exclusive.
    """

    async def get_events(call: ServiceCall) -> ServiceResponse:
        asked = call.data["entity_id"]
        entity_ids = [asked] if isinstance(asked, str) else asked
        return {
            entity_id: {
                "events": [
                    {
                        "start": day.isoformat(),
                        "end": (day + timedelta(days=1)).isoformat(),
                        "summary": "Public holiday",
                    }
                    for day in holidays
                ]
            }
            for entity_id in entity_ids
        }

    hass.services.async_register(
        "calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY
    )


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _compare(
    hass_ws_client: WebSocketGenerator,
    hass: HomeAssistant,
    start: datetime = DAY_START,
    end: datetime = DAY_END,
) -> dict[str, Any]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "home_energy_advisor/compare_plans",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"], response
    result: dict[str, Any] = response["result"]
    return result


def _by_name(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {plan["name"]: plan for plan in result["plans"]}


@pytest.fixture
async def _a_recorded_day(hass: HomeAssistant) -> None:
    """A weekday's grid flows, in at 07:00, 12:00 and 20:00, out at 12:00.

    1 kWh in at 07:00, 0.5 in and 2 out at 12:00, and 1 in at 20:00.
    """
    await hass.config.async_set_time_zone("Europe/Madrid")
    _record(hass, "sensor.grid_import", {7: 1.0, 12: 0.5, 20: 1.0})
    _record(hass, "sensor.grid_export", {12: 2.0})
    await async_wait_recording_done(hass)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_each_plan_is_priced_from_the_hours_the_meters_recorded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the current plan and an offer, and no holiday that day
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )

    # When - over the whole day
    result = await _compare(hass_ws_client, hass)

    # Then - what was recorded, and each plan priced at it
    assert result["imported_kwh"] == pytest.approx(2.5)
    assert result["exported_kwh"] == pytest.approx(2.0)
    assert result["days"] == pytest.approx(1)
    plans = _by_name(result)
    flat = plans["Flat rate"]
    assert flat["current"] is True
    assert flat["energy"] == pytest.approx(0.585)  # 2.5 kWh at 0.234
    assert flat["export_credit"] == pytest.approx(0.1)  # 2.0 at 0.05
    assert flat["daily_charges"] == pytest.approx(0.45)
    assert flat["total"] == pytest.approx(0.935)
    offer = plans["Night saver"]
    assert offer["current"] is False
    # 07:00 at night price, 12:00 and 20:00 at the day price
    assert offer["energy"] == pytest.approx(0.09 + 0.5 * 0.31 + 0.31)
    assert offer["total"] == pytest.approx(0.555 - 0.08 + 0.30)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_holiday_in_the_plans_calendar_is_priced_as_a_rest_day(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the Wednesday is a public holiday in the offer's calendar
    _calendar(hass, [DAY_START.date()])
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _OFFER))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - every hour at the rest-day price
    assert _by_name(result)["Night saver"]["energy"] == pytest.approx(2.5 * 0.09)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_calendar_that_cannot_answer_leaves_the_plan_without_holidays(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the offer names a calendar, but no calendar is set up to answer
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _OFFER))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - priced as the weekday it is, as a plan with no calendar would be
    assert _by_name(result)["Night saver"]["energy"] == pytest.approx(0.555)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_plan_that_leaves_hours_unpriced_is_listed_not_guessed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - a plan whose bands stop at 22:00 on weekdays, which only an entry
    # edited outside its form can hold
    gappy = {**_FLAT, CONF_BANDS: [{**_FLAT[CONF_BANDS][0], CONF_BAND_END: 22}]}
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, gappy))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - named, marked incomplete, and given no figure
    assert result["plans"] == [
        {
            "id": result["plans"][0]["id"],
            "name": "Flat rate",
            "current": True,
            "incomplete": True,
        }
    ]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_part_of_a_day_carries_that_share_of_the_daily_charge(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When - midnight to noon
    result = await _compare(hass_ws_client, hass, end=DAY_START + timedelta(hours=12))

    # Then - half a day of charges, and only the morning's import
    flat = _by_name(result)["Flat rate"]
    assert result["days"] == pytest.approx(0.5)
    assert flat["daily_charges"] == pytest.approx(0.225)
    assert flat["energy"] == pytest.approx(0.234)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_every_import_register_is_counted(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - a second register on its own grid entry, importing 1 kWh at 03:00
    _record(hass, "sensor.night_register", {3: 1.0})
    await async_wait_recording_done(hass)
    night = {
        CONF_NAME: "Night register",
        CONF_GRID_IMPORT_ENTITY: "sensor.night_register",
        CONF_FIXED_PRICE: 0.1,
    }
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_GRID, night),
            (SUBENTRY_TYPE_PLAN, _FLAT),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the plan prices all the house imported, whichever register counted it
    assert result["imported_kwh"] == pytest.approx(3.5)
    assert _by_name(result)["Flat rate"]["energy"] == pytest.approx(3.5 * 0.234)


@pytest.mark.usefixtures("recorder_mock")
async def test_a_period_with_nothing_recorded_charges_only_the_days(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no statistics at all
    await hass.config.async_set_time_zone("Europe/Madrid")
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - said as no hours recorded, so the card can say so too
    assert result["hours"] == 0
    flat = _by_name(result)["Flat rate"]
    assert (flat["energy"], flat["daily_charges"]) == (0, pytest.approx(0.45))


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_household_without_plans_has_nothing_to_compare(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given
    await _set_up(hass, _house((SUBENTRY_TYPE_GRID, _GRID)))

    # When / Then
    assert (await _compare(hass_ws_client, hass))["plans"] == []


@pytest.mark.usefixtures("recorder_mock")
async def test_a_period_that_is_not_a_time_is_refused(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )
    client = await hass_ws_client(hass)

    # When
    await client.send_json_auto_id(
        {
            "type": "home_energy_advisor/compare_plans",
            "start_time": "last tuesday",
            "end_time": DAY_END.isoformat(),
        }
    )
    response = await client.receive_json()

    # Then
    assert response["success"] is False
    assert response["error"]["code"] == "invalid_format"
