from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _parent_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    entry.add_to_hass(hass)
    return entry


def _register_device_sensors(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "sensor.guest_bedroom_aircon_energy",
        "12.5",
        {"device_class": "energy", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.living_room_lights_power",
        "40",
        {"device_class": "power", "state_class": "measurement"},
    )


async def _start_add(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return result["flow_id"]


async def test_add_device_subentry_with_an_energy_sensor(hass: HomeAssistant) -> None:
    # Given — a configured household and a device that reports its own energy
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When — the device is added by name and energy sensor
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Guest Bedroom Aircon",
            CONF_ENERGY_ENTITY: "sensor.guest_bedroom_aircon_energy",
        },
    )

    # Then — a device subentry is created on the parent entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Guest Bedroom Aircon"
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    assert subentry.data[CONF_ENERGY_ENTITY] == "sensor.guest_bedroom_aircon_energy"


async def test_add_device_subentry_with_a_power_sensor(hass: HomeAssistant) -> None:
    # Given — a power-only device (energy is derived later via an Integral helper)
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When — the device is added by name and power sensor
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Living Room Lights",
            CONF_POWER_ENTITY: "sensor.living_room_lights_power",
        },
    )

    # Then — the subentry records the power sensor
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_POWER_ENTITY] == "sensor.living_room_lights_power"


async def test_adding_a_device_with_both_sensors_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given — the add-device form
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When — both an energy and a power sensor are given
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Confused Device",
            CONF_ENERGY_ENTITY: "sensor.guest_bedroom_aircon_energy",
            CONF_POWER_ENTITY: "sensor.living_room_lights_power",
        },
    )

    # Then — the form re-shows with an error; a device has exactly one source
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "select_one_sensor"}


async def test_adding_a_device_with_no_sensor_is_rejected(hass: HomeAssistant) -> None:
    # Given — the add-device form
    entry = _parent_entry(hass)
    flow_id = await _start_add(hass, entry)

    # When — neither sensor is given
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {CONF_NAME: "Sensorless Device"}
    )

    # Then — the form re-shows with the same error
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "select_one_sensor"}
