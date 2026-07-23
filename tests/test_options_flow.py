from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
_POWER = {"unit_of_measurement": "W", "device_class": "power"}


def _entry(hass: HomeAssistant) -> MockConfigEntry:
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


async def _open_cycles(hass: HomeAssistant, entry: MockConfigEntry) -> ConfigFlowResult:
    """Open the options menu and step into the cycle-totals form."""
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    assert menu["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cycles"}
    )


async def test_options_flow_records_the_cycle_opt_ins(hass: HomeAssistant) -> None:
    # Given — a configured household, on the cycle-totals form
    entry = _entry(hass)
    result = await _open_cycles(hass, entry)
    assert result["type"] is FlowResultType.FORM

    # When — the optional cycle totals are toggled
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CYCLE_WEEKLY: True,
            CONF_CYCLE_QUARTERLY: False,
            CONF_CYCLE_YEARLY: True,
        },
    )

    # Then — the choices are stored in the entry options
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CYCLE_WEEKLY] is True
    assert entry.options[CONF_CYCLE_QUARTERLY] is False
    assert entry.options[CONF_CYCLE_YEARLY] is True


async def test_options_flow_defaults_the_opt_ins_off(hass: HomeAssistant) -> None:
    # Given — a household that has never set cycle options, on the cycle form
    entry = _entry(hass)
    result = await _open_cycles(hass, entry)

    # When — the form is accepted unchanged
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})

    # Then — the optional cycles are off by default (entity-count discipline)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CYCLE_WEEKLY] is False
    assert entry.options[CONF_CYCLE_QUARTERLY] is False
    assert entry.options[CONF_CYCLE_YEARLY] is False


def _register(hass: HomeAssistant, object_id: str, device_class: str, name: str) -> str:
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "demo",
        object_id,
        suggested_object_id=object_id,
        original_device_class=device_class,
        original_name=name,
    )
    return entity.entity_id


async def test_discovery_step_adds_selected_devices_and_creates_their_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running, device-less household with two untracked candidates
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.electricity_price_import", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    pool = _register(hass, "pool_pump_energy", "energy", "Pool Pump Energy")
    lights = _register(hass, "hallway_lights_power", "power", "Hallway Lights Power")
    hass.states.async_set(pool, "0", _ENERGY)
    hass.states.async_set(lights, "60", _POWER)
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the user opens discovery and selects both candidates
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )
    assert form["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {"discovered_devices": [pool, lights]}
    )
    await hass.async_block_till_done()

    # Then — a device subentry exists for each, with the right source sensor...
    assert result["type"] is FlowResultType.CREATE_ENTRY
    by_title = {s.title: s for s in entry.subentries.values()}
    assert set(by_title) == {"Pool Pump", "Hallway Lights"}
    assert by_title["Pool Pump"].data[CONF_ENERGY_ENTITY] == pool

    # ...and the reload created each device's sensors (add → reload → sensors)
    assert hass.states.get("sensor.pool_pump_actual_cost") is not None
    assert hass.states.get("sensor.hallway_lights_actual_cost") is not None


async def test_discovery_step_aborts_when_nothing_to_add(
    hass: HomeAssistant,
) -> None:
    # Given — a household with no untracked energy/power sensors
    entry = _entry(hass)

    # When — the user opens discovery
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )

    # Then — it aborts cleanly rather than showing an empty list
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_candidates"
