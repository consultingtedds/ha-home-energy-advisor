"""The recorder probe behind the never-reported Repair (HEA-69).

These run against a real recorder rather than a stubbed one: the whole value of
the probe is that it answers "has this sensor ever produced a reading" correctly,
and that answer is the difference between accusing a dead sensor and accusing a
device that is merely switched off for the season.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.home_energy_advisor.source_history import (
    async_has_ever_reported,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


@pytest.mark.usefixtures("recorder_mock")
async def test_a_sensor_with_a_recorded_reading_has_reported(
    hass: HomeAssistant,
) -> None:
    # Given — a counter that produced a reading and then went unavailable, which
    # is what a device switched off for the season looks like
    hass.states.async_set("sensor.guest_aircon_energy", "412.3", _ENERGY)
    hass.states.async_set("sensor.guest_aircon_energy", "unavailable")
    await async_wait_recording_done(hass)

    # When / Then — the earlier reading answers the question
    assert await async_has_ever_reported(hass, "sensor.guest_aircon_energy") is True


@pytest.mark.usefixtures("recorder_mock")
async def test_a_sensor_that_only_ever_yielded_unknown_has_never_reported(
    hass: HomeAssistant,
) -> None:
    # Given — the shape HEA-64 found on a real instance: a well-formed kWh
    # counter that has only ever held `unknown`
    hass.states.async_set("sensor.panel_heater_energy", "unknown", _ENERGY)
    hass.states.async_set("sensor.panel_heater_energy", "unavailable")
    await async_wait_recording_done(hass)

    # When / Then — recorded states exist, but not one of them is a reading
    assert await async_has_ever_reported(hass, "sensor.panel_heater_energy") is False


@pytest.mark.usefixtures("recorder_mock")
async def test_a_sensor_the_recorder_has_never_seen_has_never_reported(
    hass: HomeAssistant,
) -> None:
    # Given — a recorder holding nothing at all for the sensor
    await async_wait_recording_done(hass)

    # When / Then — no history is the same answer as no readings in it
    assert await async_has_ever_reported(hass, "sensor.absent_energy") is False


async def test_the_question_is_unanswerable_without_a_recorder(
    hass: HomeAssistant,
) -> None:
    # Given — an instance running with the recorder disabled, so there is no
    # history to consult. `None` is deliberately not `False`: the caller must be
    # able to tell "no evidence of life" from "no way to look" (ADR-0010)
    hass.states.async_set("sensor.panel_heater_energy", "unknown", _ENERGY)

    # When / Then
    assert await async_has_ever_reported(hass, "sensor.panel_heater_energy") is None
