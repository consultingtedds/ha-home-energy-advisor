"""Serve the shipped Lovelace cards and have the frontend load them.

The bundle built from ``frontend/`` ships inside the integration, so one deploy
carries both halves and the cards can never be a different version from the
accounting they draw. This module puts it on a url keyed to the release and to
the bundle itself, and has the frontend load it two ways: as an extra module url,
and as a Lovelace resource the integration owns and keeps pointed at the current
url. Neither asks anything of the household.

Both are needed. The extra module url covers every page; the resource is what
Lovelace *waits for* before it renders a dashboard, and the dashboard strategy
needs that. A card that arrives late paints "custom element not found" and
recovers; a strategy asked for before its element exists fails the whole
dashboard.

Where an install has no frontend the cards are skipped, and where it has no
Lovelace in storage mode only the resource is: the accounting is the product, and
a headless instance still gets every sensor.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.components.lovelace.resources import ResourceStorageCollection
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
    hass.data[_CARDS_URL] = url
    module_url = f"{url}/{ENTRY_POINT}"
    if not await _async_reconcile_resource(hass, module_url):
        # Nothing to register with, so fall back to putting the module in the
        # page directly. Worse, for the reason below, but a household whose
        # dashboards are YAML files would otherwise get no cards at all.
        add_extra_js_url(hass, module_url)
    return url


async def _async_reconcile_resource(hass: HomeAssistant, module_url: str) -> bool:
    """Keep exactly one Lovelace resource, pointing at the url served now.

    Returns whether the resource is registered, so the caller knows whether the
    cards will reach the browser without help.

    A resource rather than an extra module url, and that distinction is the
    whole of HEA-114. An extra module url is placed in the page during the
    frontend's own boot, and Home Assistant replaces ``window.customElements``
    with a scoped registry part-way through that boot. A bundle loaded early
    defines its cards and strategies into the registry that is about to be
    thrown away; Home Assistant then asks the new one for the dashboard
    strategy, waits five seconds, and renders nothing. Lovelace imports its
    resources after the boot has finished, so what the module defines is what is
    later found.

    Loading it both ways does not help, which is what the first attempt at this
    assumed. A module is evaluated once per url, so the resource import of an
    already-loaded url does nothing at all.

    Reconciled rather than created: the url carries the bundle's digest, so it
    moves whenever a card changes. A resource left behind on an old url loads a
    second copy of the cards into the same page, where the two collide on
    ``customElements.define`` and whichever loses dies part-way through
    registering.

    Only urls this integration serves are considered, so a household's own
    resources are never touched.
    """
    data = hass.data.get(LOVELACE_DATA)
    if data is None or data.resource_mode != MODE_STORAGE:
        return False
    resources = data.resources
    if not isinstance(resources, ResourceStorageCollection):
        return False

    # `async_items` does not read storage; only the mutating calls do. Asking
    # for the info is the public way to be sure what is already registered
    # before deciding whether to add to it - without it a household's existing
    # resources are invisible and ours would be created a second time.
    await resources.async_get_info()
    ours = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).startswith(f"/{DOMAIN}/")
    ]
    for duplicate in ours[1:]:
        await resources.async_delete_item(duplicate["id"])
    if not ours:
        await resources.async_create_item({"res_type": "module", "url": module_url})
    elif ours[0]["url"] != module_url:
        await resources.async_update_item(ours[0]["id"], {"url": module_url})
    return True


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
