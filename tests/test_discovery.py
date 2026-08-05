"""Candidate discovery for the guided "add devices" flow (HEA-45).

Discovery only ever *suggests*: it scans registered energy/power sensors and
returns the ones that could be tracked devices, excluding the house-level inputs,
the price entity, already-tracked devices, and HEA's own sensors. It never adds
anything — the options flow lets the user pick from the suggestions (false
friends like a phone battery are the user's to reject, not ours to auto-add).

A well-formed sensor is not automatically a device, so discovery also asks what a
candidate *means* and whether it *works* (ADR-0010): sensors derived from inputs
the integration already consumes are excluded, as are the other outputs of the
generation and storage hardware, and a device whose energy counter never reports
is offered by the power sensor beside it instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.derivative.const import DOMAIN as DERIVATIVE_DOMAIN
from homeassistant.components.integration.const import DOMAIN as INTEGRATION_DOMAIN
from homeassistant.components.utility_meter.const import (
    DOMAIN as UTILITY_METER_DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    CONF_NAME,
    CONF_SOURCE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.discovery import async_discover_candidates

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


_ELIGIBLE_STATE_CLASS = {"energy": "total_increasing", "power": "measurement"}


def _register(  # noqa: PLR0913 - a test fixture builder; each kwarg is a distinct axis
    hass: HomeAssistant,
    object_id: str,
    device_class: str,
    *,
    name: str | None = None,
    device_id: str | None = None,
    state_class: str | None = "eligible",
    state: str | None = None,
    config_entry: MockConfigEntry | None = None,
) -> str:
    """Register a sensor with a device_class and state_class; return its entity_id.

    ``state_class`` defaults to the eligible class for the device_class; pass an
    explicit value (or ``None``) to register an ineligible candidate. It is stored
    as a registry capability, since most discovery candidates have no live state.

    ``state`` additionally puts the sensor in the state machine, as Home Assistant
    writes it: an available sensor carries its device_class and state_class, while
    an ``unavailable`` one carries no attributes at all — which is exactly why
    discovery falls back to the registry capabilities.
    """
    resolved = (
        _ELIGIBLE_STATE_CLASS.get(device_class)
        if state_class == "eligible"
        else state_class
    )
    capabilities = {"state_class": resolved} if resolved is not None else None
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        config_entry.domain if config_entry else "sensor_source",
        object_id,
        suggested_object_id=object_id,
        original_device_class=device_class,
        original_name=name or object_id.replace("_", " ").title(),
        device_id=device_id,
        capabilities=capabilities,
        config_entry=config_entry,
    )
    if state is not None:
        attributes = (
            {}
            if state == STATE_UNAVAILABLE
            else {"device_class": device_class, "state_class": resolved}
        )
        hass.states.async_set(entity.entity_id, state, attributes)
    return entity.entity_id


def _helper_output(  # noqa: PLR0913 - a test fixture builder; each kwarg is a distinct axis
    hass: HomeAssistant,
    helper_domain: str,
    *,
    source: str,
    object_id: str,
    name: str,
    device_class: str = "energy",
    device_id: str | None = None,
) -> str:
    """Create a helper config entry over ``source``; return its output sensor.

    Models how a native `utility_meter` / Integral / Derivative helper records its
    input — ``options["source"]`` on its own config entry — which is the only
    declaration of provenance Home Assistant offers and what discovery walks.
    """
    helper = MockConfigEntry(domain=helper_domain, options={CONF_SOURCE: source})
    helper.add_to_hass(hass)
    return _register(
        hass,
        object_id,
        device_class,
        name=name,
        device_id=device_id,
        config_entry=helper,
    )


def _entry(hass: HomeAssistant, **house_inputs: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            **house_inputs,
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_aircon_energy",
                },
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def test_discovery_offers_untracked_energy_and_power_sensors(
    hass: HomeAssistant,
) -> None:
    # Given — a home with a price entity, a grid meter, and one already-tracked
    # device, plus two untracked candidates (an energy meter and a power sensor)
    entry = _entry(hass)
    _register(hass, "grid_import", "energy")  # house input
    _register(hass, "electricity_price", "monetary")  # price (not energy/power)
    _register(hass, "guest_aircon_energy", "energy")  # already tracked
    dryer = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")
    lights = _register(
        hass, "power_only_lights_power", "power", name="Power Only Lights Power"
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — only the two untracked sensors are offered; house/price/tracked excluded
    by_entity = {c.entity_id: c for c in candidates}
    assert set(by_entity) == {dryer, lights}
    # ...with the source key each device subentry needs, and a trimmed name
    assert by_entity[dryer].source_key == CONF_ENERGY_ENTITY
    assert by_entity[dryer].name == "Tumble Dryer"
    assert by_entity[lights].source_key == CONF_POWER_ENTITY
    assert by_entity[lights].name == "Power Only Lights"


async def test_discovery_prefers_the_energy_sensor_when_a_device_has_both(
    hass: HomeAssistant,
) -> None:
    # Given — one physical device exposing both an energy and a power sensor
    entry = _entry(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "utility_plug")}
    )
    energy = _register(hass, "utility_plug_energy", "energy", device_id=device.id)
    _register(hass, "utility_plug_power", "power", device_id=device.id)

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the device is offered once, as its energy sensor (not double-counted)
    assert [c.entity_id for c in candidates] == [energy]


async def test_discovery_names_a_device_from_its_parent_ha_device(
    hass: HomeAssistant,
) -> None:
    # Given — a sensor whose own name is just "Energy" (has_entity_name), while its
    # real identity lives on the parent HA device
    entry = _entry(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "panel_heater")},
        name="Power Only Panel Heater",
    )
    heater = _register(
        hass,
        "power_only_panel_heater_energy",
        "energy",
        name="Energy",
        device_id=device.id,
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the suggested name is the device's, not the bare "Energy"
    by_entity = {c.entity_id: c for c in candidates}
    assert by_entity[heater].name == "Power Only Panel Heater"


async def test_discovery_sorts_likely_false_friends_last(
    hass: HomeAssistant,
) -> None:
    # Given — a genuine device power sensor and an obvious false friend (a phone
    # battery power sensor)
    entry = _entry(hass)
    _register(hass, "phone_battery_power", "power", name="Phone Battery Power")
    real = _register(hass, "dishwasher_power", "power", name="Dishwasher Power")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — both are offered (the user decides), but the false friend sorts last
    assert candidates[0].entity_id == real
    assert candidates[-1].entity_id.endswith("phone_battery_power")
    assert candidates[-1].likely_false_friend is True


async def test_discovery_sorts_sensors_without_an_ha_device_last(
    hass: HomeAssistant,
) -> None:
    # Given — an appliance sensor belonging to an HA device, alongside two
    # device-less sensors that would otherwise sort ahead of it by name. On a
    # real instance the device-less sensors are overwhelmingly template outputs
    # and helper results — house infrastructure rather than appliances — while
    # every genuinely trackable device has a device behind it, so the link is the
    # best evidence discovery holds (HEA-70). It only ranks; nothing is hidden
    entry = _entry(hass)
    plug = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "washing_machine")},
        name="Washing Machine",
    )
    appliance = _register(hass, "washing_machine_energy", "energy", device_id=plug.id)
    inverter = _register(
        hass, "inverter_string_1_energy", "energy", name="Inverter String 1"
    )
    load = _register(hass, "grid_load_total_power", "power", name="Grid Load Total")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the appliance leads, despite sorting last of the three by name
    assert [c.entity_id for c in candidates] == [appliance, load, inverter]


async def test_discovery_ranks_the_device_link_above_the_false_friend_hint(
    hass: HomeAssistant,
) -> None:
    # Given — a phone battery power sensor, which the name hints flag, but which
    # belongs to a real HA device; and a device-less sensor with an innocent
    # name. Belonging to a device is the stronger signal: a flagged false friend
    # is one row the user skips, whereas the device-less tail is where the
    # hundreds of helper and infrastructure sensors sit
    entry = _entry(hass)
    phone = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "phone")}, name="Phone"
    )
    flagged = _register(
        hass,
        "phone_battery_power",
        "power",
        name="Phone Battery Power",
        device_id=phone.id,
    )
    device_less = _register(hass, "house_load_power", "power", name="House Load Power")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the flagged sensor still ranks above the device-less one
    assert [c.entity_id for c in candidates] == [flagged, device_less]
    assert candidates[0].likely_false_friend is True


async def test_discovery_excludes_sensors_with_an_ineligible_state_class(
    hass: HomeAssistant,
) -> None:
    # Given — valid candidates alongside sources the engine would mis-account: a
    # net (`total`) energy counter, a forecast energy sensor with no state_class,
    # and a "power" sensor that is really a running total. Unlike a false-friend
    # name, a wrong state_class is not a user judgement call — it is provably
    # mis-accounted — so discovery never suggests it (HEA-54).
    entry = _entry(hass)
    good_energy = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")
    good_power = _register(hass, "fridge_power", "power", name="Fridge Power")
    _register(hass, "solar_net_energy", "energy", state_class="total")
    _register(hass, "solar_forecast_energy", "energy", state_class=None)
    _register(hass, "grid_power_total", "power", state_class="total_increasing")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — only the two eligible sensors are offered
    assert {c.entity_id for c in candidates} == {good_energy, good_power}


async def test_discovery_excludes_a_cycle_meter_over_a_house_level_input(
    hass: HomeAssistant,
) -> None:
    # Given — the household's own daily utility_meter over the configured grid
    # import meter. It is a well-formed total_increasing kWh counter, so every
    # structural check passes; it is nonetheless house energy the integration
    # already consumes, and picking it would book it a second time as a device
    entry = _entry(hass)
    _register(hass, "grid_import", "energy")
    _helper_output(
        hass,
        UTILITY_METER_DOMAIN,
        source="sensor.grid_import",
        object_id="daily_grid_import",
        name="Daily Grid Import",
    )
    dryer = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the period aggregate is not offered; the genuine device still is
    assert [c.entity_id for c in candidates] == [dryer]


async def test_discovery_follows_a_derivation_chain_through_several_helpers(
    hass: HomeAssistant,
) -> None:
    # Given — a helper over a helper over the grid meter: a Derivative giving the
    # import rate in watts, and a Riemann integral turning that back into kWh.
    # Neither names the grid meter directly, so the chain has to be walked
    entry = _entry(hass)
    _register(hass, "grid_import", "energy")
    rate = _helper_output(
        hass,
        DERIVATIVE_DOMAIN,
        source="sensor.grid_import",
        object_id="grid_import_rate",
        name="Grid Import Rate",
        device_class="power",
    )
    _helper_output(
        hass,
        INTEGRATION_DOMAIN,
        source=rate,
        object_id="grid_import_reintegrated",
        name="Grid Import Reintegrated",
    )
    dryer = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — every link in the chain is excluded, however many hops from the meter
    assert [c.entity_id for c in candidates] == [dryer]


async def test_discovery_excludes_a_helper_over_an_already_tracked_device_source(
    hass: HomeAssistant,
) -> None:
    # Given — a utility_meter the household built over the tracked aircon's own
    # energy counter. Selecting it would book that device's energy twice, and
    # proportional allocation would then under-report every other device
    entry = _entry(hass)
    _register(hass, "guest_aircon_energy", "energy")
    _helper_output(
        hass,
        UTILITY_METER_DOMAIN,
        source="sensor.guest_aircon_energy",
        object_id="daily_coarse_step_aircon",
        name="Daily Coarse Step Aircon",
    )
    dryer = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the meter over a tracked source is not offered
    assert [c.entity_id for c in candidates] == [dryer]


async def test_discovery_offers_an_integral_the_user_built_over_a_plug(
    hass: HomeAssistant,
) -> None:
    # Given — a smart plug the user tracks through their own Riemann integral over
    # its power sensor. The candidate is a helper output, but its chain terminates
    # in an ordinary device sensor, so it is a legitimate way to track the plug —
    # the case that stops the derivation filter becoming "exclude all helpers"
    entry = _entry(hass)
    plug = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "dehumidifier_plug")},
        name="Landing Dehumidifier",
    )
    _register(hass, "dehumidifier_plug_power", "power", device_id=plug.id)
    integral = _helper_output(
        hass,
        INTEGRATION_DOMAIN,
        source="sensor.dehumidifier_plug_power",
        object_id="landing_dehumidifier_energy",
        name="Landing Dehumidifier Energy",
        device_id=plug.id,
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the plug is offered once, by the energy the user's helper produces
    assert [c.entity_id for c in candidates] == [integral]


async def test_discovery_excludes_the_other_outputs_of_the_supply_hardware(
    hass: HomeAssistant,
) -> None:
    # Given — a hybrid inverter supplying the generation and battery house inputs.
    # Its remaining outputs are the same physical system measured differently, so
    # none of them is an appliance the user could track
    entry = _entry(
        hass,
        **{
            CONF_SOLAR_ENTITY: "sensor.inverter_generation",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.inverter_battery_discharge",
        },
    )
    inverter = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "inverter")},
        name="Inverter",
    )
    _register(hass, "inverter_generation", "energy", device_id=inverter.id)
    _register(hass, "inverter_battery_discharge", "energy", device_id=inverter.id)
    _register(hass, "inverter_string_2_energy", "energy", device_id=inverter.id)
    _register(hass, "inverter_load_power", "power", device_id=inverter.id)
    dryer = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the whole family goes, including outputs never named in the config
    assert [c.entity_id for c in candidates] == [dryer]


async def test_discovery_still_offers_the_circuits_of_a_whole_home_meter(
    hass: HomeAssistant,
) -> None:
    # Given — a multi-channel CT clamp: one HA device whose mains channel is the
    # configured grid import and whose remaining channels are separate circuits.
    # A metering point is not the supply system, so its siblings are real devices
    # and must survive — ADR-0010 hides only what is *provably* not a device
    entry = _entry(hass)
    clamp = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "circuit_monitor")},
        name="Circuit Monitor",
    )
    _register(hass, "grid_import", "energy", device_id=clamp.id)
    oven = _register(
        hass, "circuit_2_energy", "energy", name="Oven Circuit", device_id=clamp.id
    )
    heating = _register(
        hass, "circuit_3_energy", "energy", name="Heating Circuit", device_id=clamp.id
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the mains channel is excluded and both circuits are still offered
    assert {c.entity_id for c in candidates} == {oven, heating}


async def test_discovery_drops_the_power_sibling_of_a_tracked_energy_sensor(
    hass: HomeAssistant,
) -> None:
    # Given — the already-tracked aircon's device also exposes a power sensor.
    # Offering it invites the user to add the same appliance a second time
    entry = _entry(hass)
    aircon = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "guest_aircon")},
        name="Coarse Step Aircon",
    )
    _register(hass, "guest_aircon_energy", "energy", device_id=aircon.id)
    _register(hass, "guest_aircon_power", "power", device_id=aircon.id)
    dryer = _register(hass, "tumble_dryer_energy", "energy", name="Tumble Dryer Energy")

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the tracked device is not offered again through its power sensor
    assert [c.entity_id for c in candidates] == [dryer]


async def test_discovery_offers_power_when_the_energy_sensor_never_reports(
    hass: HomeAssistant,
) -> None:
    # Given — a duty-cycle heater whose energy counter is a well-formed
    # total_increasing kWh sensor that only ever yields `unknown`, beside a power
    # sensor genuinely reading 0 W and a static nameplate wattage. Offered by the
    # energy sensor the device could only ever accumulate nothing (HEA-64)
    entry = _entry(hass)
    heater = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "panel_heater")},
        name="Landing Panel Heater",
    )
    _register(
        hass, "panel_heater_energy", "energy", device_id=heater.id, state=STATE_UNKNOWN
    )
    effective = _register(
        hass,
        "panel_heater_effective_power",
        "power",
        device_id=heater.id,
        state="0",
    )
    _register(
        hass,
        "panel_heater_nominal_power",
        "power",
        device_id=heater.id,
        state_class=None,
        state="300",
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the device is offered once, by the sensor that actually reports; the
    # nameplate wattage stays out on its missing state_class
    assert [c.entity_id for c in candidates] == [effective]
    assert candidates[0].source_key == CONF_POWER_ENTITY


async def test_discovery_keeps_energy_for_a_device_that_is_merely_switched_off(
    hass: HomeAssistant,
) -> None:
    # Given — a seasonal device switched off out of season: neither its energy
    # counter nor its power sensor reports anything. Silence now is not evidence
    # a counter is dead — seasonal silence is normal (HEA-24) — so the preference
    # for a measured counter must not flip
    entry = _entry(hass)
    aircon = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "study_aircon")},
        name="Study Aircon",
    )
    energy = _register(
        hass,
        "study_aircon_energy",
        "energy",
        device_id=aircon.id,
        state=STATE_UNAVAILABLE,
    )
    _register(
        hass,
        "study_aircon_power",
        "power",
        device_id=aircon.id,
        state=STATE_UNAVAILABLE,
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — still offered by its energy counter, exactly as when it is running
    assert [c.entity_id for c in candidates] == [energy]


async def test_discovery_still_offers_a_device_whose_only_sensor_never_reports(
    hass: HomeAssistant,
) -> None:
    # Given — the same dead energy counter, with no power sensor to fall back to
    entry = _entry(hass)
    boiler = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "immersion_heater")},
        name="Immersion Heater",
    )
    energy = _register(
        hass,
        "immersion_heater_energy",
        "energy",
        device_id=boiler.id,
        state=STATE_UNKNOWN,
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — offered anyway: a device is never silently hidden, and the user can
    # still see it and judge for themselves (ADR-0004, never auto-onboard)
    assert [c.entity_id for c in candidates] == [energy]
