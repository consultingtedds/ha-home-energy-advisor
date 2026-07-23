"""Config flow for Home Energy Advisor — the global house-level setup.

Collects the house-level energy inputs (ADR-0002): the import price and currency,
grid import, and the optional solar and battery sources. Source entities are
pre-filled from the Energy Dashboard configuration where the household has set it
up, on a best-effort basis — prefill never blocks the flow. Per-device tracking
is added afterwards as config subentries, not here.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.energy.data import async_get_manager
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DEFAULT_CURRENCY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from .discovery import async_discover_candidates

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .discovery import DeviceCandidate

_TITLE = "Home Energy Advisor"
# Options-flow-internal key for the multi-select of discovered devices to add.
_CONF_DISCOVERED = "discovered_devices"

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the house-level configuration in place, without reinstalling."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _build_schema({}), entry.data
            ),
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003 - HA signature; the types are entry-independent
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Register the per-device subentry flow."""
        return {SUBENTRY_TYPE_DEVICE: DeviceSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,  # noqa: ARG004 - HA signature; the entry is read via self
    ) -> HomeEnergyAdvisorOptionsFlow:
        """Provide the options flow for the global cycle opt-ins."""
        return HomeEnergyAdvisorOptionsFlow()


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
            source(CONF_GRID_EXPORT_ENTITY, required=False): _ENERGY_SELECTOR,
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
        for source in data.get("energy_sources", []):
            _collect_prefs_source(source, defaults)
    except Exception:  # noqa: BLE001 - prefill is optional; it must never block setup
        return {}
    return defaults


def _collect_prefs_source(
    source: Any,  # noqa: ANN401 - untyped Energy Dashboard preference structure
    defaults: dict[str, str],
) -> None:
    """Map one Energy Dashboard source onto the matching config defaults."""
    kind = source.get("type")
    if kind == "grid":
        if imports := source.get("flow_from"):
            defaults[CONF_GRID_IMPORT_ENTITY] = imports[0]["stat_energy_from"]
        if exports := source.get("flow_to"):
            defaults[CONF_GRID_EXPORT_ENTITY] = exports[0]["stat_energy_to"]
    elif kind == "solar" and (stat := source.get("stat_energy_from")):
        defaults[CONF_SOLAR_ENTITY] = stat
    elif kind == "battery":
        if charge := source.get("stat_energy_to"):
            defaults[CONF_BATTERY_CHARGE_ENTITY] = charge
        if discharge := source.get("stat_energy_from"):
            defaults[CONF_BATTERY_DISCHARGE_ENTITY] = discharge


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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing device's name or source sensor."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = _validate_device_sources(user_input)
            if error is None:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _DEVICE_SCHEMA, subentry.data
            ),
            errors=errors,
        )


def _validate_device_sources(user_input: dict[str, Any]) -> str | None:
    """Require exactly one of an energy or a power sensor."""
    has_energy = bool(user_input.get(CONF_ENERGY_ENTITY))
    has_power = bool(user_input.get(CONF_POWER_ENTITY))
    if has_energy == has_power:
        return "select_one_sensor"
    return None


class HomeEnergyAdvisorOptionsFlow(OptionsFlow):
    """Options: the cycle-total opt-ins and the guided device-discovery step.

    Daily and monthly cycle totals are always created; the longer cycles are
    opt-in to keep the entity count in check across many devices (ADR-0004).
    Discovery (HEA-45) offers untracked energy/power sensors to add as devices —
    it only suggests; the user picks. Both are re-runnable from Configure.
    """

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA menu step signature
    ) -> ConfigFlowResult:
        """Offer the two options branches."""
        return self.async_show_menu(
            step_id="init", menu_options=["cycles", "discover_devices"]
        )

    async def async_step_cycles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the cycle opt-ins."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    key, default=options.get(key, False)
                ): selector.BooleanSelector()
                for key in (CONF_CYCLE_WEEKLY, CONF_CYCLE_QUARTERLY, CONF_CYCLE_YEARLY)
            }
        )
        return self.async_show_form(step_id="cycles", data_schema=schema)

    async def async_step_discover_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer untracked energy/power sensors; add the ones the user selects."""
        candidates = async_discover_candidates(self.hass, self.config_entry)
        if user_input is not None:
            self._add_devices(candidates, user_input.get(_CONF_DISCOVERED, []))
            return self.async_create_entry(data=dict(self.config_entry.options))
        if not candidates:
            return self.async_abort(reason="no_candidates")
        return self.async_show_form(
            step_id="discover_devices", data_schema=_discovery_schema(candidates)
        )

    def _add_devices(
        self, candidates: list[DeviceCandidate], selected: list[str]
    ) -> None:
        """Create a device subentry for each selected candidate."""
        by_entity = {candidate.entity_id: candidate for candidate in candidates}
        for entity_id in selected:
            candidate = by_entity.get(entity_id)
            if candidate is None:
                continue
            self.hass.config_entries.async_add_subentry(
                self.config_entry,
                ConfigSubentry(
                    data=MappingProxyType(
                        {CONF_NAME: candidate.name, candidate.source_key: entity_id}
                    ),
                    subentry_type=SUBENTRY_TYPE_DEVICE,
                    title=candidate.name,
                    unique_id=None,
                ),
            )


def _discovery_schema(candidates: list[DeviceCandidate]) -> vol.Schema:
    options = [
        selector.SelectOptionDict(
            value=candidate.entity_id, label=_candidate_label(candidate)
        )
        for candidate in candidates
    ]
    return vol.Schema(
        {
            vol.Optional(_CONF_DISCOVERED, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def _candidate_label(candidate: DeviceCandidate) -> str:
    label = f"{candidate.name} ({candidate.entity_id})"
    return f"{label} — may not be a device" if candidate.likely_false_friend else label
