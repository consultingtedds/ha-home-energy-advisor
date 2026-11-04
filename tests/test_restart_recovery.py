"""Accounting continues across a restart, and is counted once.

Two stores hold a figure over a restart: the engine's snapshot and each sensor's
restored state. These tests hold the seam between them - the accounting must
survive, and it must not arrive twice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.helpers import restore_state
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_CHARGING,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.engine.house_balance import ChargeSource

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
_AIRCON_ENERGY = "sensor.coarse_step_aircon_energy_used"
_AIRCON_COST = "sensor.coarse_step_aircon_actual_cost"
START = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)


def _published(hass: HomeAssistant, entity_id: str) -> Decimal:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return Decimal(state.state)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.coarse_step_energy",
                },
                unique_id=None,
            )
        ],
    )


async def _accrue_and_publish(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """Run one interval through to a published figure, then let the store write."""
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to(START + timedelta(minutes=5))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()

    # Past the lateness margin, so the interval closes and is published.
    freezer.move_to(START + timedelta(minutes=30))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Home Assistant flushes pending delayed writes on its way down, which is
    # what puts the snapshot on disk before the process ends.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()
    return entry


async def test_a_restart_neither_loses_nor_doubles_the_published_total(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    # Given - a device with a published figure behind it, and a snapshot written
    entry = await _accrue_and_publish(hass, freezer)
    before = _published(hass, _AIRCON_ENERGY)
    assert before == Decimal("0.6")
    assert f"{DOMAIN}.{entry.entry_id}.accountant" in hass_storage

    # When - the integration comes back up, restoring from both the snapshot and
    # the sensor's own state
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the figure is exactly what it was. Adding the engine's carried total
    # to the sensor's restored baseline would read 1.2 here, and a household
    # would see its energy double at every restart.
    assert _published(hass, _AIRCON_ENERGY) == before
    assert _published(hass, _AIRCON_COST) == Decimal("0.1800")


async def test_a_restart_carries_the_engine_state_the_sensors_cannot_hold(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running integration whose counter has stepped
    entry = await _accrue_and_publish(hass, freezer)
    coordinator = entry.runtime_data
    sources = {s["entity_id"]: s for s in coordinator.diagnostics()["sources"]}
    assert sources["sensor.coarse_step_energy"]["last_value"] == "0.6"

    # When - it restarts
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - each counter resumes from where it stood rather than rebaselining,
    # which is what the sensors' restored totals cannot express: they carry the
    # published figure, not the engine's position in the meter's history.
    restarted = entry.runtime_data
    assert restarted.restored is not None
    resumed = {s["entity_id"]: s for s in restarted.diagnostics()["sources"]}
    assert resumed["sensor.coarse_step_energy"]["last_value"] == "0.6"


async def test_adding_a_second_device_does_not_rebase_the_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Adding a device reloads the entry, and a household adds several in a row.

    A published `total_increasing` figure that dips is not merely a wobble on a
    chart: Home Assistant's statistics read the fall as a counter starting again,
    so the energy before it is counted a second time and the dashboard, which
    sums recorded change, reads high for ever after (HEA-134, GitHub #20).
    """
    # Given - a device with a published figure behind it
    entry = await _accrue_and_publish(hass, freezer)
    before = _published(hass, _AIRCON_ENERGY)
    assert before == Decimal("0.6")

    # When - a second device is added, as the options flow does, and the entry
    # reloads to pick it up
    hass.states.async_set("sensor.steady_pump_energy", "0", _ENERGY)
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_NAME: "Steady Pump",
                    CONF_ENERGY_ENTITY: "sensor.steady_pump_energy",
                }
            ),
            subentry_type=SUBENTRY_TYPE_DEVICE,
            title="Steady Pump",
            unique_id=None,
        ),
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the first device's figure is untouched
    assert _published(hass, _AIRCON_ENERGY) == before


async def test_a_reload_does_not_republish_what_ran_since_the_snapshot(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    """The seam the other reload test cannot reach (HEA-183).

    `_accrue_and_publish` flushes the store and reloads straight away, so the
    meters have not moved since the snapshot and there is no gap to count twice.
    Every real reload has one: a config save arrives whenever the household
    happens to make it, and on the reference instance that was 42 minutes after
    the last write, which came back as 4.8 kWh of energy nobody used.

    A restore hands the engine the snapshot's totals, and `async_start` then
    feeds each meter's current reading, which re-books everything since. The
    sensor's restored state already holds that, so unless the baseline is worked
    out against the engine *after* those readings land, the gap arrives twice.
    """
    # Given - a published figure, a snapshot written behind it, and then a
    # further interval that runs and publishes with no new snapshot written
    entry = await _accrue_and_publish(hass, freezer)
    assert f"{DOMAIN}.{entry.entry_id}.accountant" in hass_storage

    freezer.move_to(START + timedelta(minutes=35))
    hass.states.async_set("sensor.grid_import", "2.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "1.2", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(START + timedelta(minutes=60))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    before = _published(hass, _AIRCON_ENERGY)
    assert before == Decimal("1.2")

    # The precondition, asserted rather than assumed: the snapshot must still be
    # the older one, or there is no gap and this test proves nothing. It is the
    # trap the neighbouring reload test fell into.
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}.accountant"]
    snapshot_sources = stored["data"]["state"]["sources"]
    assert snapshot_sources["sensor.coarse_step_energy"]["last"]["value"] == "0.6"

    # When - the entry reloads, as saving any option does, and the readings it
    # takes on the way up are allowed to settle. They carry the meters' own
    # timestamps, so they land in intervals that have already closed and come
    # through on the next finalisation rather than immediately
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(START + timedelta(minutes=90))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then - the figure is what it was. The 0.6 kWh that ran between the
    # snapshot and the reload is counted once, not once by the sensor's restored
    # state and again by the meter reading that reproduces it
    assert _published(hass, _AIRCON_ENERGY) == before


async def test_a_snapshot_the_engine_cannot_read_falls_back_to_a_cold_start(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored snapshot that is present, stamped and recent, so the store
    # hands it over, but whose contents this engine cannot make sense of
    entry = await _accrue_and_publish(hass, freezer)
    before = _published(hass, _AIRCON_ENERGY)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}.accountant"]
    stored["data"]["state"] = {"sources": {}, "raw": "not a list of buckets"}

    # When - it starts up against that snapshot
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - setup succeeds. A snapshot is a cache, so an unreadable one costs a
    # restart's accounting, never the integration.
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.restored is None

    # ...and the sensors' own restored totals still carry the published figure,
    # so the household sees continuity rather than a reset to zero.
    assert _published(hass, _AIRCON_ENERGY) == before


async def test_a_cold_start_still_takes_the_sensors_restored_baseline(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    # Given - a published figure, and no snapshot on disk: the upgrade path every
    # existing install takes once
    entry = await _accrue_and_publish(hass, freezer)
    before = _published(hass, _AIRCON_ENERGY)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    hass_storage.pop(f"{DOMAIN}.{entry.entry_id}.accountant")

    # When - it starts with only the sensors' own restored state to go on
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the total is still carried, by the baseline alone
    assert entry.runtime_data.restored is None
    assert _published(hass, _AIRCON_ENERGY) == before


# A house whose own meters reset every midnight (HEA-269, discussion 58): an
# inverter's daily counters for the grid, the battery and the house, beside a
# device on a lifetime meter, with the battery charging from the grid too.

_DAILY_GRID = "sensor.inverter_daily_grid_import"
_DAILY_CHARGE = "sensor.inverter_daily_battery_charge"
_DAILY_DISCHARGE = "sensor.inverter_daily_battery_discharge"
_DAILY_LOAD = "sensor.inverter_daily_load"
_LEVEL = "sensor.inverter_battery_level"
_WHOLE_HOME = ("sensor.whole_home_actual_cost", "sensor.whole_home_energy_from_grid")
_FIGURES = (
    *_WHOLE_HOME,
    _AIRCON_COST,
    _AIRCON_ENERGY,
    "sensor.untracked_energy_devices_actual_cost",
    "sensor.untracked_energy_devices_energy_used",
)


def _daily_house() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "AUD",
            CONF_GRID_IMPORT_ENTITY: _DAILY_GRID,
            CONF_HOUSE_CONSUMPTION_ENTITY: _DAILY_LOAD,
            CONF_BATTERY_CHARGING: ChargeSource.GRID_TOO.value,
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_BATTERY,
                title="Inverter battery",
                data={
                    CONF_NAME: "Inverter battery",
                    CONF_BATTERY_CHARGE_ENTITY: _DAILY_CHARGE,
                    CONF_BATTERY_DISCHARGE_ENTITY: _DAILY_DISCHARGE,
                    CONF_BATTERY_SOC_ENTITY: _LEVEL,
                    CONF_BATTERY_CAPACITY_KWH: 10.0,
                },
                unique_id=None,
            ),
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.coarse_step_energy",
                },
                unique_id=None,
            ),
        ],
    )


async def _interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    at: datetime,
    readings: dict[str, str],
) -> None:
    """Meters reporting at `at`, then the interval closed and published."""
    freezer.move_to(at)
    for entity_id, value in readings.items():
        attributes = {"device_class": "battery"} if entity_id == _LEVEL else _ENERGY
        hass.states.async_set(entity_id, value, attributes)
    await hass.async_block_till_done()
    freezer.move_to(at + timedelta(minutes=30))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


def _figures(hass: HomeAssistant) -> dict[str, Decimal]:
    return {entity_id: _published(hass, entity_id) for entity_id in _FIGURES}


async def _a_day_reset_at_midnight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """An evening, the counters' midnight reset, and the morning after it."""
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.45")
    for meter in (_DAILY_GRID, _DAILY_CHARGE, _DAILY_DISCHARGE, _DAILY_LOAD):
        hass.states.async_set(meter, "5.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "100.0", _ENERGY)
    hass.states.async_set(_LEVEL, "50", {"device_class": "battery"})
    entry = _daily_house()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The evening: 1 kWh in, half of it into the battery, the aircon running
    await _interval(
        hass,
        freezer,
        START + timedelta(minutes=5),
        {
            _DAILY_GRID: "6.0",
            _DAILY_CHARGE: "5.5",
            _DAILY_LOAD: "5.5",
            "sensor.coarse_step_energy": "100.3",
            _LEVEL: "55",
        },
    )
    # Midnight: every daily counter starts again from nothing
    await _interval(
        hass,
        freezer,
        START + timedelta(hours=1),
        {_DAILY_GRID: "0", _DAILY_CHARGE: "0", _DAILY_DISCHARGE: "0", _DAILY_LOAD: "0"},
    )
    # The morning: a little more from the grid, and the battery giving back
    await _interval(
        hass,
        freezer,
        START + timedelta(hours=2),
        {
            _DAILY_GRID: "0.4",
            _DAILY_DISCHARGE: "0.3",
            _DAILY_LOAD: "0.7",
            "sensor.coarse_step_energy": "100.5",
            _LEVEL: "52",
        },
    )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()
    return entry


async def test_a_restart_on_daily_counters_keeps_every_figure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a day on daily counters, published
    entry = await _a_day_reset_at_midnight(hass, freezer)
    before = _figures(hass)
    # Asserted rather than assumed, so a day that published nothing cannot pass
    # by comparing nothing with nothing: 1.2 kWh used at 0.45, half a kWh of it
    # the aircon's
    assert before["sensor.whole_home_actual_cost"] == Decimal("0.5400")
    assert before[_AIRCON_ENERGY] == Decimal("0.500000")
    assert before["sensor.untracked_energy_devices_energy_used"] == Decimal("0.700000")

    # When - Home Assistant restarts, as an update does, mid-morning
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(START + timedelta(hours=3))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then - every figure is what it was: none restarted from nothing, and none
    # came back holding more than it had
    assert _figures(hass) == before


async def test_after_a_restart_on_daily_counters_an_interval_adds_only_itself(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the same day, and a restart
    entry = await _a_day_reset_at_midnight(hass, freezer)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    before = _figures(hass)

    # When - 0.2 kWh more from the grid, all of it the aircon's
    await _interval(
        hass,
        freezer,
        START + timedelta(hours=3),
        {
            _DAILY_GRID: "0.6",
            _DAILY_LOAD: "0.9",
            "sensor.coarse_step_energy": "100.7",
        },
    )

    # Then - the whole home paid for 0.2 kWh at 0.45, and nothing else moved
    after = _figures(hass)
    assert after["sensor.whole_home_energy_from_grid"] - before[
        "sensor.whole_home_energy_from_grid"
    ] == Decimal("0.2")
    assert after["sensor.whole_home_actual_cost"] - before[
        "sensor.whole_home_actual_cost"
    ] == Decimal("0.09")
