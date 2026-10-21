"""Constants for the Home Energy Advisor integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "home_energy_advisor"

# House-level configuration - global, one set per household (ADR-0002). The grid
# meters and their prices are held on the grid entries (SUBENTRY_TYPE_GRID).
CONF_PRICE_ENTITY: Final = "price_entity"
CONF_CURRENCY: Final = "currency"
CONF_GRID_IMPORT_ENTITY: Final = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY: Final = "grid_export_entity"
CONF_GENERATION_ENTITY: Final = "generation_entity"
CONF_BATTERY_CHARGE_ENTITY: Final = "battery_charge_entity"
CONF_BATTERY_DISCHARGE_ENTITY: Final = "battery_discharge_entity"
# What the battery actually holds, so the stored-cost ledger can be written down
# to it rather than drifting upwards for ever (HEA-178). A percentage needs the
# capacity to mean anything in kWh, so the two are only useful together.
CONF_BATTERY_SOC_ENTITY: Final = "battery_soc_entity"
CONF_BATTERY_CAPACITY_KWH: Final = "battery_capacity_kwh"
CONF_HOUSE_CONSUMPTION_ENTITY: Final = "house_consumption_entity"
# How the battery charges, which decides what charged it where the house imports,
# generates and charges all at once - the meters cannot see it, so the household
# says. Its answers are the engine's ChargeSource values (HEA-233).
CONF_BATTERY_CHARGING: Final = "battery_charging"

DEFAULT_CURRENCY: Final = "EUR"

# Per-device configuration - one config subentry per tracked device.
SUBENTRY_TYPE_DEVICE: Final = "device"
# One config subentry per battery, holding a battery system's own fields: its
# charge and discharge meters (the CONF_BATTERY_* keys above), and optionally its
# level and capacity (ADR-0031).
SUBENTRY_TYPE_BATTERY: Final = "battery"
# One config subentry per grid source, as the Energy Dashboard holds them: an import
# meter, its price, and optionally an export meter (CONF_GRID_IMPORT_ENTITY,
# CONF_PRICE_ENTITY or CONF_FIXED_PRICE, CONF_GRID_EXPORT_ENTITY). A dual-rate
# meter is two of them, one per register (ADR-0032).
SUBENTRY_TYPE_GRID: Final = "grid"
# A price typed as a number rather than read from an entity, as the Energy
# Dashboard allows, per kWh in the household's currency.
CONF_FIXED_PRICE: Final = "fixed_price"
CONF_ENERGY_ENTITY: Final = "energy_entity"
CONF_POWER_ENTITY: Final = "power_entity"

# Device key for the whole-home aggregate (Σ devices + Untracked). Shared so the
# cycle-meter reconciliation can exclude it: its period totals are derivable and
# duplicate the Energy Dashboard, so it carries running totals only (HEA-48).
WHOLE_HOME_KEY: Final = "whole_home"

# Bookkeeping (entry data): the native Integral helpers we auto-created for
# power-only devices, as {subentry_id: helper_config_entry_id}. Lets us reuse a
# device's helper across reloads and remove it when the device is (HEA-34).
CONF_INTEGRAL_HELPERS: Final = "integral_helpers"

# Bookkeeping (entry data): the Energy Dashboard's house as it stood when the
# household last answered for it - at setup, or by keeping their own over a
# change - so the same difference is not offered twice (ADR-0030).
CONF_ENERGY_DASHBOARD_ANSWERED: Final = "energy_dashboard_answered"

# Bookkeeping (entry data): the native utility_meter cycle helpers we auto-created,
# as {"source_entity|cycle": helper_config_entry_id}. Reused across reloads and
# reconciled away when a device (and so its source sensors) is removed (HEA-23).
CONF_CYCLE_METERS: Final = "cycle_meters"

# The supported reset of a household's accumulated totals (HEA-57). An action
# rather than a button entity: rebasing is irreversible, and a button on a device
# page is one accidental tap away with no confirmation.
SERVICE_RESET_TOTALS: Final = "reset_totals"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

# Dispatcher signal telling a household's sensors to drop the restore baseline
# they add on top of the runtime's running total, when those totals are rebased
# to zero (HEA-57). Formatted per config entry so one household's reset never
# touches another's figures.
SIGNAL_RESET_TOTALS: Final = f"{DOMAIN}_reset_totals_{{entry_id}}"

# Optional cycle totals (options flow). Daily and monthly are always on; these
# are opt-in to keep the entity count in check (ADR-0004 / PLAN.md).
CONF_CYCLE_DAILY: Final = "cycle_daily"
CONF_CYCLE_MONTHLY: Final = "cycle_monthly"
CONF_CYCLE_WEEKLY: Final = "cycle_weekly"
CONF_CYCLE_QUARTERLY: Final = "cycle_quarterly"
CONF_CYCLE_YEARLY: Final = "cycle_yearly"

# Optional per-device cost bounds (options flow). The whole-home band is always
# published - it is what makes every install honest by default - but two more
# sensors for every tracked device is a recorder cost a household should choose,
# so the per-device band follows the same opt-in precedent (ADR-0016).
CONF_DEVICE_COST_BOUNDS: Final = "device_cost_bounds"
