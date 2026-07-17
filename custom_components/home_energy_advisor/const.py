"""Constants for the Home Energy Advisor integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "home_energy_advisor"

# House-level configuration — global, one set per household (ADR-0002).
CONF_PRICE_ENTITY: Final = "price_entity"
CONF_CURRENCY: Final = "currency"
CONF_GRID_IMPORT_ENTITY: Final = "grid_import_entity"
CONF_SOLAR_ENTITY: Final = "solar_entity"
CONF_BATTERY_CHARGE_ENTITY: Final = "battery_charge_entity"
CONF_BATTERY_DISCHARGE_ENTITY: Final = "battery_discharge_entity"
CONF_HOUSE_CONSUMPTION_ENTITY: Final = "house_consumption_entity"

DEFAULT_CURRENCY: Final = "EUR"
