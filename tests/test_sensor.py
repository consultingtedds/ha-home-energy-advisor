"""Per-device sensor layer (HEA-22): the four figures ADR-0003 fixes.

Each tracked device - and the Untracked remainder - carries Energy Used, Actual
Cost, Cost at Grid Price and Cost Savings. These tests pin the ADR-0003 contract
(unique_id, device_class, state_class, translation_key, unit) because those are
what make long-term statistics and i18n durable, and the restore-on-restart
behaviour that keeps the totals continuous across a Home Assistant restart.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorExtraStoredData
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_DEVICE_COST_BOUNDS,
    CONF_ENERGY_ENTITY,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.sensor import (
    _BOUND_CONCEPTS as BOUND_DESCRIPTIONS,
)
from custom_components.home_energy_advisor.sensor import (
    _CONCEPTS as CONCEPT_DESCRIPTIONS,
)

if TYPE_CHECKING:
    from typing import Any

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
_CONCEPTS = ("energy_used", "actual_cost", "cost_at_grid_price", "cost_savings")


def _entry(options: dict[str, Any] | None = None) -> MockConfigEntry:
    """A home with one energy-metered device and one power-only device."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        options=options or {},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.coarse_step_energy",
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


def _aircon_subentry_id(entry: MockConfigEntry) -> str:
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
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)


async def _run_one_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Import 1 kWh over an interval; the aircon device draws 0.6 of it."""
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def test_setup_creates_the_four_sensors_for_every_device_and_untracked(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a home with two devices (one energy-metered, one power-only)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When - the integration starts
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - four concept sensors exist for each device, the Untracked remainder and
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
    # Given - a running integration with the Untracked remainder
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the Untracked remainder is a normal device (entry_type None), like the
    # real tracked devices: it reads as a genuine, intentional entry, not a service
    # device. (Marking it SERVICE did not suppress HA's area-assignment prompt, so
    # that approach was dropped in favour of a clearer name - HEA-44.)
    devices = dr.async_get(hass)
    untracked = devices.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_untracked")}
    )
    assert untracked is not None
    assert untracked.entry_type is None


async def test_each_concept_carries_its_adr_0003_identity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - each of the aircon device's four sensors matches the ADR-0003 table
    registry = er.async_get(hass)
    subentry_id = _aircon_subentry_id(entry)
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
    # Given - a running integration with the Untracked remainder
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the Untracked remainder's energy and grid-priced costs are `total`, not
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
    # Given - a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the Whole Home aggregate is its own device, and its energy/cost totals
    # stay `total_increasing` (they only ever grow - corrections add to the home)
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

    # When - one interval is accounted (import 1 kWh, device draws 0.6 @ €0.30)
    await _run_one_interval(hass, freezer)

    # Then - the whole home rolls up the full consumption and its real cost, the sum
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
    # Given - a running integration reading zero
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - one interval is accounted (import 1 kWh, device draws 0.6 @ €0.30)
    await _run_one_interval(hass, freezer)

    # Then - the aircon device's energy and actual cost are published...
    registry = er.async_get(hass)
    subentry_id = _aircon_subentry_id(entry)

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
    # Given - a running integration with an interval already accounted
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - the power-only device has its four sensors, all at zero, because its
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
    # Given - the actual-cost sensor restored a pre-restart total of €0.18, the
    # runtime having reset its since-startup counter to zero on restart
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    subentry_id = _aircon_subentry_id(entry)
    entity_id = "sensor.coarse_step_aircon_actual_cost"
    restored = SensorExtraStoredData(
        native_value=Decimal("0.18"), native_unit_of_measurement="EUR"
    )
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "0.18"), restored.as_dict()),)
    )
    entry.add_to_hass(hass)

    # When - the integration starts back up and accounts a fresh interval that
    # adds another €0.18 of actual cost to the aircon device
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - the sensor reads the baseline plus the new run, not just the new run
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
    # Given - a running integration with two tracked devices and Untracked
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # a tick so the sensor recomputes once the per-device entities are registered
    await _tick(hass, freezer)

    # Then - one devices-registry sensor exists, its state the tracked-device count
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


async def test_every_concept_key_is_the_entity_id_suffix(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a card builds a statistic id as `sensor.<slug>_<concept>` from the
    # concept key alone (`hea-statistics.js`), and an entity id is built from the
    # *translated name*. The two agree only while every concept's key and its
    # name say the same thing, and nothing enforced that.
    #
    # HEA-84 shipped with `cost_floor` named "Lowest Possible Cost". The cards
    # asked for `sensor.x_cost_floor` forever, against an entity that was really
    # `sensor.x_lowest_possible_cost`, and both sides' tests passed because the
    # frontend fixture was built from the same wrong constant as the card.
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry({CONF_DEVICE_COST_BOUNDS: True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When / Then - for every concept on every device, including the aggregates
    registry = er.async_get(hass)
    keys = [_aircon_subentry_id(entry), "untracked", "whole_home"]
    checked = 0
    for device_key in keys:
        for concept in (*CONCEPT_DESCRIPTIONS, *BOUND_DESCRIPTIONS):
            unique_id = f"{entry.entry_id}_{device_key}_{concept.key}"
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id is None:
                continue  # a concept this device does not carry
            assert entity_id.endswith(f"_{concept.key}"), (
                f"{entity_id} cannot be reached as sensor.<slug>_{concept.key}"
            )
            checked += 1
    # Guard the guard: a typo in the keys above would pass vacuously.
    assert checked >= len(CONCEPT_DESCRIPTIONS) * 2


async def test_devices_registry_sensor_locates_the_whole_home_without_listing_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a card needs the whole-home entity slug to show a household figure
    # no device carries: the always-published cost range (ADR-0016)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_devices"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None

    # Then - it is a separate attribute, resolved the same way a device's is. Not
    # a row in `devices`: every card sums that list, and the whole home is the sum
    # (Σ devices + Untracked), so a row there would double the household's totals.
    whole_home = state.attributes["whole_home"]
    assert whole_home["key"] == "whole_home"
    assert whole_home["name"] == "Whole Home"
    assert whole_home["device_id"]
    assert "whole_home" not in {device["key"] for device in state.attributes["devices"]}
    assert state.state == "2"


async def test_devices_registry_sensor_lives_on_the_hub_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the sensor is grouped under a single hub device, not a tracked device
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
    # Given - a sensor reading a restored pre-restart baseline plus a fresh run
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

    # When - the household's totals are rebased
    entry.runtime_data.async_reset_totals()
    await hass.async_block_till_done()

    # Then - the sensor reads zero. Clearing the runtime's running total alone
    # would leave it falling back to the €0.18 restored baseline, so the baseline
    # has to go too
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal(0)


async def test_reset_leaves_the_split_reconciling_as_it_accumulates_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running household whose totals have just been rebased
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)
    entry.runtime_data.async_reset_totals()
    await hass.async_block_till_done()

    # When - a further interval is accounted after the rebase
    freezer.move_to(datetime(2026, 7, 8, 23, 0, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "2.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "1.0", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 23, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then - the aggregate invariant still holds from the new zero: the tracked
    # device plus the Untracked remainder equal the whole-home total
    def energy(entity_id: str) -> Decimal:
        state = hass.states.get(entity_id)
        assert state is not None
        return Decimal(state.state)

    aircon = energy("sensor.coarse_step_aircon_energy_used")
    untracked = energy("sensor.untracked_energy_devices_energy_used")
    assert aircon > 0
    assert aircon + untracked == energy("sensor.whole_home_energy_used")


async def _run_a_repeating_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Bank one bucket holding a repeating decimal, to make precision observable.

    Both meters move once over a 7-minute span, so the ledger spreads 5/7 of each
    delta into the 22:00 bucket and 2/7 into the 22:05 one. Time then advances far
    enough to finalise only the first, leaving totals that recur forever - which is
    exactly how the live instance came to publish 28-significant-digit states.
    """
    freezer.move_to(datetime(2026, 7, 8, 22, 7, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0.5", _ENERGY)
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
    # Given - a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - an interval whose figures recur forever is accounted
    await _run_a_repeating_interval(hass, freezer)

    # Then - no sensor publishes beyond its precision: 6 dp for energy (1 mWh),
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

    # And - the rounded figures are the correctly-rounded ones. The aircon device
    # drew 5/7 of 0.5 kWh, at 5/7 of 1.0 kWh imported at €0.30
    coarse_step_energy = hass.states.get("sensor.coarse_step_aircon_energy_used")
    aircon_cost = hass.states.get("sensor.coarse_step_aircon_actual_cost")
    assert coarse_step_energy is not None
    assert aircon_cost is not None
    assert Decimal(coarse_step_energy.state) == Decimal("0.357143")
    assert Decimal(aircon_cost.state) == Decimal("0.1071")


async def test_a_restart_does_not_drift_the_running_total(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a sensor restoring the rounded value a previous run published, which
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

    # When - the same repeating interval is accounted again after the restart
    await _run_a_repeating_interval(hass, freezer)

    # Then - the total matches rounding the full-precision sum (2 x 5/7 x 0.5 kWh
    # = 0.714285714...), so the restart introduced no drift beyond half an ulp
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal("0.714286")


_BY_SOURCE = ("energy_from_grid", "energy_from_generation", "energy_from_battery")


def _generation_entry() -> MockConfigEntry:
    """A home with generation and export meters, so a bucket is served by a real mix."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_GENERATION_ENTITY: "sensor.generation",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
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


async def _run_a_generation_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Serve 0.7 kWh from 0.4 grid + 0.3 self-consumed generation; device draws 0.5."""
    for entity in ("sensor.grid_import", "sensor.generation", "sensor.grid_export"):
        hass.states.async_set(entity, "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    hass.states.async_set("sensor.price", "0.30")
    await hass.async_block_till_done()

    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "0.4", _ENERGY)
    hass.states.async_set("sensor.generation", "0.5", _ENERGY)
    hass.states.async_set("sensor.grid_export", "0.2", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0.5", _ENERGY)
    await hass.async_block_till_done()

    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def test_each_device_gets_energy_by_source_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a generating home with one tracked device
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    entry = _generation_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - an interval served by a grid/generation mix is accounted
    await _run_a_generation_interval(hass, freezer)

    # Then - the device's energy is published split by the source that served it,
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

    # And - the three sum to the device's energy, which is what makes a
    # self-sufficiency percentage total 100 %
    total = sum(
        energy(f"sensor.coarse_step_aircon_{concept}") for concept in _BY_SOURCE
    )
    assert total == energy("sensor.coarse_step_aircon_energy_used")


async def test_untracked_by_source_is_total_because_late_energy_pulls_it_down(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a generating home that has accounted an interval
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    entry = _generation_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_a_generation_interval(hass, freezer)

    # Then - Untracked's by-source figures are `total`, not `total_increasing`: they
    # are derived, so a late correction legitimately pulls them down, which
    # statistics would otherwise misread as a meter reset (ADR-0006)
    for concept in _BY_SOURCE:
        state = hass.states.get(f"sensor.untracked_energy_devices_{concept}")
        assert state is not None, f"no untracked {concept}"
        assert state.attributes["state_class"] == "total"

    # And - a tracked device's stay `total_increasing`: they only ever rise
    for concept in _BY_SOURCE:
        state = hass.states.get(f"sensor.coarse_step_aircon_{concept}")
        assert state is not None
        assert state.attributes["state_class"] == "total_increasing"


def _place_source_in_an_area(
    hass: HomeAssistant, *, entity_id: str, area: str, floor: str | None = None
) -> None:
    """Put a source sensor on a real device in a real area, as a household would."""
    areas = ar.async_get(hass)
    the_area = areas.async_get_or_create(area)
    if floor is not None:
        the_floor = fr.async_get(hass).async_create(floor)
        the_area = areas.async_update(the_area.id, floor_id=the_floor.floor_id)

    source_entry = MockConfigEntry(domain="aircon_integration")
    source_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_entry.entry_id,
        identifiers={("aircon_integration", entity_id)},
        name="Coarse Step Aircon",
    )
    dr.async_get(hass).async_update_device(device.id, area_id=the_area.id)
    registered = er.async_get(hass).async_get_or_create(
        "sensor",
        "aircon_integration",
        f"unique_{entity_id}",
        suggested_object_id=entity_id.removeprefix("sensor."),
        device_id=device.id,
        config_entry=source_entry,
    )
    # Registering after a state of the same name exists would silently yield
    # `..._2` and quietly defeat the test, so pin it.
    assert registered.entity_id == entity_id, (
        f"source registered as {registered.entity_id}, not {entity_id}"
    )


async def _devices_payload(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> dict[str, Any]:
    await _tick(hass, freezer)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_devices"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return {device["key"]: device for device in state.attributes["devices"]}


async def test_devices_sensor_publishes_the_real_statistic_ids(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the devices-registry sensor is read
    by_key = await _devices_payload(hass, entry, freezer)

    # Then - each concept carries the entity id it actually has, so no card ever
    # composes one. A card that builds `sensor.<key>_actual_cost` is guessing, and
    # guessing in English is how HEA-89 arose (ADR-0018)
    statistics = by_key["coarse_step_aircon"]["statistics"]
    registry = er.async_get(hass)
    for concept in _CONCEPTS:
        assert statistics[concept] == registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{_aircon_subentry_id(entry)}_{concept}"
        )


async def test_published_statistic_ids_follow_a_renamed_entity(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - an entity id that is not its English concept suffix. Two ordinary
    # causes: a household that renamed the entity, and a non-English instance,
    # where Home Assistant builds the id from the *translated* name for the 41
    # languages in NATIVE_ENTITY_IDS - `es` among them, and HEA's own es.json
    # already says "Coste real" (HEA-89)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_{_aircon_subentry_id(entry)}_actual_cost"
    original = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert original == "sensor.coarse_step_aircon_actual_cost"

    # When - that entity is renamed the way a Spanish instance would have named it
    renamed = "sensor.aire_acondicionado_coste_real"
    registry.async_update_entity(original, new_entity_id=renamed)
    await hass.async_block_till_done()

    # Then - the published id follows the registry rather than the suffix. The
    # key must not be derived by stripping "_actual_cost" either: that suffix is
    # absent here, so stripping leaves the whole id and a card composing from it
    # asks for something that was never created
    by_key = await _devices_payload(hass, entry, freezer)
    aircon = next(
        device
        for device in by_key.values()
        if device["statistics"].get("actual_cost") == renamed
    )
    assert aircon["statistics"]["actual_cost"] == renamed


async def test_devices_sensor_exposes_the_source_devices_area_and_floor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the household's own aircon sensor sits on a device in a room, on a
    # floor, which is where the building hierarchy actually lives
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _place_source_in_an_area(
        hass,
        entity_id="sensor.coarse_step_energy",
        area="Studio",
        floor="First Floor",
    )
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the devices-registry sensor is read
    by_key = await _devices_payload(hass, entry, freezer)

    # Then - the tracked device carries the hierarchy of the sensor it measures, so
    # a card can roll cost up by room and floor without HEA touching any registry
    aircon = by_key["coarse_step_aircon"]
    assert aircon["area_name"] == "Studio"
    assert aircon["floor_name"] == "First Floor"
    assert aircon["area_id"]
    assert aircon["floor_id"]


async def test_devices_sensor_leaves_the_hierarchy_null_when_there_is_none(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose sources are plain sensors with no device at all (a
    # template or YAML sensor), which is ordinary and must not be an error
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the devices-registry sensor is read
    by_key = await _devices_payload(hass, entry, freezer)

    # Then - every location field is null, and nothing is raised
    aircon = by_key["coarse_step_aircon"]
    for field in ("area_id", "area_name", "floor_id", "floor_name"):
        assert aircon[field] is None, f"{field} should be null without a device"

    # And - the Untracked remainder is never in a room by construction
    untracked = by_key["untracked_energy_devices"]
    assert untracked["area_id"] is None
    assert untracked["floor_name"] is None


async def test_an_area_on_the_source_entity_wins_over_its_devices(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a source whose device is in one room but whose entity the user has
    # deliberately reassigned to another. Home Assistant treats the entity-level
    # area as the override, and so must we
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _place_source_in_an_area(hass, entity_id="sensor.coarse_step_energy", area="Studio")
    _seed_states(hass)
    landing = ar.async_get(hass).async_get_or_create("Landing")
    registry = er.async_get(hass)
    source = registry.async_get_entity_id(
        "sensor", "aircon_integration", "unique_sensor.coarse_step_energy"
    )
    assert source is not None
    registry.async_update_entity(source, area_id=landing.id)

    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When / Then - the entity's own area is what the payload reports
    by_key = await _devices_payload(hass, entry, freezer)
    assert by_key["coarse_step_aircon"]["area_name"] == "Landing"


async def test_hierarchy_is_exposed_without_touching_heas_own_devices(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a tracked device whose source sits in a room
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _place_source_in_an_area(hass, entity_id="sensor.coarse_step_energy", area="Studio")
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _tick(hass, freezer)

    # Then - HEA's own device is still unassigned. Assigning it would rewrite every
    # entity id (HA composes `area + device + entity`, doubling the room name), and
    # `suggested_area` is removed in HA 2026.9 - so the hierarchy is exposed as
    # data, never written to the registry
    devices = dr.async_get(hass)
    hea_device = devices.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_{_aircon_subentry_id(entry)}")}
    )
    assert hea_device is not None
    assert hea_device.area_id is None
    assert hass.states.get("sensor.coarse_step_aircon_energy_used") is not None


async def test_unreconciled_energy_reads_zero_when_the_meters_agree(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose device counters and house meter reconcile, which
    # they do even while disagreeing bucket by bucket (HEA-81)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - zero, which is the reading that makes any other reading worth
    # acting on. It is diagnostic: context for the totals, not a headline figure.
    state = hass.states.get("sensor.home_energy_advisor_unreconciled_energy")
    assert state is not None
    assert Decimal(state.state) == Decimal(0)
    assert state.attributes["unit_of_measurement"] == "kWh"
    registry = er.async_get(hass)
    resolved = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_unreconciled_energy"
    )
    assert resolved is not None
    registry_entry = registry.async_get(resolved)
    assert registry_entry is not None
    assert registry_entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_unreconciled_energy_lives_on_the_hub_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - it describes the household's metering, not any one appliance
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then
    hub = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    registry = er.async_get(hass)
    resolved = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_unreconciled_energy"
    )
    assert hub is not None
    assert resolved is not None
    registry_entry = registry.async_get(resolved)
    assert registry_entry is not None
    assert registry_entry.device_id == hub.id


async def test_unreconciled_energy_survives_a_restart_via_restore(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - 0.25 kWh already unreconciled before the restart. The engine counts
    # from zero again on startup, and a figure whose job is to flag a problem
    # must not appear to clear itself every time Home Assistant restarts.
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entity_id = "sensor.home_energy_advisor_unreconciled_energy"
    restored = SensorExtraStoredData(
        native_value=Decimal("0.25"), native_unit_of_measurement="kWh"
    )
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "0.25"), restored.as_dict()),)
    )
    entry.add_to_hass(hass)

    # When - it starts back up and accounts an interval that reconciles cleanly
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - the restored total stands rather than resetting to zero
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal("0.25")


async def test_the_household_is_told_its_cost_band_without_being_asked(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a coarse counter reveals a step that accrued somewhere inside its
    # span, so the household's cost is knowable only to a range (ADR-0016)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - two sensors that make every install honest by default, in money so a
    # near-zero cost cannot explode into a meaningless percentage (HEA-75)
    floor = hass.states.get("sensor.whole_home_lowest_possible_cost")
    actual = hass.states.get("sensor.whole_home_actual_cost")
    ceiling = hass.states.get("sensor.whole_home_highest_possible_cost")
    assert floor is not None
    assert actual is not None
    assert ceiling is not None
    assert Decimal(floor.state) <= Decimal(actual.state) <= Decimal(ceiling.state)
    assert floor.attributes["unit_of_measurement"] == "EUR"
    assert ceiling.attributes["unit_of_measurement"] == "EUR"


async def test_the_cost_band_is_diagnostic_context_not_a_headline_figure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - the bound qualifies a figure; it is not one to read first
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - off the headline device page, still recorded and chartable
    registry = er.async_get(hass)
    for concept in ("lowest_possible_cost", "highest_possible_cost"):
        resolved = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_whole_home_{concept}"
        )
        assert resolved is not None
        registry_entry = registry.async_get(resolved)
        assert registry_entry is not None
        assert registry_entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_per_device_bands_wait_to_be_asked_for(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - two more sensors per device is a real recorder cost on a home with
    # many devices, so the household chooses it (ADR-0016, as `opt_in_cycles` does)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When - no opt-in
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - the household band still stands, composed from parts the engine
    # tracks whether or not it publishes them
    assert hass.states.get("sensor.coarse_step_aircon_lowest_possible_cost") is None
    assert hass.states.get("sensor.coarse_step_aircon_highest_possible_cost") is None
    assert hass.states.get("sensor.whole_home_lowest_possible_cost") is not None


async def test_per_device_bands_appear_once_opted_in(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household that wants to know which of its devices it can price
    # confidently and which it cannot
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry({CONF_DEVICE_COST_BOUNDS: True})
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then - a band per device, bracketing what that device was charged
    floor = hass.states.get("sensor.coarse_step_aircon_lowest_possible_cost")
    actual = hass.states.get("sensor.coarse_step_aircon_actual_cost")
    ceiling = hass.states.get("sensor.coarse_step_aircon_highest_possible_cost")
    assert floor is not None
    assert actual is not None
    assert ceiling is not None
    assert Decimal(floor.state) <= Decimal(actual.state) <= Decimal(ceiling.state)


async def test_the_remainder_publishes_no_band_of_its_own(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - Untracked is derived per slice from meters that reported for that
    # slice, so its floor and ceiling are its cost. Two sensors that can only ever
    # repeat a third are noise, not disclosure.
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry({CONF_DEVICE_COST_BOUNDS: True})
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _run_one_interval(hass, freezer)

    # Then
    assert hass.states.get("sensor.untracked_energy_devices_actual_cost") is not None
    assert (
        hass.states.get("sensor.untracked_energy_devices_lowest_possible_cost") is None
    )
    assert (
        hass.states.get("sensor.untracked_energy_devices_highest_possible_cost") is None
    )


async def test_a_first_install_says_it_is_warming_up_rather_than_broken(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a first install, whose figures sit at zero for ~20 minutes while the
    # lateness margin runs. On the first live install this read as "nothing is
    # working" when the engine was in fact counting correctly (HEA-47)
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)

    # When - it starts, with no interval closed yet
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the sensor sitting at zero says why, where the user is already
    # looking. A Repair was rejected for this: HEA-24 reserves those for degraded
    # inputs, and spending one on normal startup teaches users to dismiss them
    state = hass.states.get("sensor.coarse_step_aircon_actual_cost")
    assert state is not None
    assert Decimal(state.state) == Decimal(0)
    assert state.attributes["warming_up"] is True


async def test_the_warming_up_signal_goes_away_rather_than_turning_false(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a first install
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the first interval closes and real figures appear
    await _run_one_interval(hass, freezer)

    # Then - the attribute is absent, not present-and-false. It exists to explain
    # an anomaly; once there is no anomaly it should cost a household's recorder
    # and templates nothing at all
    state = hass.states.get("sensor.coarse_step_aircon_actual_cost")
    assert state is not None
    assert Decimal(state.state) == Decimal("0.18")
    assert "warming_up" not in state.attributes


async def test_a_restart_with_history_behind_it_is_never_warming_up(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - an established household restarting: the accountant is rebuilt from
    # nothing every startup, so "no interval has closed" is true here too, and on
    # its own it would flag months of history as a fresh install (HEA-47)
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

    # When - it comes back up, before any interval has had time to close
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - no warming-up claim: there is a figure on screen to read, which is
    # the whole thing the signal is there to excuse the absence of. The second
    # half of the condition - a restored baseline - is what tells the two apart
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal("0.18")
    assert "warming_up" not in state.attributes


async def test_a_device_that_has_never_cost_anything_is_not_warming_up(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a device with months of history that has simply never drawn: a
    # seasonal heater out of season, a rail that is genuinely off. It restores a
    # baseline, and that baseline is exactly zero
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entity_id = "sensor.coarse_step_aircon_actual_cost"
    restored = SensorExtraStoredData(
        native_value=Decimal("0.0000"), native_unit_of_measurement="EUR"
    )
    mock_restore_cache_with_extra_data(
        hass, ((State(entity_id, "0.0000"), restored.as_dict()),)
    )
    entry.add_to_hass(hass)

    # When - it restarts, before any interval has closed
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - no warming-up claim. Reading zero is this device's settled answer,
    # not a figure still on its way, and promising one that will never arrive is
    # worse than saying nothing. Restoring *nothing* and restoring *zero* are
    # different facts, so the signal cannot be inferred from the value: found on
    # the live instance where four such sensors claimed it (HEA-47)
    state = hass.states.get(entity_id)
    assert state is not None
    assert Decimal(state.state) == Decimal(0)
    assert "warming_up" not in state.attributes


async def test_the_warming_up_signal_is_kept_out_of_the_recorder(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a first install, whose cost sensors are carrying the signal
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    _seed_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the set Home Assistant actually excludes from recorded state is read
    # (the combined set, assembled down the inheritance chain, rather than the
    # literal declared on any one class - declaring it in the wrong place is the
    # way this fails, and only the combined set can catch that)
    component = hass.data["entity_components"][SENSOR_DOMAIN]
    sensor = next(
        entity
        for entity in component.entities
        if entity.entity_id == "sensor.coarse_step_aircon_actual_cost"
    )
    excluded = sensor._Entity__combined_unrecorded_attributes  # noqa: SLF001

    # Then - a flag that is true for the first 20 minutes of a household's life
    # and never again is noise in the history, recorded once a minute for every
    # HEA entity and every cycle meter mirroring one (HEA-59)
    assert "warming_up" in excluded
