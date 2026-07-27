"""Auto-created native utility_meter cycle totals for per-device sensors (HEA-23).

Per the build-on-foundations decision (ADR-0004), daily/monthly (and opt-in
weekly/quarterly/yearly) cost and energy totals are provided by programmatically
creating native `utility_meter` helpers over the integration's own per-device
sensors — not by reimplementing period-reset logic. Each helper is one
(source sensor x cycle) pair; its output sensor is a terminal figure the user
reads, so nothing here feeds back into the accounting engine.

The creation mechanism is the `SchemaConfigFlowHandler` path proven in HEA-34
(`integral_helper.py`); this module reuses that shape — idempotent create,
ownership tracked on the config entry, reconcile-and-remove on device removal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.components.utility_meter.const import (
    CONF_METER_DELTA_VALUES,
    CONF_METER_NET_CONSUMPTION,
    CONF_METER_OFFSET,
    CONF_METER_PERIODICALLY_RESETTING,
    CONF_METER_TYPE,
    CONF_SOURCE_SENSOR,
    CONF_TARIFFS,
)
from homeassistant.components.utility_meter.const import (
    DOMAIN as UTILITY_METER_DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import translation

from . import issues
from .const import (
    CONF_CYCLE_METERS,
    CONF_CYCLE_QUARTERLY,
    CONF_CYCLE_WEEKLY,
    CONF_CYCLE_YEARLY,
    WHOLE_HOME_KEY,
)
from .helper_ownership import (
    helper_entry_id,
    helper_was_created,
    resolve_provenance,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# Daily and monthly are always created; the longer cycles are opt-in (ADR-0004).
_DEFAULT_CYCLES = ("daily", "monthly")
_OPT_IN_CYCLES = {
    CONF_CYCLE_WEEKLY: "weekly",
    CONF_CYCLE_QUARTERLY: "quarterly",
    CONF_CYCLE_YEARLY: "yearly",
}
# utility_meter's own translated cycle labels live here (built-in, incl. es).
_CYCLE_LABEL_PREFIX = f"component.{UTILITY_METER_DOMAIN}.selector.cycle.options."


async def async_ensure_utility_meter(
    hass: HomeAssistant,
    *,
    name: str,
    source_entity: str,
    cycle: str,
    net_consumption: bool,
) -> str:
    """Create a native utility_meter over ``source_entity`` for ``cycle``.

    Idempotent: an existing meter over the same source and cycle is reused rather
    than duplicated. ``net_consumption`` is set for sources that can fall (the
    Cost Savings figure under battery arbitrage); the lifetime sources never reset
    on their own, so ``periodically_resetting`` is off. Returns the helper's
    config entry id.
    """
    existing = _utility_meter_for(hass, source_entity, cycle)
    if existing is not None:
        await _reconcile_net_consumption(
            hass, existing, net_consumption=net_consumption
        )
        return existing
    result = await hass.config_entries.flow.async_init(
        UTILITY_METER_DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_NAME: name,
            CONF_SOURCE_SENSOR: source_entity,
            CONF_METER_TYPE: cycle,
            CONF_METER_OFFSET: 0,
            CONF_TARIFFS: [],
            CONF_METER_NET_CONSUMPTION: net_consumption,
            CONF_METER_DELTA_VALUES: False,
            CONF_METER_PERIODICALLY_RESETTING: False,
        },
    )
    return result["result"].entry_id


def utility_meter_output_sensor(hass: HomeAssistant, entry_id: str) -> str | None:
    """Return the cycle-total sensor the utility_meter ``entry_id`` publishes."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry_id)
    return entries[0].entity_id if entries else None


async def async_sync_cycle_meters(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reconcile utility_meter helpers to the current device sensors and cycles.

    Runs on every setup (including the reload a device removal triggers), after
    the sensor platform has forwarded so the source entity ids exist. Creates a
    meter for each per-device cost/energy sensor times each enabled cycle, removes
    meters whose source or cycle is gone, and remembers what it owns on the entry.
    """
    cycles = _enabled_cycles(entry)
    sources = _device_cost_sensors(hass, entry)
    desired = {_key(source, cycle) for source in sources for cycle in cycles}
    owned = dict(entry.data.get(CONF_CYCLE_METERS, {}))
    await _remove_orphaned_meters(hass, owned, desired)
    recreated = _any_meter_deleted(hass, owned, desired)
    labels = await _cycle_labels(hass)
    await _ensure_meters(hass, sources, cycles, labels, owned)
    _persist_owned_meters(hass, entry, owned)
    if recreated:
        # One aggregate Repair — a user may delete several cycle meters at once,
        # and one meter per (sensor x cycle) would flood Repairs.
        issues.async_raise(
            hass,
            issues.ISSUE_CYCLE_HELPER_RECREATED,
            issues.ISSUE_CYCLE_HELPER_RECREATED,
        )


def _any_meter_deleted(
    hass: HomeAssistant, owned: dict[str, Any], desired: set[str]
) -> bool:
    """Whether a still-wanted cycle meter's config entry the user deleted is gone."""
    return any(
        key in desired
        and hass.config_entries.async_get_entry(helper_entry_id(record)) is None
        for key, record in owned.items()
    )


def _key(source: str, cycle: str) -> str:
    """Ownership key for a (source sensor, cycle) meter; ``|`` never occurs in ids."""
    return f"{source}|{cycle}"


def _enabled_cycles(entry: ConfigEntry) -> list[str]:
    """The cycles to meter: daily + monthly always, plus any opted-in longer ones."""
    opted_in = [
        cycle for flag, cycle in _OPT_IN_CYCLES.items() if entry.options.get(flag)
    ]
    return [*_DEFAULT_CYCLES, *opted_in]


def _device_cost_sensors(hass: HomeAssistant, entry: ConfigEntry) -> list[str]:
    """Entity ids of the integration's own per-device and Untracked cost sensors.

    A removed device's sensor registry entries linger briefly (they are cleared
    after the reload the removal triggers), so a sensor counts only while its
    subentry is still live — Untracked sensors carry no subentry. Diagnostic
    entities (the hub's devices-registry sensor) are excluded: only the four
    cost/energy figures — which carry no ``entity_category`` — get cycle totals.
    The whole-home aggregate is excluded too: its period totals are the sum of the
    device and Untracked cycle meters and duplicate the Energy Dashboard, so it
    carries lifetime running totals only (HEA-48).
    """
    registry = er.async_get(hass)
    whole_home_prefix = f"{entry.entry_id}_{WHOLE_HOME_KEY}_"
    return sorted(
        entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == "sensor"
        and entity.entity_category is None
        and not (entity.unique_id or "").startswith(whole_home_prefix)
        and (
            entity.config_subentry_id is None
            or entity.config_subentry_id in entry.subentries
        )
    )


async def _remove_orphaned_meters(
    hass: HomeAssistant, owned: dict[str, Any], desired: set[str]
) -> None:
    """Remove meters whose source or cycle is no longer wanted, mutating ``owned``.

    Only meters HEA created are deleted; a utility_meter the user already had over
    the source (adopted) is forgotten but left intact (HEA-52).
    """
    for key, record in list(owned.items()):
        if key not in desired:
            meter_id = helper_entry_id(record)
            if (
                helper_was_created(record)
                and hass.config_entries.async_get_entry(meter_id) is not None
            ):
                await hass.config_entries.async_remove(meter_id)
            del owned[key]


async def _ensure_meters(
    hass: HomeAssistant,
    sources: list[str],
    cycles: list[str],
    labels: dict[str, str],
    owned: dict[str, Any],
) -> None:
    """Ensure a meter for each source x cycle, recording ownership in ``owned``."""
    for source in sources:
        state = hass.states.get(source)
        net_consumption = bool(
            state and state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
        )
        display = state.name if state else source
        for cycle in cycles:
            name = f"{display} {labels.get(cycle, cycle.capitalize())}"
            key = _key(source, cycle)
            # A meter already over this source+cycle before we ensure one is the
            # user's own (adopt, never delete); otherwise HEA is creating it.
            pre_existing = _utility_meter_for(hass, source, cycle)
            meter_id = await async_ensure_utility_meter(
                hass,
                name=name,
                source_entity=source,
                cycle=cycle,
                net_consumption=net_consumption,
            )
            owned[key] = resolve_provenance(
                owned.get(key), meter_id, pre_existing=pre_existing
            )


async def _cycle_labels(hass: HomeAssistant) -> dict[str, str]:
    """utility_meter's own translated cycle names, keyed by cycle (empty on miss)."""
    strings = await translation.async_get_translations(
        hass, hass.config.language, "selector", {UTILITY_METER_DOMAIN}
    )
    return {
        key.removeprefix(_CYCLE_LABEL_PREFIX): value
        for key, value in strings.items()
        if key.startswith(_CYCLE_LABEL_PREFIX)
    }


def _persist_owned_meters(
    hass: HomeAssistant, entry: ConfigEntry, owned: dict[str, Any]
) -> None:
    """Store the meter map on the entry, if it changed."""
    if owned != entry.data.get(CONF_CYCLE_METERS, {}):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CYCLE_METERS: owned}
        )


async def _reconcile_net_consumption(
    hass: HomeAssistant, entry_id: str, *, net_consumption: bool
) -> None:
    """Switch a reused meter's net_consumption when its source's semantics change.

    A meter is reused across reloads by source + cycle, but its options are frozen
    at creation. The Untracked remainder's cost meters were created while its
    sources were ``total_increasing``; once those move to ``total`` (HEA-48), the
    meter must become net-consumption or the first downward correction reads as a
    reset and corrupts the cycle total. Reconciled in place so the accumulated
    period value is preserved; a reload lets the running meter pick up the change.
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        return
    if entry.options.get(CONF_METER_NET_CONSUMPTION) == net_consumption:
        return
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_METER_NET_CONSUMPTION: net_consumption}
    )
    await hass.config_entries.async_reload(entry_id)


def _utility_meter_for(
    hass: HomeAssistant, source_entity: str, cycle: str
) -> str | None:
    """Return the entry_id of an existing meter over ``source_entity`` + ``cycle``."""
    for entry in hass.config_entries.async_entries(UTILITY_METER_DOMAIN):
        if (
            entry.options.get(CONF_SOURCE_SENSOR) == source_entity
            and entry.options.get(CONF_METER_TYPE) == cycle
        ):
            return entry.entry_id
    return None
