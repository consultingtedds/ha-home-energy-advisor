"""Config flow for Home Energy Advisor — the global house-level setup.

Collects the house-level energy inputs (ADR-0002): the import price and currency,
grid import, and the optional solar and battery sources. Source entities are
pre-filled from the Energy Dashboard configuration where the household has set it
up, on a best-effort basis — prefill never blocks the flow. Per-device tracking
is added afterwards as config subentries, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.energy.data import async_get_manager
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DEFAULT_CURRENCY,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_TITLE = "Home Energy Advisor"

_PRICE_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)
_ENERGY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
)


class HomeEnergyAdvisorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the one-time, house-level configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the house-level inputs and create the single config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title=_TITLE, data=user_input)

        defaults = await _energy_prefs_defaults(self.hass)
        return self.async_show_form(step_id="user", data_schema=_build_schema(defaults))


def _build_schema(defaults: dict[str, str]) -> vol.Schema:
    def source(key: str, *, required: bool) -> vol.Marker:
        marker = vol.Required if required else vol.Optional
        if key in defaults:
            return marker(key, description={"suggested_value": defaults[key]})
        return marker(key)

    return vol.Schema(
        {
            vol.Required(CONF_PRICE_ENTITY): _PRICE_SELECTOR,
            vol.Required(
                CONF_CURRENCY, default=DEFAULT_CURRENCY
            ): selector.TextSelector(),
            source(CONF_GRID_IMPORT_ENTITY, required=True): _ENERGY_SELECTOR,
            source(CONF_SOLAR_ENTITY, required=False): _ENERGY_SELECTOR,
            source(CONF_BATTERY_CHARGE_ENTITY, required=False): _ENERGY_SELECTOR,
            source(CONF_BATTERY_DISCHARGE_ENTITY, required=False): _ENERGY_SELECTOR,
            source(CONF_HOUSE_CONSUMPTION_ENTITY, required=False): _ENERGY_SELECTOR,
        }
    )


async def _energy_prefs_defaults(hass: HomeAssistant) -> dict[str, str]:
    """Best-effort source defaults from the Energy Dashboard; empty if unset."""
    defaults: dict[str, str] = {}
    try:
        manager = await async_get_manager(hass)
        data: Any = manager.data or {}
        for entry in data.get("energy_sources", []):
            kind = entry.get("type")
            if kind == "grid" and (flows := entry.get("flow_from")):
                defaults[CONF_GRID_IMPORT_ENTITY] = flows[0]["stat_energy_from"]
            elif kind == "solar" and (stat := entry.get("stat_energy_from")):
                defaults[CONF_SOLAR_ENTITY] = stat
            elif kind == "battery":
                if charge := entry.get("stat_energy_to"):
                    defaults[CONF_BATTERY_CHARGE_ENTITY] = charge
                if discharge := entry.get("stat_energy_from"):
                    defaults[CONF_BATTERY_DISCHARGE_ENTITY] = discharge
    except Exception:  # noqa: BLE001 - prefill is optional; it must never block setup
        return {}
    return defaults
