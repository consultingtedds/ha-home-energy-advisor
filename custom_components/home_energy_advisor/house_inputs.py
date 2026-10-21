"""Reading the house-level inputs out of a config entry."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_NAME

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_FIXED_PRICE,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_GRID,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry


def house_entities(data: Mapping[str, Any], key: str) -> tuple[str, ...]:
    """The meters configured under one house input, none if it is unset.

    Generation holds a list - Home Assistant's Energy Dashboard takes any number
    of solar sources, so a household with two arrays has two meters (HEA-219) -
    and every other input holds one entity id. Reading both through here means
    no caller has to know which is which.
    """
    value = data.get(key)
    if not value:
        return ()
    return (value,) if isinstance(value, str) else tuple(value)


@dataclass(frozen=True)
class Battery:
    """One battery, in the shape of Home Assistant's battery system (ADR-0031)."""

    name: str
    charge: str | None
    discharge: str | None
    level: str | None
    capacity: Decimal | None

    @property
    def knows_its_contents(self) -> bool:
        """Whether its level can be turned into kWh: a percentage needs a capacity."""
        return self.level is not None and self.capacity is not None


def batteries_of(entry: ConfigEntry) -> dict[str, Battery]:
    """Every battery the household has entered, keyed by its subentry id."""
    return {
        subentry_id: battery_from(subentry.title, subentry.data)
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_BATTERY
    }


def battery_from(name: str, data: Mapping[str, Any]) -> Battery:
    """A battery from what its entry holds."""
    return Battery(
        name=data.get(CONF_NAME) or name,
        charge=data.get(CONF_BATTERY_CHARGE_ENTITY) or None,
        discharge=data.get(CONF_BATTERY_DISCHARGE_ENTITY) or None,
        level=data.get(CONF_BATTERY_SOC_ENTITY) or None,
        capacity=_decimal(data.get(CONF_BATTERY_CAPACITY_KWH)),
    )


def battery_meters(entry: ConfigEntry, key: str) -> tuple[str, ...]:
    """Every battery's meter of one kind - charge or discharge - in entry order.

    The pool's meters for the house balance, which adds them up as it adds up
    several generation meters (HEA-219).
    """
    field = {
        CONF_BATTERY_CHARGE_ENTITY: "charge",
        CONF_BATTERY_DISCHARGE_ENTITY: "discharge",
    }[key]
    return tuple(
        meter
        for battery in batteries_of(entry).values()
        if (meter := getattr(battery, field)) is not None
    )


@dataclass(frozen=True)
class GridMeter:
    """One grid source, in the shape of the Energy Dashboard's (ADR-0032).

    Its import is priced at an entity's state or at a fixed number, whichever
    the household gave; the form takes exactly one.
    """

    name: str
    imported: str
    price_entity: str | None
    fixed_price: Decimal | None
    exported: str | None


def grid_meters_of(entry: ConfigEntry) -> dict[str, GridMeter]:
    """Every grid source the household has entered, keyed by its subentry id."""
    return {
        subentry_id: grid_meter_from(subentry.title, subentry.data)
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_GRID
    }


def grid_meter_from(name: str, data: Mapping[str, Any]) -> GridMeter:
    """A grid source from what its entry holds."""
    return GridMeter(
        name=data.get(CONF_NAME) or name,
        imported=data[CONF_GRID_IMPORT_ENTITY],
        price_entity=data.get(CONF_PRICE_ENTITY) or None,
        fixed_price=_decimal(data.get(CONF_FIXED_PRICE)),
        exported=data.get(CONF_GRID_EXPORT_ENTITY) or None,
    )


def grid_meters(entry: ConfigEntry, key: str) -> tuple[str, ...]:
    """Every grid source's meter of one kind - import or export - in entry order.

    Added up into the house balance, as several generation meters are
    (HEA-219); import is priced register by register on top of that.
    """
    field = {
        CONF_GRID_IMPORT_ENTITY: "imported",
        CONF_GRID_EXPORT_ENTITY: "exported",
    }[key]
    return tuple(
        meter
        for grid in grid_meters_of(entry).values()
        if (meter := getattr(grid, field)) is not None
    )


def _decimal(raw: object) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None
