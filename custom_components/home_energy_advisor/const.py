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
# The usable capacity as the battery's own management system publishes it, which
# follows the battery as it ages. Optional beside the typed figure, and read in
# its place when it reports (HEA-244, ADR-0035).
CONF_BATTERY_CAPACITY_ENTITY: Final = "battery_capacity_entity"
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
# One config subentry per tariff plan the household compares, the one it is on
# included: its details, its named prices, then its time bands, each a mapping of
# the CONF_BAND_* keys naming the price it charges (ADR-0036, HEA-262). Read by
# the plan comparison only, never by the accounting.
SUBENTRY_TYPE_PLAN: Final = "plan"
# Where a plan was marked as the one the household is on, before the integration
# kept that plan itself (ADR-0042). Only the migration reads it.
CONF_PLAN_CURRENT: Final = "current_plan"
# The plan the household is on, priced at the prices Paid is priced at rather
# than a schedule of its own (ADR-0042).
CONF_PLAN_FOLLOWS: Final = "follows_prices"
# The current plan's daily charge as the recorded cost of an Energy Dashboard
# grid source, the way households enter a standing charge there, named by that
# source's meter (ADR-0042).
CONF_PLAN_DAILY_CHARGE_SOURCE: Final = "daily_charge_source"
# The current plan's daily charge read from an entity giving it per day, as a
# supplier's integration publishes it (HEA-317).
CONF_PLAN_DAILY_CHARGE_ENTITY: Final = "daily_charge_entity"
# On the current plan, the name of the typed plan it took over from on upgrade,
# until the household has been told that plan now duplicates it (ADR-0042).
CONF_PLAN_REPLACED: Final = "replaced_plan"
# On the current plan, the plans the household has been on: each a typed plan by
# subentry id, from a local day as YYYY-MM-DD, the first from always. Where the
# price sensors it follows have no statistics, an hour is priced at the plan of
# its day (HEA-311, HEA-307, ADR-0048).
CONF_PLAN_PERIODS: Final = "price_periods"
# On the current plan: whether this integration provides the household's price
# sensors, fed by the plan of the period in force today (ADR-0048).
CONF_PLAN_PROVIDES_PRICES: Final = "provides_prices"
# On a typed plan: left out of the comparison's table and action, and counted;
# still read for the days the household was on it (HEA-307).
CONF_PLAN_ARCHIVED: Final = "archived"
# On the current plan, for one reload: the old sources the household chose to
# carry the price history in from when it ticked "Provide my price sensors",
# by sensor key, run once those sensors exist (ADR-0048 decision 4).
CONF_PLAN_CARRY_IN: Final = "carry_in"
CONF_PERIOD_PLAN: Final = "plan"
CONF_PERIOD_FROM: Final = "from"
# On a period whose plan was deleted: the household said it deleted it on
# purpose, so the period stays missing and is not asked about again.
CONF_PERIOD_GONE_KNOWN: Final = "deleted_on_purpose"
CONF_PLAN_DAILY_CHARGE: Final = "daily_charge"
CONF_PLAN_EXPORT_PRICE: Final = "plan_export_price"
# The kWh a day the export price pays on, and the price for the rest (ADR-0039).
CONF_PLAN_EXPORT_ALLOWANCE: Final = "plan_export_allowance"
CONF_PLAN_EXPORT_PRICE_AFTER: Final = "plan_export_price_after"
# Whether what export earns a month is capped at its energy cost (HEA-258).
CONF_PLAN_EXPORT_CAP: Final = "plan_export_cap"
CONF_PLAN_HOLIDAYS: Final = "holiday_calendar"
# A market price the plan imports or exports at instead of a schedule (ADR-0037):
# a plan importing at one has no prices or bands.
CONF_PLAN_IMPORT_PRICE_ENTITY: Final = "import_price_entity"
CONF_PLAN_EXPORT_PRICE_ENTITY: Final = "export_price_entity"
# What the plan adds per kWh to a market price, then multiplies it by (HEA-273).
CONF_PLAN_IMPORT_PRICE_ADD: Final = "import_price_add"
CONF_PLAN_IMPORT_PRICE_MULTIPLY: Final = "import_price_multiply"
CONF_PLAN_EXPORT_PRICE_ADD: Final = "export_price_add"
CONF_PLAN_EXPORT_PRICE_MULTIPLY: Final = "export_price_multiply"
# Each a name with an import price and optionally an export price of its own.
CONF_PRICES: Final = "prices"
CONF_BANDS: Final = "bands"
CONF_BAND_DAYS: Final = "days"
CONF_BAND_START: Final = "start_hour"
CONF_BAND_END: Final = "end_hour"
CONF_BAND_PRICE: Final = "price"
# A price's figures; a band entered before prices were named carries them itself.
CONF_BAND_IMPORT_PRICE: Final = "import_price"
CONF_BAND_EXPORT_PRICE: Final = "band_export_price"
# The kWh a day a price's own export price pays on (ADR-0039).
CONF_BAND_EXPORT_ALLOWANCE: Final = "band_export_allowance"
# The kWh a price's import price charges on each day, week or month, and the
# other named price its hours are charged beyond it (HEA-264).
CONF_BAND_IMPORT_ALLOWANCE: Final = "band_import_allowance"
CONF_BAND_IMPORT_ALLOWANCE_PERIOD: Final = "band_import_allowance_period"
CONF_BAND_IMPORT_PRICE_AFTER: Final = "band_import_price_after"
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
# More energy than any home could use in an hour: a large three-phase
# connection delivers around 40 to 45 kW. A meter's statistics changing by more,
# either way, is a fault in them (ADR-0044, ADR-0045).
IMPOSSIBLE_KWH_PER_HOUR: Final = 100

SERVICE_RESET_TOTALS: Final = "reset_totals"
SERVICE_COMPARE_PLANS: Final = "compare_plans"
SERVICE_CARRY_IN_HISTORY: Final = "carry_in_history"
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
