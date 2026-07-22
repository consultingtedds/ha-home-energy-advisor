"""Constants for the Home Energy Advisor integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "home_energy_advisor"

# House-level configuration — global, one set per household (ADR-0002).
CONF_PRICE_ENTITY: Final = "price_entity"
CONF_CURRENCY: Final = "currency"
CONF_GRID_IMPORT_ENTITY: Final = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY: Final = "grid_export_entity"
CONF_SOLAR_ENTITY: Final = "solar_entity"
CONF_BATTERY_CHARGE_ENTITY: Final = "battery_charge_entity"
CONF_BATTERY_DISCHARGE_ENTITY: Final = "battery_discharge_entity"
CONF_HOUSE_CONSUMPTION_ENTITY: Final = "house_consumption_entity"

DEFAULT_CURRENCY: Final = "EUR"

# Per-device configuration — one config subentry per tracked device.
SUBENTRY_TYPE_DEVICE: Final = "device"
CONF_ENERGY_ENTITY: Final = "energy_entity"
CONF_POWER_ENTITY: Final = "power_entity"

# Bookkeeping (entry data): the native Integral helpers we auto-created for
# power-only devices, as {subentry_id: helper_config_entry_id}. Lets us reuse a
# device's helper across reloads and remove it when the device is (HEA-34).
CONF_INTEGRAL_HELPERS: Final = "integral_helpers"

# Bookkeeping (entry data): the native utility_meter cycle helpers we auto-created,
# as {"source_entity|cycle": helper_config_entry_id}. Reused across reloads and
# reconciled away when a device (and so its source sensors) is removed (HEA-23).
CONF_CYCLE_METERS: Final = "cycle_meters"

# Optional cycle totals (options flow). Daily and monthly are always on; these
# are opt-in to keep the entity count in check (ADR-0004 / PLAN.md).
CONF_CYCLE_WEEKLY: Final = "cycle_weekly"
CONF_CYCLE_QUARTERLY: Final = "cycle_quarterly"
CONF_CYCLE_YEARLY: Final = "cycle_yearly"
