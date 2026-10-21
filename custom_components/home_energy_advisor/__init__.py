"""Home Energy Advisor - per-device financial accounting for Home Assistant.

Home Assistant's Energy Dashboard explains energy flows; this integration
explains money: what each tracked device actually cost to run, what it would
have cost at grid prices, and what the difference saved.

This package is the thin Home Assistant adapter layer. The accounting engine
lives in ``engine/`` and imports nothing from ``homeassistant``, so the
financial model can be unit-tested without a running instance.

The config entry holds the global house-level configuration; tracked devices
arrive as config subentries. The sensor platform (HEA-22) publishes the four
per-device figures plus the Untracked remainder.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME, Platform

from . import reset
from .accountant_store import AccountantStore
from .cards import async_register_cards
from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CYCLE_DAILY,
    CONF_CYCLE_METERS,
    CONF_CYCLE_MONTHLY,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_INTEGRAL_HELPERS,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_GRID,
)
from .coordinator import HeaCoordinator
from .cycle_meter import async_sync_cycle_meters
from .helper_ownership import helper_entry_id, helper_was_created
from .house_inputs import house_entities
from .integral_helper import async_sync_power_device_helpers

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

    from .coordinator import HeaConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]

# The pre-ADR-0011 key for the local-generation input, as it still sits in an
# installed household's .storage. Only the migration below knows this name.
_LEGACY_GENERATION_KEY = "solar_entity"

# Config entry schema versions, named for what each one got wrong, because a
# migration reads as arithmetic otherwise.
_RENAMED_GENERATION_KEY = 1
_CYCLES_ALWAYS_CREATED = 2
_CYCLES_OPTED_INTO = 3
_SEVERAL_GENERATION_METERS = 4
_BATTERY_CHARGING_ASKED = 5
_BATTERIES_ARE_ENTRIES = 6
_GRID_METERS_ARE_ENTRIES = 7

# The key 0.12.0 stored its answer to which the panels feed first under. Only the
# migration below knows this name.
_LEGACY_SOLAR_PRIORITY_KEY = "solar_priority"


async def async_setup_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Set up Home Energy Advisor: build the coordinator and start accounting."""
    # Registered here rather than in async_setup: the reset action needs a loaded
    # entry to act on, and re-registering the same handler is a no-op (HEA-57).
    reset.async_register(hass)
    await async_register_cards(hass)
    power_energy_entities = await async_sync_power_device_helpers(hass, entry)
    coordinator = HeaCoordinator(
        hass, entry, power_energy_entities=power_energy_entities
    )
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # After the sensors exist, reconcile the utility_meter cycle totals over them
    # (daily/monthly + opt-in longer cycles), creating and cleaning up as needed.
    await async_sync_cycle_meters(hass, entry)
    # Reload on any config change so adding, editing or removing a device takes
    # effect live - and so a removed device's auto-created helpers (Integral and
    # cycle meters) are reconciled away on the next setup (HEA-34, HEA-23).
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Bring an older config entry up to the current schema.

    Version 1 stored the local-generation input under ``solar_entity``. ADR-0009
    renamed the concept but kept the key; ADR-0011 revises that, so the key moves
    to ``generation_entity``.

    Version 2 created daily and monthly cycle totals for every household. They
    are opted into now (HEA-145), and reconciliation removes meters nobody wants
    - so without this an update would delete ninety helpers, and the history on
    them, from a household that never asked for either. What they already have
    is therefore opted in on their behalf, and stays until they say otherwise.

    Version 3 held one generation meter. Generation is a list now, because the
    Energy Dashboard takes several solar sources (HEA-219), so the one meter
    becomes a list of one. A household with none is left with none rather than
    an empty list. The version moving also stops an older release loading an
    entry whose generation it would read as a single entity id.

    Version 4 may hold an answer to which the panels feed first. The question
    is now how the battery charges (HEA-233), and neither old answer reads as an
    answer to it: "house" is also what anybody who opened Reconfigure stored
    without choosing, and "battery" means the new default anyway. So the key
    goes, and the household is on the default until they answer.

    Version 5 held one battery on the house screen, which now has an entry of
    its own (ADR-0031).

    Version 6 held one grid meter and its price on the house screen, which now
    have an entry of their own, one per grid source (ADR-0032).
    """
    if entry.version == _RENAMED_GENERATION_KEY:
        data = {**entry.data}
        if (generation := data.pop(_LEGACY_GENERATION_KEY, None)) is not None:
            data[CONF_GENERATION_ENTITY] = generation
        hass.config_entries.async_update_entry(
            entry, data=data, version=_CYCLES_ALWAYS_CREATED
        )
    if entry.version == _CYCLES_ALWAYS_CREATED:
        options = {**entry.options}
        if entry.data.get(CONF_CYCLE_METERS):
            options = {**options, CONF_CYCLE_DAILY: True, CONF_CYCLE_MONTHLY: True}
        hass.config_entries.async_update_entry(
            entry, options=options, version=_CYCLES_OPTED_INTO
        )
    if entry.version == _CYCLES_OPTED_INTO:
        data = {**entry.data}
        if generation := house_entities(data, CONF_GENERATION_ENTITY):
            data[CONF_GENERATION_ENTITY] = list(generation)
        hass.config_entries.async_update_entry(
            entry, data=data, version=_SEVERAL_GENERATION_METERS
        )
    if entry.version == _SEVERAL_GENERATION_METERS:
        data = {**entry.data}
        data.pop(_LEGACY_SOLAR_PRIORITY_KEY, None)
        hass.config_entries.async_update_entry(
            entry, data=data, version=_BATTERY_CHARGING_ASKED
        )
    if entry.version == _BATTERY_CHARGING_ASKED:
        _move_the_battery_into_its_own_entry(hass, entry)
    if entry.version == _BATTERIES_ARE_ENTRIES:
        _move_the_grid_into_its_own_entry(hass, entry)
    return True


def _move_the_battery_into_its_own_entry(
    hass: HomeAssistant, entry: HeaConfigEntry
) -> None:
    """Version 5 held one battery on the house screen; it becomes a battery entry.

    Batteries are entered one per battery now, as Home Assistant's battery
    systems are (ADR-0031). The household's one battery moves into an entry of
    its own with every field it had, so its meters, level and capacity - and so
    its figures - carry on unchanged. A level or capacity with no meter beside it
    described no battery, and goes with the rest of the old fields.
    """
    data = {**entry.data}
    battery = {key: data.pop(key) for key in _BATTERY_KEYS if key in data}
    hass.config_entries.async_update_entry(
        entry, data=data, version=_BATTERIES_ARE_ENTRIES
    )
    if not (
        battery.get(CONF_BATTERY_CHARGE_ENTITY)
        or battery.get(CONF_BATTERY_DISCHARGE_ENTITY)
    ):
        return
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_NAME: _FIRST_BATTERY, **battery}),
            subentry_type=SUBENTRY_TYPE_BATTERY,
            title=_FIRST_BATTERY,
            unique_id=None,
        ),
    )


_FIRST_BATTERY = "Battery"
_BATTERY_KEYS = (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_CAPACITY_KWH,
)


def _move_the_grid_into_its_own_entry(
    hass: HomeAssistant, entry: HeaConfigEntry
) -> None:
    """Version 6 held one grid meter on the house screen; it becomes a grid entry.

    Grid meters are entered one per grid source now, as the Energy Dashboard
    holds them (ADR-0032). The household's import meter, its price and its
    export meter move into an entry of their own unchanged, so the same meters
    are read at the same price and the figures carry on.
    """
    data = {**entry.data}
    grid = {key: data.pop(key) for key in _GRID_KEYS if key in data}
    hass.config_entries.async_update_entry(
        entry, data=data, version=_GRID_METERS_ARE_ENTRIES
    )
    if not grid.get(CONF_GRID_IMPORT_ENTITY):
        return
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_NAME: _FIRST_GRID, **grid}),
            subentry_type=SUBENTRY_TYPE_GRID,
            title=_FIRST_GRID,
            unique_id=None,
        ),
    )


_FIRST_GRID = "Grid"
_GRID_KEYS = (CONF_GRID_IMPORT_ENTITY, CONF_PRICE_ENTITY, CONF_GRID_EXPORT_ENTITY)


async def async_unload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> bool:
    """Unload the config entry and its platforms.

    Flushes the coordinator's in-flight accounting first, while the sensors still
    exist, so they bank up to ~20 min of otherwise-discarded buckets into their
    restore baseline before teardown - otherwise every restart and every
    options/config change silently drops them (HEA-53).
    """
    coordinator = entry.runtime_data
    if coordinator is not None:
        coordinator.async_flush()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Clean up the native helpers this integration auto-created (HEA-42).

    The Integral (power-only devices) and utility_meter (cycle totals) helpers are
    independent config entries owned via the entry's data. Reconciliation only
    prunes them when a *device* is removed, so without this hook they would be
    orphaned when the whole integration is deleted - leaving no clean uninstall.

    Only helpers HEA created are removed: a helper the user already had over a
    source (adopted) is theirs to keep, never deleted on uninstall (HEA-52).

    The accounting snapshot goes too, so a later reinstall starts from zero
    rather than inheriting the totals the household deleted.
    """
    await AccountantStore(hass, entry.entry_id).async_remove()
    owned = (
        *entry.data.get(CONF_INTEGRAL_HELPERS, {}).values(),
        *entry.data.get(CONF_CYCLE_METERS, {}).values(),
    )
    for record in owned:
        if not helper_was_created(record):
            continue
        helper_id = helper_entry_id(record)
        if hass.config_entries.async_get_entry(helper_id) is not None:
            await hass.config_entries.async_remove(helper_id)


def _tracked_subentry_id(entry: HeaConfigEntry, device: DeviceEntry) -> str | None:
    """The subentry a HEA device page belongs to, or None if it is an aggregate.

    Membership of ``entry.subentries`` is the whole test. The hub carries the
    bare entry id and the Untracked and whole-home devices carry suffixes that
    are not subentry ids, so all three fall out without a list of exclusions to
    keep in step with the sensor platform.
    """
    prefix = f"{entry.entry_id}_"
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and (sub := identifier.removeprefix(prefix)) in (
            entry.subentries
        ):
            return sub
    return None


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: HeaConfigEntry, device: DeviceEntry
) -> bool:
    """Let a tracked device be deleted from its own device page (HEA-56).

    Removing the device alone would not stick: the subentry is authoritative, so
    the sensor platform would rebuild the device on the next reload. Removing the
    subentry is what makes the deletion real - and Home Assistant's own
    ``async_remove_subentry`` clears the device registry for it, while the update
    listener below reloads the entry and reconciles the auto-created Integral and
    cycle-meter helpers away (HEA-34, HEA-23).

    The aggregates are refused: Untracked and whole home are derived figures and
    the hub is the integration itself, so none of them is a user's to delete.
    """
    if (subentry_id := _tracked_subentry_id(entry, device)) is None:
        return False
    hass.config_entries.async_remove_subentry(entry, subentry_id)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: HeaConfigEntry) -> None:
    """Reload the entry when its configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)
