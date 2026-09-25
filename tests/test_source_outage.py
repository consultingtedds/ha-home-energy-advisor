"""What a device source going unavailable does to the figures over it (HEA-176).

A cumulative figure that stops being fed does not go blank - it holds its last
value for ever - so a household sees a plausible number that has quietly stopped
moving, and nothing anywhere says so.

ADR-0024 puts the whole disclosure on one diagnostic entity per device, Last
Reading, and leaves every cost figure alone. So these tests hold two claims at
once, and the second is the one worth guarding: the signal has to appear, *and*
the money must not move. A radiator that ran all week and was then unplugged for
eight months really did cost what it says, and withdrawing that figure for the
whole winter would answer a rare fault by degrading the ordinary case.

The statistics test runs against the real recorder and the real compiler, because
the obligation is what Home Assistant records rather than what this integration
believes it published. A `total` figure that fell to zero, or came back stamped
with a new zero point, is the defect HEA-122 shipped.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from homeassistant.components.sensor import ATTR_LAST_RESET
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, STATE_UNKNOWN
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
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
# A power-only device: smart wall lights report instantaneous watts and nothing
# cumulative, so ADR-0004 gives them an auto-created Integral helper.
_POWER = {"unit_of_measurement": "W", "device_class": "power"}

START = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
# When the source falls silent. The counter's last reading was at 22:05, so the
# grace runs from a state change rather than from setup.
OUTAGE = datetime(2026, 7, 8, 22, 31, tzinfo=UTC)
# Inside the thirty-minute grace, and past the twenty minutes the engine takes to
# settle a bucket - so any figure still owed has already been published.
DURING_GRACE = datetime(2026, 7, 8, 22, 55, tzinfo=UTC)
# Past it.
PAST_GRACE = datetime(2026, 7, 8, 23, 10, tzinfo=UTC)
# The reading the counter last gave before it died.
LAST_READING = START + timedelta(minutes=5)

_AIRCON_ENERGY = "sensor.coarse_step_aircon_energy_used"
_AIRCON_COST = "sensor.coarse_step_aircon_actual_cost"
_AIRCON_LAST_READING = "sensor.coarse_step_aircon_last_reading"
_WHOLE_HOME_COST = "sensor.whole_home_actual_cost"
_UNTRACKED_COST = "sensor.untracked_energy_devices_actual_cost"


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


def _power_only_entry() -> MockConfigEntry:
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
                title="Wall Lights",
                data={
                    CONF_NAME: "Wall Lights",
                    CONF_POWER_ENTITY: "sensor.wall_lights_power",
                },
                unique_id=None,
            )
        ],
    )


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return state.state


def _published(hass: HomeAssistant, entity_id: str) -> Decimal:
    return Decimal(_state(hass, entity_id))


def _zero_point(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return state.attributes.get(ATTR_LAST_RESET)


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: datetime
) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def _household_with_a_running_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """A set-up household whose tracked device carries real accumulated money."""
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to(LAST_READING)
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()

    # Past the lateness margin, so the interval closes and the figures publish.
    await _tick(hass, freezer, START + timedelta(minutes=30))
    return entry


async def _go_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entity_id: str
) -> None:
    freezer.move_to(OUTAGE)
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()


async def test_a_device_says_when_its_source_last_reported(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - a household whose tracked device is reporting normally
    await _household_with_a_running_device(hass, freezer)

    # Then - the moment of its last reading is published, which answers the
    # question without any tooling at all: a person reading the device page sees
    # how long ago the figures beside it last moved.
    assert _state(hass, _AIRCON_LAST_READING) == LAST_READING.isoformat()


async def test_a_device_whose_source_stops_withdraws_its_last_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose tracked device has real money against it
    await _household_with_a_running_device(hass, freezer)
    assert _published(hass, _AIRCON_COST) > 0

    # When - that device's energy counter goes unavailable and stays there
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")
    await _tick(hass, freezer, PAST_GRACE)

    # Then - the entity whose job is to say so withdraws itself. That is the one
    # vocabulary an unavailable-entity check already understands, which is what
    # the report asked for: the figures themselves are present and healthy, so
    # nothing else here is something Spook or Watchman could ever notice.
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNAVAILABLE


async def test_a_devices_costs_are_never_withdrawn_with_its_source(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The half that protects the ordinary case (ADR-0024).

    A radiator that ran all week and was then unplugged for eight months really
    did cost what it says. Withdrawing that figure for the whole winter would
    answer a rare fault - a sensor that dies while its device runs on - by
    degrading the common one, and we cannot tell the two apart.
    """
    # Given - a device with a week's money against it
    await _household_with_a_running_device(hass, freezer)
    cost = _published(hass, _AIRCON_COST)
    energy = _published(hass, _AIRCON_ENERGY)

    # When - it is unplugged, and stays unplugged for a season
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")
    await _tick(hass, freezer, PAST_GRACE)
    await _tick(hass, freezer, START + timedelta(days=240))

    # Then - every figure still reads what it cost, all winter
    assert _published(hass, _AIRCON_COST) == cost
    assert _published(hass, _AIRCON_ENERGY) == energy
    assert _zero_point(hass, _AIRCON_COST) is None


async def test_a_brief_outage_withdraws_nothing(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose tracked device has real money against it
    await _household_with_a_running_device(hass, freezer)

    # When - the counter blips out for less than the grace period, as it does on
    # every integration reload
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")
    await _tick(hass, freezer, DURING_GRACE)

    # Then - nothing is said. An entity that flickered on every reload is one a
    # household mutes, and a muted signal is worse than the staleness it
    # discloses.
    assert _state(hass, _AIRCON_LAST_READING) == LAST_READING.isoformat()


async def test_the_house_figures_keep_publishing_through_a_device_outage(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose tracked device has gone unavailable for good
    await _household_with_a_running_device(hass, freezer)
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")

    # When - the outage passes the grace and the house meter keeps reporting
    freezer.move_to(PAST_GRACE)
    hass.states.async_set("sensor.grid_import", "2.0", _ENERGY)
    await hass.async_block_till_done()
    await _tick(hass, freezer, PAST_GRACE + timedelta(minutes=30))

    # Then - whole home and Untracked are still numbers. The energy the silent
    # device used still reached the house meter, so the total is still right and
    # that energy lands in the remainder.
    assert _published(hass, _WHOLE_HOME_COST) > 0
    assert _published(hass, _UNTRACKED_COST) > 0
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNAVAILABLE


async def test_a_source_that_comes_back_says_so_at_its_new_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a device whose Last Reading was withdrawn after its counter died
    await _household_with_a_running_device(hass, freezer)
    cost = _published(hass, _AIRCON_COST)
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")
    await _tick(hass, freezer, PAST_GRACE)
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNAVAILABLE

    # When - the counter reports again, at the reading it was last seen at
    back = PAST_GRACE + timedelta(minutes=5)
    freezer.move_to(back)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    await _tick(hass, freezer, back + timedelta(minutes=1))

    # Then - it clears itself and names the new reading. Nothing to acknowledge
    # at either end: a household that fixes a sensor, or simply plugs a heater
    # back in, is never asked to dismiss anything (HEA-24).
    assert _state(hass, _AIRCON_LAST_READING) == back.isoformat()

    # ...and the money is exactly what it was throughout
    assert _published(hass, _AIRCON_COST) == cost


@pytest.mark.usefixtures("recorder_mock")
async def test_an_outage_books_no_negative_change_in_the_money_statistics(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """What Home Assistant records across an outage, not what we published.

    The risk this ADR had to clear. A figure that fell to zero while its source
    was away, or came back stamped with a fresh zero point, is read by the
    compiler as a cycle starting again - which put -94.86 on Cost Savings for the
    reference home (HEA-122). Withdrawing nothing is what makes this hold, and it
    is worth recording that it does.
    """
    # Given - a household with money accumulated on its figures, compiled into
    # statistics the way a live instance's would be
    await _household_with_a_running_device(hass, freezer)
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=START + timedelta(minutes=30))
    await async_wait_recording_done(hass)

    # When - the device's counter dies for long enough to be noticed, then comes
    # back at the reading it left
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")
    await _tick(hass, freezer, PAST_GRACE)
    # Asserted, not assumed: with nothing withdrawn this test would be exercising
    # an ordinary quiet stretch rather than an outage.
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNAVAILABLE
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=PAST_GRACE)
    await async_wait_recording_done(hass)

    back = PAST_GRACE + timedelta(minutes=5)
    freezer.move_to(back)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    await _tick(hass, freezer, back + timedelta(minutes=1))
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=back)
    await async_wait_recording_done(hass)

    # Then - nothing was booked as a fall, and the recovery invents nothing
    # either: energy a source never reported is energy it never used.
    assert all(change >= 0 for change in _changes(hass, _AIRCON_COST))
    assert all(change >= 0 for change in _changes(hass, _AIRCON_ENERGY))
    assert _changes(hass, _AIRCON_COST)[-1] == 0.0


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


async def test_the_last_reading_survives_a_restart_mid_outage(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Where the moment comes from, and why it is not the sensor's own state.

    A household restarting mid-outage would otherwise come back with nothing to
    show: the entity was unavailable when it went down, so its own restored state
    says only that. It reads the engine's position instead, which is persisted
    for the accounting's sake and carries the moment of the last reading with it.
    """
    # Given - a device whose Last Reading has been withdrawn
    entry = await _household_with_a_running_device(hass, freezer)
    await _go_unavailable(hass, freezer, "sensor.coarse_step_energy")
    await _tick(hass, freezer, PAST_GRACE)
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNAVAILABLE

    # When - Home Assistant restarts while the source is still gone, and the
    # counter reports again afterwards
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    back = PAST_GRACE + timedelta(minutes=10)
    freezer.move_to(back)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    await _tick(hass, freezer, back + timedelta(minutes=1))

    # Then - it names the new reading, having carried the old one across
    assert _state(hass, _AIRCON_LAST_READING) == back.isoformat()


async def test_a_source_removed_from_home_assistant_withdraws_it_too(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose tracked device has real money against it
    await _household_with_a_running_device(hass, freezer)

    # When - the counter is not merely unavailable but gone from Home Assistant,
    # as it is when its integration is removed
    freezer.move_to(OUTAGE)
    hass.states.async_remove("sensor.coarse_step_energy")
    await hass.async_block_till_done()
    # An absent state carries no timestamp of its own, so the grace runs from the
    # first publication that finds it gone - a minute away on a live instance.
    await _tick(hass, freezer, OUTAGE + timedelta(minutes=1))
    await _tick(hass, freezer, PAST_GRACE)

    # Then - it is withdrawn on the same grounds. A reading that is absent moves
    # the figures exactly as little as one that is unavailable.
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNAVAILABLE


async def test_a_device_whose_source_has_never_reported_has_no_last_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - a household configured against a counter that has a state
    # but has never produced a reading this engine could count (HEA-69)
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", STATE_UNAVAILABLE)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - unknown, not a guess and not a withdrawal. Nothing has stopped here;
    # nothing has started, and saying "unavailable" would claim a fault where
    # there has only ever been silence.
    assert _state(hass, _AIRCON_LAST_READING) == STATE_UNKNOWN


async def test_a_power_only_device_follows_its_power_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Through the Integral helper, which is what the engine actually reads.

    A power-only device's readings reach the engine from an auto-created
    `integration` helper, not from the sensor the household chose - so this only
    holds because that helper propagates its own source's unavailability. Home
    Assistant's behaviour, not ours, and asserted end to end rather than assumed:
    if it ever stops, every power-only device silently loses this disclosure.
    """
    # Given - a running household whose one device is power-only
    freezer.move_to(START)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.wall_lights_power", "100", _POWER)
    entry = _power_only_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # The helper integrates between readings, so the lights have to report twice
    # before there is any energy for the engine to count.
    freezer.move_to(LAST_READING)
    hass.states.async_set("sensor.wall_lights_power", "100", _POWER)
    await hass.async_block_till_done()
    await _tick(hass, freezer, START + timedelta(minutes=30))
    assert _state(hass, "sensor.wall_lights_last_reading") not in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    )

    # When - the power sensor dies, so the helper over it has nothing to integrate
    await _go_unavailable(hass, freezer, "sensor.wall_lights_power")
    await _tick(hass, freezer, PAST_GRACE)

    # Then - the device's Last Reading is withdrawn, one hop further down the
    # chain, while its cost figures carry on reading what the lights cost
    assert _state(hass, "sensor.wall_lights_last_reading") == STATE_UNAVAILABLE
    assert _state(hass, "sensor.wall_lights_actual_cost") not in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    )
