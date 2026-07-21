"""Runtime coordinator: wires the HA state machine to the accounting runtime.

Feeds every configured meter's state changes into a pure-Python ``Accountant``
(HEA-21 stage A), finalises completed intervals on a timer, and publishes the
per-device running totals as the coordinator data the sensors (HEA-22) read.

The coordinator is push-mode: it never polls. State-change events and the
finalisation timer drive ``async_set_updated_data``. Config changes are picked up
by the config entry reloading (the reconfigure/options flows request it), which
rebuilds the coordinator from scratch.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from .engine.accountant import Accountant, SourceRole, Totals
from .engine.energy_source import EnergyUnit

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State

_LOGGER = logging.getLogger(__name__)

_FINALIZE_INTERVAL = timedelta(minutes=1)
_UNAVAILABLE = {"unavailable", "unknown"}

_ROLE_BY_CONF: dict[str, SourceRole] = {
    CONF_GRID_IMPORT_ENTITY: SourceRole.GRID_IMPORT,
    CONF_GRID_EXPORT_ENTITY: SourceRole.GRID_EXPORT,
    CONF_SOLAR_ENTITY: SourceRole.SOLAR,
    CONF_BATTERY_CHARGE_ENTITY: SourceRole.BATTERY_CHARGE,
    CONF_BATTERY_DISCHARGE_ENTITY: SourceRole.BATTERY_DISCHARGE,
    CONF_HOUSE_CONSUMPTION_ENTITY: SourceRole.HOUSE_CONSUMPTION,
}

type HeaConfigEntry = ConfigEntry[HeaCoordinator]


class HeaCoordinator(DataUpdateCoordinator[Totals]):
    """Drives the accounting runtime from Home Assistant state changes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HeaConfigEntry,
        *,
        power_energy_entities: dict[str, str] | None = None,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self._entry = entry
        self._price_entity = entry.data[CONF_PRICE_ENTITY]
        house_sources = {
            role: entry.data[conf]
            for conf, role in _ROLE_BY_CONF.items()
            if entry.data.get(conf)
        }
        devices = {
            subentry_id: subentry.data[CONF_ENERGY_ENTITY]
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
            and CONF_ENERGY_ENTITY in subentry.data
        }
        # Power-only devices reach the same pipeline through the energy sensor of
        # an auto-created native Integral helper (ADR-0004 / HEA-34).
        devices.update(power_energy_entities or {})
        self._energy_entities = {*house_sources.values(), *devices.values()}
        self._accountant = Accountant(
            house_sources=house_sources,
            device_energy_entities=devices,
            units=self._read_units(),
        )

    async def async_start(self) -> None:
        """Baseline current states, subscribe to changes, and start the timer."""
        for entity_id in self._energy_entities:
            self._feed_energy(entity_id, self.hass.states.get(entity_id))
        self._feed_price(self.hass.states.get(self._price_entity))

        self._entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                [*self._energy_entities, self._price_entity],
                self._handle_state_change,
            )
        )
        self._entry.async_on_unload(
            async_track_time_interval(self.hass, self._handle_tick, _FINALIZE_INTERVAL)
        )
        self.async_set_updated_data(self._accountant.totals())

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        state = event.data["new_state"]
        if entity_id == self._price_entity:
            self._feed_price(state)
        else:
            self._feed_energy(entity_id, state)

    @callback
    def _handle_tick(self, now: datetime) -> None:
        self._accountant.finalize(now)
        self.async_set_updated_data(self._accountant.totals())

    def _feed_energy(self, entity_id: str, state: State | None) -> None:
        if state is None:
            return
        value = None if state.state in _UNAVAILABLE else _to_decimal(state.state)
        self._accountant.observe(entity_id, state.last_updated, value)

    def _feed_price(self, state: State | None) -> None:
        if state is None or state.state in _UNAVAILABLE:
            return
        price = _to_decimal(state.state)
        if price is not None:
            self._accountant.record_price(state.last_updated, price)

    def _read_units(self) -> dict[str, EnergyUnit]:
        units: dict[str, EnergyUnit] = {}
        for entity_id in self._energy_entities:
            state = self.hass.states.get(entity_id)
            unit = state and state.attributes.get("unit_of_measurement", "")
            if isinstance(unit, str) and unit.lower() == "wh":
                units[entity_id] = EnergyUnit.WH
        return units


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw)
    except InvalidOperation, ValueError:
        return None
