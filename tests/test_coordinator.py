from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_NAME
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
                title="Guest Bedroom Aircon",
                data={
                    CONF_NAME: "Guest Bedroom Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_energy",
                },
                unique_id=None,
            )
        ],
    )


async def test_coordinator_accounts_for_a_device_over_an_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a configured home with a grid meter, a tracked device, and a price,
    # all reading zero at the top of a 5-minute interval
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — over the interval the house imports 1 kWh and the device draws 0.6
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()

    # ...and the finalisation timer fires well past the lateness margin
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — the coordinator has priced the device at the import rate
    coordinator = entry.runtime_data
    subentry_id = next(iter(entry.subentries))
    guest = coordinator.data.devices[subentry_id]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.18")
    assert coordinator.data.untracked.energy_kwh == Decimal("0.4")


async def test_setup_creates_the_coordinator_and_unload_tears_it_down(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a configured, running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the coordinator is attached and holds initial (zero) totals
    subentry_id = next(iter(entry.subentries))
    assert entry.runtime_data.data.devices[subentry_id].energy_kwh == Decimal(0)

    # When / Then — the entry unloads cleanly, tearing down its listeners and timer
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_price_changes_and_bad_readings_are_handled(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.10")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the price changes, then briefly goes unavailable, and the grid meter
    # reports a garbage value before the real reading lands
    freezer.move_to(datetime(2026, 7, 8, 22, 1, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.price", "unavailable")
    hass.states.async_set("sensor.grid_import", "not-a-number", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — accounting carries on through the noise; the bucket is priced at the
    # rate active at its start (€0.10), the mid-bucket change and outages ignored
    coordinator = entry.runtime_data
    subentry_id = next(iter(entry.subentries))
    guest = coordinator.data.devices[subentry_id]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.06")


async def test_a_watt_hour_device_is_normalised_to_kwh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a device whose energy sensor reports in Wh, not kWh
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    watt_hours = {"unit_of_measurement": "Wh", "device_class": "energy"}
    hass.states.async_set("sensor.guest_energy", "0", watt_hours)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — it climbs by 600 Wh over the interval
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "600", watt_hours)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — that is accounted as 0.6 kWh, not 600
    guest = entry.runtime_data.data.devices[next(iter(entry.subentries))]
    assert guest.energy_kwh == Decimal("0.6")
