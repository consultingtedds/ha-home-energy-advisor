from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.diagnostics import (
    async_get_config_entry_diagnostics,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
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


async def test_diagnostics_redacts_entity_ids_and_device_names(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a configured, running home
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then — the price and per-source entity ids are redacted, but the non-personal
    # role labels that make the file useful survive
    assert result["config"]["price_entity"] == REDACTED
    grid = next(
        source
        for source in result["config"]["house_sources"]
        if source["role"] == "grid_import"
    )
    assert grid["entity"] == REDACTED

    # ...and each observed source keeps its decision log while its entity id and
    # the user-chosen device name are masked
    source = next(item for item in result["sources"] if item["device_id"] is not None)
    assert source["entity_id"] == REDACTED
    assert source["device"] == REDACTED
    assert source["role"] is None
    assert "decisions" in source
