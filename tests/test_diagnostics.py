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
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.coarse_step_energy",
                },
                unique_id=None,
            )
        ],
    )


async def test_diagnostics_redacts_entity_ids_and_device_names(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a configured, running home
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the price and per-source entity ids are redacted, but the non-personal
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


async def test_diagnostics_expose_the_battery_ledger(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a configured, running home
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the stored-cost ledger is in it. Discharge is priced from these two
    # figures and nothing else, so a household given a discharge costed below the
    # import rate can otherwise only infer why (HEA-112).
    assert result["battery"] == {"stored_kwh": "0", "stored_cost": "0"}

    # ...and it carries no entity id or device name, so nothing here needs
    # redacting on a public bug report
    assert set(result["battery"]) == {"stored_kwh", "stored_cost"}


async def test_diagnostics_say_why_the_previous_accounting_was_not_carried(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a first run on a household that has never written a snapshot
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - it records that the run began cold and why. A restart that silently
    # drops the battery ledger changes what discharge costs, so the download has
    # to explain the change rather than leave the figures unaccountable.
    assert result["snapshot"] == {"status": "absent", "age_seconds": None}
