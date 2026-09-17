"""Diagnostics download for Home Energy Advisor (HEA-24).

Home Assistant discovers this platform automatically and offers the download from
the config entry's menu. The coordinator assembles the full picture - config,
per-source accumulator state and gating decision log, and the running totals - as
JSON-safe primitives, and the file names the entities and devices those figures
came from.

Naming them is the point (HEA-147). Every figure here is an answer to "which
sensor did this come from", and a report that masks the sensor cannot be acted on
without asking the household to unmask it by hand - which is what happened on
GitHub #22, where three devices were named as condemned and no one could say
which sensor each one was. Home Assistant's own integrations carry entity ids in
their diagnostics for the same reason; what they redact is credentials, and there
are none here.

The file is generated on request and downloaded by the household, who decides
whether to attach it anywhere. That decision is theirs to make, and it needs a
file that says something.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from homeassistant.core import HomeAssistant

    from .coordinator import HeaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001 - platform signature; state is on the entry
    entry: HeaConfigEntry,
) -> dict[str, Any]:
    """Return the diagnostics for a config entry."""
    return entry.runtime_data.diagnostics()
