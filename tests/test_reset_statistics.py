"""What a rebase leaves behind in the long-term statistics (HEA-122).

A rebase clears HEA's statistics and sends every figure to zero. On the
reference instance that left the money series holding one enormous negative on
the day of the reset - about -EUR 95 of Cost Savings - while the energy series
came through clean. The cards read `change` and sum the buckets in a period, so
any period containing that day reported money that was not merely wrong but
inverted.

The asymmetry is the whole story. Energy is `total_increasing`, and Home
Assistant's statistics compiler treats a `total_increasing` counter falling to
zero as a new cycle. Money is `total` (ADR-0007), and for `total` the compiler
has only one way to be told a new cycle began: the `last_reset` attribute
moving. Without it a rebase reads as a meter that simply fell by the whole
balance, and the compiler books that fall.

These tests run against the real recorder and the real compiler, because the
obligation is what Home Assistant records, not what this integration publishes.
A double that agreed with our own reading of the compiler would prove nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from homeassistant.components.sensor import ATTR_LAST_RESET
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
    statistics_during_period,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SERVICE_RESET_TOTALS,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}

START = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
# The rebase and the last figure published before it land in the same five-minute
# compile window, which is the shape that produced the crater: the clear empties
# the history, and the window that follows holds a full balance and then a zero.
REBASE_WINDOW = datetime(2026, 7, 8, 22, 40, tzinfo=UTC)

_WHOLE_HOME_COST = "sensor.whole_home_actual_cost"
_WHOLE_HOME_ENERGY = "sensor.whole_home_energy_used"
_AIRCON_COST = "sensor.coarse_step_aircon_actual_cost"
_AIRCON_COST_DAILY = "sensor.coarse_step_aircon_actual_cost_daily"


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


async def _household_with_a_balance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """A set-up household carrying real accumulated money on every figure."""
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

    # Past the lateness margin, so the interval closes and the figures publish.
    freezer.move_to(START + timedelta(minutes=30))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    return entry


def _published(hass: HomeAssistant, entity_id: str) -> Decimal:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return Decimal(state.state)


def _zero_point(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return state.attributes.get(ATTR_LAST_RESET)


async def _rebase(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET_TOTALS,
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    await hass.async_block_till_done()


def _changes(hass: HomeAssistant, entity_id: str) -> list[float]:
    """Every compiled change for one sensor, oldest first."""
    compiled = statistics_during_period(
        hass,
        START,
        None,
        {entity_id},
        "5minute",
        None,
        {"change"},
    )
    return [row["change"] for row in compiled.get(entity_id, [])]


@pytest.mark.usefixtures("recorder_mock")
async def test_a_rebase_books_no_negative_change_in_the_money_statistics(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household with money accumulated on its figures, and that history
    # compiled into statistics the way a live instance's would be
    entry = await _household_with_a_balance(hass, freezer)
    assert _published(hass, _WHOLE_HOME_COST) > 0
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=START + timedelta(minutes=30))
    await async_wait_recording_done(hass)

    # ...and one more publication of that balance, in the window the rebase will
    # fall into. This is what a live instance always has: the coordinator writes
    # every figure roughly once a minute, so the balance is recorded moments
    # before it goes to zero.
    freezer.move_to(REBASE_WINDOW)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # When - the household is rebased, which clears HEA's statistics and sends
    # every figure to zero, and the window holding both is then compiled
    freezer.move_to(REBASE_WINDOW + timedelta(minutes=2))
    await _rebase(hass, entry)
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=REBASE_WINDOW)
    await async_wait_recording_done(hass)

    # Then - the fall to zero is a new zero point, not a loss. Without one the
    # compiler books the whole balance as a negative change, and every card
    # reading a period that contains this day reports money inverted.
    assert _changes(hass, _WHOLE_HOME_COST) == [0.0]
    assert _changes(hass, _AIRCON_COST) == [0.0]
    # The cycle meters HEA created are rebased in the same breath and are `total`
    # too, so the same question has to be asked of them. They answer it on their
    # own: utility_meter stamps a zero point when it is built and carries one
    # ever after, which the compiler reads as a new cycle once the rebase has
    # cleared the statistics behind it. This holds that, rather than proving the
    # fix - it passes either way, which is the point worth knowing.
    assert _changes(hass, _AIRCON_COST_DAILY) == [0.0]


@pytest.mark.usefixtures("recorder_mock")
async def test_energy_and_money_come_through_a_rebase_alike(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household with a balance, published again in the rebase window
    entry = await _household_with_a_balance(hass, freezer)
    await async_wait_recording_done(hass)
    freezer.move_to(REBASE_WINDOW)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # When - it is rebased and the window is compiled
    freezer.move_to(REBASE_WINDOW + timedelta(minutes=2))
    await _rebase(hass, entry)
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=REBASE_WINDOW)
    await async_wait_recording_done(hass)

    # Then - the energy series behaves as it always did, and the money series now
    # behaves the same way. The asymmetry was the defect, so it is the thing to
    # assert: one state class must not survive a rebase that the other does not.
    assert _changes(hass, _WHOLE_HOME_ENERGY) == _changes(hass, _WHOLE_HOME_COST)


async def test_a_household_that_has_never_rebased_carries_no_zero_point(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - a household that has simply been running
    await _household_with_a_balance(hass, freezer)

    # Then - no zero point is published. This is not a detail: an existing
    # instance already has statistics compiled without one, and a zero point
    # appearing from nowhere would read to the compiler as a new cycle and book
    # the entire lifetime balance as a change. It must appear only at a rebase,
    # which is the one moment the figure really is starting again.
    assert _zero_point(hass, _WHOLE_HOME_COST) is None
    assert _zero_point(hass, _AIRCON_COST) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_a_rebase_publishes_a_zero_point_on_the_money_figures(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running household
    entry = await _household_with_a_balance(hass, freezer)

    # When - it is rebased
    freezer.move_to(REBASE_WINDOW)
    await _rebase(hass, entry)

    # Then - every money figure says when it started again
    assert _zero_point(hass, _WHOLE_HOME_COST) == REBASE_WINDOW.isoformat()
    assert _zero_point(hass, _AIRCON_COST) == REBASE_WINDOW.isoformat()


@pytest.mark.usefixtures("recorder_mock")
async def test_an_energy_counter_is_never_given_a_zero_point(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running household
    entry = await _household_with_a_balance(hass, freezer)

    # When - it is rebased
    freezer.move_to(REBASE_WINDOW)
    await _rebase(hass, entry)

    # Then - the `total_increasing` counters carry none. Home Assistant refuses a
    # zero point on any state class but `total` - loudly, with a ValueError out of
    # `state_attributes` - and it would be redundant anyway: the compiler already
    # reads a counter falling to zero as a new cycle.
    assert _zero_point(hass, _WHOLE_HOME_ENERGY) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_the_zero_point_holds_across_a_restart(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household rebased at a known moment
    entry = await _household_with_a_balance(hass, freezer)
    freezer.move_to(REBASE_WINDOW)
    await _rebase(hass, entry)
    stamped = _zero_point(hass, _WHOLE_HOME_COST)
    assert stamped == REBASE_WINDOW.isoformat()

    # When - Home Assistant restarts
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(REBASE_WINDOW + timedelta(hours=1))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the figure still names the same zero point. A stamp that moved on
    # every restart would be worse than none at all: the compiler would read each
    # one as a new cycle and book the restored lifetime balance as a change, so a
    # household's money would climb by its whole total at every restart.
    assert _zero_point(hass, _WHOLE_HOME_COST) == stamped
