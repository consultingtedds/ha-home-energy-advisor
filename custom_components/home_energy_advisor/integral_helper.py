"""Native Integral (Riemann-sum) helpers for power-only devices (HEA-34).

Power-only devices carry no energy counter, so ADR-0004 supports them by
auto-creating a native ``integration`` helper on the selected power sensor rather
than reimplementing W->kWh integration in the engine. The helper's output energy
sensor then feeds the same ``CumulativeEnergySource`` pipeline as any metered
device.

Two deliberate choices keep this thin:

* **Units are the helper's job.** We create with ``unit_time = HOURS`` and no
  unit prefix, so a watt source yields watt-hours and a kilowatt source yields
  kilowatt-hours. The coordinator already normalises Wh to kWh at the source
  boundary, so no unit maths lives here.
* **Sparse-but-steady reporting is bridged, outages are not.** ``trapezoidal``
  with a one-minute ``max_sub_interval`` keeps energy advancing while a light
  holds a steady wattage without pushing updates, yet the native helper stops
  integrating the moment the source is ``unavailable``/``unknown`` and resumes
  cleanly on recovery — the reset-on-unavailable behaviour ADR-0004 requires,
  inherited rather than rebuilt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.integration.const import (
    CONF_MAX_SUB_INTERVAL,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_TIME,
    METHOD_TRAPEZOIDAL,
)
from homeassistant.components.integration.const import (
    DOMAIN as INTEGRATION_DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_METHOD, CONF_NAME, UnitOfTime
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENERGY_ENTITY,
    CONF_INTEGRAL_HELPERS,
    CONF_POWER_ENTITY,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# One minute matches the coordinator's finalisation cadence: fine enough to track
# a steady load that stops reporting, coarse enough not to flood the recorder.
_MAX_SUB_INTERVAL = {"minutes": 1}


async def async_ensure_integral_helper(
    hass: HomeAssistant, *, name: str, source_entity: str
) -> str:
    """Create a native Integral helper over ``source_entity``; return its entry_id.

    Idempotent: config-entry setup runs on every reload, so an existing helper
    over the same source is reused rather than duplicated. Drives the
    ``integration`` component's own config flow, so the helper is a first-class
    Home Assistant entity the user can see and Home Assistant owns.
    """
    if (existing := _integral_helper_for_source(hass, source_entity)) is not None:
        return existing
    result = await hass.config_entries.flow.async_init(
        INTEGRATION_DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_NAME: name,
            CONF_SOURCE_SENSOR: source_entity,
            CONF_METHOD: METHOD_TRAPEZOIDAL,
            CONF_UNIT_TIME: UnitOfTime.HOURS,
            CONF_MAX_SUB_INTERVAL: _MAX_SUB_INTERVAL,
        },
    )
    return result["result"].entry_id


async def async_sync_power_device_helpers(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, str]:
    """Reconcile Integral helpers to the current power-only devices; wire outputs.

    Called on every setup (including the reload that a device removal triggers):
    creates a helper for each power-only device, removes helpers whose device is
    gone, remembers which helper belongs to which device, and returns
    ``{subentry_id: output_sensor_entity_id}`` for the coordinator to wire.
    Energy-metered devices are absent — the coordinator wires those directly.
    """
    power_devices = _power_only_devices(entry)
    owned = dict(entry.data.get(CONF_INTEGRAL_HELPERS, {}))
    await _remove_orphaned_helpers(hass, owned, keep=power_devices.keys())
    energy_entities = await _ensure_helpers(hass, entry, power_devices, owned)
    _persist_owned_helpers(hass, entry, owned)
    return energy_entities


def _power_only_devices(entry: ConfigEntry) -> dict[str, str]:
    """Map ``{subentry_id: power_entity}`` for devices tracked by a power sensor."""
    return {
        subentry_id: subentry.data[CONF_POWER_ENTITY]
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
        and subentry.data.get(CONF_POWER_ENTITY)
        and not subentry.data.get(CONF_ENERGY_ENTITY)
    }


async def _remove_orphaned_helpers(
    hass: HomeAssistant, owned: dict[str, str], *, keep: Iterable[str]
) -> None:
    """Remove the helpers of devices that no longer exist, mutating ``owned``."""
    live = set(keep)
    for subentry_id, helper_id in list(owned.items()):
        if subentry_id not in live:
            if hass.config_entries.async_get_entry(helper_id) is not None:
                await hass.config_entries.async_remove(helper_id)
            del owned[subentry_id]


async def _ensure_helpers(
    hass: HomeAssistant,
    entry: ConfigEntry,
    power_devices: dict[str, str],
    owned: dict[str, str],
) -> dict[str, str]:
    """Ensure a helper per power-only device; map ``{subentry_id: energy sensor}``."""
    energy_entities: dict[str, str] = {}
    for subentry_id, power_entity in power_devices.items():
        # Name the helper after the device itself: the title is the user's own
        # (already localised) name, so no hardcoded, untranslated word is coined
        # for it here — i18n stays honest without a translation lookup.
        name = entry.subentries[subentry_id].title
        helper_id = await async_ensure_integral_helper(
            hass, name=name, source_entity=power_entity
        )
        owned[subentry_id] = helper_id
        if (output := integral_output_sensor(hass, helper_id)) is not None:
            energy_entities[subentry_id] = output
    return energy_entities


def _persist_owned_helpers(
    hass: HomeAssistant, entry: ConfigEntry, owned: dict[str, str]
) -> None:
    """Store the device->helper map on the entry, if it changed."""
    if owned != entry.data.get(CONF_INTEGRAL_HELPERS, {}):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_INTEGRAL_HELPERS: owned}
        )


def integral_output_sensor(hass: HomeAssistant, entry_id: str) -> str | None:
    """Return the energy sensor the Integral helper ``entry_id`` publishes."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry_id)
    return entries[0].entity_id if entries else None


def _integral_helper_for_source(hass: HomeAssistant, source_entity: str) -> str | None:
    """Return the entry_id of an existing Integral helper over ``source_entity``."""
    for entry in hass.config_entries.async_entries(INTEGRATION_DOMAIN):
        if entry.options.get(CONF_SOURCE_SENSOR) == source_entity:
            return entry.entry_id
    return None
