from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_options_flow_records_the_cycle_opt_ins(hass: HomeAssistant) -> None:
    # Given — a configured household
    entry = _entry(hass)

    # When — the optional cycle totals are toggled
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CYCLE_WEEKLY: True,
            CONF_CYCLE_QUARTERLY: False,
            CONF_CYCLE_YEARLY: True,
        },
    )

    # Then — the choices are stored in the entry options
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CYCLE_WEEKLY] is True
    assert entry.options[CONF_CYCLE_QUARTERLY] is False
    assert entry.options[CONF_CYCLE_YEARLY] is True


async def test_options_flow_defaults_the_opt_ins_off(hass: HomeAssistant) -> None:
    # Given — a household that has never set cycle options
    entry = _entry(hass)

    # When — the options form is opened and accepted unchanged
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})

    # Then — the optional cycles are off by default (entity-count discipline)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CYCLE_WEEKLY] is False
    assert entry.options[CONF_CYCLE_QUARTERLY] is False
    assert entry.options[CONF_CYCLE_YEARLY] is False
