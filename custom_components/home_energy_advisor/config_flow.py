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
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DEFAULT_CURRENCY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_TITLE = "Home Energy Advisor"

_PRICE_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)
_ENERGY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
)
_POWER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="power")
)
_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Optional(CONF_ENERGY_ENTITY): _ENERGY_SELECTOR,
        vol.Optional(CONF_POWER_ENTITY): _POWER_SELECTOR,
    }
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003 - HA signature; the types are entry-independent
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Register the per-device subentry flow."""
        return {SUBENTRY_TYPE_DEVICE: DeviceSubentryFlowHandler}


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


class DeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Add one tracked device as a config subentry.

    A device is identified by exactly one source sensor: an energy counter, or a
    power sensor (whose energy is derived later via an auto-created Integral
    helper, ADR-0004). Selection is always explicit — devices are never
    auto-onboarded from a matching ``device_class`` (false friends, ADR-0004).
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the device name and its single source sensor."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = _validate_device_sources(user_input)
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=_DEVICE_SCHEMA, errors=errors
        )


def _validate_device_sources(user_input: dict[str, Any]) -> str | None:
    """Require exactly one of an energy or a power sensor."""
    has_energy = bool(user_input.get(CONF_ENERGY_ENTITY))
    has_power = bool(user_input.get(CONF_POWER_ENTITY))
    if has_energy == has_power:
        return "select_one_sensor"
    return None
