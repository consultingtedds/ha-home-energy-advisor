"""Diagnostics download for Home Energy Advisor (HEA-24).

Home Assistant discovers this platform automatically and offers the download from
the config entry's menu. The coordinator assembles the full picture — config,
per-source accumulator state and gating decision log, and the running totals — as
JSON-safe primitives; this module only redacts the parts that could identify a
household before the file is shared.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.diagnostics import async_redact_data

if TYPE_CHECKING:
    from typing import Any

    from homeassistant.core import HomeAssistant

    from .coordinator import HeaConfigEntry

# Entity ids and user-chosen device names can encode room or person names, and a
# diagnostics download is routinely pasted into public issues. Roles, cycle flags,
# decision reasons and the random subentry ids are not personal and stay visible
# so the file still explains any figure.
TO_REDACT = {"entity", "entity_id", "device", "name", "price_entity"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001 - platform signature; state is on the entry
    entry: HeaConfigEntry,
) -> dict[str, Any]:
    """Return the redacted diagnostics for a config entry."""
    return async_redact_data(entry.runtime_data.diagnostics(), TO_REDACT)
