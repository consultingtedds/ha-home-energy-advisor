"""A battery is entered one per battery, as Home Assistant's battery systems are.

Home Assistant's Energy Dashboard holds each battery as its own battery system:
a charge meter, a discharge meter, an optional state-of-charge sensor and an
optional usable capacity. So does this integration, as a battery entry beside
the device entries, prefilled from the Energy Dashboard and pooled into one
battery for the accounting (ADR-0031).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
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
    CONF_GRID_IMPORT_ENTITY,
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
