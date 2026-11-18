"""The integration's ``common`` strings, translated, for wording built in code.

A plan's review and a Repair's explanation are assembled from what was entered
or recorded, so their wording cannot live in a step's own strings and is looked
up here instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import translation

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_common_strings(hass: HomeAssistant) -> dict[str, str]:
    """The integration's ``common`` strings, translated, keyed by name."""
    strings = await translation.async_get_translations(
        hass, hass.config.language, "common", {DOMAIN}
    )
    prefix = f"component.{DOMAIN}.common."
    return {
        key.removeprefix(prefix): value
        for key, value in strings.items()
        if key.startswith(prefix)
    }
