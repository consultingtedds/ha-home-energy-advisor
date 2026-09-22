from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.integration.const import (
    CONF_SOURCE_SENSOR,
    CONF_UNIT_TIME,
    METHOD_TRAPEZOIDAL,
)
from homeassistant.components.integration.const import DOMAIN as INTEGRATION_DOMAIN
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigSubentryData,
)
from homeassistant.const import CONF_METHOD, CONF_NAME, UnitOfTime
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
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
        "sensor.coarse_step_aircon_energy",
        "12.5",
        {"device_class": "energy", "state_class": "total_increasing"},
    )
    hass.states.async_set(
        "sensor.ceiling_lights_power",
        "40",
        {"device_class": "power", "state_class": "measurement"},
    )
    # Sources with a present-but-wrong state_class the engine would mis-account,
    # so the manual add flow rejects them (HEA-54): a net counter that can fall
    # (read as a reset → phantom energy), an energy sensor reporting an
    # instantaneous measurement, and a power sensor that is a running total.
    hass.states.async_set(
        "sensor.solar_net_energy",
        "3.0",
        {"device_class": "energy", "state_class": "total"},
    )
    hass.states.async_set(
        "sensor.house_power_as_energy",
        "800",
        {"device_class": "energy", "state_class": "measurement"},
    )
    hass.states.async_set(
        "sensor.grid_power_running_total",
        "1200",
        {"device_class": "power", "state_class": "total_increasing"},
    )
    # An unlabelled counter - device_class energy, no state_class at all. Manual
    # add allows it (an explicit pick of an unlabelled sensor is the user's call);
    # discovery is stricter and would not suggest it (HEA-54).
    hass.states.async_set(
        "sensor.homebrew_boiler_energy",
        "7.0",
        {"device_class": "energy"},
    )


def _a_riemann_sum(hass: HomeAssistant, object_id: str) -> str:
    """Add Home Assistant's own integral helper over a power sensor; its output id.

    Both halves are what Home Assistant really does. The output declares `total`,
    unconditionally, and what distinguishes it from a net meter is the domain of
    the config entry that owns it - which is what the registry records and the
    only place the difference is stated.
    """
    helper = MockConfigEntry(
        domain=INTEGRATION_DOMAIN,
        title="Dehumidifier Energy",
        options={
            CONF_SOURCE_SENSOR: "sensor.dehumidifier_plug_power",
            CONF_METHOD: METHOD_TRAPEZOIDAL,
            CONF_UNIT_TIME: UnitOfTime.HOURS,
        },
    )
    helper.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        INTEGRATION_DOMAIN,
        object_id,
        suggested_object_id=object_id,
        config_entry=helper,
    )
    hass.states.async_set(
        entity.entity_id,
        "3.4",
        {
            "device_class": "energy",
            "state_class": "total",
            "unit_of_measurement": "kWh",
        },
    )
    return entity.entity_id


async def _start_add(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return result["flow_id"]


async def test_add_device_subentry_with_an_energy_sensor(hass: HomeAssistant) -> None:
    # Given - a configured household and a device that reports its own energy
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - the device is added by name and energy sensor
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Coarse Step Aircon",
            CONF_ENERGY_ENTITY: "sensor.coarse_step_aircon_energy",
        },
    )

    # Then - a device subentry is created on the parent entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Coarse Step Aircon"
    assert subentry.subentry_type == SUBENTRY_TYPE_DEVICE
    assert subentry.data[CONF_ENERGY_ENTITY] == "sensor.coarse_step_aircon_energy"


async def test_add_device_subentry_with_a_power_sensor(hass: HomeAssistant) -> None:
    # Given - a power-only device (energy is derived later via an Integral helper)
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - the device is added by name and power sensor
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Ceiling Lights",
            CONF_POWER_ENTITY: "sensor.ceiling_lights_power",
        },
    )

    # Then - the subentry records the power sensor
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_POWER_ENTITY] == "sensor.ceiling_lights_power"


async def test_adding_a_device_with_both_sensors_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - the add-device form
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - both an energy and a power sensor are given
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Confused Device",
            CONF_ENERGY_ENTITY: "sensor.coarse_step_aircon_energy",
            CONF_POWER_ENTITY: "sensor.ceiling_lights_power",
        },
    )

    # Then - the form re-shows with an error; a device has exactly one source
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "select_one_sensor"}


async def test_adding_a_device_with_no_sensor_is_rejected(hass: HomeAssistant) -> None:
    # Given - the add-device form
    entry = _parent_entry(hass)
    flow_id = await _start_add(hass, entry)

    # When - neither sensor is given
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {CONF_NAME: "Sensorless Device"}
    )

    # Then - the form re-shows with the same error
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "select_one_sensor"}


async def test_adding_a_net_energy_counter_is_rejected(hass: HomeAssistant) -> None:
    # Given - the add-device form
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - a `total` (net) energy counter is chosen: it can fall, which the
    # engine would read as a cycle reset and book as phantom energy
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {CONF_NAME: "Solar Net", CONF_ENERGY_ENTITY: "sensor.solar_net_energy"},
    )

    # Then - it is rejected with a translated error naming the required class
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "energy_not_total_increasing"}


async def test_adding_a_device_tracked_by_a_riemann_integral_is_accepted(
    hass: HomeAssistant,
) -> None:
    # Given - a plug tracked through the household's own Riemann integral over
    # its power sensor, which is how anybody with watts and no counter gets
    # energy. It declares `total` exactly as the net counter above does, because
    # `IntegrationSensor._attr_state_class` says so on the class whatever the
    # output does - and it is the helper this integration builds for itself on
    # every power-only device, so refusing it here refuses our own work (HEA-162)
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    integral = _a_riemann_sum(hass, "dehumidifier_energy")
    flow_id = await _start_add(hass, entry)

    # When - the device is added by that helper's output
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {CONF_NAME: "Dehumidifier", CONF_ENERGY_ENTITY: integral},
    )

    # Then - accepted, where a `total` sensor with no helper behind it is not
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_ENERGY_ENTITY] == integral


async def test_adding_a_device_in_a_unit_the_engine_cannot_count_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - a plug whose counter reports megawatt hours. The engine counts in
    # kWh and Wh; anything else is left uncounted rather than guessed at, so
    # this device would sit at zero for ever and its energy would land in
    # Untracked with nothing saying why
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    hass.states.async_set(
        "sensor.industrial_meter_energy",
        "4.2",
        {
            "device_class": "energy",
            "state_class": "total_increasing",
            "unit_of_measurement": "MWh",
        },
    )
    flow_id = await _start_add(hass, entry)

    # When
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Industrial Meter",
            CONF_ENERGY_ENTITY: "sensor.industrial_meter_energy",
        },
    )

    # Then - refused while the household is still choosing, rather than
    # discovered as a device that never costs anything
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unit_not_energy"}


async def test_adding_a_device_that_counts_in_watt_hours_is_accepted(
    hass: HomeAssistant,
) -> None:
    # Given - a plug in Wh, which is ordinary and correctly converted (HEA-149).
    # Two households have now lost time believing this was their fault; it is
    # not, and the flow must not imply it is
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    hass.states.async_set(
        "sensor.watt_hour_plug_energy",
        "2750",
        {
            "device_class": "energy",
            "state_class": "total_increasing",
            "unit_of_measurement": "Wh",
        },
    )
    flow_id = await _start_add(hass, entry)

    # When
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {
            CONF_NAME: "Watt Hour Plug",
            CONF_ENERGY_ENTITY: "sensor.watt_hour_plug_energy",
        },
    )

    # Then - added without complaint
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_adding_an_energy_sensor_reporting_measurement_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - the add-device form
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - an energy sensor that is really an instantaneous measurement is chosen
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {CONF_NAME: "House Power", CONF_ENERGY_ENTITY: "sensor.house_power_as_energy"},
    )

    # Then - rejected: the engine needs a cumulative counter, not a measurement
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "energy_not_total_increasing"}


async def test_adding_a_power_sensor_that_is_a_running_total_is_rejected(
    hass: HomeAssistant,
) -> None:
    # Given - the add-device form
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - a "power" sensor that is actually a running total is chosen: its
    # Integral helper would integrate a cumulative value, not a rate
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {CONF_NAME: "Grid", CONF_POWER_ENTITY: "sensor.grid_power_running_total"},
    )

    # Then - rejected with the power-specific error
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "power_not_measurement"}


async def test_adding_an_unlabelled_energy_counter_is_allowed(
    hass: HomeAssistant,
) -> None:
    # Given - a device whose energy counter sets no state_class at all (a custom
    # template sensor, say). Discovery would not suggest it, but an explicit manual
    # pick is the user's call, so the add flow allows it (HEA-54).
    entry = _parent_entry(hass)
    _register_device_sensors(hass)
    flow_id = await _start_add(hass, entry)

    # When - the unlabelled counter is chosen explicitly
    result = await hass.config_entries.subentries.async_configure(
        flow_id,
        {CONF_NAME: "Boiler", CONF_ENERGY_ENTITY: "sensor.homebrew_boiler_energy"},
    )

    # Then - the device is created; only a present-but-wrong class is rejected
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_ENERGY_ENTITY] == "sensor.homebrew_boiler_energy"


def _entry_with_device(hass: HomeAssistant) -> tuple[MockConfigEntry, str]:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.coarse_step_aircon_energy",
                },
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry, next(iter(entry.subentries))


async def test_reconfigure_device_switches_its_source_sensor(
    hass: HomeAssistant,
) -> None:
    # Given - an existing energy-tracked device
    _register_device_sensors(hass)
    entry, subentry_id = _entry_with_device(hass)

    # When - it is reconfigured to use a power sensor instead
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Coarse Step Aircon",
            CONF_POWER_ENTITY: "sensor.ceiling_lights_power",
        },
    )

    # Then - the subentry is updated, swapping energy for power
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = entry.subentries[subentry_id]
    assert subentry.data[CONF_POWER_ENTITY] == "sensor.ceiling_lights_power"
    assert CONF_ENERGY_ENTITY not in subentry.data


async def test_reconfigure_device_still_requires_exactly_one_sensor(
    hass: HomeAssistant,
) -> None:
    # Given - an existing device being reconfigured
    _register_device_sensors(hass)
    entry, subentry_id = _entry_with_device(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )

    # When - both sensors are given
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Coarse Step Aircon",
            CONF_ENERGY_ENTITY: "sensor.coarse_step_aircon_energy",
            CONF_POWER_ENTITY: "sensor.ceiling_lights_power",
        },
    )

    # Then - the same validation rejects it
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "select_one_sensor"}


async def test_reconfigure_device_rejects_a_wrong_state_class(
    hass: HomeAssistant,
) -> None:
    # Given - an existing device being reconfigured
    _register_device_sensors(hass)
    entry, subentry_id = _entry_with_device(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DEVICE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )

    # When - the source is switched to a net counter
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Coarse Step Aircon",
            CONF_ENERGY_ENTITY: "sensor.solar_net_energy",
        },
    )

    # Then - the state_class guard applies on reconfigure too, not only on add
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "energy_not_total_increasing"}
