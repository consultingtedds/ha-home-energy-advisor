"""Accounting continues across a restart, and is counted once.

Two stores hold a figure over a restart: the engine's snapshot and each sensor's
restored state. These tests hold the seam between them - the accounting must
survive, and it must not arrive twice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.helpers import restore_state
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)

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
