"""Config flow for Home Energy Advisor - the global house-level setup.

Collects the house-level energy inputs (ADR-0002): the currency, the optional
local generation and house consumption, and then the grid meters and batteries,
each an entry of its own (ADR-0031, ADR-0032). Source entities are pre-filled
from the Energy Dashboard configuration where the household has set it up, on a
best-effort basis - prefill never blocks the flow. Per-device tracking is added
afterwards as config subentries, not here.
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
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector, translation

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CHARGING,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENCY,
    CONF_CYCLE_DAILY,
    CONF_CYCLE_MONTHLY,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    CONF_DEVICE_COST_BOUNDS,
    CONF_ENERGY_DASHBOARD_ANSWERED,
    CONF_ENERGY_ENTITY,
    CONF_FIXED_PRICE,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    DEFAULT_CURRENCY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_DEVICE,
    SUBENTRY_TYPE_GRID,
)
from .discovery import (
    async_discover_candidates,
    is_eligible_source,
    source_state_class,
    source_unit,
)
from .energy_dashboard import answered, batteries_in, grid_meters_in, priced
from .engine.house_balance import ChargeSource
from .house_inputs import batteries_of, grid_meters, grid_meters_of, house_entities
from .reset import async_reset_totals

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .discovery import DeviceCandidate

_TITLE = "Home Energy Advisor"
# Options-flow-internal key for the multi-select of discovered devices to add.
_CONF_DISCOVERED = "discovered_devices"

#: The domains the Energy Dashboard accepts as a price: a tariff sensor, or a
#: Number helper holding a fixed rate.
_PRICE_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)
_ENERGY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
)
# Several, as the Energy Dashboard takes several solar sources: a household with
# panels on two inverter inputs has no single meter holding the lot (HEA-219).
_GENERATION_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy", multiple=True)
)
_POWER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="power")
)
# How full the battery is, and how much it holds when it is (HEA-178). The
# `battery` device class is the percentage one almost every battery integration
# publishes; the capacity is the *usable* figure a percentage is a percentage of.
_BATTERY_LEVEL_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="battery")
)
# A rate typed as it is on a bill, per kWh, as the Energy Dashboard allows.
_FIXED_PRICE_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, step="any", mode=selector.NumberSelectorMode.BOX
    )
)
_CAPACITY_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0.1,
        step=0.1,
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="kWh",
    )
)
# How the battery charges, in the engine's own terms, most common first (HEA-233).
_BATTERY_CHARGING_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[source.value for source in ChargeSource],
        mode=selector.SelectSelectorMode.LIST,
        translation_key=CONF_BATTERY_CHARGING,
    )
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

    VERSION = 7

    def __init__(self) -> None:
        """Start with nothing answered."""
        self._house: dict[str, Any] = {}
        self._offered: list[dict[str, Any]] = []
        self._grids_offered: list[dict[str, Any]] = []
        self._grids: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the house-level inputs, then the grid meters and batteries."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            errors = _validate_house_sources(self.hass, user_input)
            if not errors:
                prefs = await _energy_dashboard_prefs(self.hass)
                self._offered = batteries_in(prefs)
                self._grids_offered = grid_meters_in(self.hass, prefs)
                # Choosing which batteries and grid meters to take is an answer to
                # the Energy Dashboard as it stands, so it is not asked about
                # again (ADR-0030).
                self._house = {
                    **user_input,
                    CONF_ENERGY_DASHBOARD_ANSWERED: answered(self.hass, prefs),
                }
                if any(priced(grid) for grid in self._grids_offered):
                    return await self.async_step_grid_meters()
                return await self.async_step_grid_meter()
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    _build_schema({}), user_input
                ),
                errors=errors,
            )

        defaults = await _energy_prefs_defaults(self.hass)
        return self.async_show_form(step_id="user", data_schema=_build_schema(defaults))

    async def async_step_grid_meters(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the Energy Dashboard's grid sources, filled in, to take in one go.

        Only those that carry a price, since a grid entry cannot be counted
        without one. Choosing none goes on to a form to enter one by hand, for a
        household who keeps different meters here on purpose (ADR-0030).
        """
        offered = [grid for grid in self._grids_offered if priced(grid)]
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = [offered[int(index)] for index in user_input["grid_meters"]]
            if not chosen:
                return await self.async_step_grid_meter()
            if not any(self._refusals(grid) for grid in chosen):
                self._grids = chosen
                return await self._async_after_the_grid()
            errors["grid_meters"] = "grid_meter_not_countable"
        options = [
            selector.SelectOptionDict(value=str(index), label=_grid_label(grid))
            for index, grid in enumerate(offered)
        ]
        return self.async_show_form(
            step_id="grid_meters",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "grid_meters", default=[option["value"] for option in options]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_grid_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter one grid meter by hand; more can be added afterwards."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._refusals(user_input)
            if not errors:
                self._grids = [user_input]
                return await self._async_after_the_grid()
        suggested = user_input or next(
            iter(self._grids_offered), {CONF_NAME: _FIRST_GRID}
        )
        return self.async_show_form(
            step_id="grid_meter",
            data_schema=self.add_suggested_values_to_schema(_GRID_SCHEMA, suggested),
            errors=errors,
        )

    def _refusals(self, grid: Mapping[str, Any]) -> dict[str, str]:
        return validate_grid_meter(
            self.hass,
            grid,
            house_metered=bool(self._house.get(CONF_HOUSE_CONSUMPTION_ENTITY)),
        )

    async def _async_after_the_grid(self) -> ConfigFlowResult:
        if self._offered:
            return await self.async_step_batteries()
        return self._create()

    def _create(
        self, batteries: list[dict[str, Any]] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title=_TITLE,
            data=self._house,
            subentries=[
                *(_subentry(SUBENTRY_TYPE_GRID, grid) for grid in self._grids),
                *(_subentry(SUBENTRY_TYPE_BATTERY, b) for b in batteries or []),
            ],
        )

    async def async_step_batteries(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the Energy Dashboard's battery systems, filled in, to take in one go.

        Each one taken becomes a battery entry holding exactly what the Energy
        Dashboard does (ADR-0030, ADR-0031). Its meters are checked as a battery
        added by hand would be, so taking one cannot slip past the form's
        refusals.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = [self._offered[int(index)] for index in user_input["batteries"]]
            refused = next(
                (battery for battery in chosen if validate_battery(self.hass, battery)),
                None,
            )
            if refused is None:
                return self._create(chosen)
            errors["batteries"] = "battery_not_countable"
        options = [
            selector.SelectOptionDict(value=str(index), label=battery[CONF_NAME])
            for index, battery in enumerate(self._offered)
        ]
        return self.async_show_form(
            step_id="batteries",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "batteries", default=[option["value"] for option in options]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the house-level configuration in place, without reinstalling."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_house_sources(
                self.hass, user_input, grid_meters(entry, CONF_GRID_EXPORT_ENTITY)
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data=_reconfigured(entry.data, user_input)
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _build_schema({}), user_input or entry.data
            ),
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003 - HA signature; the types are entry-independent
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Register the per-device, per-grid-source and per-battery subentry flows."""
        return {
            SUBENTRY_TYPE_DEVICE: DeviceSubentryFlowHandler,
            SUBENTRY_TYPE_GRID: GridSubentryFlowHandler,
            SUBENTRY_TYPE_BATTERY: BatterySubentryFlowHandler,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,  # noqa: ARG004 - HA signature; the entry is read via self
    ) -> HomeEnergyAdvisorOptionsFlow:
        """Provide the options flow for the global cycle opt-ins."""
        return HomeEnergyAdvisorOptionsFlow()


def _reconfigured(
    stored: Mapping[str, Any], user_input: dict[str, Any]
) -> dict[str, Any]:
    """The entry's data after a Reconfigure.

    Every field the form asks about comes from what was submitted, and a field
    that is absent is unset: Home Assistant's form leaves an emptied field out
    altogether rather than sending it empty, so merging over the stored data
    kept an export meter or a battery capacity the household had removed
    (HEA-231).

    Everything else is kept as stored, because the entry also holds what the
    form never shows - the helpers this integration created and owns
    (CONF_INTEGRAL_HELPERS / CONF_CYCLE_METERS), which replacing the data
    outright would forget (HEA-52). The form's fields are read off its own
    schema, so a field added to it later is covered without anyone remembering.
    """
    asked = {str(marker) for marker in _build_schema({}).schema}
    kept = {key: value for key, value in stored.items() if key not in asked}
    return {**kept, **user_input}


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    def prefilled(key: str, *, required: bool) -> vol.Marker:
        marker = vol.Required if required else vol.Optional
        if key in defaults:
            return marker(key, description={"suggested_value": defaults[key]})
        return marker(key)

    # The grid meters and their prices are entries of their own (ADR-0032).
    return vol.Schema(
        {
            vol.Required(
                CONF_CURRENCY, default=DEFAULT_CURRENCY
            ): selector.TextSelector(),
            prefilled(CONF_GENERATION_ENTITY, required=False): _GENERATION_SELECTOR,
            prefilled(CONF_HOUSE_CONSUMPTION_ENTITY, required=False): _ENERGY_SELECTOR,
            # The batteries are entries of their own (ADR-0031). How they charge
            # stays here, one answer for the household (HEA-233); the default is
            # the answer true of most batteries.
            vol.Required(
                CONF_BATTERY_CHARGING, default=ChargeSource.SPARE_SOLAR.value
            ): _BATTERY_CHARGING_SELECTOR,
        }
    )


async def _energy_prefs_defaults(hass: HomeAssistant) -> dict[str, Any]:
    """Best-effort source defaults from the Energy Dashboard; empty if unset."""
    defaults: dict[str, Any] = {}
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
    defaults: dict[str, Any],
) -> None:
    """Map one Energy Dashboard source onto the matching config defaults."""
    if source.get("type") == "solar" and (stat := source.get("stat_energy_from")):
        # Every one, in the dashboard's order. Keeping only the last silently
        # offered half the generation of a household with two arrays (HEA-219).
        defaults.setdefault(CONF_GENERATION_ENTITY, []).append(stat)
    # The grid sources and batteries are offered as entries of their own, after
    # this screen (ADR-0031, ADR-0032).


async def _energy_dashboard_prefs(hass: HomeAssistant) -> Any:  # noqa: ANN401 - untyped HA prefs
    """The Energy Dashboard's preferences, or ``None``; prefill never blocks setup."""
    try:
        manager = await async_get_manager(hass)
    except Exception:  # noqa: BLE001 - prefill is optional; it must never block setup
        return None
    return manager.data


def _subentry(subentry_type: str, answers: dict[str, Any]) -> ConfigSubentryData:
    return ConfigSubentryData(
        data=answers,
        subentry_type=subentry_type,
        title=answers[CONF_NAME],
        unique_id=None,
    )


def _grid_label(answers: Mapping[str, Any]) -> str:
    """A grid source as a line to tick: its meter and what prices it."""
    price = answers.get(CONF_PRICE_ENTITY) or answers.get(CONF_FIXED_PRICE)
    return f"{answers[CONF_NAME]}: {answers[CONF_GRID_IMPORT_ENTITY]} ({price})"


_FIRST_GRID = "Grid"
_GRID_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_GRID_IMPORT_ENTITY): _ENERGY_SELECTOR,
        vol.Optional(CONF_PRICE_ENTITY): _PRICE_SELECTOR,
        vol.Optional(CONF_FIXED_PRICE): _FIXED_PRICE_SELECTOR,
        vol.Optional(CONF_GRID_EXPORT_ENTITY): _ENERGY_SELECTOR,
    }
)


class GridSubentryFlowHandler(ConfigSubentryFlow):
    """Add one grid source, in the shape of the Energy Dashboard's.

    Its import meter, the price of that import - a sensor, a Number helper or a
    plain number - and optionally its export meter (ADR-0032). A dual-rate meter
    is two of these, one per register. The Energy Dashboard's grid sources not
    yet added are offered filled in, as batteries are (ADR-0030).
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect one grid source, suggesting the next the Energy Dashboard holds."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_grid_meter(
                self.hass, user_input, house_metered=self._metered()
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        suggested = user_input or await self._next_from_the_energy_dashboard()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_GRID_SCHEMA, suggested),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a grid source's name, meters or price."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_grid_meter(
                self.hass, user_input, house_metered=self._metered()
            )
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _GRID_SCHEMA, user_input or subentry.data
            ),
            errors=errors,
        )

    def _metered(self) -> bool:
        return bool(self._get_entry().data.get(CONF_HOUSE_CONSUMPTION_ENTITY))

    async def _next_from_the_energy_dashboard(self) -> dict[str, Any]:
        """The first Energy Dashboard grid source whose meter no entry holds yet."""
        entered = {grid.imported for grid in grid_meters_of(self._get_entry()).values()}
        offered = grid_meters_in(self.hass, await _energy_dashboard_prefs(self.hass))
        return next(
            (grid for grid in offered if grid[CONF_GRID_IMPORT_ENTITY] not in entered),
            {},
        )


class DeviceSubentryFlowHandler(ConfigSubentryFlow):
    """Add one tracked device as a config subentry.

    A device is identified by exactly one source sensor: an energy counter, or a
    power sensor (whose energy is derived later via an auto-created Integral
    helper, ADR-0004). Selection is always explicit - devices are never
    auto-onboarded from a matching ``device_class`` (false friends, ADR-0004).
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the device name and its single source sensor."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = _validate_device_sources(self.hass, user_input)
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
            error = _validate_device_sources(self.hass, user_input)
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


_BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_BATTERY_CHARGE_ENTITY): _ENERGY_SELECTOR,
        vol.Required(CONF_BATTERY_DISCHARGE_ENTITY): _ENERGY_SELECTOR,
        vol.Optional(CONF_BATTERY_SOC_ENTITY): _BATTERY_LEVEL_SELECTOR,
        vol.Optional(CONF_BATTERY_CAPACITY_KWH): _CAPACITY_SELECTOR,
    }
)


class BatterySubentryFlowHandler(ConfigSubentryFlow):
    """Add one battery, in the shape of Home Assistant's battery system.

    The same fields the Energy Dashboard holds for a battery: its charge and
    discharge meters, and optionally its level and usable capacity (ADR-0031).
    The Energy Dashboard's batteries not yet added are offered filled in, since
    it is the place a household is encouraged to enter them (ADR-0030).
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect one battery, suggesting the next one the Energy Dashboard holds."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_battery(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        suggested = user_input or await self._next_from_the_energy_dashboard()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_BATTERY_SCHEMA, suggested),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a battery's name, meters, level or capacity."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_battery(self.hass, user_input)
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _BATTERY_SCHEMA, user_input or subentry.data
            ),
            errors=errors,
        )

    async def _next_from_the_energy_dashboard(self) -> dict[str, Any]:
        """The first Energy Dashboard battery whose meters no entry holds yet."""
        entered = {
            meter
            for battery in batteries_of(self._get_entry()).values()
            for meter in (battery.charge, battery.discharge)
        }
        offered = batteries_in(await _energy_dashboard_prefs(self.hass))
        return next(
            (
                battery
                for battery in offered
                if battery[CONF_BATTERY_CHARGE_ENTITY] not in entered
            ),
            {},
        )


# House inputs every decomposition branch reads, whatever else is configured. The
# grid's import meters are as well, and are checked on their own entries.
_ALWAYS_READ = (CONF_HOUSE_CONSUMPTION_ENTITY,)
# Read only by ADR-0005's full-balance branch, which runs when no house-load
# meter is configured. With one, the residual branch derives generation from the
# house total and never looks at these. The grid's export meters are too.
_FULL_BALANCE_ONLY = (CONF_GENERATION_ENTITY,)


def _validate_house_sources(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    exports: tuple[str, ...] = (),
) -> dict[str, str]:
    """Reject a house input the chosen accounting model would mis-read.

    A bad *device* source corrupts one device's share; a bad *house* source
    corrupts every figure in the ledger, because allocation is proportional. So
    these deserve at least the same scrutiny (HEA-67).

    Validation follows what the model actually consumes, not the whole form. With
    a house-load meter, ADR-0005 takes the residual branch and never reads
    generation or export, so a net counter there is genuinely harmless - and
    rejecting it would block a configuration that works. Without one, the
    full-balance branch does read them, and a net counter there is booked as
    generation with no warning at all.

    An absent state_class is allowed, as on any explicit manual pick; only a
    present-but-wrong one is refused (ADR-0010 §2).

    ``exports`` are the grid entries' export meters, which removing the house
    meter here brings into the full-balance branch. One that cannot be read
    there is refused for the form as a whole, since its field is on another
    entry.
    """
    checked = [*_ALWAYS_READ]
    metered = bool(user_input.get(CONF_HOUSE_CONSUMPTION_ENTITY))
    if not metered:
        checked += _FULL_BALANCE_ONLY
    errors: dict[str, str] = {}
    for key in checked:
        # Every meter under the input, so one bad array among several is caught:
        # the sum is only as sound as its worst member.
        if error := _house_input_error(hass, house_entities(user_input, key)):
            errors[key] = error
    if not metered and _house_input_error(hass, exports):
        errors["base"] = "grid_export_not_countable"
    return errors


def validate_grid_meter(
    hass: HomeAssistant, answers: Mapping[str, Any], *, house_metered: bool
) -> dict[str, str]:
    """Refuse a grid source whose meters or price would be misread.

    Its import meter is read by every decomposition branch, and its export
    meter by the full-balance branch, used where no house meter is configured
    (``house_metered``), so each is held to the house's standard where it is
    read (HEA-67). Its import is priced by an entity or by a number, and by
    exactly one: two would leave it unclear which is meant.
    """
    errors: dict[str, str] = {}
    checked = [CONF_GRID_IMPORT_ENTITY]
    if not house_metered:
        checked.append(CONF_GRID_EXPORT_ENTITY)
    for key in checked:
        if error := _house_input_error(hass, house_entities(answers, key)):
            errors[key] = error
    has_entity = bool(answers.get(CONF_PRICE_ENTITY))
    has_number = answers.get(CONF_FIXED_PRICE) is not None
    if has_entity == has_number:
        errors["base"] = "select_one_price"
    return errors


def validate_battery(hass: HomeAssistant, answers: Mapping[str, Any]) -> dict[str, str]:
    """Refuse a battery whose meters, level or capacity would be misread.

    Its meters feed the house balance, so they are held to the house's standard
    (HEA-67): a net or uncountable counter here skews every figure. A level needs
    the capacity it is a percentage of (HEA-178), and a capacity in watt-hours is
    refused where it is typed (HEA-227).
    """
    errors: dict[str, str] = {}
    for key in (CONF_BATTERY_CHARGE_ENTITY, CONF_BATTERY_DISCHARGE_ENTITY):
        if error := _house_input_error(hass, house_entities(answers, key)):
            errors[key] = error
    capacity = answers.get(CONF_BATTERY_CAPACITY_KWH)
    if answers.get(CONF_BATTERY_SOC_ENTITY) and capacity is None:
        errors[CONF_BATTERY_CAPACITY_KWH] = _CAPACITY_NEEDED
    elif capacity is not None and capacity > _MAX_HOME_BATTERY_KWH:
        errors[CONF_BATTERY_CAPACITY_KWH] = _CAPACITY_ERROR
    return errors


_CAPACITY_NEEDED = "capacity_needed"


# Above this, a home battery's capacity is a figure in Wh typed into the kWh
# field rather than a battery: the largest home systems are a few tens of kWh.
# Left unchecked, a 1500 Wh battery at 32% reads as holding 480 kWh, and the
# loss measurement and the stored-cost write-down are judged against that
# (HEA-227).
_MAX_HOME_BATTERY_KWH = 200
_CAPACITY_ERROR = "capacity_not_kwh"


def _house_input_error(hass: HomeAssistant, entity_ids: tuple[str, ...]) -> str | None:
    """The first reason any of these meters cannot be counted, else ``None``."""
    for entity_id in entity_ids:
        if _wrong_state_class_error(hass, entity_id, CONF_ENERGY_ENTITY):
            return _HOUSE_STATE_CLASS_ERROR
        if _uncountable_unit_error(hass, entity_id):
            return _UNIT_ERROR
    return None


_HOUSE_STATE_CLASS_ERROR = "house_not_total_increasing"
_UNIT_ERROR = "unit_not_energy"


def _uncountable_unit_error(hass: HomeAssistant, entity_id: str) -> str | None:
    """Reject an energy source reporting in a unit the engine cannot count in.

    The engine works in kWh and Wh and converts between them from each reading
    (HEA-149), so a mixture of the two is correct and is deliberately *not*
    flagged: telling a household their working setup is wrong would have them
    swap the entity, which re-baselines the counter and loses accounting for
    nothing. Two households have already lost time believing a Wh sensor was
    their fault (GitHub #24, #27) - it is not.

    Anything else is a different matter. A megawatt-hour counter is not
    converted and not counted, so the device sits at zero for ever and its
    energy falls into Untracked with nothing saying why. Refusing it while
    somebody is still choosing beats a Repair a week later (HEA-161).

    A sensor that reports *no* unit is allowed through, exactly as an absent
    state_class is (ADR-0010 section 2). A cloud meter reconnecting publishes no
    unit for a few seconds, and reading that silence as a fact about the sensor
    is the mistake HEA-149 exists to correct.
    """
    unit = source_unit(hass, entity_id)
    if unit is None or unit.strip().lower() in _COUNTABLE_UNITS:
        return None
    return _UNIT_ERROR


# Lowered, because a household's integration may write "WH", "Wh" or "wh" and
# all three are the same unit.
_COUNTABLE_UNITS = frozenset({"kwh", "wh"})


def _validate_device_sources(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> str | None:
    """Require exactly one source sensor, and that its state_class fits the engine.

    Exactly one of an energy or a power sensor, then a state_class check: a
    *present-but-wrong* class is rejected (a `total` net counter or a measurement
    where a total_increasing counter is needed would book phantom energy). An
    absent state_class is allowed on this explicit manual pick - discovery is
    stricter and simply never suggests one (HEA-54).
    """
    energy = user_input.get(CONF_ENERGY_ENTITY, "")
    power = user_input.get(CONF_POWER_ENTITY, "")
    if bool(energy) == bool(power):
        return "select_one_sensor"
    source_key = CONF_ENERGY_ENTITY if energy else CONF_POWER_ENTITY
    wrong_class = _wrong_state_class_error(hass, energy or power, source_key)
    if wrong_class is not None:
        return wrong_class
    # Only the energy source: a power sensor is read by the Integral helper HA
    # creates for it (ADR-0004), and the helper derives its own output unit from
    # whatever that sensor reports.
    return _uncountable_unit_error(hass, energy) if energy else None


def _wrong_state_class_error(
    hass: HomeAssistant, entity_id: str, source_key: str
) -> str | None:
    """The error for a class the engine cannot account in, else ``None``.

    An absent class is allowed here and refused by discovery, which is the
    asymmetry ADR-0010 section 2 draws. What counts as present-and-right is
    `discovery.is_eligible_source`, so the flow and the suggestions can never
    disagree about a sensor - the defect HEA-162 closed was exactly that.
    """
    if source_state_class(hass, entity_id) is None:
        return None
    if is_eligible_source(hass, entity_id, source_key):
        return None
    return _STATE_CLASS_ERROR[source_key]


_STATE_CLASS_ERROR = {
    CONF_ENERGY_ENTITY: "energy_not_total_increasing",
    CONF_POWER_ENTITY: "power_not_measurement",
}


class HomeEnergyAdvisorOptionsFlow(OptionsFlow):
    """Options: the opt-in toggles and the guided device-discovery step.

    Cycle totals are opt-in, every cycle of them: the cards read long-term
    statistics, so nothing the dashboard draws needs a helper, and creating
    ninety of them for a household that never asked is a cost without a
    capability (HEA-145, ADR-0008's own revisit condition). The
    per-device cost range is opt-in for the same reason (ADR-0016) - the
    whole-home range is published either way. Discovery (HEA-45) offers untracked
    energy/power sensors to add as devices - it only suggests; the user picks.
    All are re-runnable from Configure.
    """

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA menu step signature
    ) -> ConfigFlowResult:
        """Offer the options branches."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "cycles",
                "cost_bounds",
                "discover_devices",
                "reset_totals",
            ],
        )

    def _store(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Merge one branch's answers into the options rather than replacing them.

        ``async_create_entry`` writes the options wholesale, so a branch that
        submits only its own keys would silently clear every other branch's.
        """
        return self.async_create_entry(data={**self.config_entry.options, **user_input})

    def _toggles(self, *keys: str) -> vol.Schema:
        options = self.config_entry.options
        return vol.Schema(
            {
                vol.Required(
                    key, default=options.get(key, False)
                ): selector.BooleanSelector()
                for key in keys
            }
        )

    async def async_step_cycles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the cycle opt-ins.

        Every cycle, daily included. The dashboard answers any range from
        long-term statistics without these, so a household that wants a *live*
        entity for a template or an automation asks for one - rather than
        everybody carrying ninety helpers by default (HEA-145).
        """
        if user_input is not None:
            return self._store(user_input)
        return self.async_show_form(
            step_id="cycles",
            data_schema=self._toggles(
                CONF_CYCLE_DAILY,
                CONF_CYCLE_MONTHLY,
                CONF_CYCLE_WEEKLY,
                CONF_CYCLE_QUARTERLY,
                CONF_CYCLE_YEARLY,
            ),
        )

    async def async_step_cost_bounds(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the per-device cost-range opt-in (ADR-0016)."""
        if user_input is not None:
            return self._store(user_input)
        return self.async_show_form(
            step_id="cost_bounds",
            data_schema=self._toggles(CONF_DEVICE_COST_BOUNDS),
        )

    async def async_step_reset_totals(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm, then rebase every accumulated figure to zero (HEA-57).

        The empty schema is the confirmation: the form's translated text explains
        what is about to be destroyed, and only submitting it does the work. The
        flow aborts rather than creating an entry, because the options are
        unchanged and rewriting them would reload the entry for nothing.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="reset_totals", data_schema=vol.Schema({})
            )
        await async_reset_totals(self.hass, self.config_entry)
        return self.async_abort(reason="reset_totals_done")

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
        labels = await _candidate_label_templates(self.hass)
        return self.async_show_form(
            step_id="discover_devices",
            data_schema=_discovery_schema(candidates, labels),
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


def _discovery_schema(
    candidates: list[DeviceCandidate], labels: dict[str, str]
) -> vol.Schema:
    options = [
        selector.SelectOptionDict(
            value=candidate.entity_id, label=_candidate_label(candidate, labels)
        )
        for candidate in candidates
    ]
    return vol.Schema(
        {
            vol.Optional(_CONF_DISCOVERED, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    # A checkbox list, deliberately: this step is for *browsing*
                    # what a household has, and a dropdown shows nothing until
                    # the user types a name they do not yet know. The ordering
                    # does the work of making a long list usable (HEA-70).
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


async def _candidate_label_templates(hass: HomeAssistant) -> dict[str, str]:
    """The translated row templates, keyed by their ``common`` string name.

    A candidate row is built per entity, so its wording cannot live in the step's
    own strings. It is looked up from ``common`` instead, which keeps the phrase
    in `strings.json` where every user-facing string belongs - the Spanish step
    description already promises this marker, and hardcoding it in English meant
    a Spanish user was told to look for something they could never see.
    """
    strings = await translation.async_get_translations(
        hass, hass.config.language, "common", {DOMAIN}
    )
    prefix = f"component.{DOMAIN}.common."
    return {
        key.removeprefix(prefix): value
        for key, value in strings.items()
        if key.startswith(prefix)
    }


def _candidate_label(candidate: DeviceCandidate, labels: dict[str, str]) -> str:
    key = (
        "candidate_label_false_friend"
        if candidate.likely_false_friend
        else "candidate_label"
    )
    template = labels.get(key, "{name} ({entity_id})")
    return template.format(name=candidate.name, entity_id=candidate.entity_id)
