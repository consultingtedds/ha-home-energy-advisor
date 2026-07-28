"""Candidate discovery for the guided "add devices" flow (HEA-45).

Discovery only ever *suggests*: it scans registered energy/power sensors and
returns the ones that could be tracked devices, excluding the house-level inputs,
the price entity, already-tracked devices, and HEA's own sensors. It never adds
anything — the options flow lets the user pick from the suggestions (false
friends like a phone battery are the user's to reject, not ours to auto-add).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import device_registry as dr
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
) -> str:
    """Register a sensor with a device_class and state_class; return its entity_id.

    ``state_class`` defaults to the eligible class for the device_class; pass an
    explicit value (or ``None``) to register an ineligible candidate. It is stored
    as a registry capability, since discovery candidates have no live state here.
    """
    resolved = (
        _ELIGIBLE_STATE_CLASS.get(device_class)
        if state_class == "eligible"
        else state_class
    )
    capabilities = {"state_class": resolved} if resolved is not None else None
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "sensor_source",
        object_id,
        suggested_object_id=object_id,
        original_device_class=device_class,
        original_name=name or object_id.replace("_", " ").title(),
        device_id=device_id,
        capabilities=capabilities,
    )
    return entity.entity_id


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Guest Bedroom Aircon",
                data={
                    CONF_NAME: "Guest Bedroom Aircon",
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
        hass, "hallway_lights_power", "power", name="Hallway Lights Power"
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
    assert by_entity[lights].name == "Hallway Lights"


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
        name="Hallway Panel Heater",
    )
    heater = _register(
        hass,
        "hallway_panel_heater_energy",
        "energy",
        name="Energy",
        device_id=device.id,
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the suggested name is the device's, not the bare "Energy"
    by_entity = {c.entity_id: c for c in candidates}
    assert by_entity[heater].name == "Hallway Panel Heater"


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
