"""Deleting a tracked device from its own device page (HEA-56).

Home Assistant only offers a Delete action on a device page when the integration
implements ``async_remove_config_entry_device``. The config *subentry* is
authoritative, so a deletion only sticks if the subentry goes with it —
otherwise the sensor platform rebuilds the device from ``entry.subentries`` on
the next reload and it silently reappears.

The aggregate devices — Untracked, whole home, and the hub — have no subentry
behind them, so there is nothing to delete and their removal must be refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor import async_remove_config_entry_device
from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
    WHOLE_HOME_KEY,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


async def _household(hass: HomeAssistant) -> MockConfigEntry:
    """A set-up household tracking one device."""
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Guest Bedroom Aircon",
                data={
                    CONF_NAME: "Guest Bedroom Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_energy",
                },
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _device(hass: HomeAssistant, identifier: str) -> DeviceEntry:
    """The HEA device registered under ``identifier``."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, identifier)})
    assert device is not None
    return device


async def test_deleting_a_tracked_device_removes_its_subentry(
    hass: HomeAssistant,
) -> None:
    """Test the deletion sticks, rather than the device returning on reload."""
    # Given — a household tracking one device
    entry = await _household(hass)
    subentry_id = next(iter(entry.subentries))
    device = _device(hass, f"{entry.entry_id}_{subentry_id}")

    # When — that device is deleted from its device page
    assert await async_remove_config_entry_device(hass, entry, device)
    await hass.async_block_till_done()

    # Then — its subentry is gone, so nothing rebuilds it
    assert subentry_id not in entry.subentries


@pytest.mark.parametrize(
    "suffix",
    [
        pytest.param("_untracked", id="untracked"),
        pytest.param(f"_{WHOLE_HOME_KEY}", id="whole_home"),
        pytest.param("", id="hub"),
    ],
)
async def test_an_aggregate_device_cannot_be_deleted(
    hass: HomeAssistant, suffix: str
) -> None:
    """Test the aggregates are refused — they are derived, not configured."""
    # Given — a set-up household
    entry = await _household(hass)
    device = _device(hass, f"{entry.entry_id}{suffix}")

    # When / Then — Home Assistant is told the device may not be removed
    assert not await async_remove_config_entry_device(hass, entry, device)
    assert len(entry.subentries) == 1
