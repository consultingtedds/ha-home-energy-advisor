"""Behaviour + wiring tests for auto-created utility_meter cycle totals (HEA-23).

Each per-device sensor (Energy Used, Actual Cost, Cost Without Solar, Cost
Savings) and the Untracked remainder get native `utility_meter` helpers for the
enabled cycles (daily + monthly always; weekly/quarterly/yearly opt-in), so users
see "this month so far" figures without any reset logic reimplemented here. The
creation mechanism is the same `SchemaConfigFlowHandler` path proven for the
Integral helper in HEA-34, so these tests focus on the utility_meter specifics:
tracking a monetary source, the net-consumption case for a savings figure that
can fall, idempotency, and cleanup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_CYCLE_WEEKLY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.cycle_meter import (
    async_ensure_utility_meter,
    utility_meter_output_sensor,
)
from custom_components.home_energy_advisor.issues import ISSUE_CYCLE_HELPER_RECREATED

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {
    "device_class": "energy",
    "state_class": "total_increasing",
    "unit_of_measurement": "kWh",
}

_COST = {
    "device_class": "monetary",
    "state_class": "total_increasing",
    "unit_of_measurement": "EUR",
}
# Cost Savings can fall (battery arbitrage), so it is a plain `total`, not
# `total_increasing` (ADR-0003) — its meter must be net-consumption.
_SAVINGS = {
    "device_class": "monetary",
    "state_class": "total",
    "unit_of_measurement": "EUR",
}


async def test_a_utility_meter_accumulates_its_source_within_the_cycle(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a device's Actual Cost sensor reading zero at the top of the day
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    hass.states.async_set("sensor.guest_aircon_actual_cost", "0", _COST)

    # When — we auto-create a daily utility_meter over it
    entry_id = await async_ensure_utility_meter(
        hass,
        name="Guest Bedroom Aircon Actual Cost Daily",
        source_entity="sensor.guest_aircon_actual_cost",
        cycle="daily",
        net_consumption=False,
    )
    await hass.async_block_till_done()

    # Then — the meter publishes an output sensor
    output = utility_meter_output_sensor(hass, entry_id)
    assert output is not None

    # And — as the lifetime cost climbs to €1.20 within the day, the daily meter
    # tracks the €1.20 accrued this cycle
    hass.states.async_set("sensor.guest_aircon_actual_cost", "1.20", _COST)
    await hass.async_block_till_done()
    state = hass.states.get(output)
    assert state is not None
    assert Decimal(state.state) == Decimal("1.20")


async def test_ensuring_a_meter_is_idempotent_per_source_and_cycle(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a daily meter over a device's Actual Cost sensor
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    hass.states.async_set("sensor.guest_aircon_actual_cost", "0", _COST)
    first = await async_ensure_utility_meter(
        hass,
        name="Guest Bedroom Aircon Actual Cost Daily",
        source_entity="sensor.guest_aircon_actual_cost",
        cycle="daily",
        net_consumption=False,
    )
    await hass.async_block_till_done()

    # When — setup runs again for the same source and cycle (reload)
    second = await async_ensure_utility_meter(
        hass,
        name="Guest Bedroom Aircon Actual Cost Daily",
        source_entity="sensor.guest_aircon_actual_cost",
        cycle="daily",
        net_consumption=False,
    )
    # ...but a different cycle over the same source is a distinct meter
    monthly = await async_ensure_utility_meter(
        hass,
        name="Guest Bedroom Aircon Actual Cost Monthly",
        source_entity="sensor.guest_aircon_actual_cost",
        cycle="monthly",
        net_consumption=False,
    )
    await hass.async_block_till_done()

    # Then — the daily meter is reused, and only daily + monthly exist
    assert second == first
    assert monthly != first
    assert len(hass.config_entries.async_entries("utility_meter")) == 2


async def test_a_net_consumption_meter_follows_a_savings_figure_that_falls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a daily meter over a Cost Savings sensor (net consumption)
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    hass.states.async_set("sensor.guest_aircon_cost_savings", "0", _SAVINGS)
    entry_id = await async_ensure_utility_meter(
        hass,
        name="Guest Bedroom Aircon Cost Savings Daily",
        source_entity="sensor.guest_aircon_cost_savings",
        cycle="daily",
        net_consumption=True,
    )
    await hass.async_block_till_done()
    output = utility_meter_output_sensor(hass, entry_id)
    assert output is not None

    # When — savings rise to €2.00, then battery arbitrage pulls the day back to €1.50
    hass.states.async_set("sensor.guest_aircon_cost_savings", "2.00", _SAVINGS)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.guest_aircon_cost_savings", "1.50", _SAVINGS)
    await hass.async_block_till_done()

    # Then — the meter follows the fall rather than treating it as a reset
    state = hass.states.get(output)
    assert state is not None
    assert Decimal(state.state) == Decimal("1.50")


def _entry_with_one_device() -> MockConfigEntry:
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
                title="Guest Bedroom Aircon",
                data={
                    CONF_NAME: "Guest Bedroom Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_energy",
                },
                unique_id=None,
            )
        ],
    )


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_creates_daily_and_monthly_meters_for_every_cost_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When — a home with one tracked device is set up
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    await _set_up(hass, _entry_with_one_device())

    # Then — the device and the Untracked remainder each carry four sensors, and
    # every one gets a daily and a monthly meter: 2 devices x 4 sensors x 2 cycles
    meters = hass.config_entries.async_entries("utility_meter")
    assert len(meters) == 16
    assert {m.options["cycle"] for m in meters} == {"daily", "monthly"}


async def test_opting_into_weekly_adds_a_weekly_meter_per_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — the weekly cycle opted in via options
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    entry = _entry_with_one_device()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_CYCLE_WEEKLY: True})

    # When — the integration is set up
    await _set_up(hass, entry)

    # Then — three cycles now exist: 2 devices x 4 sensors x 3 cycles = 24 meters
    meters = hass.config_entries.async_entries("utility_meter")
    assert len(meters) == 24
    assert {m.options["cycle"] for m in meters} == {"daily", "weekly", "monthly"}


async def test_removing_a_device_removes_its_cycle_meters(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with one device (16 meters incl. Untracked)
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    entry = _entry_with_one_device()
    await _set_up(hass, entry)
    assert len(hass.config_entries.async_entries("utility_meter")) == 16
    subentry_id = next(iter(entry.subentries))

    # When — the device is removed (which reloads the entry)
    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()

    # Then — only the Untracked remainder's meters remain: 1 x 4 sensors x 2 cycles
    assert len(hass.config_entries.async_entries("utility_meter")) == 8


async def test_removing_a_device_less_integration_cleans_up_untracked_meters(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a house-level-only install (no tracked devices), so the only cycle
    # meters are the eight over the Untracked remainder's four sensors
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    await _set_up(hass, entry)
    assert len(hass.config_entries.async_entries("utility_meter")) == 8

    # When — the integration is removed before any device was ever added (the
    # "cancelled part-way through setup" case)
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the Untracked cycle meters are cleaned up, not left orphaned (HEA-42)
    assert hass.config_entries.async_entries("utility_meter") == []


async def test_a_user_deleted_cycle_meter_is_recreated_and_raises_a_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with its full set of cycle meters
    freezer.move_to(datetime(2026, 7, 8, 0, 0, tzinfo=UTC))
    entry = _entry_with_one_device()
    await _set_up(hass, entry)
    assert len(hass.config_entries.async_entries("utility_meter")) == 16

    # When — the user deletes one cycle meter, then the entry reloads
    meter_id = hass.config_entries.async_entries("utility_meter")[0].entry_id
    await hass.config_entries.async_remove(meter_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the meter is recreated and a single aggregate Repair notes it
    assert len(hass.config_entries.async_entries("utility_meter")) == 16
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CYCLE_HELPER_RECREATED)
    assert issue is not None
