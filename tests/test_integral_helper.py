"""Feasibility spike + behaviour tests for the native Integral helper (HEA-34).

Power-only devices (WiZ wall lights, Rointe ``effective_power``) carry no energy
counter, so ADR-0004 supports them by auto-creating a native ``integration``
(Riemann-sum) helper on the power sensor; its output energy sensor then feeds the
same ``CumulativeEnergySource`` pipeline. These tests prove the two risky
premises of that decision against real Home Assistant:

1. the helper can be created *programmatically* and produces a working
   power->energy sensor, and
2. it accrues **no phantom energy** across an ``unavailable`` span — the
   "Rointe unplugged for six months" case — which is exactly the reset-on-
   unavailable behaviour our NEVER list demands, inherited for free.

If Home Assistant ever regresses either premise, these go red and the recorded
fallback (internal Riemann sum in the engine) takes over.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.integral_helper import (
    async_ensure_integral_helper,
    integral_output_sensor,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

# WiZ lights and the Rointe towel rail report instantaneous watts (ADR-0004,
# DEVICE_SENSOR_SURVEY): power-only, `measurement`, and `unavailable` when off.
_POWER = {"unit_of_measurement": "W", "device_class": "power"}


def _reading(hass: HomeAssistant, entity_id: str) -> Decimal:
    """Read a sensor's numeric state, asserting it is present and numeric."""
    state = hass.states.get(entity_id)
    assert state is not None
    return Decimal(state.state)


async def test_a_native_integral_helper_integrates_power_to_energy(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a power-only device (living-room wall lights) reporting 100 W
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.living_room_wall_lights_power", "100", _POWER)

    # When — we auto-create a native Integral helper on its power sensor
    entry_id = await async_ensure_integral_helper(
        hass,
        name="Living Room Wall Lights Energy",
        source_entity="sensor.living_room_wall_lights_power",
    )
    await hass.async_block_till_done()

    # Then — a native integration config entry with an output energy sensor exists
    output = integral_output_sensor(hass, entry_id)
    assert output is not None

    # And — after the light holds 100 W for an hour, the helper reports ~100 Wh
    # (100 W x 1 h), integrated by Home Assistant, not by us
    freezer.move_to(datetime(2026, 7, 8, 23, 0, tzinfo=UTC))
    hass.states.async_set("sensor.living_room_wall_lights_power", "100", _POWER)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    state = hass.states.get(output)
    assert state is not None
    assert state.state not in ("unavailable", "unknown")
    assert Decimal(state.state) == pytest.approx(Decimal(100), abs=Decimal(1))


async def test_ensuring_a_helper_twice_reuses_the_existing_one(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a power-only device with a native Integral helper already created
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.living_room_wall_lights_power", "100", _POWER)
    first = await async_ensure_integral_helper(
        hass,
        name="Living Room Wall Lights Energy",
        source_entity="sensor.living_room_wall_lights_power",
    )
    await hass.async_block_till_done()

    # When — setup runs again for the same source (config entry reload)
    second = await async_ensure_integral_helper(
        hass,
        name="Living Room Wall Lights Energy",
        source_entity="sensor.living_room_wall_lights_power",
    )
    await hass.async_block_till_done()

    # Then — the existing helper is reused, not duplicated
    assert second == first
    integration_entries = hass.config_entries.async_entries("integration")
    assert len(integration_entries) == 1


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
                title="Living Room Wall Lights",
                data={
                    CONF_NAME: "Living Room Wall Lights",
                    CONF_POWER_ENTITY: "sensor.living_room_wall_lights_power",
                },
                unique_id=None,
            )
        ],
    )


async def test_removing_a_power_device_removes_its_integral_helper(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration whose one device is power-only, so a native
    # Integral helper was auto-created for it
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", {"device_class": "energy"})
    hass.states.async_set("sensor.living_room_wall_lights_power", "100", _POWER)
    entry = _power_only_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("integration")) == 1
    subentry_id = next(iter(entry.subentries))

    # When — the user removes the device (removing a subentry reloads the entry)
    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()

    # Then — the orphaned Integral helper is cleaned up, not left behind
    assert hass.config_entries.async_entries("integration") == []


async def test_no_phantom_energy_accrues_across_an_unavailable_span(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running Integral helper on a towel-rail power sensor at 100 W,
    # having already integrated an hour's worth of energy
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.master_bathroom_towel_rail_power", "100", _POWER)
    entry_id = await async_ensure_integral_helper(
        hass,
        name="Master Bathroom Towel Rail Energy",
        source_entity="sensor.master_bathroom_towel_rail_power",
    )
    await hass.async_block_till_done()
    output = integral_output_sensor(hass, entry_id)
    assert output is not None

    freezer.move_to(datetime(2026, 7, 8, 23, 0, tzinfo=UTC))
    hass.states.async_set("sensor.master_bathroom_towel_rail_power", "100", _POWER)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    before = _reading(hass, output)

    # When — the rail is unplugged: its power sensor goes unavailable for six hours,
    # then it is switched back on
    hass.states.async_set("sensor.master_bathroom_towel_rail_power", "unavailable")
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 9, 5, 0, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.master_bathroom_towel_rail_power", "100", _POWER)
    await hass.async_block_till_done()
    after = _reading(hass, output)

    # Then — nothing accrued during the outage; a phantom would be 100 W x 6 h =
    # 600 Wh, so anything under 1 Wh proves the gap was treated as no-data
    assert after - before < Decimal(1)
