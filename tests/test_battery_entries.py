"""A battery is entered one per battery, as Home Assistant's battery systems are.

Home Assistant's Energy Dashboard holds each battery as its own battery system:
a charge meter, a discharge meter, an optional state-of-charge sensor and an
optional usable capacity. So does this integration, as a battery entry beside
the device entries, prefilled from the Energy Dashboard and pooled into one
battery for the accounting (ADR-0031).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENCY,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
)
from custom_components.home_energy_advisor.house_inputs import batteries_of

if TYPE_CHECKING:
    from collections.abc import Iterator

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_PATH = "custom_components.home_energy_advisor.config_flow.async_get_manager"
_ENERGY = {
    "device_class": "energy",
    "state_class": "total_increasing",
    "unit_of_measurement": "kWh",
}
_HOUSE = {
    CONF_PRICE_ENTITY: "sensor.electricity_price_import",
    CONF_CURRENCY: "EUR",
    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
}
# Discussion 42's household, as their Energy Dashboard holds the two batteries.
_ANKER = {
    "type": "battery",
    "name": "Anker Solix",
    "stat_energy_to": "sensor.anker_charge",
    "stat_energy_from": "sensor.anker_discharge",
    "stat_soc": "sensor.anker_level",
    "capacity": 2.7,
}
_GROWATT = {
    "type": "battery",
    "stat_energy_to": "sensor.growatt_charge",
    "stat_energy_from": "sensor.growatt_discharge",
}


@pytest.fixture(autouse=True)
def _meters(hass: HomeAssistant) -> Iterator[None]:
    hass.states.async_set(
        "sensor.electricity_price_import", "0.234", {"unit_of_measurement": "EUR/kWh"}
    )
    for meter in (
        "sensor.grid_import",
        "sensor.anker_charge",
        "sensor.anker_discharge",
        "sensor.growatt_charge",
        "sensor.growatt_discharge",
    ):
        hass.states.async_set(meter, "100", _ENERGY)
    for level in ("sensor.anker_level", "sensor.growatt_level"):
        hass.states.async_set(
            level, "50", {"device_class": "battery", "unit_of_measurement": "%"}
        )
    with patch(_PATH, AsyncMock(return_value=SimpleNamespace(data=None))):
        yield


def _with_energy_dashboard(*sources: dict[str, Any]) -> Any:  # noqa: ANN401 - a patch
    prefs = SimpleNamespace(data={"energy_sources": list(sources)})
    return patch(_PATH, AsyncMock(return_value=prefs))


# Setup


async def test_setup_offers_the_energy_dashboards_batteries_filled_in(
    hass: HomeAssistant,
) -> None:
    # Given - an Energy Dashboard holding two battery systems
    with _with_energy_dashboard(_ANKER, _GROWATT):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        # When - the house screen is answered, and both batteries are taken
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _HOUSE
        )
        assert result["step_id"] == "batteries"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"batteries": ["0", "1"]}
        )

    # Then - one battery entry each, holding exactly what the Energy Dashboard
    # does, and a name for the one it never named
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    batteries = sorted(batteries_of(entry).values(), key=lambda b: b.name)
    assert [b.name for b in batteries] == ["Anker Solix", "Battery 2"]
    anker, growatt = batteries
    assert anker.charge == "sensor.anker_charge"
    assert anker.discharge == "sensor.anker_discharge"
    assert anker.level == "sensor.anker_level"
    assert str(anker.capacity) == "2.7"
    assert growatt.charge == "sensor.growatt_charge"
    assert growatt.level is None
    assert growatt.capacity is None


async def test_setup_takes_only_the_batteries_chosen(hass: HomeAssistant) -> None:
    # Given / When - only the second battery is ticked
    with _with_energy_dashboard(_ANKER, _GROWATT):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _HOUSE
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"batteries": ["1"]}
        )

    # Then
    charges = [b.charge for b in batteries_of(result["result"]).values()]
    assert charges == ["sensor.growatt_charge"]


async def test_setup_without_energy_dashboard_batteries_skips_the_step(
    hass: HomeAssistant,
) -> None:
    # Given / When - no battery in the Energy Dashboard
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _HOUSE)

    # Then - the entry is created straight away, with no battery
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert batteries_of(result["result"]) == {}


async def test_the_house_screen_no_longer_asks_about_the_battery(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Then - its meters, level and capacity are the battery entry's now
    data_schema = result["data_schema"]
    assert data_schema is not None
    fields = {str(marker) for marker in data_schema.schema}
    assert fields.isdisjoint(
        {
            CONF_BATTERY_CHARGE_ENTITY,
            CONF_BATTERY_DISCHARGE_ENTITY,
            CONF_BATTERY_SOC_ENTITY,
            CONF_BATTERY_CAPACITY_KWH,
        }
    )


# Add battery


async def _house(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, version=6, data=dict(_HOUSE))
    entry.add_to_hass(hass)
    return entry


async def _add_battery(
    hass: HomeAssistant, entry: MockConfigEntry, answers: dict[str, Any]
) -> Any:  # noqa: ANN401 - a flow result
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_BATTERY), context={"source": SOURCE_USER}
    )
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], answers
    )


async def test_a_battery_is_added_with_its_meters_level_and_capacity(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = await _house(hass)

    # When
    result = await _add_battery(
        hass,
        entry,
        {
            CONF_NAME: "Garage battery",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
            CONF_BATTERY_CAPACITY_KWH: 13.5,
        },
    )

    # Then
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (battery,) = batteries_of(entry).values()
    assert battery.name == "Garage battery"
    assert battery.level == "sensor.anker_level"
    assert str(battery.capacity) == "13.5"


async def test_a_level_without_a_capacity_is_refused(hass: HomeAssistant) -> None:
    # Given / When - a percentage with nothing to say what it is a percentage of
    entry = await _house(hass)
    result = await _add_battery(
        hass,
        entry,
        {
            CONF_NAME: "Garage battery",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
        },
    )

    # Then - refused on the capacity, where the answer goes (HEA-178)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BATTERY_CAPACITY_KWH: "capacity_needed"}


async def test_a_battery_capacity_in_watt_hours_is_refused(hass: HomeAssistant) -> None:
    # Given / When - the HEA-227 mistake, on the battery's own entry
    entry = await _house(hass)
    result = await _add_battery(
        hass,
        entry,
        {
            CONF_NAME: "Garage battery",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
            CONF_BATTERY_CAPACITY_KWH: 1500,
        },
    )

    # Then
    assert result["errors"] == {CONF_BATTERY_CAPACITY_KWH: "capacity_not_kwh"}


@pytest.mark.parametrize(
    ("capacity", "accepted"),
    [(200, True), (200.1, False)],
)
async def test_the_capacity_limit_is_two_hundred_kwh(
    hass: HomeAssistant, capacity: float, *, accepted: bool
) -> None:
    # Given / When - either side of the limit, generous enough for several
    # stacked home batteries entered as one (HEA-227)
    entry = await _house(hass)
    result = await _add_battery(
        hass,
        entry,
        {
            CONF_NAME: "Garage battery",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
            CONF_BATTERY_CAPACITY_KWH: capacity,
        },
    )

    # Then
    if accepted:
        assert result["type"] is FlowResultType.CREATE_ENTRY
    else:
        assert result["errors"] == {CONF_BATTERY_CAPACITY_KWH: "capacity_not_kwh"}


async def test_editing_a_battery_refuses_a_capacity_in_watt_hours(
    hass: HomeAssistant,
) -> None:
    # Given - a battery entered with a correct capacity
    entry = await _house(hass)
    answers = {
        CONF_NAME: "Garage battery",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
        CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
        CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
        CONF_BATTERY_CAPACITY_KWH: 1.5,
    }
    await _add_battery(hass, entry, answers)
    (battery_id,) = batteries_of(entry)

    # When - it is edited to the figure in watt-hours
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_BATTERY),
        context={"source": "reconfigure", "subentry_id": battery_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**answers, CONF_BATTERY_CAPACITY_KWH: 1500}
    )

    # Then - refused, and what the battery holds is untouched
    assert result["errors"] == {CONF_BATTERY_CAPACITY_KWH: "capacity_not_kwh"}
    assert str(batteries_of(entry)[battery_id].capacity) == "1.5"


async def test_a_battery_meter_that_is_not_a_counter_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given - a charge meter declared a net total, as one household's was
    hass.states.async_set(
        "sensor.anker_charge",
        "100",
        {**_ENERGY, "state_class": "total"},
    )
    entry = await _house(hass)

    # When
    result = await _add_battery(
        hass,
        entry,
        {
            CONF_NAME: "Garage battery",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
        },
    )

    # Then - refused as a house meter is, for the same reason (ADR-0010)
    assert result["errors"] == {
        CONF_BATTERY_CHARGE_ENTITY: "house_not_total_increasing"
    }


async def test_add_battery_offers_the_next_energy_dashboard_battery(
    hass: HomeAssistant,
) -> None:
    # Given - the first Energy Dashboard battery is already entered
    entry = await _house(hass)
    await _add_battery(
        hass,
        entry,
        {
            CONF_NAME: "Anker Solix",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
        },
    )

    # When - Add battery is opened again
    with _with_energy_dashboard(_ANKER, _GROWATT):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_BATTERY), context={"source": SOURCE_USER}
        )

    # Then - the one not yet added is filled in
    data_schema = result["data_schema"]
    assert data_schema is not None
    suggested = {
        str(marker.schema): marker.description["suggested_value"]
        for marker in data_schema.schema
        if marker.description
    }
    assert suggested[CONF_BATTERY_CHARGE_ENTITY] == "sensor.growatt_charge"
    assert suggested[CONF_BATTERY_DISCHARGE_ENTITY] == "sensor.growatt_discharge"


# Migration


async def test_an_existing_battery_moves_into_its_own_entry(
    hass: HomeAssistant,
) -> None:
    # Given - an entry from 0.13 holding one battery on the house screen
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            **_HOUSE,
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
            CONF_BATTERY_CAPACITY_KWH: 5.0,
        },
    )
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the same battery, now an entry of its own, and nothing about it lost
    assert entry.version == 6
    (battery,) = batteries_of(entry).values()
    assert battery.name == "Battery"
    assert battery.charge == "sensor.anker_charge"
    assert battery.discharge == "sensor.anker_discharge"
    assert battery.level == "sensor.anker_level"
    assert str(battery.capacity) == "5.0"
    for key in (
        CONF_BATTERY_CHARGE_ENTITY,
        CONF_BATTERY_DISCHARGE_ENTITY,
        CONF_BATTERY_SOC_ENTITY,
        CONF_BATTERY_CAPACITY_KWH,
    ):
        assert key not in entry.data


async def test_a_house_without_a_battery_gains_none(hass: HomeAssistant) -> None:
    # Given
    entry = MockConfigEntry(domain=DOMAIN, version=5, data=dict(_HOUSE))
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then
    assert entry.version == 6
    assert batteries_of(entry) == {}


# The pool, as the running integration builds it


async def test_two_battery_entries_are_accounted_as_one_pool(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - two batteries, each with a level and a capacity: 2.7 kWh at 50% and
    # 8 kWh at 25%
    freezer.move_to(datetime(2026, 10, 19, 12, 0, tzinfo=UTC))
    hass.states.async_set("sensor.growatt_level", "25", {"unit_of_measurement": "%"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data=dict(_HOUSE),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_BATTERY,
                title="Anker Solix",
                data={
                    CONF_NAME: "Anker Solix",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
                    CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
                    CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
                    CONF_BATTERY_CAPACITY_KWH: 2.7,
                },
                unique_id=None,
            ),
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_BATTERY,
                title="Growatt",
                data={
                    CONF_NAME: "Growatt",
                    CONF_BATTERY_CHARGE_ENTITY: "sensor.growatt_charge",
                    CONF_BATTERY_DISCHARGE_ENTITY: "sensor.growatt_discharge",
                    CONF_BATTERY_SOC_ENTITY: "sensor.growatt_level",
                    CONF_BATTERY_CAPACITY_KWH: 8,
                },
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    # When - it is set up and runs for a minute
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 10, 19, 12, 1, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Then - both batteries' meters feed the house, and the pool holds their
    # capacity-weighted sum: 1.35 + 2 kWh, as Home Assistant weights them
    diagnostics = entry.runtime_data.diagnostics()
    sources = {
        (source["role"], source["entity"])
        for source in diagnostics["config"]["house_sources"]
    }
    assert {
        ("battery_charge", "sensor.anker_charge"),
        ("battery_charge", "sensor.growatt_charge"),
        ("battery_discharge", "sensor.anker_discharge"),
        ("battery_discharge", "sensor.growatt_discharge"),
    } <= sources
    anchor = diagnostics["battery"]["loss"]["anchor"]
    assert Decimal(anchor["available_kwh"]) == Decimal("3.35")


# Each battery's own Battery Losses


def _metered_house_with(*batteries: dict[str, Any]) -> MockConfigEntry:
    """A house metering everything a loss is measured from, with these batteries."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
            CONF_GENERATION_ENTITY: ["sensor.generation"],
            CONF_HOUSE_CONSUMPTION_ENTITY: "sensor.house_load",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_BATTERY,
                title=battery[CONF_NAME],
                data=battery,
                unique_id=None,
            )
            for battery in batteries
        ],
    )


_ANKER_ENTRY = {
    CONF_NAME: "Anker Solix",
    CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
    CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
    CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
    CONF_BATTERY_CAPACITY_KWH: 4.0,
}
_GROWATT_ENTRY = {
    CONF_NAME: "Growatt",
    CONF_BATTERY_CHARGE_ENTITY: "sensor.growatt_charge",
    CONF_BATTERY_DISCHARGE_ENTITY: "sensor.growatt_discharge",
    CONF_BATTERY_SOC_ENTITY: "sensor.growatt_level",
    CONF_BATTERY_CAPACITY_KWH: 1.0,
}


async def _a_span_with_a_loss(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry
) -> None:
    """The single-battery loss test (HEA-182), its charge split between two.

    Overnight at 30 c the house imports 4 kWh, puts 3 into one battery and 1
    into the other, and draws 1 itself; the levels read 2.0 and 0.5 kWh, which
    only anchors the measurement. Then 2 kWh more is imported, 1.5 and 0.5 go
    into the batteries, and the house draws 0.5. The first battery reaches 3.2
    kWh and the second stays at 0.5, so the pool gained 1.2 of the 1.5 the
    house's meters cannot account for: 0.3 lost, published a day later.
    """
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    for meter in (
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.generation",
        "sensor.house_load",
        "sensor.anker_charge",
        "sensor.anker_discharge",
        "sensor.growatt_charge",
        "sensor.growatt_discharge",
    ):
        hass.states.async_set(meter, "0", _ENERGY)
    for level in ("sensor.anker_level", "sensor.growatt_level"):
        hass.states.async_set(level, "0", {"device_class": "battery"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def interval(at: datetime, readings: dict[str, str]) -> None:
        freezer.move_to(at)
        for meter, value in readings.items():
            attributes = (
                {"device_class": "battery"} if meter.endswith("_level") else _ENERGY
            )
            hass.states.async_set(meter, value, attributes)
        await hass.async_block_till_done()
        freezer.move_to(at + timedelta(minutes=35))
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done()

    await interval(
        datetime(2026, 7, 8, 22, 5, tzinfo=UTC),
        {
            "sensor.grid_import": "4.0",
            "sensor.anker_charge": "3.0",
            "sensor.growatt_charge": "1.0",
            "sensor.house_load": "1.0",
            "sensor.anker_level": "50",
            "sensor.growatt_level": "50",
        },
    )
    await interval(
        datetime(2026, 7, 8, 22, 45, tzinfo=UTC),
        {
            "sensor.grid_import": "6.0",
            "sensor.anker_charge": "4.5",
            "sensor.growatt_charge": "1.5",
            "sensor.house_load": "1.5",
            "sensor.anker_level": "80",
            "sensor.growatt_level": "50",
        },
    )
    freezer.move_to(datetime(2026, 7, 9, 23, 20, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def test_two_batteries_each_publish_their_own_losses(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - two batteries, and a span in which the pool lost 0.3 kWh
    await _a_span_with_a_loss(
        hass, freezer, _metered_house_with(_ANKER_ENTRY, _GROWATT_ENTRY)
    )

    # Then - the pool's Battery Losses is the single-battery figure...
    assert _state(hass, "sensor.battery_losses_energy_used") == "0.300000"
    assert _state(hass, "sensor.battery_losses_actual_cost") == "0.0900"
    # ...and each battery has its share, split 3:5 by the room its own meters
    # left for a loss (1.5 in less 1.2 gained, against 0.5 in and nothing gained)
    anker = "sensor.battery_losses_anker_solix"
    growatt = "sensor.battery_losses_growatt"
    assert _state(hass, f"{anker}_energy_used") == "0.112500"
    assert _state(hass, f"{growatt}_energy_used") == "0.187500"
    assert _state(hass, f"{anker}_actual_cost") == "0.0338"
    assert _state(hass, f"{growatt}_actual_cost") == "0.0562"
    # ...and what each could have earned, which for grid charge is nothing
    # (HEA-229): the engine's tests carry the sunny figures
    assert _state(hass, "sensor.battery_losses_forgone_export") == "0.0000"
    assert _state(hass, f"{anker}_forgone_export") == "0.0000"
    assert _state(hass, f"{growatt}_forgone_export") == "0.0000"


async def test_each_battery_sits_inside_the_pool_on_the_devices_list(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - two batteries
    await _a_span_with_a_loss(
        hass, freezer, _metered_house_with(_ANKER_ENTRY, _GROWATT_ENTRY)
    )

    # Then - each battery's row names the pool's, so a card adding the rows up
    # counts the loss once, and the pool says its figures include theirs
    rows = _device_rows(hass)
    pool = rows["Battery Losses"]
    assert (pool["upstream"], pool["gross"]) == (None, True)
    for name in ("Battery Losses (Anker Solix)", "Battery Losses (Growatt)"):
        assert (rows[name]["upstream"], rows[name]["gross"]) == (pool["key"], False)
    assert rows["Battery Losses (Anker Solix)"]["statistics"] == {
        "energy_used": "sensor.battery_losses_anker_solix_energy_used",
        "actual_cost": "sensor.battery_losses_anker_solix_actual_cost",
        "forgone_export": "sensor.battery_losses_anker_solix_forgone_export",
    }


def _device_rows(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    state = hass.states.get("sensor.home_energy_advisor_devices")
    assert state is not None
    return {row["name"]: row for row in state.attributes["devices"]}


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} was never created"
    return state.state


async def test_one_battery_has_no_second_battery_losses_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - the same span through one battery
    entry = _metered_house_with(_ANKER_ENTRY)
    hass.states.async_set("sensor.growatt_charge", "0", _ENERGY)
    await _a_span_with_a_loss(hass, freezer, entry)

    # Then - its pool is the battery, and nothing repeats it under another name
    registry = dr.async_get(hass)
    names = {
        device.name_by_user or device.name
        for device in dr.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert "Battery Losses" in names
    assert not any(name and name.startswith("Battery Losses (") for name in names)
    # ...and its row is an ordinary one, with nothing inside it
    rows = _device_rows(hass)
    assert [name for name in rows if name.startswith("Battery Losses")] == [
        "Battery Losses"
    ]
    assert rows["Battery Losses"]["gross"] is False
