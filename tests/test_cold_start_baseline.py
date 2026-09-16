"""A restart that finds neither store still knows what the household had.

Two stores carry a figure across a restart, and both are delayed writes: the
engine's snapshot, and the sensor's own restored state. A restart landing before
either has been flushed finds nothing, and every figure republishes from zero.

That is a household's lifetime totals disappearing at once. It reaches them as
the dashboard disagreeing with the device page - the statistics kept what the
sensors lost, so the cards read right and the sensors read low - and it is worst
on the first day, when somebody sets devices up and restarts minutes later
(HEA-134, GitHub #20).

Home Assistant recorded those figures. These tests hold the seam: what the
recorder kept is what a figure with nothing else to go on comes back holding.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import restore_state
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
    do_adhoc_statistics,
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
_PUMP_ENERGY = "sensor.water_pump_energy_used"
_PUMP_COST = "sensor.water_pump_actual_cost"
_WHOLE_HOME_ENERGY = "sensor.whole_home_energy_used"
START = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)


def _published(hass: HomeAssistant, entity_id: str) -> Decimal:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return Decimal(state.state)


async def _a_household_with_history(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """A set-up household whose 0.6 kWh has reached the long-term statistics."""
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.pump", "0", _ENERGY)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Water Pump",
                data={CONF_NAME: "Water Pump", CONF_ENERGY_ENTITY: "sensor.pump"},
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to(START + timedelta(minutes=5))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.pump", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(START + timedelta(minutes=30))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Home Assistant compiles the published figures into statistics, as it does
    # every five minutes on a live instance.
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=START + timedelta(minutes=30))
    await async_wait_recording_done(hass)
    return entry


async def _cold_start(
    hass: HomeAssistant, entry: MockConfigEntry, storage: dict[str, Any]
) -> None:
    """Restart with neither store: no snapshot, and no restored states."""
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    storage.pop(f"{DOMAIN}.{entry.entry_id}.accountant", None)
    restore_state.async_get(hass).last_states.clear()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cold_start_takes_its_baseline_from_the_recorded_history(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    # Given - a household whose pump has used 0.6 kWh, recorded
    entry = await _a_household_with_history(hass, freezer)
    assert _published(hass, _PUMP_ENERGY) == Decimal("0.6")

    # When - it restarts before either store was written
    await _cold_start(hass, entry, hass_storage)

    # Then - the figure is what it was. Starting from zero here loses the
    # household's lifetime totals silently, and leaves every card reading above
    # every sensor for ever, because the statistics kept what the sensor lost
    assert _published(hass, _PUMP_ENERGY) == Decimal("0.6")


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cold_start_keeps_accounting_from_there(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    # Given - a household that has come back from a cold start
    entry = await _a_household_with_history(hass, freezer)
    await _cold_start(hass, entry, hass_storage)

    # When - the pump draws another 0.3 kWh
    freezer.move_to(START + timedelta(minutes=60))
    hass.states.async_set("sensor.grid_import", "2.0", _ENERGY)
    hass.states.async_set("sensor.pump", "0.9", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(START + timedelta(minutes=85))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then - the figure is the whole lifetime, not the part since the restart.
    # The recovered baseline has to sit *under* the engine's running total, the
    # same way a restored state does, or the recovery merely moves the loss
    assert _published(hass, _PUMP_ENERGY) == Decimal("0.9")


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cold_start_recovers_money_and_the_house_as_well(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    # Given - a household whose cost and whole-home figures are recorded too
    entry = await _a_household_with_history(hass, freezer)
    cost = _published(hass, _PUMP_COST)
    house = _published(hass, _WHOLE_HOME_ENERGY)
    assert cost > 0
    assert house > 0

    # When - it restarts with nothing to restore from
    await _cold_start(hass, entry, hass_storage)

    # Then - every figure comes back, not only the energy of one device: the
    # household lost them all at once, and money is what they will look at first
    assert _published(hass, _PUMP_COST) == cost
    assert _published(hass, _WHOLE_HOME_ENERGY) == house


@pytest.mark.usefixtures("recorder_mock")
async def test_a_first_install_starts_at_zero(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The guard: nothing recorded means nothing to recover, not an error."""
    # Given / When - a household sets the integration up for the first time, so
    # there are no statistics behind any of its figures
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.pump", "0", _ENERGY)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Water Pump",
                data={CONF_NAME: "Water Pump", CONF_ENERGY_ENTITY: "sensor.pump"},
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - it reads zero, and says it is warming up rather than claiming a
    # history it does not have (HEA-47)
    assert _published(hass, _PUMP_ENERGY) == Decimal(0)
    state = hass.states.get(_PUMP_COST)
    assert state is not None
    assert state.attributes.get("warming_up") is True
