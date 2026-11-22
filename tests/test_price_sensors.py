"""The price sensors the current plan provides, where the household asks (ADR-0048).

The household ticks "Provide my price sensors" on its current plan, and points
its Energy Dashboard and grid meters at them once. They follow the plan of the
period in force today: its bands by the clock, its holidays from its calendar, a
market plan's market, and the next period from the start of its day, so their
recorded statistics keep every price as it was charged.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import ConfigSubentryData, ConfigSubentryDataWithId
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_EXPORT_PRICE,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_PERIOD_FROM,
    CONF_PERIOD_PLAN,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_ALLOWANCE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_EXPORT_PRICE_AFTER,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_HOLIDAYS,
    CONF_PLAN_IMPORT_PRICE_ADD,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PLAN_PERIODS,
    CONF_PLAN_PROVIDES_PRICES,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

MADRID = ZoneInfo("Europe/Madrid")
# Thursday 19 November 2026, mid-morning.
THURSDAY_MORNING = datetime(2026, 11, 19, 10, tzinfo=MADRID)

_THREE_PERIODS = {
    CONF_NAME: "Three periods",
    CONF_PLAN_DAILY_CHARGE: 1.47,
    CONF_PLAN_EXPORT_PRICE: 0.04,
    CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "weekdays",
            CONF_BAND_START: 8,
            CONF_BAND_END: 22,
            CONF_BAND_IMPORT_PRICE: 0.245,
            CONF_BAND_EXPORT_PRICE: 0.08,
        },
        {
            CONF_BAND_DAYS: "weekdays",
            CONF_BAND_START: 22,
            CONF_BAND_END: 8,
            CONF_BAND_IMPORT_PRICE: 0.098,
        },
        {
            CONF_BAND_DAYS: "rest_days",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.098,
        },
    ],
}
_FLAT = {
    CONF_NAME: "Flat",
    CONF_PLAN_DAILY_CHARGE: 0.9,
    CONF_PLAN_EXPORT_PRICE: 0.05,
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.18,
        }
    ],
}
_MARKET = {
    CONF_NAME: "Market tracker",
    CONF_PLAN_DAILY_CHARGE: 0.25,
    CONF_PLAN_EXPORT_PRICE: 0.04,
    CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.market_price",
    CONF_PLAN_IMPORT_PRICE_ADD: 0.03,
}
_CAPPED = {
    **_FLAT,
    CONF_NAME: "Capped export",
    CONF_PLAN_EXPORT_ALLOWANCE: 8,
    CONF_PLAN_EXPORT_PRICE_AFTER: 0.01,
}


def _house(
    *periods: tuple[str, str | None],
    plans: dict[str, dict[str, Any]],
    provides: bool = True,
) -> MockConfigEntry:
    """Typed plans by subentry id, and the current plan's periods on them."""
    current: dict[str, Any] = {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 1.0,
        CONF_PLAN_PERIODS: [
            {CONF_PERIOD_PLAN: plan} | ({CONF_PERIOD_FROM: day} if day else {})
            for plan, day in periods
        ],
        **({CONF_PLAN_PROVIDES_PRICES: True} if provides else {}),
    }
    subentries: list[ConfigSubentryData] = [
        ConfigSubentryDataWithId(
            subentry_id=plan_id,
            subentry_type=SUBENTRY_TYPE_PLAN,
            title=plan[CONF_NAME],
            data=plan,
            unique_id=None,
        )
        for plan_id, plan in plans.items()
    ]
    subentries.append(
        ConfigSubentryDataWithId(
            subentry_id="current",
            subentry_type=SUBENTRY_TYPE_PLAN,
            title=current[CONF_NAME],
            data=current,
            unique_id=None,
        )
    )
    return MockConfigEntry(
        domain=DOMAIN,
        version=8,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=subentries,
    )


async def _set_up(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry
) -> None:
    await hass.config.async_set_time_zone("Europe/Madrid")
    freezer.move_to(THURSDAY_MORNING)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _at(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, moment: datetime
) -> None:
    freezer.move_to(moment)
    async_fire_time_changed(hass, moment)
    await hass.async_block_till_done()


def _entity(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_current_plan_{key}"
    )


def _price(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    entity_id = _entity(hass, entry, key)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _calendar(hass: HomeAssistant, holidays: list[date]) -> None:
    """A calendar answering `calendar.get_events` with these all-day holidays."""

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


async def test_periods_alone_add_no_price_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the plans been on, as every upgraded household has, not ticked
    entry = _house(("three", None), plans={"three": _THREE_PERIODS}, provides=False)

    # When
    await _set_up(hass, freezer, entry)

    # Then - the household has its own price sensors, and nothing is added
    assert _entity(hass, entry, "import_price") is None
    assert _entity(hass, entry, "export_price") is None


async def test_the_import_price_follows_the_plan_s_bands_through_the_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - on Three periods, no holiday today
    _calendar(hass, [])
    entry = _house(("three", None), plans={"three": _THREE_PERIODS})
    await _set_up(hass, freezer, entry)

    # Then - the weekday peak now
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.245)

    # When - the band ends at 22:00
    await _at(hass, freezer, datetime(2026, 11, 19, 22, tzinfo=MADRID))

    # Then
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.098)


async def test_the_export_price_is_the_band_s_own_or_else_the_plan_s(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given
    _calendar(hass, [])
    entry = _house(("three", None), plans={"three": _THREE_PERIODS})
    await _set_up(hass, freezer, entry)

    # Then - the peak pays its own
    assert float(_price(hass, entry, "export_price")) == pytest.approx(0.08)

    # When - overnight, which pays the plan's
    await _at(hass, freezer, datetime(2026, 11, 19, 23, tzinfo=MADRID))

    # Then
    assert float(_price(hass, entry, "export_price")) == pytest.approx(0.04)


async def test_the_next_period_changes_the_prices_at_midnight_and_not_before(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - switching from Three periods to Flat on Friday the 20th
    _calendar(hass, [])
    entry = _house(
        ("three", None),
        ("flat", "2026-11-20"),
        plans={"three": _THREE_PERIODS, "flat": _FLAT},
    )
    await _set_up(hass, freezer, entry)

    # When - the last minute of the old plan
    await _at(hass, freezer, datetime(2026, 11, 19, 23, 59, tzinfo=MADRID))

    # Then - still Three periods' night price
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.098)

    # When - midnight
    await _at(hass, freezer, datetime(2026, 11, 20, 0, 0, 1, tzinfo=MADRID))

    # Then - Flat's, and its export price
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.18)
    assert float(_price(hass, entry, "export_price")) == pytest.approx(0.05)


async def test_a_public_holiday_is_priced_as_the_plan_prices_holidays(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - today, a Thursday, is a public holiday in the plan's calendar
    _calendar(hass, [date(2026, 11, 19)])
    entry = _house(("three", None), plans={"three": _THREE_PERIODS})

    # When
    await _set_up(hass, freezer, entry)

    # Then - the weekend and holiday price, not the weekday peak
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.098)


async def test_a_market_plan_s_import_price_follows_its_market(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the market at 0.10, the plan adding 0.03
    hass.states.async_set(
        "sensor.market_price", "0.10", {"unit_of_measurement": "EUR/kWh"}
    )
    entry = _house(("market", None), plans={"market": _MARKET})
    await _set_up(hass, freezer, entry)

    # Then
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.13)

    # When - the market moves
    hass.states.async_set(
        "sensor.market_price", "0.20", {"unit_of_measurement": "EUR/kWh"}
    )
    await hass.async_block_till_done()

    # Then
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.23)

    # When - the market goes unavailable
    hass.states.async_set("sensor.market_price", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    # Then - the last price kept, as a missing price keeps the last; a zero
    # would have been taken as a real price
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.23)


async def test_before_the_first_period_the_prices_are_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - switching to Flat from next week, nothing before it
    entry = _house(("flat", "2026-11-26"), plans={"flat": _FLAT})

    # When
    await _set_up(hass, freezer, entry)

    # Then - no plan feeds them yet
    assert _price(hass, entry, "import_price") == STATE_UNAVAILABLE


async def test_a_plan_with_an_allowance_feeds_no_price(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - on a plan whose export price depends on how much was exported
    entry = _house(("capped", None), plans={"capped": _CAPPED})

    # When
    await _set_up(hass, freezer, entry)

    # Then - no hour's price can say it yet (HEA-309)
    assert _price(hass, entry, "export_price") == STATE_UNAVAILABLE


async def test_editing_the_plan_fed_from_changes_the_price_without_a_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - on Flat at 0.18
    entry = _house(("flat", None), plans={"flat": _FLAT})
    await _set_up(hass, freezer, entry)

    # When - its price edited
    flat = entry.subentries["flat"]
    hass.config_entries.async_update_subentry(
        entry,
        flat,
        data={
            **flat.data,
            CONF_BANDS: [
                {
                    CONF_BAND_DAYS: "every_day",
                    CONF_BAND_START: 0,
                    CONF_BAND_END: 24,
                    CONF_BAND_IMPORT_PRICE: 0.2,
                }
            ],
        },
    )
    await hass.async_block_till_done()

    # Then - the new price at once
    assert float(_price(hass, entry, "import_price")) == pytest.approx(0.2)


async def test_unticking_removes_the_price_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - provided
    entry = _house(("flat", None), plans={"flat": _FLAT})
    await _set_up(hass, freezer, entry)
    assert _entity(hass, entry, "import_price") is not None

    # When - unticked
    current = entry.subentries["current"]
    hass.config_entries.async_update_subentry(
        entry,
        current,
        data={
            key: value
            for key, value in current.data.items()
            if key != CONF_PLAN_PROVIDES_PRICES
        },
    )
    await hass.async_block_till_done()

    # Then - gone, not left behind unavailable
    assert _entity(hass, entry, "import_price") is None
    assert _entity(hass, entry, "export_price") is None


async def test_the_prices_are_recorded_as_a_price_per_kwh_in_the_currency(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given
    entry = _house(("flat", None), plans={"flat": _FLAT})

    # When
    await _set_up(hass, freezer, entry)

    # Then - a mean per hour in the statistics, as the Energy Dashboard reads a
    # price
    entity_id = _entity(hass, entry, "import_price")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "EUR/kWh"
    assert state.attributes["state_class"] == "measurement"
