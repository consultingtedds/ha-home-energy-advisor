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

    # Then — four concept sensors exist for each device, the Untracked remainder and
    # the Whole Home aggregate (the hub's devices-registry sensor is separate):
    # 4 groups x 4 concepts = 16
    registry = er.async_get(hass)
    concept_sensors = [
        e
        for e in registry.entities.values()
        if e.platform == DOMAIN
        and e.domain == "sensor"
        and e.translation_key in _CONCEPTS
    ]
    assert len(concept_sensors) == 16
    assert {e.translation_key for e in concept_sensors} == set(_CONCEPTS)


async def test_untracked_is_a_normal_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with the Untracked remainder
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the Untracked remainder is a normal device (entry_type None), like the
    # real tracked devices: it reads as a genuine, intentional entry, not a service
    # device. (Marking it SERVICE did not suppress HA's area-assignment prompt, so
    # that approach was dropped in favour of a clearer name — HEA-44.)
    devices = dr.async_get(hass)
    untracked = devices.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_untracked")}
    )
    assert untracked is not None
    assert untracked.entry_type is None


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


async def test_untracked_costs_use_total_not_total_increasing_state_class(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with the Untracked remainder
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the Untracked remainder's energy and grid-priced costs are `total`, not
    # `total_increasing`: a late device correction legitimately pulls them down, and
    # `total_increasing` would misread that as a meter reset (HEA-48). Cost Savings
    # is `total` here as it is on every device.
    registry = er.async_get(hass)
    expected = {
        "energy_used": "total",
        "actual_cost": "total",
        "cost_without_solar": "total",
        "cost_savings": "total",
    }
    for concept, state_class in expected.items():
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_untracked_{concept}"
        )
        assert entity_id is not None, f"no untracked {concept} sensor"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["state_class"] == state_class


async def test_whole_home_aggregate_publishes_the_monotonic_total(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the Whole Home aggregate is its own device, and its energy/cost totals
    # stay `total_increasing` (they only ever grow — corrections add to the home)
    devices = dr.async_get(hass)
    whole_home = devices.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_whole_home")}
    )
    assert whole_home is not None
    registry = er.async_get(hass)
    energy_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_whole_home_energy_used"
    )
    assert energy_id is not None
    energy_state = hass.states.get(energy_id)
    assert energy_state is not None
    assert energy_state.attributes["state_class"] == "total_increasing"

    # When — one interval is accounted (import 1 kWh, device draws 0.6 @ €0.30)
    await _run_one_interval(hass, freezer)

    # Then — the whole home rolls up the full consumption and its real cost, the sum
    # of the tracked device and the Untracked remainder
    def state_of(concept: str) -> Decimal:
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_whole_home_{concept}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return Decimal(state.state)

    assert state_of("energy_used") == Decimal("1.0")
    assert state_of("actual_cost") == Decimal("0.30")


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


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fire a finalisation tick so coordinator entities recompute their state."""
    freezer.tick(60)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def test_devices_registry_sensor_lists_devices_with_slug_name_and_flags(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration with two tracked devices and Untracked
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # a tick so the sensor recomputes once the per-device entities are registered
    await _tick(hass, freezer)

    # Then — one devices-registry sensor exists, its state the tracked-device count
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_devices"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2"

    # ...and its `devices` attribute is the authoritative list: real names, entity
    # slugs, and the Untracked row flagged
    by_key = {device["key"]: device for device in state.attributes["devices"]}
    assert by_key["guest_bedroom_aircon"]["name"] == "Guest Bedroom Aircon"
    assert by_key["guest_bedroom_aircon"]["untracked"] is False
    assert by_key["guest_bedroom_aircon"]["device_id"]
    assert "hallway_lights" in by_key
    untracked = by_key["untracked_energy_devices"]
    assert untracked["untracked"] is True
    assert untracked["name"] == "Untracked Energy Devices"


async def test_devices_registry_sensor_lives_on_the_hub_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the sensor is grouped under a single hub device, not a tracked device
    devices = dr.async_get(hass)
    hub = devices.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert hub is not None
    assert hub.name == "Home Energy Advisor"
    registry = er.async_get(hass)
    resolved = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_devices"
    )
    assert resolved is not None
    registry_entry = registry.async_get(resolved)
    assert registry_entry is not None
    assert registry_entry.device_id == hub.id
