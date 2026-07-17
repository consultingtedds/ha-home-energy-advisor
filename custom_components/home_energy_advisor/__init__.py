"""Home Energy Advisor — per-device financial accounting for Home Assistant.

Home Assistant's Energy Dashboard explains energy flows; this integration
explains money: what each tracked device actually cost to run, what it would
have cost without local generation, and what solar saved.

This package is the thin Home Assistant adapter layer. The accounting engine
lives in ``engine/`` and imports nothing from ``homeassistant``, so the
financial model can be unit-tested without a running instance.

The config entry holds the global house-level configuration; tracked devices
arrive as config subentries. No entity platforms are wired up yet — ``PLATFORMS``
is empty until the sensor layer (HEA-22) adds ``Platform.SENSOR``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Energy Advisor from its config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and its platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
