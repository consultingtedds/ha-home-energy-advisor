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
    excluded = _excluded_entities(entry, registry)
    paired = [
        (entity, candidate)
        for entity in registry.entities.values()
        if entity.domain == "sensor"
        and entity.platform != DOMAIN
        and entity.entity_id not in excluded
        and (candidate := _candidate(hass, entity)) is not None
    ]
    kept = _prefer_energy(paired)
    return sorted(kept, key=lambda c: (c.likely_false_friend, c.name))


def _candidate(hass: HomeAssistant, entity: RegistryEntry) -> DeviceCandidate | None:
    kind = _energy_or_power(hass, entity)
    if kind is None:
        return None
    return DeviceCandidate(
        entity_id=entity.entity_id,
        name=_suggested_name(entity),
        source_key=_SOURCE_KEY[kind],
        likely_false_friend=_looks_like_a_false_friend(entity),
    )


def _energy_or_power(hass: HomeAssistant, entity: RegistryEntry) -> str | None:
    device_class = entity.original_device_class
    if device_class is None and (state := hass.states.get(entity.entity_id)):
        raw = state.attributes.get("device_class")
        device_class = raw if isinstance(raw, str) else None
    return device_class if device_class in _SOURCE_KEY else None


def _suggested_name(entity: RegistryEntry) -> str:
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
        *entry.data.get(CONF_INTEGRAL_HELPERS, {}).values(),
        *entry.data.get(CONF_CYCLE_METERS, {}).values(),
    )
    return {
        registry_entry.entity_id
        for helper_id in helper_ids
        for registry_entry in er.async_entries_for_config_entry(registry, helper_id)
    }
