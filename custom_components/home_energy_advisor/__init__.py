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

from .coordinator import HeaCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import HeaConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Set up Home Energy Advisor: build the coordinator and start accounting."""
    coordinator = HeaCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Unload the config entry and its platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
