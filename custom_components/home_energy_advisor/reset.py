"""Rebasing a household's accumulated totals to zero (HEA-57).

A figure this integration publishes is a restored baseline plus the runtime's
since-startup total, and Home Assistant keeps both that baseline and the
long-term statistics keyed by entity id. Deleting and re-adding the integration
therefore does not clear anything — a fresh add re-adopts the old values. Short
of filesystem surgery on a running instance, there was no way out; this module
is the supported one.

Three things have to happen together, in this order:

1. the runtime's running totals and the sensors' restore baselines go to zero,
2. the cycle meters HEA created are calibrated to zero — after step 1, never
   before, because a net-consumption meter subtracts its source's drop,
3. HEA's own long-term statistics are cleared, so the cleared figures are not
   contradicted by the history behind them.

Everything here is scoped to one config entry and to entities this integration
owns. A helper the user built themselves is never touched, and the recorder is
never asked for anything broader than HEA's own statistic ids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import get_instance

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_CYCLE_METERS,
    DOMAIN,
    SERVICE_RESET_TOTALS,
)
from .cycle_meter import async_reset_cycle_meters, utility_meter_output_sensor
from .helper_ownership import helper_entry_id, helper_was_created

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import HeaConfigEntry

_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string})


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the reset action, once for the integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_TOTALS, _async_handle_reset, schema=_SCHEMA
    )


async def _async_handle_reset(call: ServiceCall) -> None:
    """Rebase the household named by the call."""
    entry = _target_entry(call)
    await async_reset_totals(call.hass, entry)


def _target_entry(call: ServiceCall) -> HeaConfigEntry:
    """The loaded HEA config entry the call names, or a translated refusal."""
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = call.hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="reset_unknown_entry",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="reset_entry_not_loaded"
        )
    return entry


async def async_reset_totals(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Rebase one household: sensors, its own cycle meters, and its statistics."""
    statistic_ids = _owned_statistic_ids(hass, entry)
    entry.runtime_data.async_reset_totals()
    await async_reset_cycle_meters(hass, entry)
    get_instance(hass).async_clear_statistics(statistic_ids)


def _owned_statistic_ids(hass: HomeAssistant, entry: HeaConfigEntry) -> list[str]:
    """Statistic ids for HEA's own sensors plus the cycle meters it created.

    A sensor's statistic id is its entity id. Adopted meters are excluded along
    with everything else outside this integration: clearing statistics is
    destructive and permanent, so the list is built from what HEA owns rather
    than from anything broader.
    """
    registry = er.async_get(hass)
    own = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == "sensor"
    ]
    metered = [
        output
        for record in entry.data.get(CONF_CYCLE_METERS, {}).values()
        if helper_was_created(record)
        and (output := utility_meter_output_sensor(hass, helper_entry_id(record)))
        is not None
    ]
    return [*own, *metered]
