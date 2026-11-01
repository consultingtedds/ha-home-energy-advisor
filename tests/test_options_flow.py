from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType, SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigSubentry
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
    SUBENTRY_TYPE_DEVICE,
    SUBENTRY_TYPE_GRID,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

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
    # Given - a configured household, on the cycle-totals form
    entry = _entry(hass)
    result = await _open_cycles(hass, entry)
    assert result["type"] is FlowResultType.FORM

    # When - the optional cycle totals are toggled
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CYCLE_WEEKLY: True,
            CONF_CYCLE_QUARTERLY: False,
            CONF_CYCLE_YEARLY: True,
        },
    )

    # Then - the choices are stored in the entry options
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CYCLE_WEEKLY] is True
    assert entry.options[CONF_CYCLE_QUARTERLY] is False
    assert entry.options[CONF_CYCLE_YEARLY] is True


async def test_options_flow_defaults_the_opt_ins_off(hass: HomeAssistant) -> None:
    # Given - a household that has never set cycle options, on the cycle form
    entry = _entry(hass)
    result = await _open_cycles(hass, entry)

    # When - the form is accepted unchanged
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})

    # Then - the optional cycles are off by default (entity-count discipline)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CYCLE_WEEKLY] is False
    assert entry.options[CONF_CYCLE_QUARTERLY] is False
    assert entry.options[CONF_CYCLE_YEARLY] is False


async def test_options_flow_records_the_per_device_cost_range_opt_in(
    hass: HomeAssistant,
) -> None:
    # Given - a household on the cost-range form. The whole-home range is always
    # published; this asks whether to publish one per device too (ADR-0016).
    entry = _entry(hass)
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cost_bounds"}
    )
    assert result["type"] is FlowResultType.FORM

    # When - accepted unchanged, then turned on
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

    # Then - off by default (two more sensors per device is a real recorder cost)
    # and stored when asked for
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEVICE_COST_BOUNDS] is True


async def test_one_options_branch_does_not_clear_another(hass: HomeAssistant) -> None:
    # Given - a household that has opted into yearly cycle totals
    entry = _entry(hass)
    result = await _open_cycles(hass, entry)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CYCLE_YEARLY: True}
    )

    # When - a different branch is submitted. Options are written wholesale, so a
    # branch that stores only its own keys would silently drop every other one.
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "cost_bounds"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE_COST_BOUNDS: True}
    )

    # Then - both survive
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
    # Given - a running, device-less household with two untracked candidates
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.electricity_price_import", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    dryer = _register(hass, "tumble_dryer_energy", "energy", "Tumble Dryer Energy")
    lights = _register(
        hass, "power_only_lights_power", "power", "Power Only Lights Power"
    )
    hass.states.async_set(dryer, "0", _ENERGY)
    hass.states.async_set(lights, "60", _POWER)
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the user opens discovery and selects both candidates
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )
    assert form["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {"discovered_devices": [dryer, lights]}
    )
    await hass.async_block_till_done()

    # Then - a device subentry exists for each, with the right source sensor...
    assert result["type"] is FlowResultType.CREATE_ENTRY
    by_title = {
        s.title: s
        for s in entry.subentries.values()
        if s.subentry_type == SUBENTRY_TYPE_DEVICE
    }
    assert set(by_title) == {"Tumble Dryer", "Power Only Lights"}
    assert by_title["Tumble Dryer"].data[CONF_ENERGY_ENTITY] == dryer

    # ...and the reload created each device's sensors (add → reload → sensors).
    # Asserted as a cost sensor rather than merely as a state: a device added
    # through the options flow has to arrive fully formed, not as a bare entity
    for entity_id in (
        "sensor.tumble_dryer_actual_cost",
        "sensor.power_only_lights_actual_cost",
    ):
        cost = hass.states.get(entity_id)
        assert cost is not None, entity_id
        assert cost.attributes["device_class"] == "monetary"
        assert cost.attributes["state_class"] == "total"
        assert cost.attributes["unit_of_measurement"] == "EUR"


async def test_discovery_step_offers_a_browsable_checkbox_list(
    hass: HomeAssistant,
) -> None:
    # Given - a household with a genuine candidate and an obvious false friend
    dryer = _register(hass, "tumble_dryer_energy", "energy", "Tumble Dryer Energy")
    phone = _register(hass, "phone_battery_power", "power", "Phone Battery Power")
    hass.states.async_set(dryer, "0", _ENERGY)
    hass.states.async_set(phone, "3", _POWER)
    entry = _entry(hass)

    # When - the user opens discovery
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )

    # Then - the multi-select stays a checkbox list. The step is for *browsing*
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
        "Phone Battery (sensor.phone_battery_power) - may not be a device"
    )


async def test_discovery_step_aborts_when_nothing_to_add(
    hass: HomeAssistant,
) -> None:
    # Given - a household with no untracked energy/power sensors
    entry = _entry(hass)

    # When - the user opens discovery
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )

    # Then - it aborts cleanly rather than showing an empty list
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_candidates"


_PREFS = "custom_components.home_energy_advisor.energy_dashboard.async_get_manager"


def _energy_dashboard(*devices: dict[str, str]) -> AbstractContextManager[object]:
    """An Energy Dashboard listing these devices, as its manager holds them."""
    manager = SimpleNamespace(
        data={"energy_sources": [], "device_consumption": devices}
    )
    return patch(_PREFS, AsyncMock(return_value=manager))


async def _open_discovery(
    hass: HomeAssistant, entry: MockConfigEntry
) -> ConfigFlowResult:
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "discover_devices"}
    )


def _field(form: ConfigFlowResult, name: str) -> tuple[object, dict[str, str]]:
    """A field's default, and its options as value to label."""
    schema = form["data_schema"]
    assert schema is not None
    marker, chosen = next(
        (key, value) for key, value in schema.schema.items() if key.schema == name
    )
    labels = {option["value"]: option["label"] for option in chosen.config["options"]}
    return marker.default(), labels


async def test_discovery_offers_the_energy_dashboard_devices_first_and_ticked(
    hass: HomeAssistant,
) -> None:
    # Given - a dishwasher the household listed in their Energy Dashboard under a
    # name of their own, and a dryer they did not list (HEA-247)
    dishwasher = _register(hass, "dishwasher_energy", "energy", "Dishwasher Energy")
    dryer = _register(hass, "tumble_dryer_energy", "energy", "Tumble Dryer Energy")
    hass.states.async_set(dishwasher, "0", _ENERGY)
    hass.states.async_set(dryer, "0", _ENERGY)
    entry = _entry(hass)

    # When
    with _energy_dashboard(
        {"stat_consumption": dishwasher, "name": "Kitchen dishwasher"}
    ):
        form = await _open_discovery(hass, entry)

    # Then - the household's own choice comes first, in their own words, and
    # already ticked; the search below offers only what the list does not
    schema = form["data_schema"]
    assert schema is not None
    assert [key.schema for key in schema.schema] == [
        "energy_dashboard_devices",
        "discovered_devices",
    ]
    assert _field(form, "energy_dashboard_devices") == (
        [dishwasher],
        {dishwasher: "Kitchen dishwasher (sensor.dishwasher_energy)"},
    )
    assert _field(form, "discovered_devices") == (
        [],
        {dryer: "Tumble Dryer (sensor.tumble_dryer_energy)"},
    )


async def test_discovery_adds_an_energy_dashboard_device_by_its_own_name(
    hass: HomeAssistant,
) -> None:
    # Given
    dishwasher = _register(hass, "dishwasher_energy", "energy", "Dishwasher Energy")
    hass.states.async_set(dishwasher, "0", _ENERGY)
    entry = _entry(hass)

    # When - the household submits the list as it was offered
    with _energy_dashboard(
        {"stat_consumption": dishwasher, "name": "Kitchen dishwasher"}
    ):
        form = await _open_discovery(hass, entry)
        result = await hass.config_entries.options.async_configure(
            form["flow_id"],
            {"energy_dashboard_devices": [dishwasher]},
        )

    # Then - tracked from the sensor the Energy Dashboard reads, which is also
    # what lets its nesting there be matched to it
    assert result["type"] is FlowResultType.CREATE_ENTRY
    devices = [
        (subentry.title, dict(subentry.data))
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    ]
    assert devices == [
        (
            "Kitchen dishwasher",
            {"name": "Kitchen dishwasher", CONF_ENERGY_ENTITY: dishwasher},
        )
    ]


async def test_discovery_names_an_energy_dashboard_device_listed_without_a_name(
    hass: HomeAssistant,
) -> None:
    # Given - the Energy Dashboard leaves `name` out unless one was typed
    dishwasher = _register(hass, "dishwasher_energy", "energy", "Dishwasher Energy")
    hass.states.async_set(dishwasher, "0", _ENERGY)
    entry = _entry(hass)

    # When
    with _energy_dashboard({"stat_consumption": dishwasher}):
        form = await _open_discovery(hass, entry)

    # Then - the name discovery would have suggested
    assert _field(form, "energy_dashboard_devices")[1] == {
        dishwasher: "Dishwasher (sensor.dishwasher_energy)"
    }


async def test_discovery_skips_an_energy_dashboard_device_already_tracked(
    hass: HomeAssistant,
) -> None:
    # Given - the dishwasher is tracked; only the dryer is new
    dishwasher = _register(hass, "dishwasher_energy", "energy", "Dishwasher Energy")
    dryer = _register(hass, "tumble_dryer_energy", "energy", "Tumble Dryer Energy")
    hass.states.async_set(dishwasher, "0", _ENERGY)
    hass.states.async_set(dryer, "0", _ENERGY)
    entry = _entry(hass)
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {"name": "Dishwasher", CONF_ENERGY_ENTITY: dishwasher}
            ),
            subentry_type=SUBENTRY_TYPE_DEVICE,
            title="Dishwasher",
            unique_id=None,
        ),
    )

    # When
    with _energy_dashboard(
        {"stat_consumption": dishwasher, "name": "Kitchen dishwasher"},
        {"stat_consumption": dryer, "name": "Dryer"},
    ):
        form = await _open_discovery(hass, entry)

    # Then - nothing to say about it: it is not a device that could not be added
    assert _field(form, "energy_dashboard_devices") == (
        [dryer],
        {dryer: "Dryer (sensor.tumble_dryer_energy)"},
    )
    assert form["description_placeholders"] == {"not_offered": ""}


async def test_discovery_says_why_an_energy_dashboard_device_is_not_offered(
    hass: HomeAssistant,
) -> None:
    # Given - three the household listed that cannot be tracked: figures
    # imported as a statistic with no sensor behind them, a net counter, and
    # the grid meter itself listed as a device
    meter = _register(hass, "heat_pump_meter", "energy", "Heat Pump Meter")
    hass.states.async_set(meter, "0", {**_ENERGY, "state_class": "total"})
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    entry = _entry(hass)
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    "name": "Grid",
                    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
                    CONF_PRICE_ENTITY: "sensor.electricity_price_import",
                }
            ),
            subentry_type=SUBENTRY_TYPE_GRID,
            title="Grid",
            unique_id=None,
        ),
    )

    # When
    with _energy_dashboard(
        {"stat_consumption": "tibber:energy_consumption", "name": "Heat pump"},
        {"stat_consumption": meter, "name": "Heat pump meter"},
        {"stat_consumption": "sensor.grid_import", "name": "Mains"},
    ):
        form = await _open_discovery(hass, entry)

    # Then - none of them is offered and nothing else is either, so the step
    # ends - but says why, rather than "nothing found" over a list the
    # household can see in their Energy Dashboard
    assert form["type"] is FlowResultType.ABORT
    assert form["reason"] == "no_candidates"
    assert form["description_placeholders"] == {
        "not_offered": (
            "\n\nNot offered from your Energy Dashboard: "
            "Heat pump (its figures are not a sensor Home Energy Advisor can read), "
            "Heat pump meter (its sensor is not a running total of energy used), "
            "Mains (it is house energy, already counted)."
        )
    }


async def test_discovery_aborts_only_when_the_energy_dashboard_offers_nothing_either(
    hass: HomeAssistant,
) -> None:
    # Given - no other sensor to suggest, and one in the Energy Dashboard
    dishwasher = _register(hass, "dishwasher_energy", "energy", "Dishwasher Energy")
    hass.states.async_set(dishwasher, "0", _ENERGY)
    entry = _entry(hass)
    with (
        patch(
            "custom_components.home_energy_advisor.config_flow.async_discover_candidates",
            return_value=[],
        ),
        _energy_dashboard({"stat_consumption": dishwasher, "name": "Dishwasher"}),
    ):
        # When
        form = await _open_discovery(hass, entry)

    # Then - the list is shown, rather than "nothing found"
    assert form["type"] is FlowResultType.FORM
    schema = form["data_schema"]
    assert schema is not None
    assert [key.schema for key in schema.schema] == ["energy_dashboard_devices"]
