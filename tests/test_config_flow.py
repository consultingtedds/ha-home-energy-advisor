from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DOMAIN,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant

_PATH = "custom_components.home_energy_advisor.config_flow.async_get_manager"


@pytest.fixture(autouse=True)
def _no_energy_prefs() -> Iterator[None]:
    # Default: no Energy Dashboard configured, so nothing is pre-filled.
    with patch(_PATH, AsyncMock(return_value=SimpleNamespace(data=None))):
        yield


def _register_source_sensors(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "sensor.electricity_price_import", "0.234", {"unit_of_measurement": "EUR/kWh"}
    )
    for entity_id in (
        "sensor.grid_import",
        "sensor.solar",
        "sensor.battery_charge",
        "sensor.battery_discharge",
    ):
        hass.states.async_set(
            entity_id,
            "100",
            {
                "device_class": "energy",
                "state_class": "total_increasing",
                "unit_of_measurement": "kWh",
            },
        )


def _suggested_values(schema: vol.Schema) -> dict[str, Any]:
    return {
        str(marker.schema): marker.description["suggested_value"]
        for marker in schema.schema
        if isinstance(marker, vol.Marker) and marker.description
    }


async def test_user_flow_shows_the_configuration_form(hass: HomeAssistant) -> None:
    # Given / When — a fresh install starts the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Then — the house-level input form is shown
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_creates_entry_from_the_required_inputs(
    hass: HomeAssistant,
) -> None:
    # Given — a tariff-only household (no solar or battery) with its sensors
    _register_source_sensors(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # When — only the required inputs are supplied
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )

    # Then — an entry is created holding the house-level configuration
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PRICE_ENTITY] == "sensor.electricity_price_import"
    assert result["data"][CONF_CURRENCY] == "EUR"
    assert result["data"][CONF_GRID_IMPORT_ENTITY] == "sensor.grid_import"


async def test_user_flow_records_optional_solar_and_battery_inputs(
    hass: HomeAssistant,
) -> None:
    # Given — a household with solar and a battery
    _register_source_sensors(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # When — the optional source entities are supplied too
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_SOLAR_ENTITY: "sensor.solar",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.battery_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.battery_discharge",
        },
    )

    # Then — they are stored alongside the required inputs
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOLAR_ENTITY] == "sensor.solar"
    assert result["data"][CONF_BATTERY_CHARGE_ENTITY] == "sensor.battery_charge"
    assert result["data"][CONF_BATTERY_DISCHARGE_ENTITY] == "sensor.battery_discharge"


async def test_only_one_instance_can_be_configured(hass: HomeAssistant) -> None:
    # Given — Home Energy Advisor is already configured (its config is global)
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    # When — the user tries to add it again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Then — the flow aborts rather than creating a second instance
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_energy_dashboard_preferences_prefill_the_source_entities(
    hass: HomeAssistant,
) -> None:
    # Given — the household has configured the Energy Dashboard
    prefs = SimpleNamespace(
        data={
            "energy_sources": [
                {
                    "type": "grid",
                    "flow_from": [{"stat_energy_from": "sensor.grid_import"}],
                },
                {"type": "solar", "stat_energy_from": "sensor.solar"},
                {
                    "type": "battery",
                    "stat_energy_to": "sensor.battery_charge",
                    "stat_energy_from": "sensor.battery_discharge",
                },
            ]
        }
    )

    # When — the flow opens
    with patch(_PATH, AsyncMock(return_value=prefs)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # Then — the source fields are pre-filled from those preferences
    data_schema = result["data_schema"]
    assert data_schema is not None
    suggested = _suggested_values(data_schema)
    assert suggested[CONF_GRID_IMPORT_ENTITY] == "sensor.grid_import"
    assert suggested[CONF_SOLAR_ENTITY] == "sensor.solar"
    assert suggested[CONF_BATTERY_CHARGE_ENTITY] == "sensor.battery_charge"
    assert suggested[CONF_BATTERY_DISCHARGE_ENTITY] == "sensor.battery_discharge"


async def test_prefill_failure_never_blocks_the_flow(hass: HomeAssistant) -> None:
    # Given — reading the Energy Dashboard configuration fails
    with patch(_PATH, AsyncMock(side_effect=RuntimeError("energy unavailable"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # Then — the form is still shown, just with nothing pre-filled
    assert result["type"] is FlowResultType.FORM
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert _suggested_values(data_schema) == {}
