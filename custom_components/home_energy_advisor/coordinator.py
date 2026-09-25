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

from homeassistant.components.energy.data import async_get_manager
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_state_report_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import issues
from .accountant_store import AccountantStore, SnapshotStatus
from .const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    CONF_DEVICE_COST_BOUNDS,
    CONF_ENERGY_ENTITY,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    DEFAULT_CURRENCY,
    DOMAIN,
    SIGNAL_RESET_TOTALS,
    SUBENTRY_TYPE_DEVICE,
)
from .engine.accountant import Accountant, SourceRole, Totals
from .engine.energy_source import EnergyUnit
from .source_history import async_has_ever_reported

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from typing import Any

    from homeassistant.core import (
        Event,
        EventStateChangedData,
        EventStateReportedData,
        HomeAssistant,
        State,
    )

    from .engine.accountant import DeviceTotals

_LOGGER = logging.getLogger(__name__)

_FINALIZE_INTERVAL = timedelta(minutes=1)
_UNAVAILABLE = {"unavailable", "unknown"}

# HEA-24 Repairs. A critical input (price or a house-level source) may be gone
# this long before a Repair is raised - long enough to ride out restarts and brief
# outages, short enough to surface a genuinely dead sensor the same day.
_UNAVAILABLE_GRACE = timedelta(hours=1)
# How far the published totals may sit above the metered house before the
# household is told. Calibrated rather than chosen: replaying 72 h of real
# readings forgives nothing at all, and drifting those same readings through a
# synthetic over-read gives 0.01 % at 1 %, 0.17 % at 10 % and 0.61 % at 25 %. One
# percent is therefore far outside anything reporting latency produces, and needs
# roughly a 30-40 % over-read to reach - egregious, which is the bar a Repair
# nobody can act on has to clear (HEA-69, HEA-82).
_UNRECONCILED_SHARE_LIMIT = Decimal("0.01")

# Where the scale-change Repair sends a household for the full instructions.
# The Repair itself stays short: the fix is a template sensor, and a YAML
# snippet inside a notification is a thing people paste without reading - which
# on a scale problem means getting the direction wrong and being out by a
# hundred rather than by ten (HEA-159).
_SCALE_HELP_URL = (
    "https://github.com/consultingtedds/ha-home-energy-advisor"
    "/blob/main/docs/troubleshooting.md#a-device-paused-after-its-firmware-updated"
)

_ROLE_BY_CONF: dict[str, SourceRole] = {
    CONF_GRID_IMPORT_ENTITY: SourceRole.GRID_IMPORT,
    CONF_GRID_EXPORT_ENTITY: SourceRole.GRID_EXPORT,
    CONF_GENERATION_ENTITY: SourceRole.GENERATION,
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
        # auto-created helper outputs of power-only devices are excluded - their
        # health is the helper's concern (surfaced via the helper-recreated Repair).
        helper_outputs = set((power_energy_entities or {}).values())
        self._critical_entities = {*house_sources.values(), self._price_entity}
        self._monitored_entities = self._critical_entities | (
            set(self._device_of_entity) - helper_outputs
        )
        self._unhealthy_since: dict[str, datetime] = {}
        self._input_issues: dict[str, str] = {}
        # HEA-69. Device sources are watched for one thing device unavailability
        # deliberately does not cover: never having reported at all. Helper
        # outputs are included - a power-only device whose power sensor is dead
        # yields a helper that never reports, and the user's loss is identical.
        self._device_sources = set(self._device_of_entity)
        self._reporting_seen: set[str] = set()
        self._silent_since: dict[str, datetime] = {}
        self._history_probed: set[str] = set()
        self._unreconciled_raised = False
        self._implausible_sources: set[str] = set()
        # Inputs whose counter leapt, so the Repair is raised once and cleared once.
        self._refused_steps: frozenset[str] = frozenset()
        # Inputs the engine cannot count because of their unit, and when each
        # first went unit-less, so a reconnection is not mistaken for a fault.
        self._unsupported_units: set[str] = set()
        self._missing_units: set[str] = set()
        self._unitless_since: dict[str, datetime] = {}
        # Inputs whose counter changed the size of unit it reports in.
        self._rescaled_sources: set[str] = set()
        self._devices = devices
        self._accountant = self._new_accountant()
        self._store = AccountantStore(self.hass, entry.entry_id)
        self._restored: Totals | None = None
        self._snapshot_status = SnapshotStatus.ABSENT
        self._snapshot_age: timedelta | None = None

    async def _async_follow_nesting(self) -> None:
        """Take the device hierarchy from the Energy Dashboard, and keep taking it.

        A household describes their wiring once, where Home Assistant already
        asks for it: a device-consumption entry naming the device whose total
        already contains it. Holding a second copy here would be a maintenance
        burden with no case behind it - there is no hierarchy somebody would
        want only in this integration.

        Subscribed rather than read once, so re-nesting in the Energy Dashboard
        reaches the engine without a restart. `async_listen_updates` has **no
        unsubscribe**, so the callback cannot be handed to `async_on_unload` and
        guards on the entry's state instead.

        Failure is swallowed for the same reason the config flow's prefill
        swallows it: a household with no Energy Dashboard configured is
        ordinary, and nesting is an improvement on the figures rather than a
        precondition for them.
        """
        try:
            manager = await async_get_manager(self.hass)
        except Exception:  # noqa: BLE001 - nesting is optional; never block setup
            return
        self._apply_nesting(manager.data)
        manager.async_listen_updates(self._async_nesting_changed)

    async def _async_nesting_changed(self) -> None:
        """Re-read the hierarchy after the household edited the Energy Dashboard."""
        if self._entry.state is not ConfigEntryState.LOADED:
            # The listener outlives the entry, so a reloaded or removed
            # household would otherwise be accounted by a dead coordinator.
            return
        try:
            manager = await async_get_manager(self.hass)
        except Exception:  # noqa: BLE001 - as above; a failed re-read changes nothing
            return
        self._apply_nesting(manager.data)

    def _apply_nesting(self, prefs: Any) -> None:  # noqa: ANN401 - untyped HA prefs
        self._accountant.set_nesting(_nesting_of(prefs, self._device_of_entity))

    def _new_accountant(self) -> Accountant:
        return Accountant(
            house_sources=self._house_sources,
            device_energy_entities=self._devices,
        )

    @property
    def restored(self) -> Totals | None:
        """Totals carried in from the snapshot, or ``None`` on a cold start.

        The sensors read this to work out how much of their restored state the
        engine is already holding, so the two do not both count it.
        """
        return self._restored

    async def _async_restore_accounting(self) -> None:
        """Carry the previous run's accounting in, if there is any to trust.

        The store checks that a snapshot is present, stamped and recent; only
        the engine can say whether it is *shaped* right. A snapshot written by a
        build that keyed the state differently would raise here, so the engine
        gets a fresh accountant and the household loses one restart's accounting
        rather than the integration failing to start.
        """
        loaded = await self._store.async_load(now=dt_util.utcnow())
        self._snapshot_status = loaded.status
        self._snapshot_age = loaded.age
        if loaded.state is None:
            return
        try:
            self._accountant.restore(loaded.state)
        except KeyError, TypeError, ValueError, InvalidOperation:
            _LOGGER.warning(
                "Ignoring an accounting snapshot this version cannot read; "
                "accounting resumes from the sensors' restored totals"
            )
            self._accountant = self._new_accountant()
            self._snapshot_status = SnapshotStatus.INCOMPATIBLE
            return
        self._restored = self._accountant.totals()

    async def async_start(self) -> None:
        """Restore, baseline current states, subscribe, and start the timer."""
        await self._async_restore_accounting()
        await self._async_follow_nesting()
        self._adopt_standing_accusations()
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
        # Polled integrations (aircon ~1/min, Tuya cloud) re-report an unchanged
        # counter between its rare steps. Tracking those reports advances each
        # source's last-seen time, so when the counter finally moves the delta spans
        # only the poll interval rather than the whole quiet stretch - keeping late
        # portions few and shallow (HEA-48 / ADR-0006). Price is not tracked here:
        # its unchanged re-reports carry no new information.
        self._entry.async_on_unload(
            async_track_state_report_event(
                self.hass, list(self._energy_entities), self._handle_state_report
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
    def _handle_state_report(self, event: Event[EventStateReportedData]) -> None:
        self._feed_energy(event.data["entity_id"], event.data["new_state"])

    @callback
    def async_flush(self) -> None:
        """Seal in-flight accounting and publish once, before the entry unloads.

        A reload - restart, or any options/config change - otherwise discards up to
        ~20 min of unfinalised buckets. Finalising them here and publishing while
        the sensors still exist lets each RestoreSensor bank the totals into its
        restore baseline on removal, so nothing is lost across the reload (HEA-53).
        """
        self._accountant.flush(dt_util.utcnow())
        self.async_set_updated_data(self._accountant.totals())

    @callback
    def async_reset_totals(self) -> None:
        """Rebases this household's accumulated totals to zero (HEA-57).

        Both halves are needed. Clearing only the engine's running totals leaves
        every sensor reading the restore baseline it adds on top; clearing only
        the baselines leaves the current run to be re-added on the next publish.
        The signal goes out before the publish so the sensors are already rebased
        when they recompute.
        """
        self._accountant.reset_totals()
        async_dispatcher_send(
            self.hass, SIGNAL_RESET_TOTALS.format(entry_id=self._entry.entry_id)
        )
        self.async_set_updated_data(self._accountant.totals())

    @callback
    def _handle_tick(self, now: datetime) -> None:
        self._accountant.finalize(now)
        self._check_input_health(now)
        self._check_sources_ever_reported(now)
        self._check_remainder_health()
        self._check_source_plausibility()
        self._check_refused_steps()
        self._check_rescaled_sources()
        self._check_source_units(now)
        self.async_set_updated_data(self._accountant.totals())
        self._store.async_schedule_save(
            self._accountant.snapshot, now_func=dt_util.utcnow
        )

    def _check_sources_ever_reported(self, now: datetime) -> None:
        """Name, in Repairs, a device source that has never produced a reading.

        A device configured against a source that never reports accumulates
        nothing and shows zero indefinitely, which reads as a quiet appliance
        rather than a misconfiguration (HEA-69).

        Silence alone is not evidence: a seasonal device is legitimately off for
        months, and HEA-24 settled that device unavailability must never raise a
        Repair. Only a source that has *never* reported qualifies, and for one
        already configured before this run began, the recorder settles it.
        """
        for entity in self._device_sources:
            if self._is_reporting(entity):
                self._mark_source_reporting(entity)
            elif self._is_silent_past_grace(entity, now):
                self._probe_source_history(entity)

    def _is_reporting(self, entity: str) -> bool:
        return (state := self.hass.states.get(entity)) is not None and (
            state.state not in _UNAVAILABLE
        )

    def _mark_source_reporting(self, entity: str) -> None:
        """Record the first reading seen this run, and retract any accusation.

        Clearing runs on that first reading rather than only when this run raised
        the issue, so a Repair left standing by a previous run is retracted too.
        """
        if entity in self._reporting_seen:
            return
        self._reporting_seen.add(entity)
        self._silent_since.pop(entity, None)
        issues.async_clear(self.hass, issues.source_never_reported_issue_id(entity))

    def _is_silent_past_grace(self, entity: str, now: datetime) -> bool:
        """Whether a never-yet-seen source has been silent long enough to ask."""
        if entity in self._reporting_seen:
            return False
        # Timed from the first tick of this run, not from the state's own
        # timestamps: a source that has never reported has nothing to measure
        # from, and restarting the clock each run only ever delays the question.
        since = self._silent_since.setdefault(entity, now)
        return now - since >= _UNAVAILABLE_GRACE

    def _probe_source_history(self, entity: str) -> None:
        """Ask the recorder, once per source, whether it ever worked."""
        if entity in self._history_probed:
            return
        self._history_probed.add(entity)
        self._entry.async_create_background_task(
            self.hass,
            self._async_judge_silent_source(entity),
            f"{DOMAIN}_history_{entity}",
        )

    async def _async_judge_silent_source(self, entity: str) -> None:
        """Raise the Repair only for a source with no history to speak for it.

        An unanswerable question - no recorder - is not evidence, so it is
        treated the same as history found: say nothing. Wrongly accusing a
        working sensor costs more than staying quiet about a broken one.
        """
        if await async_has_ever_reported(self.hass, entity) is not False:
            return
        issues.async_raise(
            self.hass,
            issues.source_never_reported_issue_id(entity),
            issues.ISSUE_SOURCE_NEVER_REPORTED,
            {
                "entity_id": entity,
                "name": self._device_name(self._device_of_entity[entity]),
            },
        )

    def _adopt_standing_accusations(self) -> None:
        """Take over the Repairs a previous run raised and has not withdrawn.

        Both checks below retract by comparing what they found against what they
        raised, and both would otherwise start each run believing they had raised
        nothing - leaving a household who deleted the device or repointed the
        sensor with a permanent accusation about neither (HEA-146).
        """
        self._implausible_sources = issues.async_raised_subjects(
            self.hass, issues.ISSUE_IMPLAUSIBLE_SOURCE
        )
        self._refused_steps = frozenset(
            issues.async_raised_subjects(self.hass, issues.ISSUE_IMPLAUSIBLE_STEP)
        )

    def _check_source_plausibility(self) -> None:
        """Name, in Repairs, any device whose source is claiming the impossible.

        The engine has already stopped booking that energy (HEA-60); this is the
        half that tells the user, because a device silently frozen at a stale
        figure is exactly the kind of quiet wrongness the product exists to avoid.
        Raised per device so the message can name the one to go and look at.

        A device that is no longer configured is passed over. Deleting one from
        its device page removes the subentry and reloads the entry asynchronously,
        so this can run against a device that has already gone - and the only
        name left to call it by is its subentry id, which means nothing to the
        household and names nothing they can open (HEA-146).
        """
        implausible = {
            self._device_name(device)
            for device in self._accountant.implausible_devices()
            if device in self._entry.subentries
        }
        for name in implausible - self._implausible_sources:
            issues.async_raise(
                self.hass,
                issues.implausible_source_issue_id(name),
                issues.ISSUE_IMPLAUSIBLE_SOURCE,
                {"name": name},
            )
        for name in self._implausible_sources - implausible:
            issues.async_clear(self.hass, issues.implausible_source_issue_id(name))
        self._implausible_sources = implausible

    def _check_refused_steps(self) -> None:
        """Name, in Repairs, any input whose counter leapt and was refused.

        The engine has already declined to book it (HEA-137); this is the half
        that says so. A household who replaced a sensor sees why their figures
        did not move, and one whose site genuinely draws past the limit learns
        that it does - which is the only way that case ever reaches us.
        """
        refused = self._accountant.refused_steps()
        for entity in refused - self._refused_steps:
            issues.async_raise(
                self.hass,
                issues.implausible_step_issue_id(entity),
                issues.ISSUE_IMPLAUSIBLE_STEP,
                {"entity_id": entity},
            )
        for entity in self._refused_steps - refused:
            issues.async_clear(self.hass, issues.implausible_step_issue_id(entity))
        self._refused_steps = refused

    def _check_rescaled_sources(self) -> None:
        """Name an input whose counter changed the scale it reports in (HEA-159).

        The engine has refused the step, so the figures are safe; this says what
        happened, because the Repair beside it - "reporting more energy than the
        whole house" - is true and sends the household to look at the wrong
        thing. What they need to know is that a firmware update changed the size
        of the unit their counter reports in.

        It says the factor and **not** which way to correct it. The direction is
        not the answer: the reference instance's plugs were multiplied by ten on
        one day and divided by ten four days later, and the second change was the
        vendor putting it *right*. Identical evidence, opposite conclusions - so
        the household, who can see the appliance and its rating, decides.
        """
        rescaled = self._accountant.rescaled_sources()
        for entity, change in rescaled.items():
            if entity in self._rescaled_sources:
                continue
            issues.async_raise(
                self.hass,
                issues.rescaled_source_issue_id(entity),
                issues.ISSUE_RESCALED_SOURCE,
                {
                    "entity_id": entity,
                    # Whole, because every factor worth naming is a power of
                    # ten. Trimming trailing zeros instead turns "10" into "1".
                    "factor": f"{change.factor:.0f}",
                },
                learn_more_url=_SCALE_HELP_URL,
            )
        for entity in self._rescaled_sources - set(rescaled):
            issues.async_clear(self.hass, issues.rescaled_source_issue_id(entity))
        self._rescaled_sources = set(rescaled)

    def _check_source_units(self, now: datetime) -> None:
        """Name, in Repairs, an input whose unit stops it being counted (HEA-156).

        The engine has already refused those readings (HEA-149), which is safe
        and entirely silent: the device sits at zero for ever, its energy falls
        into the Untracked remainder, and the household's figures are short by
        it with nothing anywhere saying why. This is the half that says so.

        Two situations, told apart because their remedies and their timing
        differ:

        * **A stated unit the engine cannot convert** - megawatt hours, joules.
          Knowable the moment it is reported and it will never improve on its
          own, so waiting would be an hour of silence for nothing.
        * **No unit at all.** Every source looks like this while its integration
          reconnects, which is precisely the case HEA-149 exists to tolerate, so
          it gets the same grace an unavailable input gets. A Repair that fires
          on every reconnection is one a household learns to dismiss (HEA-24).

        An *unavailable* sensor is passed over entirely. It carries no unit
        either, but silence is not a mislabelled unit, and device unavailability
        never raises a Repair at all (HEA-24).
        """
        unsupported: set[str] = set()
        missing: set[str] = set()
        for entity in self._energy_entities:
            fault = self._unit_fault(entity, now)
            if fault is issues.ISSUE_SOURCE_UNIT_UNSUPPORTED:
                unsupported.add(entity)
            elif fault is issues.ISSUE_SOURCE_UNIT_MISSING:
                missing.add(entity)
        self._reconcile_unit_issues(unsupported, missing)

    def _unit_fault(self, entity: str, now: datetime) -> str | None:
        """Which unit fault this input warrants now, or ``None`` for none.

        Also keeps the unit-less clock: it starts when a reading is first *seen*
        without one and is dropped the moment the sensor recovers, so a source
        that flaps in and out never accumulates its way to an accusation.
        """
        state = self.hass.states.get(entity)
        if state is None or state.state in _UNAVAILABLE:
            self._unitless_since.pop(entity, None)
            return None
        if _unit_of(state) is not EnergyUnit.UNKNOWN:
            self._unitless_since.pop(entity, None)
            return None
        if _stated_unit(state):
            self._unitless_since.pop(entity, None)
            return issues.ISSUE_SOURCE_UNIT_UNSUPPORTED
        since = self._unitless_since.setdefault(entity, now)
        if now - since < _UNAVAILABLE_GRACE:
            return None
        return issues.ISSUE_SOURCE_UNIT_MISSING

    def _reconcile_unit_issues(self, unsupported: set[str], missing: set[str]) -> None:
        """Raise what is newly true and withdraw what no longer is (HEA-146)."""
        for entity in unsupported - self._unsupported_units:
            state = self.hass.states.get(entity)
            issues.async_raise(
                self.hass,
                issues.source_unit_unsupported_issue_id(entity),
                issues.ISSUE_SOURCE_UNIT_UNSUPPORTED,
                {"entity_id": entity, "unit": _stated_unit(state) if state else ""},
            )
        for entity in self._unsupported_units - unsupported:
            issues.async_clear(
                self.hass, issues.source_unit_unsupported_issue_id(entity)
            )
        for entity in missing - self._missing_units:
            issues.async_raise(
                self.hass,
                issues.source_unit_missing_issue_id(entity),
                issues.ISSUE_SOURCE_UNIT_MISSING,
                {"entity_id": entity},
            )
        for entity in self._missing_units - missing:
            issues.async_clear(self.hass, issues.source_unit_missing_issue_id(entity))
        self._unsupported_units = unsupported
        self._missing_units = missing

    def _check_input_health(self, now: datetime) -> None:
        """Raise or clear the source/price Repairs from each input's health."""
        for entity in self._monitored_entities:
            self._reconcile_input_issue(entity, self._pending_issue(entity, now))

    def _pending_issue(self, entity: str, now: datetime) -> tuple[str, str] | None:
        """The (issue_id, translation_key) an input warrants now, or ``None``.

        ``None`` means healthy, or not yet past the grace period - either way no
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
        # A removed entity has no state, so no onset timestamp - track from the
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
        """Raise or clear the Repair for totals that never reconcile (HEA-82).

        Judged on energy the house meters never accounted for, not on over-drawn
        buckets: since the carry landed those are ordinary coarse-counter timing,
        absorbed and repaid within the quiet span. What survives that is the
        household's own meters disagreeing, and it is the only thing that can now
        lift the published total above the meter.

        Both raising and clearing follow the same figure, so a household that
        fixes a double-counted sensor sees this go away on its own: the forgiven
        total stops growing while good energy keeps accumulating beneath it.
        """
        share = self._accountant.unreconciled_share()
        egregious = share >= _UNRECONCILED_SHARE_LIMIT
        if egregious and not self._unreconciled_raised:
            issues.async_raise(
                self.hass,
                issues.ISSUE_UNRECONCILED_ENERGY,
                issues.ISSUE_UNRECONCILED_ENERGY,
                {"share": f"{share:.1%}"},
            )
            self._unreconciled_raised = True
        elif not egregious and self._unreconciled_raised:
            issues.async_clear(self.hass, issues.ISSUE_UNRECONCILED_ENERGY)
            self._unreconciled_raised = False

    def _feed_energy(self, entity_id: str, state: State | None) -> None:
        if state is None:
            return
        value = None if state.state in _UNAVAILABLE else _to_decimal(state.state)
        # ``last_reported`` (every write), not ``last_updated`` (only on change), so
        # an unchanged re-report still advances the source's last-seen time and
        # shrinks the next delta's span (HEA-48). They coincide on a real change.
        self._accountant.observe(entity_id, state.last_reported, value, _unit_of(state))

    def _feed_price(self, state: State | None) -> None:
        if state is None or state.state in _UNAVAILABLE:
            return
        price = _to_decimal(state.state)
        if price is not None:
            self._accountant.record_price(state.last_updated, price)

    def is_warming_up(self) -> bool:
        """Whether the engine is counting but has not yet closed an interval.

        True for roughly the first twenty minutes of a runtime's life. On its own
        that is not enough to tell a first install from a routine restart - the
        accountant is rebuilt from nothing every startup, so a household with
        months of history passes through this state too. The sensors pair it with
        their own restored baseline to tell the two apart (HEA-47).
        """
        return not self._accountant.has_finalised()

    @property
    def settled_until(self) -> datetime | None:
        """The instant up to which every published figure is complete (HEA-140).

        Read by the devices sensor and drawn on by the cards, so a household can
        tell a finished hour from one still filling rather than reading the
        difference as a disagreement with the Energy Dashboard.
        """
        return self._accountant.settled_until()

    def diagnostics(self) -> dict[str, Any]:
        """Assemble the diagnostics download (HEA-24) as JSON-safe primitives.

        Joins the entry configuration, the engine's per-source accumulator state
        and decision log, the battery's stored-cost ledger, the house energy
        still awaiting the counterpart that explains it, and the running totals -
        everything needed to explain any published figure without a live
        instance.
        """
        return {
            "config": self._config_diagnostics(),
            "sources": self._source_diagnostics(),
            "battery": self._accountant.battery_diagnostics(),
            "balance": self._accountant.balance_diagnostics(),
            "snapshot": self._snapshot_diagnostics(),
            "totals": self._totals_diagnostics(),
        }

    def _snapshot_diagnostics(self) -> dict[str, Any]:
        """Whether this run carried the previous one's accounting, and why not.

        A run that started cold prices battery discharge at zero until the
        stored-cost ledger refills, and holds no open buckets from before the
        restart. Both change what the figures say, so the download has to name
        the cause rather than leave them unaccountable.
        """
        return {
            "status": str(self._snapshot_status),
            "age_seconds": (
                None
                if self._snapshot_age is None
                else self._snapshot_age.total_seconds()
            ),
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
            "device_cost_bounds": bool(options.get(CONF_DEVICE_COST_BOUNDS)),
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
            "whole_home": _totals_to_dict(totals.whole_home),
        }

    def _device_name(self, sub_id: str) -> str:
        subentry = self._entry.subentries.get(sub_id)
        return subentry.title if subentry is not None else sub_id


def _nesting_of(prefs: Any, device_of_entity: Mapping[str, str]) -> dict[str, str]:  # noqa: ANN401 - untyped Energy Dashboard preference structure
    """Which tracked device sits inside which, per the Energy Dashboard.

    A `device_consumption` entry carries `included_in_stat`: the statistic id of
    the device whose total already contains this one. For an entity-backed
    sensor a statistic id *is* the entity id, which is what lets it be matched
    to our own devices at all.

    Both ends have to be tracked by us. A child whose parent we do not track has
    no double count to remove - its energy is inside a counter nobody is
    reading - and a link to a device we have never heard of is simply not ours
    to act on. Either way the pair is skipped, which leaves today's behaviour
    rather than a guess.

    A device declared inside itself is dropped too: nothing in Home Assistant
    forbids it through the websocket API, and netting a device against itself
    would erase it.
    """
    nesting: dict[str, str] = {}
    for entry in prefs.get("device_consumption", []) if prefs else []:
        parent = device_of_entity.get(entry.get("included_in_stat"))
        child = device_of_entity.get(entry.get("stat_consumption"))
        if parent is not None and child is not None and parent != child:
            nesting[child] = parent
    return nesting


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw)
    except InvalidOperation, ValueError:
        return None


def _stated_unit(state: State) -> str:
    """The unit the sensor claims, or the empty string if it claims none.

    Distinct from :func:`_unit_of`, which answers what the engine can *count*
    in. A sensor reporting megawatt hours and one reporting nothing at all are
    both uncountable, but only the first has said something - and a household
    can act on being told which unit was refused (HEA-156).
    """
    unit = state.attributes.get("unit_of_measurement")
    return unit.strip() if isinstance(unit, str) else ""


def _unit_of(state: State) -> EnergyUnit:
    """What this reading counts in, or ``UNKNOWN`` where the state cannot say.

    Read from every state rather than once at startup. A sensor that has not
    reconnected yet carries no unit at all, and a counter whose firmware changed
    carries a different one from the day before - a source told its unit once
    is wrong in both cases and has no way of finding out (GitHub #24, HEA-149).

    Anything other than the two units the engine counts in reads as unknown, so
    a source reporting megawatt hours is left uncounted rather than counted as a
    thousandth of itself. Both are silent; only one of them is wrong.
    """
    unit = state.attributes.get("unit_of_measurement")
    if not isinstance(unit, str):
        return EnergyUnit.UNKNOWN
    return _ENERGY_UNITS.get(unit.strip().lower(), EnergyUnit.UNKNOWN)


# Keyed on the lowered unit, because a household's integration may write "WH",
# "Wh" or "wh" and all three are the same unit.
_ENERGY_UNITS = {
    "wh": EnergyUnit.WH,
    "kwh": EnergyUnit.KWH,
}


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
        "energy_from_grid": str(totals.energy_from_grid),
        "energy_from_generation": str(totals.energy_from_generation),
        "energy_from_battery": str(totals.energy_from_battery),
        # Always here, whether or not this household publishes them as sensors:
        # a figure that fails to sit inside its own bounds is the first thing to
        # look for when a cost is disputed (ADR-0016).
        "cost_floor": str(totals.cost_floor),
        "cost_ceiling": str(totals.cost_ceiling),
    }
