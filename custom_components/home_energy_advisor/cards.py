"""Serve the shipped Lovelace cards and have the frontend load them.

The bundle built from ``frontend/`` ships inside the integration, so one deploy
carries both halves and the cards can never be a different version from the
accounting they draw. This module puts it on a url keyed to the release and to
the bundle itself, and registers that url as an extra frontend module, which is
what removes any need for a hand-managed Lovelace resource. Where an install has
no frontend the cards are skipped: the accounting is the product, and a headless
instance still gets every sensor.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CARDS_DIR = Path(__file__).parent / "frontend"

#: Every card registers itself when this module is imported, so one url covers
#: the family and a card added later needs no dashboard change.
ENTRY_POINT = "hea-cards.js"

_CARDS_URL: HassKey[str] = HassKey(f"{DOMAIN}_cards_url")


async def async_register_cards(hass: HomeAssistant) -> str | None:
    """Serve the cards under a versioned url and have the frontend load them.

    Returns the url, or ``None`` where there is no frontend to serve them to.
    Safe to call on every setup: a second call returns what the first
    established, because aiohttp's router only grows and the config entry
    reloads on every configuration change.
    """
    if (existing := async_cards_url(hass)) is not None:
        return existing
    if "frontend" not in hass.config.components:
        return None
    url = f"/{DOMAIN}/{await _async_cache_key(hass)}"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url, str(CARDS_DIR), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{url}/{ENTRY_POINT}")
    hass.data[_CARDS_URL] = url
    return url


def async_cards_url(hass: HomeAssistant) -> str | None:
    """Where the cards are served from, or ``None`` if they are not."""
    return hass.data.get(_CARDS_URL)


def fingerprint(directory: Path) -> str:
    """A short digest of what is served from ``directory``.

    Content, not timestamps. A deploy copies the bundle, which resets its mtime,
    so reading timestamps would move the url on every deploy and discard a cache
    that was still good.
    """
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.js")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


async def _async_cache_key(hass: HomeAssistant) -> str:
    """The path segment the cards are served under.

    In the *path* rather than a query string, so the whole thing re-fetches at
    once. The release alone is not enough to move it: every build between two
    releases carries the same version, so a household - or a maintainer
    redeploying - would keep being served a month-old cached copy of whatever
    changed.
    """
    integration = await async_get_integration(hass, DOMAIN)
    digest = await hass.async_add_executor_job(fingerprint, CARDS_DIR)
    return f"{integration.version}-{digest}"
