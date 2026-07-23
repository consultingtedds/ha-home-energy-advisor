"""Per-device sensor layer (HEA-22): the four figures ADR-0003 fixes.

Each tracked device — and the Untracked remainder — carries Energy Used, Actual
Cost, Cost Without Solar and Cost Savings. These tests pin the ADR-0003 contract
(unique_id, device_class, state_class, translation_key, unit) because those are
what make long-term statistics and i18n durable, and the restore-on-restart
behaviour that keeps the totals continuous across a Home Assistant restart.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorExtraStoredData
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.core import State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
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
_CONCEPTS = ("energy_used", "actual_cost", "cost_without_solar", "cost_savings")


def _entry() -> MockConfigEntry:
    """A home with one energy-metered device and one power-only device."""
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
            ),
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Hallway Lights",
                data={
                    CONF_NAME: "Hallway Lights",
                    CONF_POWER_ENTITY: "sensor.hallway_power",
                },
                unique_id=None,
            ),
        ],
    )


def _guest_subentry_id(entry: MockConfigEntry) -> str:
    return str(
        next(
            subentry_id
            for subentry_id, subentry in entry.subentries.items()
            if subentry.title == "Guest Bedroom Aircon"
        )
    )


def _seed_states(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)


async def _run_one_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Import 1 kWh over an interval; the guest device draws 0.6 of it."""
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def test_setup_creates_the_four_sensors_for_every_device_and_untracked(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a home with two devices (one energy-metered, one power-only)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When — the integration starts
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — four sensors exist for each device plus the Untracked remainder
    registry = er.async_get(hass)
    hea_sensors = [
        e
        for e in registry.entities.values()
        if e.platform == DOMAIN and e.domain == "sensor"
    ]
    assert len(hea_sensors) == 12
    assert {e.translation_key for e in hea_sensors} == set(_CONCEPTS)


async def test_untracked_is_a_service_device_while_real_devices_are_not(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with one real tracked device and the Untracked
    # remainder
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the Untracked remainder is a SERVICE device: a virtual aggregate, so
    # Home Assistant should not prompt the user to place it in an area...
    devices = dr.async_get(hass)
    untracked = devices.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_untracked")}
    )
    assert untracked is not None
    assert untracked.entry_type is dr.DeviceEntryType.SERVICE

    # ...while a real tracked device stays a normal device the user can assign
    guest = devices.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_{_guest_subentry_id(entry)}")}
    )
    assert guest is not None
    assert guest.entry_type is None


async def test_each_concept_carries_its_adr_0003_identity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — each of the guest device's four sensors matches the ADR-0003 table
    registry = er.async_get(hass)
    subentry_id = _guest_subentry_id(entry)
    expected = {
        "energy_used": ("energy", "total_increasing", "kWh"),
        "actual_cost": ("monetary", "total_increasing", "EUR"),
        "cost_without_solar": ("monetary", "total_increasing", "EUR"),
        "cost_savings": ("monetary", "total", "EUR"),
    }
    for concept, (device_class, state_class, unit) in expected.items():
        unique_id = f"{entry.entry_id}_{subentry_id}_{concept}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"no entity for {concept}"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["device_class"] == device_class
        assert state.attributes["state_class"] == state_class
        assert state.attributes["unit_of_measurement"] == unit


async def test_sensors_publish_the_running_totals_over_an_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration reading zero
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — one interval is accounted (import 1 kWh, device draws 0.6 @ €0.30)
    await _run_one_interval(hass, freezer)

    # Then — the guest device's energy and actual cost are published...
    registry = er.async_get(hass)
    subentry_id = _guest_subentry_id(entry)

    def state_of(device_key: str, concept: str) -> Decimal:
        unique_id = f"{entry.entry_id}_{device_key}_{concept}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return Decimal(state.state)

    assert state_of(subentry_id, "energy_used") == Decimal("0.6")
    assert state_of(subentry_id, "actual_cost") == Decimal("0.18")
    # ...and the unexplained 0.4 kWh lands on the Untracked remainder
    assert state_of("untracked", "energy_used") == Decimal("0.4")
    assert state_of("untracked", "actual_cost") == Decimal("0.12")


async def test_power_only_device_gets_sensors_reading_zero_until_energy_is_wired(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with an interval already accounted
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then — the power-only device has its four sensors, all at zero, because its
    # energy source (an Integral helper) is not wired until a later ticket
    registry = er.async_get(hass)
    power_id = next(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.title == "Hallway Lights"
    )
    for concept in _CONCEPTS:
        unique_id = f"{entry.entry_id}_{power_id}_{concept}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"no {concept} sensor for the power-only device"
        state = hass.states.get(entity_id)
        assert state is not None
        assert Decimal(state.state) == Decimal(0)


async def test_totals_survive_a_restart_via_restore(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — the actual-cost sensor restored a pre-restart total of €0.18, the
    # runtime having reset its since-startup counter to zero on restart
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    subentry_id = _guest_subentry_id(entry)
    entity_id = "sensor.guest_bedroom_aircon_actual_cost"
    restored = SensorExtraStoredData(
        native_value=Decimal("0.18"), native_unit_of_measurement="EUR"
    )
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "0.18"), restored.as_dict()),)
    )
    entry.add_to_hass(hass)

    # When — the integration starts back up and accounts a fresh interval that
    # adds another €0.18 of actual cost to the guest device
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then — the sensor reads the baseline plus the new run, not just the new run
    registry = er.async_get(hass)
    resolved = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_{subentry_id}_actual_cost"
    )
    assert resolved == entity_id
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal("0.36")
