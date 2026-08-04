"""Per-device sensor layer (HEA-22): the four figures ADR-0003 fixes.

Each tracked device — and the Untracked remainder — carries Energy Used, Actual
Cost, Cost at Grid Price and Cost Savings. These tests pin the ADR-0003 contract
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
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_SOLAR_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
_CONCEPTS = ("energy_used", "actual_cost", "cost_at_grid_price", "cost_savings")


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
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_energy",
                },
                unique_id=None,
            ),
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Power Only Lights",
                data={
                    CONF_NAME: "Power Only Lights",
                    CONF_POWER_ENTITY: "sensor.power_only_lights_power",
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
            if subentry.title == "Coarse Step Aircon"
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
    # Money is `total`, energy is `total_increasing` (ADR-0007): HA rejects
    # monetary + total_increasing, and only Energy Used is a strictly-rising meter.
    expected = {
        "energy_used": ("energy", "total_increasing", "kWh"),
        "actual_cost": ("monetary", "total", "EUR"),
        "cost_at_grid_price": ("monetary", "total", "EUR"),
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
        "cost_at_grid_price": "total",
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
        if subentry.title == "Power Only Lights"
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
    entity_id = "sensor.coarse_step_aircon_actual_cost"
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
    assert by_key["coarse_step_aircon"]["name"] == "Coarse Step Aircon"
    assert by_key["coarse_step_aircon"]["untracked"] is False
    assert by_key["coarse_step_aircon"]["device_id"]
    assert "power_only_lights" in by_key
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


async def test_reset_rebases_a_sensor_past_its_restored_baseline(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a sensor reading a restored pre-restart baseline plus a fresh run
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entity_id = "sensor.coarse_step_aircon_actual_cost"
    restored = SensorExtraStoredData(
        native_value=Decimal("0.18"), native_unit_of_measurement="EUR"
    )
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "0.18"), restored.as_dict()),)
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal("0.36")

    # When — the household's totals are rebased
    entry.runtime_data.async_reset_totals()
    await hass.async_block_till_done()

    # Then — the sensor reads zero. Clearing the runtime's running total alone
    # would leave it falling back to the €0.18 restored baseline, so the baseline
    # has to go too
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal(0)


async def test_reset_leaves_the_split_reconciling_as_it_accumulates_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running household whose totals have just been rebased
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)
    entry.runtime_data.async_reset_totals()
    await hass.async_block_till_done()

    # When — a further interval is accounted after the rebase
    freezer.move_to(datetime(2026, 7, 8, 23, 0, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "2.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "1.0", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 23, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — the aggregate invariant still holds from the new zero: the tracked
    # device plus the Untracked remainder equal the whole-home total
    def energy(entity_id: str) -> Decimal:
        state = hass.states.get(entity_id)
        assert state is not None
        return Decimal(state.state)

    guest = energy("sensor.coarse_step_aircon_energy_used")
    untracked = energy("sensor.untracked_energy_devices_energy_used")
    assert guest > 0
    assert guest + untracked == energy("sensor.whole_home_energy_used")


async def _run_a_repeating_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Bank one bucket holding a repeating decimal, to make precision observable.

    Both meters move once over a 7-minute span, so the ledger spreads 5/7 of each
    delta into the 22:00 bucket and 2/7 into the 22:05 one. Time then advances far
    enough to finalise only the first, leaving totals that recur forever — which is
    exactly how the live instance came to publish 28-significant-digit states.
    """
    freezer.move_to(datetime(2026, 7, 8, 22, 7, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.5", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 23, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


def _decimal_places(state: str) -> int:
    # A non-int exponent means NaN or Infinity, which no cost sensor may publish.
    exponent = Decimal(state).as_tuple().exponent
    assert isinstance(exponent, int), f"not a finite decimal: {state}"
    return max(0, -exponent)


async def test_published_values_are_rounded_to_the_publishing_precision(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — an interval whose figures recur forever is accounted
    await _run_a_repeating_interval(hass, freezer)

    # Then — no sensor publishes beyond its precision: 6 dp for energy (1 mWh),
    # 4 dp for money. The engine keeps full Decimal precision; this is the
    # boundary where a value becomes a recorded Home Assistant state (HEA-59)
    registry = er.async_get(hass)
    published = 0
    for entity in registry.entities.values():
        if entity.platform != DOMAIN or entity.translation_key not in _CONCEPTS:
            continue
        state = hass.states.get(entity.entity_id)
        assert state is not None
        limit = 6 if entity.translation_key == "energy_used" else 4
        assert _decimal_places(state.state) <= limit, (
            f"{entity.entity_id} published {state.state}"
        )
        published += 1
    assert published == 16

    # And — the rounded figures are the correctly-rounded ones. The guest device
    # drew 5/7 of 0.5 kWh, at 5/7 of 1.0 kWh imported at €0.30
    guest_energy = hass.states.get("sensor.coarse_step_aircon_energy_used")
    guest_cost = hass.states.get("sensor.coarse_step_aircon_actual_cost")
    assert guest_energy is not None
    assert guest_cost is not None
    assert Decimal(guest_energy.state) == Decimal("0.357143")
    assert Decimal(guest_cost.state) == Decimal("0.1071")


async def test_a_restart_does_not_drift_the_running_total(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a sensor restoring the rounded value a previous run published, which
    # is what a restart really hands back (the published state is the baseline)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entity_id = "sensor.coarse_step_aircon_energy_used"
    restored = SensorExtraStoredData(
        native_value=Decimal("0.357143"), native_unit_of_measurement="kWh"
    )
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "0.357143"), restored.as_dict()),)
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the same repeating interval is accounted again after the restart
    await _run_a_repeating_interval(hass, freezer)

    # Then — the total matches rounding the full-precision sum (2 x 5/7 x 0.5 kWh
    # = 0.714285714...), so the restart introduced no drift beyond half an ulp
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal("0.714286")


_BY_SOURCE = ("energy_from_grid", "energy_from_generation", "energy_from_battery")


def _solar_entry() -> MockConfigEntry:
    """A home with solar and export meters, so a bucket is served by a real mix."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_SOLAR_ENTITY: "sensor.solar",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_energy",
                },
                unique_id=None,
            )
        ],
    )


async def _run_a_solar_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Serve 0.7 kWh from 0.4 grid + 0.3 self-consumed solar; the device draws 0.5."""
    for entity in ("sensor.grid_import", "sensor.solar", "sensor.grid_export"):
        hass.states.async_set(entity, "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    hass.states.async_set("sensor.price", "0.30")
    await hass.async_block_till_done()

    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "0.4", _ENERGY)
    hass.states.async_set("sensor.solar", "0.5", _ENERGY)
    hass.states.async_set("sensor.grid_export", "0.2", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.5", _ENERGY)
    await hass.async_block_till_done()

    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def test_each_device_gets_energy_by_source_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a solar home with one tracked device
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    entry = _solar_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — an interval served by a grid/solar mix is accounted
    await _run_a_solar_interval(hass, freezer)

    # Then — the device's energy is published split by the source that served it,
    # so energy self-sufficiency can be charted per device (HEA-51)
    def energy(entity_id: str) -> Decimal:
        state = hass.states.get(entity_id)
        assert state is not None, f"no {entity_id}"
        assert state.attributes["device_class"] == "energy"
        assert state.attributes["unit_of_measurement"] == "kWh"
        return Decimal(state.state)

    assert energy("sensor.coarse_step_aircon_energy_from_grid") == Decimal("0.285714")
    assert energy("sensor.coarse_step_aircon_energy_from_generation") == Decimal(
        "0.214286"
    )
    assert energy("sensor.coarse_step_aircon_energy_from_battery") == Decimal(0)

    # And — the three sum to the device's energy, which is what makes a
    # self-sufficiency percentage total 100 %
    total = sum(
        energy(f"sensor.coarse_step_aircon_{concept}") for concept in _BY_SOURCE
    )
    assert total == energy("sensor.coarse_step_aircon_energy_used")


async def test_untracked_by_source_is_total_because_late_energy_pulls_it_down(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a solar home that has accounted an interval
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    entry = _solar_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_a_solar_interval(hass, freezer)

    # Then — Untracked's by-source figures are `total`, not `total_increasing`: they
    # are derived, so a late correction legitimately pulls them down, which
    # statistics would otherwise misread as a meter reset (ADR-0006)
    for concept in _BY_SOURCE:
        state = hass.states.get(f"sensor.untracked_energy_devices_{concept}")
        assert state is not None, f"no untracked {concept}"
        assert state.attributes["state_class"] == "total"

    # And — a tracked device's stay `total_increasing`: they only ever rise
    for concept in _BY_SOURCE:
        state = hass.states.get(f"sensor.coarse_step_aircon_{concept}")
        assert state is not None
        assert state.attributes["state_class"] == "total_increasing"
