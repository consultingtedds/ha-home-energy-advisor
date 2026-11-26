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
from homeassistant.components.energy.data import async_get_manager
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
from homeassistant.exceptions import ServiceValidationError
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
    CONF_PERIOD_FROM,
    CONF_PERIOD_PLAN,
    CONF_PLAN_ARCHIVED,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_ENTITY,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_DEMAND_CHARGE_ENTITY,
    CONF_PLAN_EXPORT_ALLOWANCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_EXPORT_PRICE_AFTER,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_HOLIDAYS,
    CONF_PLAN_IMPORT_PRICE_ADD,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PLAN_PERIODS,
    CONF_PLAN_WITHOUT_INSTALLATION,
    CONF_PRICE_ENTITY,
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
# A typed plan: one price all day.
_FLAT: dict[str, Any] = {
    CONF_NAME: "Flat rate",
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
        version=8,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=kind, title=data[CONF_NAME], data=data, unique_id=None
            )
            for kind, data in subentries
        ],
    )


def _record(
    hass: HomeAssistant,
    statistic_id: str,
    hours: dict[int, float],
    missing: frozenset[int] = frozenset(),
) -> None:
    """Hourly statistics for a meter: kWh in each local hour of the day, else 0.

    No row at all for the `missing` hours, as when the recorder was down. The
    counter kept counting, so what it counted then arrives in the next row.
    """
    total = 0.0
    rows = []
    for hour in range(24):
        total += hours.get(hour, 0.0)
        if hour in missing:
            continue
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
    # Given - two typed plans, one of them once marked as the household's, and
    # no holiday that day
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

    # Then - what was recorded, and each plan priced at it. Every hour has a row,
    # the hours with nothing imported included, so nothing is left out. Neither
    # typed plan is the current one: that one the integration keeps (ADR-0042)
    assert result["imported_kwh"] == pytest.approx(2.5)
    assert result["exported_kwh"] == pytest.approx(2.0)
    assert result["days"] == pytest.approx(1)
    assert result["left_out"] == []
    plans = _by_name(result)
    flat = plans["Flat rate"]
    assert flat["current"] is False
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


_TWO_PRICES = {
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


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_each_plan_breaks_its_cost_down_line_by_line_as_a_bill_does(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - two named prices: 07:00's 1 kWh falls at Night, 12:00's 0.5 and
    # 20:00's 1 at Peak
    _calendar(hass, [])
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _TWO_PRICES))
    )

    # When
    plan = _by_name(await _compare(hass_ws_client, hass))["Two prices"]

    # Then - the daily charge, each price's kWh and cost, and what export was
    # paid on, so every line can be matched against a bill (HEA-300)
    assert plan["breakdown"] == {
        "daily": {"rate": 0.45, "days": 1.0, "amount": 0.45},
        "imports": [
            {"name": "Peak", "rate": 0.31, "kwh": 1.5, "amount": 0.465},
            {"name": "Night", "rate": 0.09, "kwh": 1.0, "amount": 0.09},
        ],
        "exports": [
            {
                "name": "",
                "rate": 0.05,
                "kwh": 2.0,
                "amount": 0.1,
                "beyond_allowance": False,
            }
        ],
        # 0.555 for 2.5 kWh, read between the plan's cheapest and dearest
        "average_import_rate": 0.222,
        "cheapest_import_rate": 0.09,
        "dearest_import_rate": 0.31,
    }


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
    gappy_row = _by_name(result)["Flat rate"]
    assert gappy_row == {
        "id": gappy_row["id"],
        "name": "Flat rate",
        "current": False,
        "rates": {
            "prices": [{"name": "", "import": 0.234, "export": None}],
            "export": 0.05,
            "daily_charge": 0.45,
            "import_market": False,
            "export_market": False,
        },
        "incomplete": True,
    }


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
async def test_a_period_with_nothing_recorded_charges_nothing(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no statistics at all
    await hass.config.async_set_time_zone("Europe/Madrid")
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the whole day left out, its daily charge with it: a day the meters
    # have no record of is not a day of no use (ADR-0043). Said as no hours
    # recorded, so the card can say so too
    assert result["hours"] == 0
    assert result["days"] == 0
    assert _left_out(result) == [(DAY_START, DAY_END, "grid")]
    flat = _by_name(result)["Flat rate"]
    assert (flat["energy"], flat["daily_charges"]) == (0, 0)


def _left_out(result: dict[str, Any]) -> list[tuple[datetime, datetime, str]]:
    """The stretches the comparison left out, as times and what had no data."""
    return [
        (_time(stretch["from"]), _time(stretch["to"]), stretch["source"])
        for stretch in result["left_out"]
    ]


def _time(text: str) -> datetime:
    moment = dt_util.parse_datetime(text)
    assert moment is not None, text
    return moment


def _at(hour: float) -> datetime:
    return DAY_START + timedelta(hours=hour)


# Hours with no data, left out for every plan (HEA-299, ADR-0043)


@pytest.mark.usefixtures("recorder_mock")
async def test_hours_the_grid_meters_did_not_record_are_left_out_for_every_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the day's flows, but no row at all from 13:00 to 18:00, as when
    # the recorder was down for five hours
    await hass.config.async_set_time_zone("Europe/Madrid")
    gap = frozenset(range(13, 18))
    _record(hass, "sensor.grid_import", {7: 1.0, 12: 0.5, 20: 1.0}, gap)
    _record(hass, "sensor.grid_export", {12: 2.0}, gap)
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - those five hours are left out with the 18:00 row that carries
    # whatever they recorded (ADR-0046), and every plan's daily charge for them
    # with them; the energy recorded either side is priced as before
    assert _left_out(result) == [(_at(13), _at(19), "grid")]
    assert result["days"] == pytest.approx(18 / 24, abs=1e-4)
    plans = _by_name(result)
    assert plans["Flat rate"]["energy"] == pytest.approx(2.5 * 0.234)
    assert plans["Flat rate"]["daily_charges"] == pytest.approx(
        0.45 * 18 / 24, abs=1e-4
    )
    assert plans["Night saver"]["daily_charges"] == pytest.approx(
        0.30 * 18 / 24, abs=1e-4
    )
    # The breakdown covers the same hours, so its lines add up to the figures
    breakdown = plans["Night saver"]["breakdown"]
    assert sum(line["kwh"] for line in breakdown["imports"]) == pytest.approx(
        result["imported_kwh"]
    )
    assert breakdown["daily"]["days"] == pytest.approx(18 / 24, abs=1e-4)


@pytest.mark.usefixtures("recorder_mock")
async def test_the_row_that_ends_a_long_gap_is_left_out_with_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no rows from 13:00 to 16:00 while 3 kWh was imported, so the
    # 16:00 row's change carries all three hours (ADR-0046)
    await hass.config.async_set_time_zone("Europe/Madrid")
    gap = frozenset({13, 14, 15})
    _record(hass, "sensor.grid_import", {7: 1.0, 14: 3.0, 20: 1.0}, gap)
    _record(hass, "sensor.grid_export", {}, gap)
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the gap's energy is never priced as one hour
    assert _left_out(result) == [(_at(13), _at(17), "grid")]
    assert result["imported_kwh"] == pytest.approx(2.0)
    assert _by_name(result)["Flat rate"]["energy"] == pytest.approx(2.0 * 0.234)


@pytest.mark.usefixtures("recorder_mock")
async def test_two_hours_the_grid_meters_did_not_record_are_bridged(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no row for 13:00 or 14:00: a restart, the counter counting on
    await hass.config.async_set_time_zone("Europe/Madrid")
    gap = frozenset({13, 14})
    _record(hass, "sensor.grid_import", {7: 1.0, 12: 0.5, 14: 0.4, 20: 1.0}, gap)
    _record(hass, "sensor.grid_export", {12: 2.0}, gap)
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - nothing left out: the whole day's charge, and 14:00's 0.4 kWh
    # arriving in the 15:00 row
    assert result["left_out"] == []
    assert result["days"] == pytest.approx(1)
    assert result["imported_kwh"] == pytest.approx(2.9)
    assert _by_name(result)["Flat rate"]["daily_charges"] == pytest.approx(0.45)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_price_missing_for_two_hours_carries_the_last_price(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no price for 11:00 or 12:00, after 0.40 at 10:00
    prices = {hour: 0.20 for hour in range(24) if hour not in {11, 12}} | {10: 0.40}
    _record_prices(hass, "sensor.market_import", prices)
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - 12:00's import at the price before the gap, and nothing left out
    assert result["left_out"] == []
    market = _by_name(result)["Wholesale"]
    assert market["energy"] == pytest.approx(0.20 + 0.5 * 0.40 + 0.20)
    assert market["daily_charges"] == pytest.approx(1.0)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_price_missing_for_longer_is_left_out_for_every_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no price from 10:00 to 13:00, three hours, beside a banded plan
    prices = {hour: 0.20 for hour in range(24) if hour not in {10, 11, 12}}
    _record_prices(hass, "sensor.market_import", prices)
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

    # Then - those hours left out of both plans, 12:00's import and export
    # with them, so the two are compared over the same 21 hours; the sensor
    # with no statistics is named
    assert _left_out(result) == [(_at(10), _at(13), "sensor.market_import")]
    assert result["imported_kwh"] == pytest.approx(2.0)
    assert result["exported_kwh"] == 0
    plans = _by_name(result)
    flat = plans["Flat rate"]
    assert flat["energy"] == pytest.approx(2.0 * 0.234)
    assert flat["export_credit"] == 0
    assert flat["daily_charges"] == pytest.approx(0.45 * 21 / 24, abs=1e-4)
    market = plans["Wholesale"]
    assert market["energy"] == pytest.approx(2.0 * 0.20)
    assert market["daily_charges"] == pytest.approx(1.0 * 21 / 24, abs=1e-4)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_price_that_stops_part_way_leaves_out_the_rest_of_the_period(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the market price recorded until 16:00, then nothing: the GloBird
    # case, a sensor whose statistics stopped (discussion 58)
    _record_prices(hass, "sensor.market_import", dict.fromkeys(range(16), 0.2))
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

    # Then - not one price carried across the evening: 16:00 onwards left out,
    # 20:00's import with it
    assert _left_out(result) == [(_at(16), DAY_END, "sensor.market_import")]
    assert result["imported_kwh"] == pytest.approx(1.5)
    market = _by_name(result)["Wholesale"]
    assert market["energy"] == pytest.approx(1.5 * 0.20)
    assert market["daily_charges"] == pytest.approx(16 / 24, abs=1e-4)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_price_just_before_the_period_carries_into_its_first_hour(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - 0.30 at 23:00 the night before, then nothing until 01:00
    _record_prices(
        hass,
        "sensor.market_import",
        {-1: 0.30} | dict.fromkeys(range(1, 24), 0.2),
    )
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - an hour's gap across midnight, carried, so the whole day compared
    assert result["left_out"] == []
    assert _by_name(result)["Wholesale"]["daily_charges"] == pytest.approx(1.0)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_price_recorded_only_before_the_period_cannot_be_compared(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the market price stopped the day before, beside a banded plan
    _record_prices(hass, "sensor.market_import", dict.fromkeys(range(-24, 0), 0.2))
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

    # Then - nothing carried in from the day before; the plan is listed alone,
    # naming its sensor, and the banded plan keeps the whole day
    assert result["left_out"] == []
    plans = _by_name(result)
    assert plans["Wholesale"]["no_price"] is True
    assert plans["Wholesale"]["no_price_entities"] == ["sensor.market_import"]
    assert plans["Flat rate"]["daily_charges"] == pytest.approx(0.45)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_household_without_plans_compares_only_its_current_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no plan typed
    await _set_up(hass, _house((SUBENTRY_TYPE_GRID, _GRID)))

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the plan it is on, which the integration keeps (ADR-0042)
    assert [plan["name"] for plan in result["plans"]] == ["Your current plan"]


@pytest.mark.usefixtures("recorder_mock")
async def test_the_dashboard_can_ask_which_plans_there_are(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - two typed plans, beside the current plan the integration keeps
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
    assert plans == {
        "Flat rate": False,
        "Night saver": False,
        "Your current plan": True,
    }


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


# The comparison as an action, for scripts and other tools (HEA-302)


async def _call_compare(
    hass: HomeAssistant, start: str | datetime, end: str | datetime
) -> ServiceResponse:
    return await hass.services.async_call(
        DOMAIN,
        "compare_plans",
        {"start": start, "end": end},
        blocking=True,
        return_response=True,
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_the_action_returns_what_the_card_is_shown(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the current plan and an offer
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _TWO_PRICES),
        ),
    )

    # When - the same day asked both ways, the action in local time as a
    # household types it into a script
    shown = await _compare(hass_ws_client, hass)
    returned = await _call_compare(hass, "2026-10-14 00:00:00", "2026-10-15 00:00:00")

    # Then - one comparison, whichever asks
    assert returned == shown
    assert set(_by_name(shown)) == {"Flat rate", "Two prices", "Your current plan"}


@pytest.mark.usefixtures("recorder_mock")
async def test_the_action_refuses_an_end_before_its_start(hass: HomeAssistant) -> None:
    # Given
    await hass.config.async_set_time_zone("Europe/Madrid")
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When / Then - said in the household's language, not as a traceback
    with pytest.raises(ServiceValidationError) as refused:
        await _call_compare(hass, DAY_END, DAY_START)
    assert refused.value.translation_key == "compare_end_before_start"


@pytest.mark.usefixtures("recorder_mock")
async def test_the_action_refuses_a_period_that_has_not_started(
    hass: HomeAssistant,
) -> None:
    # Given
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )
    tomorrow = dt_util.now() + timedelta(days=1)

    # When / Then - nothing has been recorded yet to compare
    with pytest.raises(ServiceValidationError) as refused:
        await _call_compare(hass, tomorrow, tomorrow + timedelta(days=1))
    assert refused.value.translation_key == "compare_not_started"


@pytest.mark.usefixtures("recorder_mock")
async def test_the_action_refuses_while_the_integration_is_not_set_up(
    hass: HomeAssistant,
) -> None:
    # Given - set up, then unloaded, so the action is registered but has
    # nothing to compare
    entry = _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    await _set_up(hass, entry)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # When / Then
    with pytest.raises(ServiceValidationError) as refused:
        await _call_compare(hass, DAY_START, DAY_END)
    assert refused.value.translation_key == "compare_not_loaded"


# Plans priced from a market price entity (HEA-260, ADR-0037)

# A wholesale plan: import at whatever the market charged, a flat feed-in, and
# the daily charge the feed leaves out.
_MARKET = {
    CONF_NAME: "Wholesale",
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
    assert result["left_out"] == []
    assert result["five_minute_from"] is None
    # One line for the market, no rate of its own; its average read between the
    # cheapest and dearest hours it was charged at, not the hours nothing was
    # imported in
    breakdown = market["breakdown"]
    assert breakdown["imports"] == [
        {"name": "", "rate": None, "kwh": 2.5, "amount": 0.49}
    ]
    assert breakdown["average_import_rate"] == pytest.approx(0.196)
    assert (breakdown["cheapest_import_rate"], breakdown["dearest_import_rate"]) == (
        0.12,
        0.30,
    )


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
async def test_an_hour_with_no_five_minute_prices_takes_its_hourly_mean(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - 5-minute meters from 12:00, but the price entity's history only
    # hourly, as when it was carried in behind a new sensor (HEA-320): 0.25 all
    # day, 0.30 at 12:00 and 0.22 at 20:00
    _record_prices(
        hass,
        "sensor.market_import",
        dict.fromkeys(range(24), 0.25) | {12: 0.30, 20: 0.22},
    )
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
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - every hour priced at its hourly mean, nothing left out
    assert result["left_out"] == []
    market = _by_name(result)["Wholesale"]
    assert market["energy"] == pytest.approx(1 * 0.25 + 0.5 * 0.30 + 1 * 0.22)
    assert "no_price" not in market


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
    # over the same hours; what was left out is said, and which sensor had no
    # statistics (HEA-294, ADR-0043)
    assert _left_out(result) == [(DAY_START, _at(10), "sensor.market_import")]
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
    # a plan, left the first day out
    assert _left_out(result) == [(DAY_START - timedelta(days=1), DAY_START, "grid")]
    assert _by_name(result)["Flat rate"]["daily_charges"] == pytest.approx(0.45)


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


# Each plan priced as if the household had no solar or battery (HEA-293)


def _home_with(
    data: dict[str, Any], *subentries: tuple[str, dict[str, Any]]
) -> MockConfigEntry:
    """A house whose own inputs are these, beside its grid, batteries and plans."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=8,
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


# An hour no home could use, left out for every plan (HEA-301, ADR-0044)


def _impossible(result: dict[str, Any]) -> list[tuple[datetime, datetime, str, float]]:
    """The stretches left out for recording more than a home could use."""
    return [
        (
            _time(stretch["from"]),
            _time(stretch["to"]),
            stretch["source"],
            stretch["kwh"],
        )
        for stretch in result["left_out"]
        if "kwh" in stretch
    ]


@pytest.mark.usefixtures("recorder_mock")
async def test_a_grid_hour_no_home_could_import_is_left_out_for_every_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the day's flows, and 13:00 recording 11,041 kWh in, as a glitched
    # template leaves in the statistics
    await hass.config.async_set_time_zone("Europe/Madrid")
    _record(hass, "sensor.grid_import", {7: 1.0, 12: 0.5, 13: 11041.0, 20: 1.0})
    _record(hass, "sensor.grid_export", {12: 2.0})
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - that hour left out of every plan with its daily charge, and named
    # with what the meter recorded, so it can be found and corrected
    assert _impossible(result) == [(_at(13), _at(14), "sensor.grid_import", 11041.0)]
    assert result["imported_kwh"] == pytest.approx(2.5)
    assert result["days"] == pytest.approx(23 / 24, abs=1e-4)
    flat = _by_name(result)["Flat rate"]
    assert flat["energy"] == pytest.approx(2.5 * 0.234)
    assert flat["daily_charges"] == pytest.approx(0.45 * 23 / 24, abs=1e-4)


@pytest.mark.usefixtures("recorder_mock")
async def test_an_impossible_row_after_a_short_gap_takes_the_gap_with_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - no rows at 13:00 or 14:00, a gap short enough to bridge, and the
    # 15:00 row recording 11,041 kWh: a counter carries a gap's energy into the
    # row after it, so that row's change covers 13:00 to 16:00
    await hass.config.async_set_time_zone("Europe/Madrid")
    gap = frozenset({13, 14})
    _record(hass, "sensor.grid_import", {7: 1.0, 15: 11041.0, 20: 1.0}, gap)
    _record(hass, "sensor.grid_export", {12: 2.0}, gap)
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the gap is left out with the row that carries it, its daily
    # charges too, rather than bridged and priced as if nothing was used
    assert _impossible(result) == [(_at(13), _at(16), "sensor.grid_import", 11041.0)]
    assert result["days"] == pytest.approx(21 / 24, abs=1e-4)
    assert _by_name(result)["Flat rate"]["energy"] == pytest.approx(2.0 * 0.234)


@pytest.mark.usefixtures("recorder_mock")
async def test_an_hour_at_the_ceiling_is_a_real_hour(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - exactly 100 kWh in an hour, more than any home here would, but
    # not beyond what the ceiling allows
    await hass.config.async_set_time_zone("Europe/Madrid")
    _record(hass, "sensor.grid_import", {3: 100.0})
    _record(hass, "sensor.grid_export", {})
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - priced, nothing left out
    assert result["left_out"] == []
    assert _by_name(result)["Flat rate"]["energy"] == pytest.approx(100 * 0.234)


@pytest.mark.usefixtures("recorder_mock")
async def test_a_counter_that_fell_by_more_than_the_ceiling_is_left_out_too(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - an export meter whose statistics fell by 500 kWh at 15:00, as a
    # bad correction leaves them
    await hass.config.async_set_time_zone("Europe/Madrid")
    _record(hass, "sensor.grid_import", {7: 1.0})
    _record(hass, "sensor.grid_export", {12: 2.0, 15: -500.0})
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _FLAT))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then
    assert _impossible(result) == [(_at(15), _at(16), "sensor.grid_export", -500.0)]
    assert result["exported_kwh"] == pytest.approx(2.0)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_impossible_hour_on_the_house_meter_is_left_out_for_every_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the house meter recorded 11,041 kWh at 20:00, the hour hlps4's
    # did, while the grid meters are sound
    _record(hass, "sensor.generation", {12: 3.0})
    _record(hass, "sensor.house_consumption", {7: 1.0, 12: 2.0, 20: 11041.0})
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
    result = await _compare(hass_ws_client, hass)

    # Then - the hour is left out of every figure, not only the one it would
    # have multiplied, so every column still covers the same hours
    assert _impossible(result) == [
        (_at(20), _at(21), "sensor.house_consumption", 11041.0)
    ]
    flat = _by_name(result)["Flat rate"]
    assert flat["energy"] == pytest.approx(1.5 * 0.234)
    assert flat["without_installation"] == pytest.approx(
        3.0 * 0.234 + 0.45 * 23 / 24, abs=1e-4
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_five_minutes_are_held_to_the_same_rate(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - five-minute statistics from 12:00, with 9 kWh in the five minutes
    # from 12:05: 108 kWh an hour, over the ceiling, though far under 100 kWh
    await hass.config.async_set_time_zone("Europe/Madrid")
    _record(hass, "sensor.grid_import", {7: 1.0})
    _record(hass, "sensor.grid_export", {})
    _record_prices(hass, "sensor.market_import", dict.fromkeys(range(24), 0.25))
    _record_five_minute_meter(
        hass, "sensor.grid_import", 12, total_before=1.0, kwh={(12, 5): 9.0}
    )
    _record_five_minute_meter(hass, "sensor.grid_export", 12, total_before=0.0, kwh={})
    _record_five_minute_prices(hass, "sensor.market_import", 12, 0.25, {})
    await async_wait_recording_done(hass)
    await _set_up(
        hass, _house((SUBENTRY_TYPE_GRID, _GRID), (SUBENTRY_TYPE_PLAN, _MARKET))
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - those five minutes left out, and only those
    five = timedelta(minutes=5)
    assert _impossible(result) == [
        (_at(12) + five, _at(12) + 2 * five, "sensor.grid_import", 9.0)
    ]
    assert result["imported_kwh"] == pytest.approx(1.0)


# The current plan, priced at the prices Paid is priced at (ADR-0042)

_CURRENT = "Your current plan"


def _current_plan(**rules: Any) -> tuple[str, dict[str, Any]]:  # noqa: ANN401 - its rules
    return (
        SUBENTRY_TYPE_PLAN,
        {CONF_NAME: _CURRENT, CONF_PLAN_FOLLOWS: True, **rules},
    )


async def _energy_dashboard_export(
    hass: HomeAssistant, *, entity: str | None = None, number: float | None = None
) -> None:
    """The Energy Dashboard's grid source, its export priced as given."""
    manager = await async_get_manager(hass)
    source: dict[str, Any] = {
        "type": "grid",
        "stat_energy_from": "sensor.grid_import",
        "stat_energy_to": "sensor.grid_export",
        "entity_energy_price_export": entity,
        "number_energy_price_export": number,
    }
    update: Any = {"energy_sources": [source]}
    await manager.async_update(update)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_the_current_plan_is_priced_at_the_grid_meter_s_own_price(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the grid meter priced at 0.20 fixed, export at 0.05 in the Energy
    # Dashboard, and a typed plan the household had marked as the one it is on
    _calendar(hass, [])
    await _energy_dashboard_export(hass, number=0.05)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the day's 2.5 kWh at the meter's 0.20 and 2 kWh out at 0.05, with
    # its own daily charge; the typed plan is an ordinary plan beside it
    current = _by_name(result)[_CURRENT]
    assert current["current"] is True
    assert current["follows_prices"] is True
    assert current["energy"] == pytest.approx(2.5 * 0.2)
    assert current["export_credit"] == pytest.approx(2.0 * 0.05)
    assert current["daily_charges"] == pytest.approx(0.45)
    assert "daily_charge_missing" not in current
    assert _by_name(result)["Flat rate"]["current"] is False


@pytest.mark.usefixtures("recorder_mock")
async def test_each_grid_meter_is_priced_at_its_own_price(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - a dual-rate home: the day register priced by a sensor at 0.30
    # until 16:00 and 0.40 after, the night one at a fixed 0.10
    await hass.config.async_set_time_zone("Europe/Madrid")
    _record(hass, "sensor.day_register", {10: 2.0, 18: 1.0})
    _record(hass, "sensor.night_register", {3: 4.0})
    _record_prices(
        hass,
        "sensor.day_price",
        {hour: 0.30 if hour < 16 else 0.40 for hour in range(24)},
    )
    await async_wait_recording_done(hass)
    day = {
        CONF_NAME: "Day",
        CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
        CONF_PRICE_ENTITY: "sensor.day_price",
    }
    night = {
        CONF_NAME: "Night",
        CONF_GRID_IMPORT_ENTITY: "sensor.night_register",
        CONF_FIXED_PRICE: 0.1,
    }
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, day),
            (SUBENTRY_TYPE_GRID, night),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - each meter's energy at its own price, as Paid prices it
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(2.0 * 0.30 + 1.0 * 0.40 + 4.0 * 0.10)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_export_follows_the_energy_dashboard_s_export_price(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - export priced by a sensor, 0.06 that day
    _record_prices(hass, "sensor.export_price", dict.fromkeys(range(24), 0.06))
    await async_wait_recording_done(hass)
    await _energy_dashboard_export(hass, entity="sensor.export_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then
    assert _by_name(result)[_CURRENT]["export_credit"] == pytest.approx(2.0 * 0.06)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_daily_charge_can_follow_a_grid_source_s_recorded_cost(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the standing charge entered in the Energy Dashboard as a grid
    # source of its own, however it is built: its cost recorded at 0.13 every
    # six hours, 0.52 for the day
    _record_money(hass, "sensor.daily_charge_cost", dict.fromkeys((0, 6, 12, 18), 0.13))
    await async_wait_recording_done(hass)
    manager = await async_get_manager(hass)
    standing: Any = {
        "energy_sources": [
            {
                "type": "grid",
                "stat_energy_from": "sensor.daily_charge",
                "stat_cost": "sensor.daily_charge_cost",
            }
        ]
    }
    await manager.async_update(standing)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE_SOURCE: "sensor.daily_charge"}),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - exactly what Home Assistant recorded it costing that day
    current = _by_name(result)[_CURRENT]
    assert current["daily_charges"] == pytest.approx(0.52)
    assert "daily_charge_missing" not in current


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_followed_daily_charge_leaves_out_the_hours_compared_without_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the same source's cost, and the comparison asked for the morning
    _record_money(hass, "sensor.daily_charge_cost", dict.fromkeys((0, 6, 12, 18), 0.13))
    await async_wait_recording_done(hass)
    manager = await async_get_manager(hass)
    standing: Any = {
        "energy_sources": [
            {
                "type": "grid",
                "stat_energy_from": "sensor.daily_charge",
                "stat_cost": "sensor.daily_charge_cost",
            }
        ]
    }
    await manager.async_update(standing)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE_SOURCE: "sensor.daily_charge"}),
        ),
    )

    # When - midnight to noon
    result = await _compare(hass_ws_client, hass, end=_at(12))

    # Then - only what it cost in those hours
    assert _by_name(result)[_CURRENT]["daily_charges"] == pytest.approx(0.26)


def _record_money(
    hass: HomeAssistant, statistic_id: str, hours: dict[int, float]
) -> None:
    """A cost statistic's running total: these amounts at these local hours."""
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
        unit_class=None,
        unit_of_measurement="EUR",
    )
    async_import_statistics(hass, metadata, rows)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_without_a_daily_charge_the_current_plan_says_so(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the current plan created, its daily charge not given yet
    await _set_up(hass, _house((SUBENTRY_TYPE_GRID, _GRID), _current_plan()))

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - its energy still priced, its daily charge said to be missing, so
    # the card holds every plan's difference from it rather than rank wrongly
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(2.5 * 0.2)
    assert current["daily_charges"] == pytest.approx(0)
    assert current["daily_charge_missing"] is True


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_daily_charge_sensor_with_no_statistics_charges_what_it_reads(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - a supplier's daily charge sensor with no state class, so Home
    # Assistant keeps no statistics for it, reading 0.45 now (HEA-317)
    hass.states.async_set("sensor.supplier_daily_charge", "0.45")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(
                **{CONF_PLAN_DAILY_CHARGE_ENTITY: "sensor.supplier_daily_charge"}
            ),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the day charged what it reads
    current = _by_name(result)[_CURRENT]
    assert current["daily_charges"] == pytest.approx(0.45)
    assert "daily_charge_missing" not in current


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_unavailable_daily_charge_sensor_with_no_statistics_is_missing(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the same sensor, unavailable and never recorded
    hass.states.async_set("sensor.supplier_daily_charge", "unavailable")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(
                **{CONF_PLAN_DAILY_CHARGE_ENTITY: "sensor.supplier_daily_charge"}
            ),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - said to be missing, never charged as nothing
    assert _by_name(result)[_CURRENT]["daily_charge_missing"] is True


# What the installation saved, against the plan the household would be on
# without it (HEA-306)


async def _installed_home(hass: HomeAssistant, *plans: dict[str, Any]) -> None:
    """The day's generation, the grid, the current plan, and these plans."""
    _record(hass, "sensor.generation", {12: 3.0})
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _set_up(
        hass,
        _home_with(
            {CONF_GENERATION_ENTITY: ["sensor.generation"]},
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.3}),
            *((SUBENTRY_TYPE_PLAN, plan) for plan in plans),
        ),
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_the_installation_is_measured_against_the_plan_ticked_without_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the flat rate ticked as the plan the household would be on
    # without its installation, and the offer not
    await _installed_home(hass, {**_FLAT, CONF_PLAN_WITHOUT_INSTALLATION: True}, _OFFER)

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the flat rate bought everything from the grid, 3.5 kWh and a day's
    # charge, less what the current plan actually cost: 2.5 kWh at 0.2 and its
    # own daily charge
    without = 3.5 * 0.234 + 0.45
    paid = 2.5 * 0.2 + 0.3
    assert result["installation"] == {
        "plan": "Flat rate",
        "without_installation": pytest.approx(without),
        "paid": pytest.approx(paid),
        "saved": pytest.approx(without - paid),
    }


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_nothing_is_said_of_the_installation_with_no_plan_ticked(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given
    await _installed_home(hass, _FLAT, _OFFER)

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - never the cheapest offer chosen for it, unasked
    assert "installation" not in result


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_archived_plan_ticked_without_the_installation_still_measures_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the plan ticked, archived to keep the table to offers weighed
    await _installed_home(
        hass, {**_FLAT, CONF_PLAN_WITHOUT_INSTALLATION: True, CONF_PLAN_ARCHIVED: True}
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - left out of the table, but still the measure
    assert "Flat rate" not in _by_name(result)
    assert result["installation"]["without_installation"] == pytest.approx(
        3.5 * 0.234 + 0.45
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_the_installation_waits_for_the_current_plan_s_daily_charge(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the current plan's daily charge not given yet
    _record(hass, "sensor.generation", {12: 3.0})
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _set_up(
        hass,
        _home_with(
            {CONF_GENERATION_ENTITY: ["sensor.generation"]},
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(),
            (SUBENTRY_TYPE_PLAN, {**_FLAT, CONF_PLAN_WITHOUT_INSTALLATION: True}),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the plan named, the figure held: without its daily charge the
    # current plan would read cheaper, and the saving larger, than it is
    assert result["installation"] == {"plan": "Flat rate"}


# A demand or capacity charge from a sensor giving its cost per day (HEA-322)

_DEMAND = "sensor.capacity_charge_per_day"


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_demand_charge_sensor_adds_its_own_line_to_a_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - a household's template giving its capacity charge, 0.47 a day
    hass.states.async_set(_DEMAND, "0.47")
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, {**_FLAT, CONF_PLAN_DEMAND_CHARGE_ENTITY: _DEMAND}),
        ),
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - a day of it, apart from the daily charge, and in the total
    assert flat["demand_charges"] == pytest.approx(0.47)
    assert flat["daily_charges"] == pytest.approx(0.45)
    assert flat["total"] == pytest.approx(0.935 + 0.47)
    assert flat["breakdown"]["demand"] == {
        "rate": pytest.approx(0.47),
        "days": pytest.approx(1),
        "amount": pytest.approx(0.47),
    }


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_plan_without_a_demand_charge_sensor_has_no_demand_line(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - one plan with a demand charge and one without
    hass.states.async_set(_DEMAND, "0.47")
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, {**_FLAT, CONF_PLAN_DEMAND_CHARGE_ENTITY: _DEMAND}),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )

    # When
    offer = _by_name(await _compare(hass_ws_client, hass))["Night saver"]

    # Then - nothing said about a charge it was never given
    assert "demand_charges" not in offer
    assert "demand" not in offer["breakdown"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_buying_everything_from_the_grid_carries_the_same_demand_charge(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the day's generation, and the plan's demand charge of 0.47 a day
    _record(hass, "sensor.generation", {12: 3.0})
    await async_wait_recording_done(hass)
    hass.states.async_set(_DEMAND, "0.47")
    _calendar(hass, [])
    await _set_up(
        hass,
        _home_with(
            {CONF_GENERATION_ENTITY: ["sensor.generation"]},
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, {**_FLAT, CONF_PLAN_DEMAND_CHARGE_ENTITY: _DEMAND}),
        ),
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - the same charge on both sides, so what the installation saves is
    # what it saved before: a peak it lowered is not counted, not taken off
    assert flat["without_installation"] == pytest.approx(3.5 * 0.234 + 0.45 + 0.47)
    assert flat["without_installation"] - flat["total"] == pytest.approx(
        3.5 * 0.234 + 0.45 - 0.935
    )


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_the_current_plan_takes_a_demand_charge_from_a_sensor(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the current plan with its daily charge typed and a demand sensor
    hass.states.async_set(_DEMAND, "0.47")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            _current_plan(
                **{CONF_PLAN_DAILY_CHARGE: 0.3, CONF_PLAN_DEMAND_CHARGE_ENTITY: _DEMAND}
            ),
        ),
    )

    # When
    current = _by_name(await _compare(hass_ws_client, hass))[_CURRENT]

    # Then
    assert current["demand_charges"] == pytest.approx(0.47)
    assert current["total"] == pytest.approx(2.5 * 0.2 + 0.3 + 0.47)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_demand_charge_sensor_that_reads_nothing_is_said_to_be_missing(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the demand sensor unavailable and never recorded
    hass.states.async_set(_DEMAND, "unavailable")
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, {**_FLAT, CONF_PLAN_DEMAND_CHARGE_ENTITY: _DEMAND}),
        ),
    )

    # When
    flat = _by_name(await _compare(hass_ws_client, hass))["Flat rate"]

    # Then - said to be missing, never charged as nothing, and the total is
    # what can be priced
    assert flat["demand_charge_missing"] is True
    assert "demand_charges" not in flat
    assert flat["total"] == pytest.approx(0.935)


# Hours the current plan's price sensors have no statistics for (HEA-311)

# The grid meter priced by a sensor, as most households' is.
_GRID_PRICED = {
    CONF_NAME: "Grid",
    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
    CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
    CONF_PRICE_ENTITY: "sensor.grid_buy_price",
}


def _a_price_without_statistics(hass: HomeAssistant, entity: str) -> None:
    """A price sensor Home Assistant keeps no statistics for: no state class."""
    hass.states.async_set(entity, "0.3", {"unit_of_measurement": "EUR/kWh"})


async def _price_history_from(hass: HomeAssistant, title: str) -> None:
    """Have the current plan read the prices its sensors lack from this plan."""
    await _plans_been_on(hass, (title, None))


async def _plans_been_on(hass: HomeAssistant, *periods: tuple[str, str | None]) -> None:
    """The plans the household has been on, each by title from a day or from always."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    by_title = {subentry.title: subentry for subentry in entry.subentries.values()}
    current = by_title[_CURRENT]
    listed = [
        {CONF_PERIOD_PLAN: by_title[title].subentry_id}
        | ({CONF_PERIOD_FROM: day} if day else {})
        for title, day in periods
    ]
    hass.config_entries.async_update_subentry(
        entry, current, data={**current.data, CONF_PLAN_PERIODS: listed}
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("recorder_mock")
async def test_each_gap_hour_is_priced_at_the_plan_the_household_was_on_that_day(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - 1 kWh in at 07:00 on Tuesday 13 and on Wednesday 14 October, the
    # price sensor with no statistics, and the household on the night saver
    # until it switched to the flat rate on the 14th
    await hass.config.async_set_time_zone("Europe/Madrid")
    before = DAY_START - timedelta(days=1)
    rows = [
        StatisticData(
            start=(before + timedelta(hours=hour)).astimezone(UTC),
            state=total,
            sum=total,
        )
        for hour, total in ((h, float(h >= 7) + float(h >= 31)) for h in range(48))
    ]
    async_import_statistics(
        hass,
        StatisticMetaData(
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=None,
            source="recorder",
            statistic_id="sensor.grid_import",
            unit_class="energy",
            unit_of_measurement="kWh",
        ),
        rows,
    )
    await async_wait_recording_done(hass)
    _calendar(hass, [])
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _plans_been_on(hass, ("Night saver", None), ("Flat rate", "2026-10-14"))

    # When - both days at once
    result = await _compare(hass_ws_client, hass, start=before)

    # Then - the 13th's 07:00 at the night saver's overnight 0.09, the 14th's at
    # the flat rate's 0.234, from its first hour; both plans named, in order
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(0.09 + 0.234)
    assert current["history_from"] == ["Night saver", "Flat rate"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_period_starting_later_does_not_price_the_days_before_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the switch to the flat rate the day after the one compared
    _calendar(hass, [])
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _plans_been_on(hass, ("Night saver", None), ("Flat rate", "2026-10-15"))

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the whole day at the night saver: 07:00 overnight, 12:00 and 20:00
    # in its day band; the flat rate not named, as it priced nothing
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(1.0 * 0.09 + 1.5 * 0.31)
    assert current["history_from"] == ["Night saver"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_hours_before_the_first_dated_period_cannot_be_priced(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - only a period from the 15th: nothing says what the household was
    # on before it
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _plans_been_on(hass, ("Flat rate", "2026-10-15"))

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - listed unpriced, naming the sensor
    current = _by_name(result)[_CURRENT]
    assert current["no_price"] is True
    assert current["no_price_entities"] == ["sensor.grid_buy_price"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_hours_without_the_sensor_s_statistics_are_priced_at_the_plan_named(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the grid meter's price sensor recorded from 12:00 only, at 0.30,
    # and the current plan's price history read from the night saver
    _calendar(hass, [])
    await _energy_dashboard_export(hass, number=0.05)
    _record_prices(hass, "sensor.grid_buy_price", dict.fromkeys(range(12, 24), 0.30))
    await async_wait_recording_done(hass)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Night saver")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - 07:00's 1 kWh at the night saver's overnight 0.09, a Wednesday;
    # 12:00's 0.5 and 20:00's 1 at the sensor's 0.30; and the card told which
    # plan priced the hours the sensor has no statistics for
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(1.0 * 0.09 + 1.5 * 0.30)
    assert current["history_from"] == ["Night saver"]
    # Nothing left out for any plan: no other plan follows that sensor
    assert result["left_out"] == []
    assert result["hours"] == 24
    assert _by_name(result)["Flat rate"]["energy"] == pytest.approx(2.5 * 0.234)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_sensor_with_no_statistics_at_all_is_priced_at_the_plan_named(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the grid meter's price sensor has no state class, so no
    # statistics, as discussion 58 found
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Flat rate")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - every hour at the flat rate's 0.234, rather than no figures at all
    current = _by_name(result)[_CURRENT]
    assert "no_price" not in current
    assert current["energy"] == pytest.approx(2.5 * 0.234)
    assert current["export_credit"] == pytest.approx(2.0 * 0.05)
    assert current["history_from"] == ["Flat rate"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_day_a_shared_sensor_recorded_nothing_is_priced_at_the_plan_named(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the grid meter priced by the same sensor a wholesale plan follows,
    # with no statistics that day, as before the sensor existed (discussion 58)
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (
                SUBENTRY_TYPE_PLAN,
                {**_MARKET, CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.grid_buy_price"},
            ),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Flat rate")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the current plan at the flat rate's 0.234; the wholesale plan
    # still cannot be priced, since its price is the sensor's own
    plans = _by_name(result)
    assert plans[_CURRENT]["energy"] == pytest.approx(2.5 * 0.234)
    assert plans[_CURRENT]["history_from"] == ["Flat rate"]
    assert plans["Wholesale"]["no_price"] is True
    assert result["left_out"] == []


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_shared_sensor_s_gap_within_the_period_is_left_out_for_every_plan(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the shared sensor recorded from 12:00, so the wholesale plan has
    # no price for the morning, and a plan named for the price history
    await _energy_dashboard_export(hass, number=0.05)
    _record_prices(hass, "sensor.grid_buy_price", dict.fromkeys(range(12, 24), 0.30))
    await async_wait_recording_done(hass)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (
                SUBENTRY_TYPE_PLAN,
                {**_MARKET, CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.grid_buy_price"},
            ),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Flat rate")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the morning left out of every plan, so all are compared over the
    # same hours (ADR-0043); the current plan at the sensor's price for the rest
    assert [stretch["source"] for stretch in result["left_out"]] == [
        "sensor.grid_buy_price"
    ]
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(1.5 * 0.30)
    assert "history_from" not in current


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_market_plan_named_prices_the_gap_at_its_market_price_adjusted(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the grid meter's price sensor with no statistics, and the plan
    # named a wholesale one adding 0.05 to its market price, as discussion 58's
    # old plan was: 0.10 before noon, 0.20 to 20:00, 0.30 after
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    _record_prices(
        hass,
        "sensor.market_import",
        {
            **dict.fromkeys(range(12), 0.10),
            **dict.fromkeys(range(12, 20), 0.20),
            **dict.fromkeys(range(20, 24), 0.30),
        },
    )
    await async_wait_recording_done(hass)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, {**_MARKET, CONF_PLAN_IMPORT_PRICE_ADD: 0.05}),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Wholesale")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - each hour at the market's price that hour, plus the 0.05
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(1.0 * 0.15 + 0.5 * 0.25 + 1.0 * 0.35)
    assert current["history_from"] == ["Wholesale"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_export_price_without_statistics_is_read_from_the_plan_named(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the Energy Dashboard's export price a sensor with no statistics,
    # the grid meter at a fixed 0.20
    _calendar(hass, [])
    await _energy_dashboard_export(hass, entity="sensor.grid_sell_price")
    _a_price_without_statistics(hass, "sensor.grid_sell_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _OFFER),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Night saver")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - 12:00's 2 kWh out at the night saver's 0.04, its import at the
    # meter's own 0.20
    current = _by_name(result)[_CURRENT]
    assert current["export_credit"] == pytest.approx(2.0 * 0.04)
    assert current["energy"] == pytest.approx(2.5 * 0.2)
    assert current["history_from"] == ["Night saver"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_with_no_plan_named_a_sensor_s_gap_leaves_only_the_current_plan_out(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the price sensor recorded from 12:00 only, and no plan named to
    # read the morning's prices from
    await _energy_dashboard_export(hass, number=0.05)
    _record_prices(hass, "sensor.grid_buy_price", dict.fromkeys(range(12, 24), 0.30))
    await async_wait_recording_done(hass)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - the current plan says which sensor it lacks prices from; every
    # other plan is still priced over the whole day, since none follows it
    current = _by_name(result)[_CURRENT]
    assert current["no_price"] is True
    assert current["no_price_entities"] == ["sensor.grid_buy_price"]
    assert result["left_out"] == []
    assert result["hours"] == 24
    assert _by_name(result)["Flat rate"]["energy"] == pytest.approx(2.5 * 0.234)


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_plan_named_is_said_only_where_it_priced_an_hour(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the price sensor recorded all day
    await _energy_dashboard_export(hass, number=0.05)
    _record_prices(hass, "sensor.grid_buy_price", dict.fromkeys(range(24), 0.30))
    await async_wait_recording_done(hass)
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Flat rate")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - every hour at the sensor's own price, and nothing said
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(2.5 * 0.30)
    assert "history_from" not in current


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_a_plan_with_an_allowance_cannot_price_the_hours_a_sensor_lacks(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the plan named pays its export price on the first 8 kWh a day
    # only, which no single hour's price can say
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    allowance = {
        **_FLAT,
        CONF_NAME: "Capped export",
        CONF_PLAN_EXPORT_ALLOWANCE: 8,
        CONF_PLAN_EXPORT_PRICE_AFTER: 0.01,
    }
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, allowance),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Capped export")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - unpriced, as with no plan named, rather than priced wrongly
    current = _by_name(result)[_CURRENT]
    assert current["no_price"] is True
    assert current["no_price_entities"] == ["sensor.grid_buy_price"]


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_each_plan_says_when_the_household_was_on_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the night saver before any other, until the flat rate from the
    # 14th (HEA-307)
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _plans_been_on(hass, ("Night saver", None), ("Flat rate", "2026-10-14"))

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - each period as local days, the last one open; a plan never on has
    # none, and the current plan none of its own
    plans = _by_name(result)
    assert plans["Night saver"]["been_on"] == [{"from": None, "until": "2026-10-13"}]
    assert plans["Flat rate"]["been_on"] == [{"from": "2026-10-14", "until": None}]
    assert "been_on" not in plans[_CURRENT]


async def _archive(hass: HomeAssistant, title: str) -> None:
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    plan = next(s for s in entry.subentries.values() if s.title == title)
    hass.config_entries.async_update_subentry(
        entry, plan, data={**plan.data, CONF_PLAN_ARCHIVED: True}
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_archived_plan_is_left_out_and_counted(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the night saver archived
    _calendar(hass, [])
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            (SUBENTRY_TYPE_PLAN, _OFFER),
        ),
    )
    await _archive(hass, "Night saver")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - not compared, and the card told how many are not shown
    assert "Night saver" not in _by_name(result)
    assert "Flat rate" in _by_name(result)
    assert result["archived"] == 1


@pytest.mark.usefixtures("recorder_mock", "_a_recorded_day")
async def test_an_archived_plan_still_prices_the_days_the_household_was_on_it(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # Given - the price sensor without statistics, and the flat rate, the plan
    # the household has always been on, archived
    await _energy_dashboard_export(hass, number=0.05)
    _a_price_without_statistics(hass, "sensor.grid_buy_price")
    await _set_up(
        hass,
        _house(
            (SUBENTRY_TYPE_GRID, _GRID_PRICED),
            (SUBENTRY_TYPE_PLAN, _FLAT),
            _current_plan(**{CONF_PLAN_DAILY_CHARGE: 0.45}),
        ),
    )
    await _price_history_from(hass, "Flat rate")
    await _archive(hass, "Flat rate")

    # When
    result = await _compare(hass_ws_client, hass)

    # Then - its prices still stand in, though it is no longer a row
    current = _by_name(result)[_CURRENT]
    assert current["energy"] == pytest.approx(2.5 * 0.234)
    assert current["history_from"] == ["Flat rate"]
    assert "Flat rate" not in _by_name(result)
