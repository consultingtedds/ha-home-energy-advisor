"""The tariff plans in the diagnostics download (HEA-276, discussion 58).

A comparison could not be checked from the download, because no plan appeared
in it: a plan crediting four times what the Energy Dashboard's export price
would could not be told apart from an Energy Dashboard price set wrong. Each
plan is carried as the household entered it, which with the recorded
statistics reproduces every figure the card shows, and each market price entity
says what it is and when its statistics start - so a feed the recorder keeps no
statistics for shows up at once.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
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
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_IMPORT_PRICE_ADD,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PLAN_IMPORT_PRICE_MULTIPLY,
    CONF_PRICES,
    DOMAIN,
    SUBENTRY_TYPE_GRID,
    SUBENTRY_TYPE_PLAN,
)
from custom_components.home_energy_advisor.diagnostics import (
    async_get_config_entry_diagnostics,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# The first hour the market import price was recorded at.
FIRST_PRICED = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)

_GRID: dict[str, Any] = {
    CONF_NAME: "Grid",
    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
    CONF_FIXED_PRICE: 0.45,
}
# The household's current plan: two named prices, by time of day.
_TIME_OF_USE: dict[str, Any] = {
    CONF_NAME: "Time of use",
    CONF_PLAN_CURRENT: True,
    CONF_PLAN_DAILY_CHARGE: 1.1,
    CONF_PRICES: [
        {CONF_NAME: "Peak", CONF_BAND_IMPORT_PRICE: 0.45},
        {CONF_NAME: "Off-peak", CONF_BAND_IMPORT_PRICE: 0.22},
    ],
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 7,
            CONF_BAND_END: 22,
            CONF_BAND_PRICE: "Peak",
        },
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 22,
            CONF_BAND_END: 7,
            CONF_BAND_PRICE: "Off-peak",
        },
    ],
}
# An offer at the wholesale price with the supplier's margin, paid for export
# from a feed the recorder keeps no statistics for.
_WHOLESALE: dict[str, Any] = {
    CONF_NAME: "Wholesale",
    CONF_PLAN_CURRENT: False,
    CONF_PLAN_DAILY_CHARGE: 0.9,
    CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.market_import_price",
    CONF_PLAN_IMPORT_PRICE_ADD: 0.08,
    CONF_PLAN_IMPORT_PRICE_MULTIPLY: 1.1,
    CONF_PLAN_EXPORT_PRICE_ENTITY: "sensor.market_feed_in_price",
}


def _house() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_CURRENCY: "AUD"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=kind, title=data[CONF_NAME], data=data, unique_id=None
            )
            for kind, data in (
                (SUBENTRY_TYPE_GRID, _GRID),
                (SUBENTRY_TYPE_PLAN, _TIME_OF_USE),
                (SUBENTRY_TYPE_PLAN, _WHOLESALE),
            )
        ],
    )


def _record_market_import_price(hass: HomeAssistant) -> None:
    """Three hours of the market import price's mean, from FIRST_PRICED."""
    metadata = StatisticMetaData(
        has_sum=False,
        mean_type=StatisticMeanType.ARITHMETIC,
        name=None,
        source="recorder",
        statistic_id="sensor.market_import_price",
        unit_class=None,
        unit_of_measurement="AUD/kWh",
    )
    rows = [
        StatisticData(
            start=FIRST_PRICED + timedelta(hours=hour), mean=0.12, min=0.1, max=0.14
        )
        for hour in range(3)
    ]
    async_import_statistics(hass, metadata, rows)


def _plan_id(entry: MockConfigEntry, title: str) -> str:
    return str(
        next(
            subentry_id
            for subentry_id, subentry in entry.subentries.items()
            if subentry.title == title
        )
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_the_download_carries_each_plan_and_what_its_market_prices_are(
    hass: HomeAssistant,
) -> None:
    # Given - a running home with a time-of-use plan and a wholesale offer, its
    # import price recorded and its feed-in price not
    hass.states.async_set("sensor.grid_import", "0", {"unit_of_measurement": "kWh"})
    hass.states.async_set(
        "sensor.market_import_price",
        "0.12",
        {"unit_of_measurement": "AUD/kWh", "state_class": "measurement"},
    )
    hass.states.async_set(
        "sensor.market_feed_in_price", "0.05", {"unit_of_measurement": "AUD/kWh"}
    )
    _record_market_import_price(hass)
    await async_wait_recording_done(hass)
    entry = _house()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - each plan exactly as entered, and each market price entity's unit,
    # class, reading and the first hour it can price
    assert result["plans"] == {
        "plans": [
            {
                "id": _plan_id(entry, "Time of use"),
                "title": "Time of use",
                "settings": _TIME_OF_USE,
            },
            {
                "id": _plan_id(entry, "Wholesale"),
                "title": "Wholesale",
                "settings": _WHOLESALE,
            },
        ],
        "market_entities": {
            "sensor.market_feed_in_price": {
                "state": "0.05",
                "unit": "AUD/kWh",
                "state_class": None,
                "mean_statistics_from": None,
            },
            "sensor.market_import_price": {
                "state": "0.12",
                "unit": "AUD/kWh",
                "state_class": "measurement",
                "mean_statistics_from": "2026-10-14T06:00:00+00:00",
            },
        },
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_a_household_without_plans_carries_an_empty_section(
    hass: HomeAssistant,
) -> None:
    # Given
    hass.states.async_set("sensor.grid_import", "0", {"unit_of_measurement": "kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_CURRENCY: "AUD"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_GRID,
                title="Grid",
                data=_GRID,
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - present and empty, so "no plans" is told from "not reported"
    assert result["plans"] == {"plans": [], "market_entities": {}}
