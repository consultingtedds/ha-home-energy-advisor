from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    CONF_DEVICE_COST_BOUNDS,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant

_ENERGY = {
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "state_class": "total_increasing",
}
_POWER = {
    "unit_of_measurement": "W",
    "device_class": "power",
    "state_class": "measurement",
}


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


async def test_options_flow_records_the_per_device_cost_range_opt_in(
    hass: HomeAssistant,
) -> None:
    # Given — a household on the cost-range form. The whole-home range is always
    # published; this asks whether to publish one per device too (ADR-0016).
    entry = _entry(hass)
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cost_bounds"}
    )
    assert result["type"] is FlowResultType.FORM

    # When — accepted unchanged, then turned on
    unchanged = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert entry.options[CONF_DEVICE_COST_BOUNDS] is False
    assert unchanged["type"] is FlowResultType.CREATE_ENTRY

    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cost_bounds"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE_COST_BOUNDS: True}
    )

    # Then — off by default (two more sensors per device is a real recorder cost)
    # and stored when asked for
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEVICE_COST_BOUNDS] is True


async def test_one_options_branch_does_not_clear_another(hass: HomeAssistant) -> None:
    # Given — a household that has opted into yearly cycle totals
    entry = _entry(hass)
    result = await _open_cycles(hass, entry)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CYCLE_YEARLY: True}
    )

    # When — a different branch is submitted. Options are written wholesale, so a
    # branch that stores only its own keys would silently drop every other one.
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cost_bounds"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE_COST_BOUNDS: True}
    )

    # Then — both survive
    assert entry.options[CONF_CYCLE_YEARLY] is True
    assert entry.options[CONF_DEVICE_COST_BOUNDS] is True


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
    dryer = _register(hass, "tumble_dryer_energy", "energy", "Tumble Dryer Energy")
    lights = _register(hass, "power_only_lights_power", "power", "Power Only Lights Power")
    hass.states.async_set(dryer, "0", _ENERGY)
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
        form["flow_id"], {"discovered_devices": [dryer, lights]}
    )
    await hass.async_block_till_done()

    # Then — a device subentry exists for each, with the right source sensor...
    assert result["type"] is FlowResultType.CREATE_ENTRY
    by_title = {s.title: s for s in entry.subentries.values()}
    assert set(by_title) == {"Tumble Dryer", "Power Only Lights"}
    assert by_title["Tumble Dryer"].data[CONF_ENERGY_ENTITY] == dryer

    # ...and the reload created each device's sensors (add → reload → sensors)
    assert hass.states.get("sensor.tumble_dryer_actual_cost") is not None
    assert hass.states.get("sensor.power_only_lights_actual_cost") is not None


async def test_discovery_step_offers_a_browsable_checkbox_list(
    hass: HomeAssistant,
) -> None:
    # Given — a household with a genuine candidate and an obvious false friend
    dryer = _register(hass, "tumble_dryer_energy", "energy", "Tumble Dryer Energy")
    phone = _register(hass, "phone_battery_power", "power", "Phone Battery Power")
    hass.states.async_set(dryer, "0", _ENERGY)
    hass.states.async_set(phone, "3", _POWER)
    entry = _entry(hass)

    # When — the user opens discovery
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )

    # Then — the multi-select stays a checkbox list. The step is for *browsing*
    # what a household has; a dropdown shows nothing until the user types a name
    # they do not yet know, so ordering carries a long list, not search (HEA-70)
    schema = form["data_schema"]
    assert schema is not None
    field = next(iter(schema.schema.values()))
    assert field.config["mode"] == selector.SelectSelectorMode.LIST
    assert field.config["multiple"] is True

    # ...and each row's wording comes from strings.json, not the code, so the
    # marker the step description promises actually appears in the user's own
    # language rather than only in English
    by_value = {option["value"]: option["label"] for option in field.config["options"]}
    assert by_value[dryer] == "Tumble Dryer (sensor.tumble_dryer_energy)"
    assert by_value[phone] == (
        "Phone Battery (sensor.phone_battery_power) — may not be a device"
    )


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
