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


def _register(
    hass: HomeAssistant,
    object_id: str,
    device_class: str,
    *,
    name: str | None = None,
    device_id: str | None = None,
) -> str:
    """Register a sensor with a device_class; return its entity_id."""
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "sensor_source",
        object_id,
        suggested_object_id=object_id,
        original_device_class=device_class,
        original_name=name or object_id.replace("_", " ").title(),
        device_id=device_id,
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
    pool = _register(hass, "pool_pump_energy", "energy", name="Pool Pump Energy")
    lights = _register(
        hass, "hallway_lights_power", "power", name="Hallway Lights Power"
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — only the two untracked sensors are offered; house/price/tracked excluded
    by_entity = {c.entity_id: c for c in candidates}
    assert set(by_entity) == {pool, lights}
    # ...with the source key each device subentry needs, and a trimmed name
    assert by_entity[pool].source_key == CONF_ENERGY_ENTITY
    assert by_entity[pool].name == "Pool Pump"
    assert by_entity[lights].source_key == CONF_POWER_ENTITY
    assert by_entity[lights].name == "Hallway Lights"


async def test_discovery_prefers_the_energy_sensor_when_a_device_has_both(
    hass: HomeAssistant,
) -> None:
    # Given — one physical device exposing both an energy and a power sensor
    entry = _entry(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("demo", "well_pump")}
    )
    energy = _register(hass, "well_pump_energy", "energy", device_id=device.id)
    _register(hass, "well_pump_power", "power", device_id=device.id)

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
        identifiers={("demo", "towel_rail")},
        name="Master Bathroom Towel Rail",
    )
    towel = _register(
        hass,
        "master_bathroom_towel_rail_energy",
        "energy",
        name="Energy",
        device_id=device.id,
    )

    # When — candidates are discovered
    candidates = async_discover_candidates(hass, entry)

    # Then — the suggested name is the device's, not the bare "Energy"
    by_entity = {c.entity_id: c for c in candidates}
    assert by_entity[towel].name == "Master Bathroom Towel Rail"


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
