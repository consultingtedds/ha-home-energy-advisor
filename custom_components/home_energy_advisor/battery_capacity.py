"""Which usable capacity a battery's level is read against (HEA-244, ADR-0035).

One reader, so the coordinator, the engine and the diagnostics see a capacity
and never where it came from. In order:

1. The battery's capacity sensor, where it has one and it reads a capacity:
   positive, finite, and in a unit of energy, converted as the meters are.
2. The last capacity used, while that sensor is silent or reads something that
   is not a capacity - a sensor that is unavailable after a restart is not a
   battery that holds nothing.
3. The typed figure.

Otherwise none, and the battery's contents are unknown, as for a level that
cannot be read. Never zero.

The last capacity used stands in only for a sensor. Without one, the typed
figure is the household's answer, and a correction to it takes effect; the
engine revalues the change rather than booking it as a loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING

from .discovery import source_unit
from .engine.energy_source import EnergyUnit, energy_unit, kwh_from

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .house_inputs import Battery


class CapacitySource(StrEnum):
    """Where the capacity in force came from, as the diagnostics name it."""

    SENSOR = "sensor"
    LAST_USED = "last_used"
    TYPED = "typed"


@dataclass(frozen=True)
class Capacity:
    """A battery's usable capacity in kWh, and where it came from."""

    kwh: Decimal
    source: CapacitySource


def capacity_of(
    hass: HomeAssistant, battery: Battery, last_used: Decimal | None
) -> Capacity | None:
    """The capacity a battery's level is a percentage of, just now."""
    if battery.capacity_entity is not None:
        sensed = _sensed_capacity(hass, battery.capacity_entity)
        if sensed is not None:
            return Capacity(sensed, CapacitySource.SENSOR)
        if last_used is not None:
            return Capacity(last_used, CapacitySource.LAST_USED)
    if battery.capacity is not None:
        return Capacity(battery.capacity, CapacitySource.TYPED)
    return None


def _sensed_capacity(hass: HomeAssistant, entity_id: str) -> Decimal | None:
    """What a capacity sensor reads in kWh, or ``None`` where it is no capacity.

    A reading without a unit is refused rather than taken as kWh: a capacity a
    thousand times out would write the ledger down to almost nothing (HEA-227).
    """
    state = hass.states.get(entity_id)
    if state is None:
        return None
    try:
        value = Decimal(state.state)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    symbol = source_unit(hass, entity_id)
    unit = EnergyUnit.UNKNOWN if symbol is None else energy_unit(symbol)
    if unit is EnergyUnit.UNKNOWN:
        return None
    return kwh_from(value, unit)
