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

from . import issues
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
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DEFAULT_CURRENCY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from .engine.accountant import Accountant, SourceRole, Totals
from .engine.energy_source import EnergyUnit

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Any

    from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State

    from .engine.accountant import DeviceTotals

_LOGGER = logging.getLogger(__name__)

_FINALIZE_INTERVAL = timedelta(minutes=1)
_UNAVAILABLE = {"unavailable", "unknown"}

# HEA-24 Repairs. A critical input (price or a house-level source) may be gone
# this long before a Repair is raised — long enough to ride out restarts and brief
# outages, short enough to surface a genuinely dead sensor the same day.
_UNAVAILABLE_GRACE = timedelta(hours=1)
# Consecutive over-drawn 5-minute buckets (~one hour) before the persistent
# negative-remainder Repair is raised.
_OVERDRAWN_BUCKET_LIMIT = 12

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
        # Reverse maps label each observed meter for the diagnostics download.
        self._role_of_entity = {entity: role for role, entity in house_sources.items()}
        self._device_of_entity = {entity: sub for sub, entity in devices.items()}
        self._house_sources = house_sources
        # Repairs health monitoring (HEA-24). Critical inputs (price + house-level
        # sources) raise a Repair when unavailable past the grace period; any
        # configured entity does when it leaves Home Assistant entirely. The
        # auto-created helper outputs of power-only devices are excluded — their
        # health is the helper's concern (surfaced via the helper-recreated Repair).
        helper_outputs = set((power_energy_entities or {}).values())
        self._critical_entities = {*house_sources.values(), self._price_entity}
        self._monitored_entities = self._critical_entities | (
            set(self._device_of_entity) - helper_outputs
        )
        self._unhealthy_since: dict[str, datetime] = {}
        self._input_issues: dict[str, str] = {}
        self._negative_remainder_raised = False
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
        self._check_input_health(now)
        self._check_remainder_health()
        self.async_set_updated_data(self._accountant.totals())

    def _check_input_health(self, now: datetime) -> None:
        """Raise or clear the source/price Repairs from each input's health."""
        for entity in self._monitored_entities:
            self._reconcile_input_issue(entity, self._pending_issue(entity, now))

    def _pending_issue(self, entity: str, now: datetime) -> tuple[str, str] | None:
        """The (issue_id, translation_key) an input warrants now, or ``None``.

        ``None`` means healthy, or not yet past the grace period — either way no
        issue should stand.
        """
        state = self.hass.states.get(entity)
        if state is None:
            return self._removed_issue(entity, now)
        self._unhealthy_since.pop(entity, None)
        if state.state in _UNAVAILABLE and entity in self._critical_entities:
            return self._unavailable_issue(entity, state, now)
        return None

    def _removed_issue(self, entity: str, now: datetime) -> tuple[str, str] | None:
        # A removed entity has no state, so no onset timestamp — track from the
        # first tick that sees it gone and let the grace period ride out restarts.
        since = self._unhealthy_since.setdefault(entity, now)
        if now - since < _UNAVAILABLE_GRACE:
            return None
        return (issues.source_removed_issue_id(entity), issues.ISSUE_SOURCE_REMOVED)

    def _unavailable_issue(
        self, entity: str, state: State, now: datetime
    ) -> tuple[str, str] | None:
        # Measure the outage from when the state actually went unavailable, so a
        # missed tick or a restart cannot reset the clock.
        if now - state.last_changed < _UNAVAILABLE_GRACE:
            return None
        if entity == self._price_entity:
            return (issues.ISSUE_PRICE_UNAVAILABLE, issues.ISSUE_PRICE_UNAVAILABLE)
        return (
            issues.source_unavailable_issue_id(entity),
            issues.ISSUE_SOURCE_UNAVAILABLE,
        )

    def _reconcile_input_issue(
        self, entity: str, pending: tuple[str, str] | None
    ) -> None:
        """Drive the issue registry to match the entity's pending issue, if any."""
        current = self._input_issues.get(entity)
        desired = pending[0] if pending is not None else None
        if desired == current:
            return
        if current is not None:
            issues.async_clear(self.hass, current)
        if pending is not None:
            issue_id, translation_key = pending
            issues.async_raise(
                self.hass, issue_id, translation_key, {"entity_id": entity}
            )
            self._input_issues[entity] = issue_id
        else:
            self._input_issues.pop(entity, None)

    def _check_remainder_health(self) -> None:
        """Raise or clear the persistent negative-remainder Repair (HEA-36)."""
        overdrawn = self._accountant.consecutive_overdrawn_buckets()
        if overdrawn >= _OVERDRAWN_BUCKET_LIMIT and not self._negative_remainder_raised:
            issues.async_raise(
                self.hass,
                issues.ISSUE_NEGATIVE_REMAINDER,
                issues.ISSUE_NEGATIVE_REMAINDER,
            )
            self._negative_remainder_raised = True
        elif overdrawn == 0 and self._negative_remainder_raised:
            issues.async_clear(self.hass, issues.ISSUE_NEGATIVE_REMAINDER)
            self._negative_remainder_raised = False

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

    def diagnostics(self) -> dict[str, Any]:
        """Assemble the diagnostics download (HEA-24) as JSON-safe primitives.

        Joins the entry configuration, the engine's per-source accumulator state
        and decision log, and the running totals — everything needed to explain
        any published figure without a live instance.
        """
        return {
            "config": self._config_diagnostics(),
            "sources": self._source_diagnostics(),
            "totals": self._totals_diagnostics(),
        }

    def _config_diagnostics(self) -> dict[str, Any]:
        data = self._entry.data
        options = self._entry.options
        # Lists (not entity-keyed dicts) so the diagnostics platform can redact
        # entity ids and device names as field values without key collisions.
        return {
            "price_entity": self._price_entity,
            "currency": data.get(CONF_CURRENCY, DEFAULT_CURRENCY),
            "house_sources": [
                {"role": role.value, "entity": entity}
                for role, entity in self._house_sources.items()
            ],
            "opt_in_cycles": {
                flag: bool(options.get(flag))
                for flag in (
                    CONF_CYCLE_WEEKLY,
                    CONF_CYCLE_QUARTERLY,
                    CONF_CYCLE_YEARLY,
                )
            },
            "devices": [
                {"id": sub_id, "name": self._device_name(sub_id), "entity": entity}
                for entity, sub_id in self._device_of_entity.items()
            ],
        }

    def _source_diagnostics(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for entity, snap in self._accountant.source_diagnostics().items():
            role = self._role_of_entity.get(entity)
            sub_id = self._device_of_entity.get(entity)
            result.append(
                {
                    "entity_id": entity,
                    "role": role.value if role is not None else None,
                    "device_id": sub_id,
                    "device": self._device_name(sub_id) if sub_id is not None else None,
                    "unit": snap.unit.value,
                    "last_value": _stringify(snap.last_value),
                    "last_at": snap.last_at.isoformat() if snap.last_at else None,
                    "decisions": [
                        {
                            "at": decision.at.isoformat(),
                            "reason": decision.reason.value,
                            "kwh": _stringify(decision.kwh),
                        }
                        for decision in snap.recent_decisions
                    ],
                }
            )
        return result

    def _totals_diagnostics(self) -> dict[str, Any]:
        # ``data`` is always populated by ``async_start`` before ``runtime_data``
        # (and so this method) can be reached.
        totals = self.data
        return {
            "devices": {
                sub_id: _totals_to_dict(device)
                for sub_id, device in totals.devices.items()
            },
            "untracked": _totals_to_dict(totals.untracked),
        }

    def _device_name(self, sub_id: str) -> str:
        subentry = self._entry.subentries.get(sub_id)
        return subentry.title if subentry is not None else sub_id


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw)
    except InvalidOperation, ValueError:
        return None


def _stringify(value: Decimal | None) -> str | None:
    """Render a Decimal for diagnostics without losing precision to float."""
    return None if value is None else str(value)


def _totals_to_dict(totals: DeviceTotals) -> dict[str, str]:
    """A device's running figures as strings, safe to serialise verbatim."""
    return {
        "energy_kwh": str(totals.energy_kwh),
        "actual_cost": str(totals.actual_cost),
        "naive_cost": str(totals.naive_cost),
        "cost_savings": str(totals.cost_savings),
    }
