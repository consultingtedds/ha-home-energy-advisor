"""Home Energy Advisor — per-device financial accounting for Home Assistant.

Home Assistant's Energy Dashboard explains energy flows; this integration
explains money: what each tracked device actually cost to run, what it would
have cost without local generation, and what solar saved.

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

from .const import CONF_CYCLE_METERS, CONF_INTEGRAL_HELPERS
from .coordinator import HeaCoordinator
from .cycle_meter import async_sync_cycle_meters
from .integral_helper import async_sync_power_device_helpers

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import HeaConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Set up Home Energy Advisor: build the coordinator and start accounting."""
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


async def async_unload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Unload the config entry and its platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Clean up the native helpers this integration auto-created (HEA-42).

    The Integral (power-only devices) and utility_meter (cycle totals) helpers are
    independent config entries owned via the entry's data. Reconciliation only
    prunes them when a *device* is removed, so without this hook they would be
    orphaned when the whole integration is deleted — leaving no clean uninstall.
    """
    owned = (
        *entry.data.get(CONF_INTEGRAL_HELPERS, {}).values(),
        *entry.data.get(CONF_CYCLE_METERS, {}).values(),
    )
    for helper_id in owned:
        if hass.config_entries.async_get_entry(helper_id) is not None:
            await hass.config_entries.async_remove(helper_id)


async def _async_reload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Reload the entry when its configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)
