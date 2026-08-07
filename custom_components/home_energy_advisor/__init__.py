"""Home Energy Advisor — per-device financial accounting for Home Assistant.

Home Assistant's Energy Dashboard explains energy flows; this integration
explains money: what each tracked device actually cost to run, what it would
have cost at grid prices, and what the difference saved.

This package is the thin Home Assistant adapter layer. The accounting engine
lives in ``engine/`` and imports nothing from ``homeassistant``, so the
financial model can be unit-tested without a running instance.

The config entry holds the global house-level configuration; tracked devices
arrive as config subentries. The sensor platform (HEA-22) publishes the four
per-device figures plus the Untracked remainder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from . import reset
from .const import (
    CONF_CYCLE_METERS,
    CONF_GENERATION_ENTITY,
    CONF_INTEGRAL_HELPERS,
    DOMAIN,
)
from .coordinator import HeaCoordinator
from .cycle_meter import async_sync_cycle_meters
from .helper_ownership import helper_entry_id, helper_was_created
from .integral_helper import async_sync_power_device_helpers

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

    from .coordinator import HeaConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]

# The pre-ADR-0011 key for the local-generation input, as it still sits in an
# installed household's .storage. Only the migration below knows this name.
_LEGACY_GENERATION_KEY = "solar_entity"


async def async_setup_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Set up Home Energy Advisor: build the coordinator and start accounting."""
    # Registered here rather than in async_setup: the reset action needs a loaded
    # entry to act on, and re-registering the same handler is a no-op (HEA-57).
    reset.async_register(hass)
    power_energy_entities = await async_sync_power_device_helpers(hass, entry)
    coordinator = HeaCoordinator(
        hass, entry, power_energy_entities=power_energy_entities
    )
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # After the sensors exist, reconcile the utility_meter cycle totals over them
    # (daily/monthly + opt-in longer cycles), creating and cleaning up as needed.
    await async_sync_cycle_meters(hass, entry)
    # Reload on any config change so adding, editing or removing a device takes
    # effect live — and so a removed device's auto-created helpers (Integral and
    # cycle meters) are reconciled away on the next setup (HEA-34, HEA-23).
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Bring an older config entry up to the current schema (ADR-0011).

    Version 1 stored the local-generation input under ``solar_entity``. ADR-0009
    renamed the concept but kept the key; ADR-0011 revises that, so the key moves
    to ``generation_entity``. Nothing else about the entry changes.

    This exists for installations that predate the rename. It can go once none
    remain — pre-release, that is a single household.
    """
    if entry.version == 1:
        data = {**entry.data}
        if (generation := data.pop(_LEGACY_GENERATION_KEY, None)) is not None:
            data[CONF_GENERATION_ENTITY] = generation
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Unload the config entry and its platforms.

    Flushes the coordinator's in-flight accounting first, while the sensors still
    exist, so they bank up to ~20 min of otherwise-discarded buckets into their
    restore baseline before teardown — otherwise every restart and every
    options/config change silently drops them (HEA-53).
    """
    coordinator = entry.runtime_data
    if coordinator is not None:
        coordinator.async_flush()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Clean up the native helpers this integration auto-created (HEA-42).

    The Integral (power-only devices) and utility_meter (cycle totals) helpers are
    independent config entries owned via the entry's data. Reconciliation only
    prunes them when a *device* is removed, so without this hook they would be
    orphaned when the whole integration is deleted — leaving no clean uninstall.

    Only helpers HEA created are removed: a helper the user already had over a
    source (adopted) is theirs to keep, never deleted on uninstall (HEA-52).
    """
    owned = (
        *entry.data.get(CONF_INTEGRAL_HELPERS, {}).values(),
        *entry.data.get(CONF_CYCLE_METERS, {}).values(),
    )
    for record in owned:
        if not helper_was_created(record):
            continue
        helper_id = helper_entry_id(record)
        if hass.config_entries.async_get_entry(helper_id) is not None:
            await hass.config_entries.async_remove(helper_id)


def _tracked_subentry_id(entry: HeaConfigEntry, device: DeviceEntry) -> str | None:
    """The subentry a HEA device page belongs to, or None if it is an aggregate.

    Membership of ``entry.subentries`` is the whole test. The hub carries the
    bare entry id and the Untracked and whole-home devices carry suffixes that
    are not subentry ids, so all three fall out without a list of exclusions to
    keep in step with the sensor platform.
    """
    prefix = f"{entry.entry_id}_"
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and (sub := identifier.removeprefix(prefix)) in (
            entry.subentries
        ):
            return sub
    return None


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: HeaConfigEntry, device: DeviceEntry
) -> bool:
    """Let a tracked device be deleted from its own device page (HEA-56).

    Removing the device alone would not stick: the subentry is authoritative, so
    the sensor platform would rebuild the device on the next reload. Removing the
    subentry is what makes the deletion real — and Home Assistant's own
    ``async_remove_subentry`` clears the device registry for it, while the update
    listener below reloads the entry and reconciles the auto-created Integral and
    cycle-meter helpers away (HEA-34, HEA-23).

    The aggregates are refused: Untracked and whole home are derived figures and
    the hub is the integration itself, so none of them is a user's to delete.
    """
    if (subentry_id := _tracked_subentry_id(entry, device)) is None:
        return False
    hass.config_entries.async_remove_subentry(entry, subentry_id)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Reload the entry when its configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)
