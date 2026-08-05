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

Structural eligibility is only the entry condition. A well-formed counter can
still be house energy already accounted for, or dead, so discovery also asks what
a candidate means and whether it works (ADR-0010): it walks each candidate's
derivation chain and refuses anything that resolves to an input the integration
already consumes, refuses the other outputs of the generation and storage
hardware, and prefers a source that is actually reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.derivative.const import DOMAIN as DERIVATIVE_DOMAIN
from homeassistant.components.integration.const import (
    CONF_SOURCE_SENSOR as INTEGRAL_SOURCE,
)
from homeassistant.components.integration.const import (
    DOMAIN as INTEGRATION_DOMAIN,
)
from homeassistant.components.utility_meter.const import (
    CONF_SOURCE_SENSOR as METER_SOURCE,
)
from homeassistant.components.utility_meter.const import (
    DOMAIN as UTILITY_METER_DOMAIN,
)
from homeassistant.const import CONF_SOURCE
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
# The house inputs that identify their device as the *supply* system — an
# inverter or battery — whose every other output is house infrastructure rather
# than an appliance. Deliberately not the grid and house-consumption meters: on a
# multi-channel CT clamp the mains channel sits on the same HA device as the
# circuits feeding individual appliances, and those are real devices (HEA-66).
_SUPPLY_CONF_KEYS = (
    CONF_SOLAR_ENTITY,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
)
# Where each helper integration records the sensor it derives its output from.
# This is the only provenance Home Assistant states outright, and reading it is
# proven in-repo (`cycle_meter`, `integral_helper` both match on it). A helper of
# any other domain simply ends the walk — unknown provenance is not a reason to
# hide a device.
_DERIVED_SOURCE_KEYS = {
    DERIVATIVE_DOMAIN: CONF_SOURCE,
    INTEGRATION_DOMAIN: INTEGRAL_SOURCE,
    UTILITY_METER_DOMAIN: METER_SOURCE,
}
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


@dataclass(frozen=True)
class _Exclusions:
    """What a scan must not offer, resolved once from the config entry.

    Attributes:
        entities: Sensors that are provably not devices — the house-level inputs,
            the price entity, the sources already tracked, and the helper outputs
            HEA created. A candidate derived from any of them is one too.
        supply_devices: The HA devices behind the generation and storage inputs.
        tracked_energy_devices: The HA devices behind an already-tracked energy
            source, whose power sensors are that same device measured again.
    """

    entities: frozenset[str]
    supply_devices: frozenset[str]
    tracked_energy_devices: frozenset[str]


def async_discover_candidates(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[DeviceCandidate]:
    """Return untracked energy/power sensors to offer as devices, best first."""
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    exclusions = _exclusions(entry, registry)
    paired = [
        (entity, candidate)
        for entity in registry.entities.values()
        if entity.domain == "sensor"
        and entity.platform != DOMAIN
        and (candidate := _candidate(hass, devices, entity)) is not None
        and not _is_provably_not_a_device(hass, registry, entity.entity_id, exclusions)
    ]
    kept = _prefer_working_energy(hass, paired, exclusions.tracked_energy_devices)
    return sorted(kept, key=lambda c: (c.likely_false_friend, c.name))


def _is_provably_not_a_device(
    hass: HomeAssistant,
    registry: er.EntityRegistry,
    entity_id: str,
    exclusions: _Exclusions,
) -> bool:
    """Whether the sensor, or anything it derives from, cannot be an appliance.

    Walks the derivation chain hop by hop — a utility_meter over a Riemann
    integral over the grid meter is three links from house energy, and names it
    nowhere — stopping at the first link that is an input the integration already
    consumes or sits on the supply hardware.

    What matters is where the chain *terminates*, not that derivation exists: an
    Integral the user built over a plug's power sensor resolves to an ordinary
    device sensor and is a perfectly good way to track that plug (ADR-0010).
    """
    seen: set[str] = set()
    link: str | None = entity_id
    while link is not None and link not in seen:
        seen.add(link)
        if _is_a_consumed_input(registry, link, exclusions):
            return True
        link = _declared_source(hass, registry, link)
    return False


def _is_a_consumed_input(
    registry: er.EntityRegistry, entity_id: str, exclusions: _Exclusions
) -> bool:
    """Whether this exact sensor is house energy the integration already reads."""
    if entity_id in exclusions.entities:
        return True
    entity = registry.async_get(entity_id)
    return entity is not None and entity.device_id in exclusions.supply_devices


def _declared_source(
    hass: HomeAssistant, registry: er.EntityRegistry, entity_id: str
) -> str | None:
    """The sensor a helper derives this one from, per its own config entry."""
    entity = registry.async_get(entity_id)
    if entity is None or entity.config_entry_id is None:
        return None
    helper = hass.config_entries.async_get_entry(entity.config_entry_id)
    if helper is None:
        return None
    key = _DERIVED_SOURCE_KEYS.get(helper.domain)
    source = helper.options.get(key) if key is not None else None
    return source if isinstance(source, str) else None


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


def _prefer_working_energy(
    hass: HomeAssistant,
    paired: list[tuple[RegistryEntry, DeviceCandidate]],
    tracked_energy_devices: frozenset[str],
) -> list[DeviceCandidate]:
    """Offer each physical device once, by its energy sensor where that works.

    A measured counter beats an integrated one, so a device's power candidate is
    dropped when the same device has an energy candidate — or already supplies a
    tracked energy source, whose sibling power sensor would otherwise return as a
    second copy of a device the user is already tracking (HEA-66).

    The preference flips only when the energy sensor reports no number *and* the
    power sensor beside it does: a well-formed counter that never yields a value
    can only produce a device stuck at zero (HEA-64). Both silent means the device
    is simply off, which is normal and seasonal (HEA-24), so nothing is inferred —
    and with no power candidate the device is still offered by the energy sensor,
    because a device is never hidden for looking unpromising.
    """
    reporting = {
        entity.entity_id
        for entity, _ in paired
        if _is_reporting(hass, entity.entity_id)
    }
    energy_devices = _devices_offering(paired, CONF_ENERGY_ENTITY)
    power_devices = _devices_offering(paired, CONF_POWER_ENTITY)
    superseded = {
        device_id
        for device_id, sensors in energy_devices.items()
        if not sensors & reporting and power_devices.get(device_id, set()) & reporting
    }
    metered = (set(energy_devices) - superseded) | tracked_energy_devices
    return [
        candidate
        for entity, candidate in paired
        if _is_the_row_for_its_device(entity, candidate, metered, superseded)
    ]


def _is_the_row_for_its_device(
    entity: RegistryEntry,
    candidate: DeviceCandidate,
    metered: set[str],
    superseded: set[str],
) -> bool:
    """Whether this candidate is the row its device should be offered as."""
    if candidate.source_key == CONF_POWER_ENTITY:
        return entity.device_id not in metered
    return entity.device_id not in superseded


def _devices_offering(
    paired: list[tuple[RegistryEntry, DeviceCandidate]], source_key: str
) -> dict[str, set[str]]:
    """Each HA device's candidate sensors of one source kind, keyed by device."""
    grouped: dict[str, set[str]] = {}
    for entity, candidate in paired:
        if entity.device_id is not None and candidate.source_key == source_key:
            grouped.setdefault(entity.device_id, set()).add(entity.entity_id)
    return grouped


def _is_reporting(hass: HomeAssistant, entity_id: str) -> bool:
    """Whether the sensor currently holds a number rather than nothing at all.

    Never read on its own: `unknown` proves only that a value is absent now, and
    a device may simply be off. It decides a choice *between* two sensors on the
    same device, where one of them is working (ADR-0010).
    """
    state = hass.states.get(entity_id)
    if state is None:
        return False
    try:
        float(state.state)
    except ValueError:
        return False
    else:
        return True


def _exclusions(entry: ConfigEntry, registry: er.EntityRegistry) -> _Exclusions:
    """Resolve, once per scan, everything that must not be offered as a device."""
    house = {entry.data[key] for key in _HOUSE_CONF_KEYS if entry.data.get(key)}
    supply = {entry.data[key] for key in _SUPPLY_CONF_KEYS if entry.data.get(key)}
    tracked_energy = _tracked_sources(entry, CONF_ENERGY_ENTITY)
    tracked_power = _tracked_sources(entry, CONF_POWER_ENTITY)
    owned_helpers = _owned_helper_entities(entry, registry)
    return _Exclusions(
        entities=frozenset(house | tracked_energy | tracked_power | owned_helpers),
        supply_devices=_devices_behind(registry, supply),
        tracked_energy_devices=_devices_behind(registry, tracked_energy),
    )


def _tracked_sources(entry: ConfigEntry, source_key: str) -> set[str]:
    """Entity ids already configured as ``source_key`` on a tracked device."""
    return {
        source
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
        and (source := subentry.data.get(source_key))
    }


def _devices_behind(
    registry: er.EntityRegistry, entity_ids: set[str]
) -> frozenset[str]:
    """The HA devices the given sensors belong to, skipping those without one."""
    entities = (registry.async_get(entity_id) for entity_id in entity_ids)
    return frozenset(
        entity.device_id
        for entity in entities
        if entity is not None and entity.device_id is not None
    )


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
