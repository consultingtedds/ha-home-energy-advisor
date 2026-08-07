from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_CYCLE_METERS,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)
from custom_components.home_energy_advisor.helper_ownership import helper_was_created

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
        "sensor.grid_export",
        "sensor.generation",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_consumption",
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


def _set_state_class(hass: HomeAssistant, entity_id: str, state_class: str) -> None:
    """Re-publish a house meter with a different state_class."""
    hass.states.async_set(
        entity_id,
        "100",
        {
            "device_class": "energy",
            "state_class": state_class,
            "unit_of_measurement": "kWh",
        },
    )


async def test_a_net_counter_is_rejected_for_an_input_the_model_reads(
    hass: HomeAssistant,
) -> None:
    # Given — a household with no house-consumption meter, so ADR-0005's
    # full-balance branch runs and generation is load-bearing; its generation
    # sensor is a `total` net counter, which that branch would mis-account into
    # silently wrong whole-home figures (HEA-67)
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.generation", "total")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # When — it is submitted
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
            CONF_GENERATION_ENTITY: "sensor.generation",
        },
    )

    # Then — the form comes back with the error against that field. A bad house
    # input corrupts the whole ledger, not one device's share
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_GENERATION_ENTITY: "house_not_total_increasing"}


async def test_a_net_counter_is_accepted_for_an_input_the_model_ignores(
    hass: HomeAssistant,
) -> None:
    # Given — the same `total` generation sensor, but a household that *does*
    # have a house-consumption meter. The residual branch never reads generation,
    # so the counter's class cannot affect a single figure — and rejecting it
    # would block a configuration that is correct in practice (the reference
    # instance's own setup)
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.generation", "total")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # When — it is submitted alongside a house-consumption meter
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_GENERATION_ENTITY: "sensor.generation",
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
        },
    )

    # Then — accepted; validation follows what the model actually consumes
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GENERATION_ENTITY] == "sensor.generation"


async def test_a_net_grid_import_counter_is_always_rejected(
    hass: HomeAssistant,
) -> None:
    # Given — grid import as a `total` net counter. Every branch reads it, so
    # there is no configuration in which this one is harmless
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.grid_import", "total")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # When — it is submitted with a house-consumption meter present
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
        },
    )

    # Then — rejected
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_GRID_IMPORT_ENTITY: "house_not_total_increasing"}


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
    # Given — a tariff-only household (no generation or battery) with its sensors
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


async def test_user_flow_records_optional_generation_and_battery_inputs(
    hass: HomeAssistant,
) -> None:
    # Given — a household with local generation and a battery
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
            CONF_GENERATION_ENTITY: "sensor.generation",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.battery_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.battery_discharge",
        },
    )

    # Then — they are stored alongside the required inputs
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GENERATION_ENTITY] == "sensor.generation"
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
                    "flow_to": [{"stat_energy_to": "sensor.grid_export"}],
                },
                {"type": "solar", "stat_energy_from": "sensor.generation"},
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
    assert suggested[CONF_GRID_EXPORT_ENTITY] == "sensor.grid_export"
    assert suggested[CONF_GENERATION_ENTITY] == "sensor.generation"
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


async def test_reconfigure_updates_the_house_level_config(hass: HomeAssistant) -> None:
    # Given — a configured, running household (no generation yet)
    _register_source_sensors(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the config is edited to add generation and change the currency
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "GBP",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_GENERATION_ENTITY: "sensor.generation",
        },
    )
    await hass.async_block_till_done()

    # Then — the entry is updated in place, no reinstall
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CURRENCY] == "GBP"
    assert entry.data[CONF_GENERATION_ENTITY] == "sensor.generation"


async def test_reconfigure_preserves_helper_bookkeeping(hass: HomeAssistant) -> None:
    # Given — a running house-only install that has auto-created its cycle meters,
    # recorded on the entry as HEA-owned (created)
    _register_source_sensors(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    owned_before = dict(entry.data[CONF_CYCLE_METERS])
    assert owned_before
    assert all(helper_was_created(record) for record in owned_before.values())

    # When — the house config is reconfigured (currency change)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "GBP",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    await hass.async_block_till_done()

    # Then — the bookkeeping survived: the same meters are still tracked, still as
    # HEA-created. A wholesale data replace would have dropped the map, and the
    # reload would then have re-adopted HEA's own meters as the user's — never to
    # be cleaned up (HEA-52 (a) and (b) interact).
    assert entry.data.get(CONF_CYCLE_METERS)
    assert set(entry.data[CONF_CYCLE_METERS]) == set(owned_before)
    assert all(
        helper_was_created(record) for record in entry.data[CONF_CYCLE_METERS].values()
    )
