"""Discover candidate device sensors to offer for tracking (HEA-45).

The guided "add devices" step scans registered energy and power sensors and
suggests the ones that could be tracked devices — excluding the house-level
inputs, the price entity, already-tracked devices, and the integration's own
sensors and auto-created helper outputs. It only ever *suggests*: the options
flow lets the user pick from the list, so false friends (a phone battery, an
exercise bike's power) are the user's to reject, never auto-onboarded (ADR-0004).

A physical device exposing both an energy and a power sensor is offered once, as
its energy sensor, so the same device is never tracked twice. Sensors whose names
look like non-devices are sorted last rather than hidden — the user still decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CYCLE_METERS,
    CONF_ENERGY_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_INTEGRAL_HELPERS,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from .helper_ownership import helper_entry_id

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import RegistryEntry

# House-level inputs and the price entity are configured elsewhere, never offered
# as devices.
_HOUSE_CONF_KEYS = (
    CONF_PRICE_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_SOLAR_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
)
_SOURCE_KEY = {"energy": CONF_ENERGY_ENTITY, "power": CONF_POWER_ENTITY}
# The state_class the engine's reset semantics require of each device source: a
# total_increasing counter for energy (a fall is read as a new cycle, so a `total`
# net counter or an unlabelled forecast would book phantom energy), and an
# instantaneous measurement for power (integrated to energy by a helper). Any
# other class is provably mis-accounted, so discovery never suggests one and the
# add flow rejects a present-but-wrong one (ADR-0004; HEA-54).
REQUIRED_STATE_CLASS = {
    CONF_ENERGY_ENTITY: "total_increasing",
    CONF_POWER_ENTITY: "measurement",
}
# Trailing words trimmed from a suggested device name — the concept, not the device.
_NAME_SUFFIXES = (" energy", " power", " consumption")
# Substrings that mark a sensor as a likely non-device; offered, but sorted last.
_FALSE_FRIEND_HINTS = (
    "battery",
    "forecast",
    "predict",
    "estimate",
    "price",
    "tariff",
    "standing",
    "soc",
    "budget",
)


@dataclass(frozen=True)
class DeviceCandidate:
    """A sensor the user could choose to track as a device."""

    entity_id: str
    name: str
    source_key: str  # CONF_ENERGY_ENTITY or CONF_POWER_ENTITY
    likely_false_friend: bool


def async_discover_candidates(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[DeviceCandidate]:
    """Return untracked energy/power sensors to offer as devices, best first."""
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    excluded = _excluded_entities(entry, registry)
    paired = [
        (entity, candidate)
        for entity in registry.entities.values()
        if entity.domain == "sensor"
        and entity.platform != DOMAIN
        and entity.entity_id not in excluded
        and (candidate := _candidate(hass, devices, entity)) is not None
    ]
    kept = _prefer_energy(paired)
    return sorted(kept, key=lambda c: (c.likely_false_friend, c.name))


def _candidate(
    hass: HomeAssistant, devices: dr.DeviceRegistry, entity: RegistryEntry
) -> DeviceCandidate | None:
    kind = _energy_or_power(hass, entity)
    if kind is None:
        return None
    source_key = _SOURCE_KEY[kind]
    if not is_eligible_source(hass, entity.entity_id, source_key):
        return None
    return DeviceCandidate(
        entity_id=entity.entity_id,
        name=_suggested_name(devices, entity),
        source_key=source_key,
        likely_false_friend=_looks_like_a_false_friend(entity),
    )


def is_eligible_source(hass: HomeAssistant, entity_id: str, source_key: str) -> bool:
    """Whether a sensor's state_class exactly matches its source's requirement.

    Strict — an absent state_class fails too. Discovery uses it so it never
    *suggests* a source the engine would mis-account; the add flow is more lenient
    on an absent class, where the pick is an explicit user choice (HEA-54).
    """
    return source_state_class(hass, entity_id) == REQUIRED_STATE_CLASS[source_key]


def source_state_class(hass: HomeAssistant, entity_id: str) -> str | None:
    """A sensor's state_class, from its live state, else the entity registry.

    Discovery inspects registry entries that often have no live state, so the
    registry ``capabilities`` (where the sensor platform records state_class) is
    the fallback when the entity is unavailable or not yet in the state machine.
    """
    if (state := hass.states.get(entity_id)) is not None:
        live = state.attributes.get("state_class")
        if isinstance(live, str):
            return live
    entity = er.async_get(hass).async_get(entity_id)
    if entity is not None and entity.capabilities:
        stored = entity.capabilities.get("state_class")
        if isinstance(stored, str):
            return stored
    return None


def _energy_or_power(hass: HomeAssistant, entity: RegistryEntry) -> str | None:
    device_class = entity.original_device_class
    if device_class is None and (state := hass.states.get(entity.entity_id)):
        raw = state.attributes.get("device_class")
        device_class = raw if isinstance(raw, str) else None
    return device_class if device_class in _SOURCE_KEY else None


def _suggested_name(devices: dr.DeviceRegistry, entity: RegistryEntry) -> str:
    """The device name to suggest: the parent HA device's, else the entity's.

    Most device sensors set ``has_entity_name``, so the entity's own name is just
    the concept ("Energy") while the real identity lives on the parent device.
    Prefer that; only when there is no device do we fall back to the entity's own
    name, trimmed of a trailing concept word.
    """
    if (
        entity.device_id
        and (device := devices.async_get(entity.device_id))
        and (device_name := device.name_by_user or device.name)
    ):
        return device_name
    name = entity.name or entity.original_name or entity.entity_id
    lowered = name.lower()
    for suffix in _NAME_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)].rstrip()
    return name


def _looks_like_a_false_friend(entity: RegistryEntry) -> bool:
    haystack = f"{entity.entity_id} {entity.name or entity.original_name or ''}".lower()
    return any(hint in haystack for hint in _FALSE_FRIEND_HINTS)


def _prefer_energy(
    paired: list[tuple[RegistryEntry, DeviceCandidate]],
) -> list[DeviceCandidate]:
    """Drop a device's power candidate when the same device has an energy one."""
    energy_device_ids = {
        entity.device_id
        for entity, candidate in paired
        if candidate.source_key == CONF_ENERGY_ENTITY and entity.device_id is not None
    }
    return [
        candidate
        for entity, candidate in paired
        if not (
            candidate.source_key == CONF_POWER_ENTITY
            and entity.device_id in energy_device_ids
        )
    ]


def _excluded_entities(entry: ConfigEntry, registry: er.EntityRegistry) -> set[str]:
    """Entity ids that must never be offered as new devices."""
    excluded = {entry.data[key] for key in _HOUSE_CONF_KEYS if entry.data.get(key)}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue
        for key in (CONF_ENERGY_ENTITY, CONF_POWER_ENTITY):
            if source := subentry.data.get(key):
                excluded.add(source)
    excluded |= _owned_helper_entities(entry, registry)
    return excluded


def _owned_helper_entities(entry: ConfigEntry, registry: er.EntityRegistry) -> set[str]:
    """Entity ids published by the Integral / utility_meter helpers HEA created."""
    helper_ids = (
        helper_entry_id(record)
        for record in (
            *entry.data.get(CONF_INTEGRAL_HELPERS, {}).values(),
            *entry.data.get(CONF_CYCLE_METERS, {}).values(),
        )
    )
    return {
        registry_entry.entity_id
        for helper_id in helper_ids
        for registry_entry in er.async_entries_for_config_entry(registry, helper_id)
    }
