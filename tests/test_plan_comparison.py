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
from homeassistant.components.recorder.db_schema import StatisticsShortTerm
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_HOLIDAYS,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PRICES,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_GRID,
    SUBENTRY_TYPE_PLAN,
)
from custom_components.home_energy_advisor.plan_comparison import (
    async_compare_plans,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

LOCAL = ZoneInfo("Europe/Madrid")
# Wednesday 14 October 2026, a whole local day, and in the past: a period is
# charged only up to now.
DAY_START = datetime(2026, 10, 14, tzinfo=LOCAL)
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
async def test_each_plan_says_its_own_prices_for_the_card_to_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - a plan whose prices are named, and an offer entered before prices
    # had names, its figures on each band
    _calendar(hass, [])
    named = {
        **_FLAT,
        CONF_NAME: "Two prices",
        CONF_PRICES: [
            {CONF_NAME: "Peak", CONF_BAND_IMPORT_PRICE: 0.31},
            {CONF_NAME: "Night", CONF_BAND_IMPORT_PRICE: 0.09},
        ],
        CONF_BANDS: [
            {
                CONF_BAND_DAYS: "every_day",
                CONF_BAND_START: 8,
                CONF_BAND_END: 22,
                CONF_BAND_PRICE: "Peak",
            },
            {
                CONF_BAND_DAYS: "every_day",
                CONF_BAND_START: 22,
                CONF_BAND_END: 8,
                CONF_BAND_PRICE: "Night",
            },
        ],
    }
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, named),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )

    # When
    plans = _by_name(await _compare(hass_ws_client, hass))

    # Then - each price once, in the order the bands first use it, beside what
    # export pays and the daily charge (HEA-280). An unnamed price is told
    # apart by its figures, so the offer's two are not read as one
    assert plans["Two prices"]["rates"] == {
        "prices": [
            {"name": "Peak", "import": 0.31, "export": None},
            {"name": "Night", "import": 0.09, "export": None},
        ],
        "export": 0.05,
        "daily_charge": 0.45,
        "import_market": False,
        "export_market": False,
    }
    assert plans["Night saver"]["rates"]["prices"] == [
        {"name": "", "import": 0.31, "export": None},
        {"name": "", "import": 0.09, "export": None},
    ]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_capped_plan_says_what_export_it_did_not_pay(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the flat plan paying 0.50 for export, capped at the month's
    # energy cost (HEA-258)
    capped = {
        **_FLAT,
        CONF_NAME: "Generous feed-in",
        CONF_PLAN_EXPORT_PRICE: 0.50,
        CONF_PLAN_EXPORT_CAP: "monthly",
    }
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, capped))
    )

    # When
    plan = _by_name(await _compare(hass_ws_client, hass))["Generous feed-in"]

    # Then - 2 kWh out earns 1.00, but only the month's 0.585 of energy is paid,
    # and the card is told what was not
    assert plan["export_credit"] == pytest.approx(0.585)
    assert plan["export_unpaid"] == pytest.approx(0.415)
    assert plan["export_carried"] == 0
    assert plan["total"] == pytest.approx(0.45)


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

    # Then - named, marked incomplete, and given no figure; its prices are still
    # listed, so the household can see what it entered (HEA-280)
    assert result["plans"] == [
        {
            "id": result["plans"][0]["id"],
            "name": "Flat rate",
            "current": True,
            "rates": {
                "prices": [{"name": "", "import": 0.234, "export": None}],
                "export": 0.05,
                "daily_charge": 0.45,
                "import_market": False,
                "export_market": False,
            },
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
async def test_a_period_running_past_now_is_charged_only_up_to_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - midday on the day, which the picker's Today runs to the end of.
    # Asked directly: a websocket login refuses a clock moved into the past
    entry = _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    await _set_up(hass, entry)
    freezer.move_to(DAY_START + timedelta(hours=12))

    # When - the whole day is asked about
    result = await async_compare_plans(hass, entry, DAY_START, DAY_END)

    # Then - half a day of charges, as against the half a day of energy there is
    # so far; a whole day's would make every total read high until midnight
    assert result["days"] == pytest.approx(0.5)
    assert _by_name(result)["Flat rate"]["daily_charges"] == pytest.approx(0.225)


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
async def test_the_dashboard_can_ask_which_plans_there_are(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - two plans, one current
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )
    client = await hass_ws_client(hass)

    # When - asked without reading any statistics, as the dashboard decides
    # whether to show the comparison at all
    await client.send_json_auto_id({"type": "home_energy_advisor/list_plans"})
    response = await client.receive_json()

    # Then
    assert response["success"], response
    plans = {plan["name"]: plan["current"] for plan in response["result"]["plans"]}
    assert plans == {"Flat rate": True, "Night saver": False}


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


# Plans priced from a market price entity (HEA-260, ADR-0037)

# A wholesale plan: import at whatever the market charged, a flat feed-in, and
# the daily charge the feed leaves out.
_MARKET = {
    CONF_NAME: "Wholesale",
    CONF_PLAN_CURRENT: False,
    CONF_PLAN_DAILY_CHARGE: 1.0,
    CONF_PLAN_EXPORT_PRICE: 0.05,
    CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.market_import",
}
_FIVE_MINUTES = timedelta(minutes=5)


def _price_metadata(statistic_id: str, unit: str) -> StatisticMetaData:
    return StatisticMetaData(
        has_sum=False,
        mean_type=StatisticMeanType.ARITHMETIC,
        name=None,
        source="recorder",
        statistic_id=statistic_id,
        unit_class=None,
        unit_of_measurement=unit,
    )


def _record_prices(
    hass: HomeAssistant,
    statistic_id: str,
    hours: dict[int, float],
    unit: str = "EUR/kWh",
) -> None:
    """A price entity's hourly mean, for these local hours of the day only."""
    rows = [
        StatisticData(
            start=(DAY_START + timedelta(hours=hour)).astimezone(UTC),
            mean=price,
            min=price,
            max=price,
        )
        for hour, price in hours.items()
    ]
    async_import_statistics(hass, _price_metadata(statistic_id, unit), rows)
    hass.states.async_set(statistic_id, "0", {"unit_of_measurement": unit})


def _five_minutes_from(hour: int) -> list[datetime]:
    """Every five minutes from this local hour to the end of the day."""
    first = DAY_START + timedelta(hours=hour)
    return [first + n * _FIVE_MINUTES for n in range((24 - hour) * 12)]


def _record_five_minute_meter(
    hass: HomeAssistant,
    statistic_id: str,
    from_hour: int,
    total_before: float,
    kwh: dict[tuple[int, int], float],
) -> None:
    """A meter's 5-minute statistics from `from_hour`, as the recorder keeps them.

    `kwh` is what it counted in the five minutes starting at (hour, minute), and
    `total_before` its total when they start. One row before the first carries
    that total, as a meter's history does, so the first interval has a change.
    """
    total = total_before
    rows = [
        StatisticData(
            start=(DAY_START + timedelta(hours=from_hour) - _FIVE_MINUTES).astimezone(
                UTC
            ),
            state=total,
            sum=total,
        )
    ]
    for start in _five_minutes_from(from_hour):
        total += kwh.get((start.hour, start.minute), 0.0)
        rows.append(StatisticData(start=start.astimezone(UTC), state=total, sum=total))
    metadata = StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=None,
        source="recorder",
        statistic_id=statistic_id,
        unit_class="energy",
        unit_of_measurement="kWh",
    )
    get_instance(hass).async_import_statistics(metadata, rows, StatisticsShortTerm)


def _record_five_minute_prices(
    hass: HomeAssistant,
    statistic_id: str,
    from_hour: int,
    price: float,
    prices: dict[tuple[int, int], float],
) -> None:
    """A price entity's 5-minute means from `from_hour`: `price`, but for `prices`."""
    rows = []
    for start in _five_minutes_from(from_hour):
        mean = prices.get((start.hour, start.minute), price)
        rows.append(
            StatisticData(start=start.astimezone(UTC), mean=mean, min=mean, max=mean)
        )
    get_instance(hass).async_import_statistics(
        _price_metadata(statistic_id, "EUR/kWh"), rows, StatisticsShortTerm
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_plan_importing_at_the_market_is_priced_at_each_hours_price(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the market's hourly mean price: 0.20, but 0.12 at 07:00, 0.30 at
    # 12:00 and 0.22 at 20:00, the hours the house imported
    prices = dict.fromkeys(range(24), 0.2) | {7: 0.12, 12: 0.30, 20: 0.22}
    _record_prices(hass, "sensor.market_import", prices)
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - each hour's import at that hour's price, export at the flat price
    market = _by_name(result)["Wholesale"]
    assert market["energy"] == pytest.approx(1 * 0.12 + 0.5 * 0.30 + 1 * 0.22)
    assert market["export_credit"] == pytest.approx(2 * 0.05)
    assert market["daily_charges"] == pytest.approx(1.0)
    assert market["carried_hours"] == 0
    assert result["compared_from"] is None
    assert result["five_minute_from"] is None


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_where_five_minute_statistics_are_kept_each_is_priced_on_its_own(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the recorder still keeps 5-minute statistics from 12:00. The
    # hour's 0.5 kWh came as 0.1 at 0.30 and 0.4 when the price was below
    # nothing, and 20:00's 1 kWh at 0.20
    _record_prices(hass, "sensor.market_import", dict.fromkeys(range(24), 0.25))
    _record_five_minute_meter(
        hass,
        "sensor.grid_import",
        12,
        total_before=1.0,
        kwh={(12, 0): 0.1, (12, 5): 0.4, (20, 0): 1.0},
    )
    _record_five_minute_meter(
        hass, "sensor.grid_export", 12, total_before=0.0, kwh={(12, 10): 2.0}
    )
    _record_five_minute_prices(
        hass, "sensor.market_import", 12, 0.20, {(12, 0): 0.30, (12, 5): -0.05}
    )
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - 07:00 at its hour's mean, then five minutes at a time, nothing
    # counted twice
    assert result["imported_kwh"] == pytest.approx(2.5)
    assert result["exported_kwh"] == pytest.approx(2.0)
    market = _by_name(result)["Wholesale"]
    assert market["energy"] == pytest.approx(0.25 + 0.1 * 0.30 - 0.4 * 0.05 + 0.20)
    assert dt_util.parse_datetime(result["five_minute_from"]) == DAY_START + timedelta(
        hours=12
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_hour_the_market_price_is_missing_for_carries_the_last_price(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no price recorded for 12:00, after 0.40 at 11:00
    prices = {hour: 0.20 for hour in range(24) if hour != 12} | {11: 0.40}
    _record_prices(hass, "sensor.market_import", prices)
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - priced at the price before it, and said
    market = _by_name(result)["Wholesale"]
    assert market["energy"] == pytest.approx(0.20 + 0.5 * 0.40 + 0.20)
    assert market["carried_hours"] == 1


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_every_plan_is_compared_from_when_all_of_them_can_be_priced(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the market plan's price history starts at 10:00, after the 07:00
    # import, beside a banded plan that could price the whole day
    _record_prices(hass, "sensor.market_import", dict.fromkeys(range(10, 24), 0.2))
    await async_wait_recording_done(hass)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _MARKET),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - both from 10:00, energy and daily charges alike, so the totals are
    # over the same hours; the span is said, and which plan set it (HEA-294)
    assert dt_util.parse_datetime(result["compared_from"]) == DAY_START + timedelta(
        hours=10
    )
    assert result["compared_from_plan"] == "Wholesale"
    assert result["imported_kwh"] == pytest.approx(1.5)
    assert result["days"] == pytest.approx(14 / 24, abs=1e-4)
    plans = _by_name(result)
    flat = plans["Flat rate"]
    assert flat["energy"] == pytest.approx(1.5 * 0.234)
    assert flat["export_credit"] == pytest.approx(2.0 * 0.05)
    assert flat["daily_charges"] == pytest.approx(0.45 * 14 / 24, abs=1e-4)
    market = plans["Wholesale"]
    assert market["energy"] == pytest.approx(0.5 * 0.20 + 1 * 0.20)
    assert market["daily_charges"] == pytest.approx(1.0 * 14 / 24, abs=1e-4)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_period_before_the_meters_were_recorded_is_compared_from_them(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - two days asked for, the grid meters recorded only the second
    _calendar(hass, [])
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass, start=DAY_START - timedelta(days=1))

    # Then - one day's charge, not two against one day's energy; the meters, not
    # a plan, set the start
    assert dt_util.parse_datetime(result["compared_from"]) == DAY_START
    assert result["compared_from_plan"] is None
    assert _by_name(result)["Flat rate"]["daily_charges"] == pytest.approx(0.45)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_comparison_over_the_whole_period_says_no_start_of_its_own(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - every plan can price the whole day the meters recorded
    _calendar(hass, [])
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - nothing to say: the card shows the period it asked for
    assert result["compared_from"] is None
    assert result["compared_from_plan"] is None


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_price_per_watt_hour_is_read_per_kilowatt_hour(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the market's price stated per Wh, as the Energy Dashboard accepts
    _record_prices(
        hass,
        "sensor.market_import",
        dict.fromkeys(range(24), 0.0003),
        unit="EUR/Wh",
    )
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - 0.30 per kWh
    assert _by_name(result)["Wholesale"]["energy"] == pytest.approx(2.5 * 0.30)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_banded_plan_can_export_at_the_market(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the flat plan, its feed-in following the market at 0.15 at noon
    _record_prices(hass, "sensor.market_export", dict.fromkeys(range(24), 0.15))
    await async_wait_recording_done(hass)
    feed_in = {
        **_FLAT,
        CONF_NAME: "Flat, market feed-in",
        CONF_PLAN_EXPORT_PRICE_ENTITY: "sensor.market_export",
    }
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, feed_in))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - import at its band, export at the market
    plan = _by_name(result)["Flat, market feed-in"]
    assert plan["energy"] == pytest.approx(2.5 * 0.234)
    assert plan["export_credit"] == pytest.approx(2.0 * 0.15)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_banded_plans_alone_are_priced_by_the_hour(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - 5-minute statistics kept, but no plan priced from the market
    _record_five_minute_meter(
        hass, "sensor.grid_import", 12, total_before=1.0, kwh={(12, 0): 0.5}
    )
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - a band prices five minutes as it prices their hour, so they are
    # not read
    assert result["five_minute_from"] is None
    assert result["imported_kwh"] == pytest.approx(2.5)
    assert "carried_hours" not in _by_name(result)["Flat rate"]


# Each plan priced as if the household had no solar or battery (HEA-293)


def _home_with(
    data: dict[str, Any], *subentries: tuple[str, dict[str, Any]]
) -> MockConfigEntry:
    """A house whose own inputs are these, beside its grid, batteries and plans."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_CURRENCY: "EUR", **data},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=kind, title=sub[CONF_NAME], data=sub, unique_id=None
            )
            for kind, sub in subentries
        ],
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_plan_is_priced_on_everything_the_house_used_without_solar(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - 3 kWh generated at noon, beside the day's imports and the 2 kWh
    # exported then, and no house meter: what the house used is import plus
    # generation less export, hour by hour - 1, 1.5 and 1 kWh
    _record(hass, "sensor.generation", {12: 3.0})
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _set_up(
        hass,
        _home_with(
            {CONF_GENERATION_ENTITY: ["sensor.generation"]},
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
        ),
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - all 3.5 kWh bought at the plan's price, nothing exported, and the
    # day's charge: what the plan would have cost with no solar or battery
    assert flat["without_installation"] == pytest.approx(3.5 * 0.234 + 0.45)
    assert flat["total"] == pytest.approx(0.935)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_house_meter_says_what_the_house_used_where_there_is_one(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the same generation, and a house meter that says 4 kWh
    _record(hass, "sensor.generation", {12: 3.0})
    _record(hass, "sensor.house_consumption", {7: 1.0, 12: 2.0, 20: 1.0})
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _set_up(
        hass,
        _home_with(
            {
                CONF_GENERATION_ENTITY: ["sensor.generation"],
                CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
            },
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
        ),
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - the meter's 4 kWh, not the balance's 3.5
    assert flat["without_installation"] == pytest.approx(4.0 * 0.234 + 0.45)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_battery_s_charge_is_not_counted_as_used_until_it_is_discharged(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no export meter and no generation; a battery charging 1 kWh at
    # noon and giving back 0.8 at 20:00. At noon the house used less than
    # nothing by the balance (0.5 in, 1 into the battery), which is carried
    # into the evening rather than dropped
    _record(hass, "sensor.battery_charge", {12: 1.0})
    _record(hass, "sensor.battery_discharge", {20: 0.8})
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    grid = {key: _GRID[key] for key in _GRID if key != CONF_GRID_EXPORT_ENTITY}
    battery = {
        CONF_NAME: "Battery",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.battery_charge",
        CONF_BATTERY_DISCHARGE_ENTITY: "sensor.battery_discharge",
    }
    await _set_up(
        hass,
        _home_with(
            {},
            (SUBENTRY_TYPE_GRID, grid),
            (SUBENTRY_TYPE_BATTERY, battery),
            (SUBENTRY_TYPE_PLAN, _FLAT),
        ),
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - 1 + 0 + (1.8 - 0.5) = 2.3 kWh: the 0.2 kWh lost in the battery is
    # not something a house without one would have bought
    assert flat["without_installation"] == pytest.approx(2.3 * 0.234 + 0.45)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_house_with_no_solar_or_battery_has_nothing_to_compare_it_with(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - grid meters only
    _calendar(hass, [])
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - the figure would equal its import cost, a saving of nothing, so it
    # is not given at all
    assert "without_installation" not in flat
