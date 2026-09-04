"""Serving the Lovelace cards from the integration.

The ``frontend`` fixture stands up Home Assistant's real frontend component,
which every install has but the test harness does not boot by default. Tests
that omit it are exercising the headless path deliberately.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.cards import (
    CARDS_DIR,
    ENTRY_POINT,
    async_cards_url,
    async_register_cards,
    fingerprint,
)
from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


@pytest.fixture
async def frontend(hass: HomeAssistant) -> None:
    """A Home Assistant with its frontend up, as every real install has."""
    assert await async_setup_component(hass, "frontend", {})


async def _household(hass: HomeAssistant) -> MockConfigEntry:
    """A set-up household, tracking nothing - the cards do not depend on it."""
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("frontend")
async def test_setting_up_serves_the_cards_and_asks_the_frontend_to_load_them(
    hass: HomeAssistant,
) -> None:
    # Given / When - a household sets the integration up, doing nothing else
    await _household(hass)

    # Then - the browser is told to load the one module every card imports from,
    # so no Lovelace resource has to be added by hand
    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert any(url.endswith(f"/{ENTRY_POINT}") for url in urls)


@pytest.mark.usefixtures("frontend")
async def test_the_url_carries_the_release_so_an_upgrade_refetches_the_set(
    hass: HomeAssistant,
) -> None:
    # Given - a set-up household
    await _household(hass)

    # When - we read the url the cards are served from
    url = async_cards_url(hass)

    # Then - the release is *in the path*, not a query string: the cards are ES
    # modules and a relative import does not inherit a query string, so only a
    # moving folder re-fetches the imports along with the entry point
    assert url is not None
    assert "?" not in url
    # The release, so an upgrade always moves it, and a digest of the sources,
    # so a build between two releases moves it too
    assert url.endswith(f"/0.0.1-{fingerprint(CARDS_DIR)}")


def test_the_url_moves_when_a_card_changes_under_an_unchanged_version(
    tmp_path: Path,
) -> None:
    # Given - the same release, twice, with one card edited in between. This is
    # every deploy that is not a release: the manifest version does not move
    # between them
    (tmp_path / "hea-cards.js").write_text('import "./hea-totals-card.js";')
    before = fingerprint(tmp_path)
    (tmp_path / "hea-cards.js").write_text('import "./hea-totals-card.js";\n')

    # When / Then - a version alone would leave every browser that had already
    # loaded the cards serving them from a 31-day cache, whatever was deployed
    assert fingerprint(tmp_path) != before


def test_the_url_holds_still_when_a_deploy_only_copies_the_same_cards(
    tmp_path: Path,
) -> None:
    # Given - two copies of identical sources with different timestamps, which
    # is what copying a directory onto a share produces for every file in it
    first, second = tmp_path / "a", tmp_path / "b"
    for directory, mtime in ((first, 1_600_000_000), (second, 1_700_000_000)):
        directory.mkdir()
        card = directory / "hea-cards.js"
        card.write_text('import "./hea-totals-card.js";')
        os.utime(card, (mtime, mtime))

    # When / Then - reading timestamps would move the url on every deploy and
    # throw away a cache that was still good, for all 25 files at once
    assert fingerprint(first) == fingerprint(second)


def test_the_fingerprint_ignores_the_card_tests_shipped_beside_them(
    tmp_path: Path,
) -> None:
    # Given - a card, and the test directory that ships in the same folder
    (tmp_path / "hea-cards.js").write_text('import "./hea-totals-card.js";')
    before = fingerprint(tmp_path)
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "hea-cards.test.js").write_text("it('...', () => {});")

    # When / Then - a browser never fetches those, so editing one must not
    # invalidate a cache for every household
    assert fingerprint(tmp_path) == before


@pytest.mark.usefixtures("frontend")
async def test_reloading_registers_the_static_path_only_once(
    hass: HomeAssistant,
) -> None:
    # Given - a household whose entry reloads on every configuration change
    entry = await _household(hass)
    before = async_cards_url(hass)

    # When - the entry reloads, as it does whenever a device is added or edited
    with patch.object(
        hass.http,
        "async_register_static_paths",
        wraps=hass.http.async_register_static_paths,
    ) as register:
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    # Then - the path is not offered to aiohttp a second time, and the url the
    # browser was given still points at the same folder
    assert register.call_count == 0
    assert async_cards_url(hass) == before


async def test_a_home_assistant_without_a_frontend_still_sets_up(
    hass: HomeAssistant,
) -> None:
    # Given - a headless install: `default_config` omitted, so no frontend at all
    assert "frontend" not in hass.config.components

    # When - the integration sets up anyway, because the accounting does not need
    # a browser and refusing to run would be the wrong trade
    entry = await _household(hass)

    # Then - it is loaded, and simply has no cards to offer
    assert entry.state is entry.state.LOADED
    assert async_cards_url(hass) is None


async def test_registering_without_a_frontend_is_a_no_op(hass: HomeAssistant) -> None:
    # Given - no frontend component
    assert "frontend" not in hass.config.components

    # When / Then - asking directly is safe rather than an AttributeError on the
    # frontend's own hass.data key, which is what a bare call would hit
    assert await async_register_cards(hass) is None
