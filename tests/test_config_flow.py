from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.components.integration.const import (
    CONF_SOURCE_SENSOR,
    CONF_UNIT_TIME,
    METHOD_TRAPEZOIDAL,
)
from homeassistant.components.integration.const import DOMAIN as INTEGRATION_DOMAIN
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_METHOD, CONF_NAME, UnitOfTime
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CHARGING,
    CONF_CURRENCY,
    CONF_CYCLE_DAILY,
    CONF_CYCLE_METERS,
    CONF_CYCLE_MONTHLY,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)
from custom_components.home_energy_advisor.helper_ownership import helper_was_created
from custom_components.home_energy_advisor.house_inputs import grid_meters_of

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant

_PATH = "custom_components.home_energy_advisor.config_flow.async_get_manager"

# The house screen at its least, and the grid meter asked for after it.
_HOUSE = {CONF_CURRENCY: "EUR"}
_GRID = {
    CONF_NAME: "Grid",
    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
    CONF_PRICE_ENTITY: "sensor.electricity_price_import",
}
# An entry as it stood before the grid meters had entries of their own, which
# every older entry below starts from.
_LEGACY_HOUSE = {
    CONF_PRICE_ENTITY: "sensor.electricity_price_import",
    CONF_CURRENCY: "EUR",
    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
}


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
        "sensor.east_array_energy",
        "sensor.west_array_energy",
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


def _as_a_riemann_sum(hass: HomeAssistant, entity_id: str) -> None:
    """Re-publish a house meter as Home Assistant's own Riemann sum helper.

    Two halves, and both are what Home Assistant really does.
    ``IntegrationSensor._attr_state_class`` is ``total`` on the class, so every
    integral helper declares a net counter's class however monotonic its output
    is; what marks one as a Riemann sum rather than a net meter is the domain of
    the config entry that owns it, which is where the registry records it.
    """
    helper = MockConfigEntry(
        domain=INTEGRATION_DOMAIN,
        title="Grid Import",
        options={
            CONF_SOURCE_SENSOR: "sensor.mains_clamp_power",
            CONF_METHOD: METHOD_TRAPEZOIDAL,
            CONF_UNIT_TIME: UnitOfTime.HOURS,
        },
    )
    helper.add_to_hass(hass)
    # The registry allocates around whatever is already in the state machine, so
    # the meter has to leave it for the helper's own entry to land on that id.
    hass.states.async_remove(entity_id)
    object_id = entity_id.removeprefix("sensor.")
    er.async_get(hass).async_get_or_create(
        "sensor",
        INTEGRATION_DOMAIN,
        object_id,
        suggested_object_id=object_id,
        config_entry=helper,
    )
    _set_state_class(hass, entity_id, "total")


def _set_unit(hass: HomeAssistant, entity_id: str, unit: str | None) -> None:
    """Re-publish a house meter reporting in a different unit, or in none."""
    attributes = {"device_class": "energy", "state_class": "total_increasing"}
    if unit is not None:
        attributes["unit_of_measurement"] = unit
    hass.states.async_set(entity_id, "100", attributes)


async def _set_up(
    hass: HomeAssistant,
    house: dict[str, Any] | None = None,
    grid: dict[str, Any] | None = None,
) -> Any:  # noqa: ANN401 - a flow result
    """Answer the house screen, and then the grid meter if it is reached."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], house or _HOUSE
    )
    if result.get("step_id") != "grid_meter":
        return result
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], grid or _GRID
    )


async def test_a_house_input_in_a_unit_the_engine_cannot_count_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - a grid meter reporting kilowatts: a power sensor chosen where an
    # energy one belongs. The engine counts in every energy unit and nothing
    # else, so this would silently contribute nothing to every figure derived
    # from it
    _register_source_sensors(hass)
    _set_unit(hass, "sensor.grid_import", "kW")

    # When - it is submitted
    result = await _set_up(
        hass, {**_HOUSE, CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption"}
    )

    # Then - refused here, while somebody is looking at the screen and can pick
    # another entity. The alternative is a house that quietly accounts for
    # nothing and a Repair a week later
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "grid_meter"
    assert result["errors"] == {CONF_GRID_IMPORT_ENTITY: "unit_not_energy"}


async def test_a_watt_hour_house_input_is_accepted_beside_kilowatt_hour_ones(
    hass: HomeAssistant,
) -> None:
    # Given - the shape that cost a household a day (GitHub #27): a grid meter
    # in Wh beside kWh everywhere else. It is *not* a fault - the engine reads
    # the unit from every reading and converts (HEA-149) - and refusing it would
    # teach people to "fix" a working setup by swapping the entity, which
    # re-baselines the counter and loses accounting for nothing
    _register_source_sensors(hass)
    _set_unit(hass, "sensor.grid_import", "Wh")

    # When
    result = await _set_up(
        hass, {**_HOUSE, CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption"}
    )

    # Then - accepted
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_megawatt_hour_house_input_is_accepted(hass: HomeAssistant) -> None:
    # Given - a grid meter in MWh, a unit Home Assistant converts like any other
    # energy unit (GitHub 49)
    _register_source_sensors(hass)
    _set_unit(hass, "sensor.grid_import", "MWh")

    # When
    result = await _set_up(
        hass, {**_HOUSE, CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption"}
    )

    # Then - accepted, and counted in kWh like Wh is (HEA-246)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_house_input_that_reports_no_unit_yet_is_accepted(
    hass: HomeAssistant,
) -> None:
    # Given - a sensor that has not said what it counts in. On an explicit
    # manual pick that is not evidence of anything: a cloud meter reconnecting
    # publishes no unit for a few seconds, and refusing it here would repeat
    # HEA-149's mistake of reading a moment's silence as a fact about the sensor
    _register_source_sensors(hass)
    _set_unit(hass, "sensor.grid_import", None)

    # When
    result = await _set_up(
        hass, {**_HOUSE, CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption"}
    )

    # Then - accepted, exactly as an absent state_class is (ADR-0010 section 2).
    # A unit that never arrives is caught at runtime instead
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_a_net_counter_is_rejected_for_an_input_the_model_reads(
    hass: HomeAssistant,
) -> None:
    # Given - a household with no house-consumption meter, so ADR-0005's
    # full-balance branch runs and generation is load-bearing; its generation
    # sensor is a `total` net counter, which that branch would mis-account into
    # silently wrong whole-home figures (HEA-67)
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.generation", "total")

    # When - it is submitted
    result = await _set_up(
        hass, {**_HOUSE, CONF_GENERATION_ENTITY: ["sensor.generation"]}
    )

    # Then - the form comes back with the error against that field. A bad house
    # input corrupts the whole ledger, not one device's share
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_GENERATION_ENTITY: "house_not_total_increasing"}


async def test_a_net_export_counter_is_rejected_where_the_model_reads_it(
    hass: HomeAssistant,
) -> None:
    # Given - no house-consumption meter, so the grid's export meter is read too,
    # and it is a `total` net counter
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.grid_export", "total")

    # When - it is given with the grid meter
    result = await _set_up(
        hass, grid={**_GRID, CONF_GRID_EXPORT_ENTITY: "sensor.grid_export"}
    )

    # Then - refused on the grid meter's own form, where the field is
    assert result["step_id"] == "grid_meter"
    assert result["errors"] == {CONF_GRID_EXPORT_ENTITY: "house_not_total_increasing"}


async def test_a_net_counter_among_several_generation_meters_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - two arrays, the second published as a `total` net counter, in a
    # household whose model reads generation
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.west_array_energy", "total")
    _set_state_class(hass, "sensor.east_array_energy", "total_increasing")

    # When
    result = await _set_up(
        hass,
        {
            **_HOUSE,
            CONF_GENERATION_ENTITY: [
                "sensor.east_array_energy",
                "sensor.west_array_energy",
            ],
        },
    )

    # Then - one bad meter is enough to refuse the field: the sum is only as
    # sound as its worst member
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_GENERATION_ENTITY: "house_not_total_increasing"}


async def test_a_net_counter_is_accepted_for_an_input_the_model_ignores(
    hass: HomeAssistant,
) -> None:
    # Given - the same `total` generation sensor, but a household that *does*
    # have a house-consumption meter. The residual branch never reads generation,
    # so the counter's class cannot affect a single figure - and rejecting it
    # would block a configuration that is correct in practice (the reference
    # instance's own setup)
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.generation", "total")

    # When - it is submitted alongside a house-consumption meter
    result = await _set_up(
        hass,
        {
            **_HOUSE,
            CONF_GENERATION_ENTITY: ["sensor.generation"],
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
        },
    )

    # Then - accepted; validation follows what the model actually consumes
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GENERATION_ENTITY] == ["sensor.generation"]


async def test_a_net_grid_import_counter_is_always_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - grid import as a `total` net counter. Every branch reads it, so
    # there is no configuration in which this one is harmless
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.grid_import", "total")

    # When - it is submitted with a house-consumption meter present
    result = await _set_up(
        hass, {**_HOUSE, CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption"}
    )

    # Then - rejected
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_GRID_IMPORT_ENTITY: "house_not_total_increasing"}


async def test_a_riemann_sum_is_accepted_where_a_net_counter_is_not(
    hass: HomeAssistant,
) -> None:
    # Given - a household whose grid import is a Riemann integral over a clamp's
    # power sensor, which is how anybody with watts and no kWh meter gets one.
    # It declares `total` like the net counter above, and the two are refused or
    # accepted on the same attribute - but this one only ever climbs, and it is
    # the helper this integration creates for itself on every power-only device
    _register_source_sensors(hass)
    _as_a_riemann_sum(hass, "sensor.grid_import")

    # When - it is submitted
    result = await _set_up(
        hass, {**_HOUSE, CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption"}
    )

    # Then - accepted. Refusing it while reading one ourselves is the asymmetry,
    # not the safety (HEA-162)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (grid,) = grid_meters_of(result["result"]).values()
    assert grid.imported == "sensor.grid_import"


async def test_user_flow_shows_the_configuration_form(hass: HomeAssistant) -> None:
    # Given / When - a fresh install starts the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Then - the house-level input form is shown
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow_creates_entry_from_the_required_inputs(
    hass: HomeAssistant,
) -> None:
    # Given - a tariff-only household (no generation or battery) with its sensors
    _register_source_sensors(hass)

    # When - only the required inputs are supplied
    result = await _set_up(hass)

    # Then - an entry is created holding the house-level configuration, and its
    # grid meter as an entry of its own
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CURRENCY] == "EUR"
    (grid,) = grid_meters_of(result["result"]).values()
    assert grid.imported == "sensor.grid_import"
    assert grid.price_entity == "sensor.electricity_price_import"


async def test_a_number_helper_is_accepted_as_the_import_price(
    hass: HomeAssistant,
) -> None:
    """A household on a fixed rate types it into a Number helper.

    The Energy Dashboard takes one as a price, and so does the README, so the
    form refusing it left the household stuck (HEA-132).
    """
    # Given - a fixed-rate household whose price is a Number helper
    _register_source_sensors(hass)
    hass.states.async_set(
        "input_number.electricity_rate", "0.2134", {"unit_of_measurement": "EUR/kWh"}
    )

    # When - it is chosen as the import price
    result = await _set_up(
        hass, grid={**_GRID, CONF_PRICE_ENTITY: "input_number.electricity_rate"}
    )

    # Then - the entry is created with it
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (grid,) = grid_meters_of(result["result"]).values()
    assert grid.price_entity == "input_number.electricity_rate"


async def test_user_flow_records_optional_generation_and_house_inputs(
    hass: HomeAssistant,
) -> None:
    # Given - a household with local generation and its own house meter
    _register_source_sensors(hass)

    # When - the optional source entities are supplied too
    result = await _set_up(
        hass,
        {
            **_HOUSE,
            CONF_GENERATION_ENTITY: ["sensor.generation"],
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
        },
    )

    # Then - they are stored alongside the required inputs
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GENERATION_ENTITY] == ["sensor.generation"]
    assert result["data"][CONF_HOUSE_CONSUMPTION_ENTITY] == "sensor.house_consumption"


async def test_user_flow_records_every_generation_meter_chosen(
    hass: HomeAssistant,
) -> None:
    # Given - panels on two inverter inputs, with no one meter holding the lot,
    # as HEA-219 found
    _register_source_sensors(hass)

    # When - both are chosen
    result = await _set_up(
        hass,
        {
            **_HOUSE,
            CONF_GENERATION_ENTITY: [
                "sensor.east_array_energy",
                "sensor.west_array_energy",
            ],
        },
        {**_GRID, CONF_GRID_EXPORT_ENTITY: "sensor.grid_export"},
    )

    # Then - both are kept, in the order given
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_GENERATION_ENTITY] == [
        "sensor.east_array_energy",
        "sensor.west_array_energy",
    ]


async def test_the_household_says_its_battery_never_charges_from_the_grid(
    hass: HomeAssistant,
) -> None:
    # Given - grid charging turned off on the battery, something the meters
    # cannot see (HEA-233)
    _register_source_sensors(hass)

    # When
    result = await _set_up(hass, {**_HOUSE, CONF_BATTERY_CHARGING: "solar_only"})

    # Then
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BATTERY_CHARGING] == "solar_only"


async def test_a_battery_charges_from_spare_solar_unless_told_otherwise(
    hass: HomeAssistant,
) -> None:
    # Given / When - a household that leaves the question alone
    _register_source_sensors(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    data_schema = result["data_schema"]
    assert data_schema is not None
    field = next(
        marker for marker in data_schema.schema if str(marker) == CONF_BATTERY_CHARGING
    )

    # Then - the answer true of most batteries, offered beside the other two,
    # last on the house screen, since the batteries themselves are entries of
    # their own (ADR-0031)
    assert field.default() == "spare_solar"
    options = data_schema.schema[field].config["options"]
    assert options == ["spare_solar", "grid_too", "solar_only"]
    fields = [str(marker) for marker in data_schema.schema]
    assert fields[-1] == CONF_BATTERY_CHARGING


async def test_the_house_screen_no_longer_asks_about_the_grid(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Then - the meters and their price are the grid entry's now (ADR-0032)
    data_schema = result["data_schema"]
    assert data_schema is not None
    fields = {str(marker) for marker in data_schema.schema}
    assert fields.isdisjoint(
        {CONF_GRID_IMPORT_ENTITY, CONF_GRID_EXPORT_ENTITY, CONF_PRICE_ENTITY}
    )


@pytest.mark.parametrize("stored", ["house", "battery"])
async def test_the_solar_priority_answer_gives_way_to_the_new_question(
    hass: HomeAssistant, stored: str
) -> None:
    # Given - an entry from 0.12.0 holding either answer to the question it asked.
    # "house" is also what anybody who opened Reconfigure stored without
    # choosing, so neither can be read as a deliberate answer to the new one
    _register_source_sensors(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data={**_LEGACY_HOUSE, "solar_priority": stored},
    )
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the old key is gone and the household is on the default, which the
    # coordinator reads from the key's absence
    assert entry.version == 7
    assert "solar_priority" not in entry.data
    assert CONF_BATTERY_CHARGING not in entry.data


async def test_only_one_instance_can_be_configured(hass: HomeAssistant) -> None:
    # Given - Home Energy Advisor is already configured (its config is global)
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    # When - the user tries to add it again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Then - the flow aborts rather than creating a second instance
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def _prefill_from(
    hass: HomeAssistant, sources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Open the flow over these Energy Dashboard sources and read the suggestions."""
    prefs = SimpleNamespace(data={"energy_sources": sources})
    with patch(_PATH, AsyncMock(return_value=prefs)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    data_schema = result["data_schema"]
    assert data_schema is not None
    return _suggested_values(data_schema)


async def test_prefill_reads_the_house_screens_inputs_and_nothing_else(
    hass: HomeAssistant,
) -> None:
    # Given - a household whose Energy Dashboard names a grid, solar and battery
    suggested = await _prefill_from(
        hass,
        [
            {
                "type": "grid",
                "stat_energy_from": "sensor.grid_import",
                "stat_energy_to": "sensor.grid_export",
            },
            {"type": "solar", "stat_energy_from": "sensor.generation"},
            {
                "type": "battery",
                "stat_energy_to": "sensor.battery_charge",
                "stat_energy_from": "sensor.battery_discharge",
            },
        ],
    )

    # Then - generation arrives answered. The grid and the battery are offered on
    # steps of their own (ADR-0031, ADR-0032), so none of them lands here
    assert suggested == {CONF_GENERATION_ENTITY: ["sensor.generation"]}


async def test_prefill_offers_every_solar_source_not_only_the_last(
    hass: HomeAssistant,
) -> None:
    # Given - an Energy Dashboard holding two solar sources, as Home Assistant
    # allows. Keeping only the last silently dropped half the generation, as
    # HEA-219 found
    suggested = await _prefill_from(
        hass,
        [
            {"type": "grid", "stat_energy_from": "sensor.grid_import"},
            {"type": "solar", "stat_energy_from": "sensor.east_array_energy"},
            {"type": "solar", "stat_energy_from": "sensor.west_array_energy"},
        ],
    )

    # Then
    assert suggested[CONF_GENERATION_ENTITY] == [
        "sensor.east_array_energy",
        "sensor.west_array_energy",
    ]


async def test_prefill_failure_never_blocks_the_flow(hass: HomeAssistant) -> None:
    # Given - reading the Energy Dashboard configuration fails
    with patch(_PATH, AsyncMock(side_effect=RuntimeError("energy unavailable"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # Then - the form is still shown, just with nothing pre-filled
    assert result["type"] is FlowResultType.FORM
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert _suggested_values(data_schema) == {}


async def _running(hass: HomeAssistant, **kwargs: Any) -> MockConfigEntry:  # noqa: ANN401 - MockConfigEntry's own arguments
    entry = MockConfigEntry(domain=DOMAIN, **kwargs)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _reconfigure(
    hass: HomeAssistant, entry: MockConfigEntry, answers: dict[str, Any]
) -> Any:  # noqa: ANN401 - a flow result
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], answers)
    await hass.async_block_till_done()
    return result


async def test_reconfigure_updates_the_house_level_config(hass: HomeAssistant) -> None:
    # Given - a configured, running household (no generation yet)
    _register_source_sensors(hass)
    entry = await _running(hass, data=dict(_LEGACY_HOUSE))

    # When - the config is edited to add generation and change the currency
    result = await _reconfigure(
        hass,
        entry,
        {CONF_CURRENCY: "GBP", CONF_GENERATION_ENTITY: ["sensor.generation"]},
    )

    # Then - the entry is updated in place, no reinstall, and its grid meter is
    # untouched
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CURRENCY] == "GBP"
    assert entry.data[CONF_GENERATION_ENTITY] == ["sensor.generation"]
    (grid,) = grid_meters_of(entry).values()
    assert grid.imported == "sensor.grid_import"


async def test_reconfigure_refuses_dropping_the_house_meter_over_a_net_export(
    hass: HomeAssistant,
) -> None:
    # Given - a running house with a house meter, whose grid export meter is a
    # `total` net counter: harmless while the house meter is there
    _register_source_sensors(hass)
    _set_state_class(hass, "sensor.grid_export", "total")
    entry = await _running(
        hass,
        data={
            **_LEGACY_HOUSE,
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
        },
    )

    # When - the house meter is removed, which brings the export meter into use
    result = await _reconfigure(hass, entry, {CONF_CURRENCY: "EUR"})

    # Then - refused, and the house meter stays
    assert result["errors"] == {"base": "grid_export_not_countable"}
    assert entry.data[CONF_HOUSE_CONSUMPTION_ENTITY] == "sensor.house_consumption"


async def test_an_existing_generation_meter_becomes_a_list_of_one(
    hass: HomeAssistant,
) -> None:
    # Given - an entry as the previous version stored it: one generation meter,
    # held as a single entity id
    _register_source_sensors(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={**_LEGACY_HOUSE, CONF_GENERATION_ENTITY: "sensor.generation"},
    )
    entry.add_to_hass(hass)

    # When - it is brought up to the current schema and set up
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the same meter, now in the shape every reader expects, and nothing
    # else about the household touched
    assert entry.version == 7
    assert entry.data[CONF_GENERATION_ENTITY] == ["sensor.generation"]
    (grid,) = grid_meters_of(entry).values()
    assert grid.imported == "sensor.grid_import"


async def test_an_entry_with_no_generation_gains_none(hass: HomeAssistant) -> None:
    # Given - a grid-only household at the previous version
    _register_source_sensors(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=3, data=dict(_LEGACY_HOUSE))
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - no empty list written for a meter they never had
    assert entry.version == 7
    assert CONF_GENERATION_ENTITY not in entry.data


async def test_reconfigure_removes_an_input_the_household_emptied(
    hass: HomeAssistant,
) -> None:
    # Given - a running house with a house meter and generation, and cycle
    # meters it created, which the form knows nothing about
    _register_source_sensors(hass)
    entry = await _running(
        hass,
        options={CONF_CYCLE_DAILY: True},
        data={
            **_LEGACY_HOUSE,
            CONF_GENERATION_ENTITY: ["sensor.generation"],
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_consumption",
        },
    )
    owned_before = dict(entry.data[CONF_CYCLE_METERS])

    # When - the house meter is emptied and the form submitted, which Home
    # Assistant's form sends as the field being absent (HEA-231)
    result = await _reconfigure(
        hass,
        entry,
        {CONF_CURRENCY: "EUR", CONF_GENERATION_ENTITY: ["sensor.generation"]},
    )

    # Then - it is gone, and what the form does not ask about is kept exactly
    assert result["reason"] == "reconfigure_successful"
    assert CONF_HOUSE_CONSUMPTION_ENTITY not in entry.data
    assert entry.data[CONF_CYCLE_METERS] == owned_before


async def test_reconfigure_preserves_helper_bookkeeping(hass: HomeAssistant) -> None:
    # Given - a running house-only install that has auto-created its cycle meters,
    # recorded on the entry as HEA-owned (created). Cycle totals are opted into
    # here because a household without them owns no helpers to preserve
    _register_source_sensors(hass)
    entry = await _running(
        hass,
        options={CONF_CYCLE_DAILY: True, CONF_CYCLE_MONTHLY: True},
        data=dict(_LEGACY_HOUSE),
    )
    owned_before = dict(entry.data[CONF_CYCLE_METERS])
    assert owned_before
    assert all(helper_was_created(record) for record in owned_before.values())

    # When - the house config is reconfigured (currency change)
    await _reconfigure(hass, entry, {CONF_CURRENCY: "GBP"})

    # Then - the bookkeeping survived: the same meters are still tracked, still as
    # HEA-created. A wholesale data replace would have dropped the map, and the
    # reload would then have re-adopted HEA's own meters as the user's - never to
    # be cleaned up (HEA-52 (a) and (b) interact).
    assert entry.data.get(CONF_CYCLE_METERS)
    assert set(entry.data[CONF_CYCLE_METERS]) == set(owned_before)
    assert all(
        helper_was_created(record) for record in entry.data[CONF_CYCLE_METERS].values()
    )
