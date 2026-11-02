"""A battery's usable capacity can come from a sensor (HEA-244, ADR-0035).

Some battery systems publish the usable capacity their management system
calculates, which follows the battery as it ages. A battery entry takes one
beside the typed figure, and one reader decides which is in force: the sensor's
reading, then the last capacity used while the sensor is silent, then the typed
figure. A change in capacity is a revaluation of what the battery holds, never a
loss.
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
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.battery_capacity import (
    Capacity,
    CapacitySource,
    capacity_of,
)
from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CAPACITY_ENTITY,
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
from custom_components.home_energy_advisor.energy_dashboard import differences_from
from custom_components.home_energy_advisor.house_inputs import (
    batteries_of,
    battery_from,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_PATH = "custom_components.home_energy_advisor.config_flow.async_get_manager"
_ENERGY = {
    "device_class": "energy",
    "state_class": "total_increasing",
    "unit_of_measurement": "kWh",
}
# A capacity as a battery management system publishes it: stored energy, with
# no state class, since it is not a counter.
_CAPACITY = "sensor.growatt_usable_capacity"
_STORED_KWH = {"device_class": "energy_storage", "unit_of_measurement": "kWh"}
_STORED_WH = {"device_class": "energy_storage", "unit_of_measurement": "Wh"}

_SENSED: dict[str, Any] = {
    CONF_NAME: "Growatt",
    CONF_BATTERY_CHARGE_ENTITY: "sensor.growatt_charge",
    CONF_BATTERY_DISCHARGE_ENTITY: "sensor.growatt_discharge",
    CONF_BATTERY_SOC_ENTITY: "sensor.growatt_level",
    CONF_BATTERY_CAPACITY_ENTITY: _CAPACITY,
}
# The same battery before a capacity sensor was chosen.
_UNSENSED = {k: v for k, v in _SENSED.items() if k != CONF_BATTERY_CAPACITY_ENTITY}
TYPED = Decimal("5.0")
LAST_USED = Decimal("4.6")


# The reader


@pytest.mark.parametrize(
    ("reading", "attributes", "expected"),
    [
        ("4.8", _STORED_KWH, Capacity(Decimal("4.8"), CapacitySource.SENSOR)),
        # Converted as the meters are, exactly
        ("4800", _STORED_WH, Capacity(Decimal("4.8"), CapacitySource.SENSOR)),
        # Silent: the last capacity used, never zero
        ("unavailable", _STORED_KWH, Capacity(LAST_USED, CapacitySource.LAST_USED)),
        ("unknown", _STORED_KWH, Capacity(LAST_USED, CapacitySource.LAST_USED)),
        # Not a capacity: kept out rather than guessed at
        (
            "4.8",
            {"unit_of_measurement": "kW"},
            Capacity(LAST_USED, CapacitySource.LAST_USED),
        ),
        ("4.8", {}, Capacity(LAST_USED, CapacitySource.LAST_USED)),
        ("0", _STORED_KWH, Capacity(LAST_USED, CapacitySource.LAST_USED)),
        ("-4.8", _STORED_KWH, Capacity(LAST_USED, CapacitySource.LAST_USED)),
        ("nan", _STORED_KWH, Capacity(LAST_USED, CapacitySource.LAST_USED)),
        ("charging", _STORED_KWH, Capacity(LAST_USED, CapacitySource.LAST_USED)),
    ],
)
def test_a_capacity_sensor_is_read_and_its_silence_keeps_the_last_capacity(
    hass: HomeAssistant, reading: str, attributes: dict[str, str], expected: Capacity
) -> None:
    # Given - a battery with both a sensor and a typed figure
    hass.states.async_set(_CAPACITY, reading, attributes)
    battery = battery_from("Growatt", {**_SENSED, CONF_BATTERY_CAPACITY_KWH: 5.0})

    # When / Then
    assert capacity_of(hass, battery, LAST_USED) == expected


def test_a_sensor_silent_since_setup_falls_back_on_the_typed_figure(
    hass: HomeAssistant,
) -> None:
    # Given - no capacity used yet, and a sensor that has not reported
    hass.states.async_set(_CAPACITY, "unavailable", _STORED_KWH)
    battery = battery_from("Growatt", {**_SENSED, CONF_BATTERY_CAPACITY_KWH: 5.0})

    # When / Then
    assert capacity_of(hass, battery, None) == Capacity(TYPED, CapacitySource.TYPED)


def test_a_sensor_that_does_not_exist_falls_back_like_a_silent_one(
    hass: HomeAssistant,
) -> None:
    # Given - the sensor was removed, and nothing typed
    battery = battery_from("Growatt", _SENSED)

    # When / Then
    assert capacity_of(hass, battery, LAST_USED) == Capacity(
        LAST_USED, CapacitySource.LAST_USED
    )
    assert capacity_of(hass, battery, None) is None


def test_a_typed_capacity_wins_over_the_last_one_used(hass: HomeAssistant) -> None:
    # Given - no sensor, and a typed figure just corrected under Reconfigure
    battery = battery_from("Growatt", {**_UNSENSED, CONF_BATTERY_CAPACITY_KWH: 5.0})

    # When / Then - the correction takes effect; it is revalued, not ignored
    assert capacity_of(hass, battery, LAST_USED) == Capacity(
        TYPED, CapacitySource.TYPED
    )


def test_a_battery_with_no_capacity_at_all_has_none(hass: HomeAssistant) -> None:
    # Given
    battery = battery_from("Growatt", _UNSENSED)

    # When / Then
    assert capacity_of(hass, battery, None) is None


# The battery's settings


@pytest.fixture
def _meters(hass: HomeAssistant) -> Any:  # noqa: ANN401 - a patch
    for meter in (
        "sensor.grid_import",
        "sensor.growatt_charge",
        "sensor.growatt_discharge",
    ):
        hass.states.async_set(meter, "100", _ENERGY)
    hass.states.async_set(
        "sensor.growatt_level",
        "50",
        {"device_class": "battery", "unit_of_measurement": "%"},
    )
    hass.states.async_set(_CAPACITY, "4.8", _STORED_KWH)
    with patch(_PATH, AsyncMock(return_value=SimpleNamespace(data=None))):
        yield


async def _add_battery(hass: HomeAssistant, answers: dict[str, Any]) -> Any:  # noqa: ANN401 - flow results
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_BATTERY), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], answers
    )
    return entry, result


@pytest.mark.usefixtures("_meters")
async def test_a_level_can_be_read_against_a_capacity_sensor(
    hass: HomeAssistant,
) -> None:
    # Given / When - a level and a capacity sensor, nothing typed
    entry, result = await _add_battery(hass, _SENSED)

    # Then - accepted, and the battery knows what it holds
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (battery,) = batteries_of(entry).values()
    assert battery.capacity_entity == _CAPACITY
    assert battery.capacity is None
    assert battery.knows_its_contents


@pytest.mark.usefixtures("_meters")
async def test_a_capacity_sensor_that_is_not_energy_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given - a sensor reporting power, which no capacity is
    hass.states.async_set(_CAPACITY, "4.8", {"unit_of_measurement": "kW"})

    # When
    _entry, result = await _add_battery(hass, _SENSED)

    # Then - refused where it was chosen, as a meter in kW is
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BATTERY_CAPACITY_ENTITY: "unit_not_energy"}


@pytest.mark.usefixtures("_meters")
async def test_a_level_with_neither_capacity_is_still_refused(
    hass: HomeAssistant,
) -> None:
    # Given / When
    _entry, result = await _add_battery(hass, _UNSENSED)

    # Then - on the typed figure, the field every battery has
    assert result["errors"] == {CONF_BATTERY_CAPACITY_KWH: "capacity_needed"}


# The Energy Dashboard comparison


def test_a_battery_following_a_capacity_sensor_still_matches_the_energy_dashboard(
    hass: HomeAssistant,
) -> None:
    # Given - the Energy Dashboard holds the battery's original typed capacity,
    # and the entry here follows the battery's own sensor instead
    prefs = {
        "energy_sources": [
            {
                "type": "battery",
                "stat_energy_to": "sensor.growatt_charge",
                "stat_energy_from": "sensor.growatt_discharge",
                "stat_soc": "sensor.growatt_level",
                "capacity": 5.0,
            }
        ]
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_BATTERY,
                title="Growatt",
                data=_SENSED,
                unique_id=None,
            )
        ],
    )

    # When
    found = differences_from(hass, prefs, entry)

    # Then - the same battery, so nothing to ask about and nothing to replace
    assert (found.theirs, found.ours) == ((), ())


# Through the coordinator


def _metered_house() -> MockConfigEntry:
    """Two batteries, the second reading its capacity from a sensor."""
    anker: dict[str, Any] = {
        CONF_NAME: "Anker Solix",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
        CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
        CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
        CONF_BATTERY_CAPACITY_KWH: 4.0,
    }
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
            for battery in (anker, _SENSED)
        ],
    )


async def _a_span_whose_capacity_falls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry
) -> None:
    """The two-battery loss span (HEA-182), the second capacity falling mid-span.

    It falls from 1 kWh to 800 Wh while the second battery reads 50%
    throughout, which is 0.5 kWh before the fall and 0.4 after it, with no
    energy moving. The pool still lost 0.3 kWh.
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
    hass.states.async_set(_CAPACITY, "1.0", _STORED_KWH)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def interval(
        at: datetime, readings: dict[str, tuple[str, dict[str, str]]]
    ) -> None:
        freezer.move_to(at)
        for entity_id, (value, attributes) in readings.items():
            hass.states.async_set(entity_id, value, attributes)
        await hass.async_block_till_done()
        freezer.move_to(at + timedelta(minutes=35))
        async_fire_time_changed(hass, fire_all=True)
        await hass.async_block_till_done()

    percent = {"device_class": "battery"}
    await interval(
        datetime(2026, 7, 8, 22, 5, tzinfo=UTC),
        {
            "sensor.grid_import": ("4.0", _ENERGY),
            "sensor.anker_charge": ("3.0", _ENERGY),
            "sensor.growatt_charge": ("1.0", _ENERGY),
            "sensor.house_load": ("1.0", _ENERGY),
            "sensor.anker_level": ("50", percent),
            "sensor.growatt_level": ("50", percent),
        },
    )
    await interval(
        datetime(2026, 7, 8, 22, 45, tzinfo=UTC),
        {
            "sensor.grid_import": ("6.0", _ENERGY),
            "sensor.anker_charge": ("4.5", _ENERGY),
            "sensor.growatt_charge": ("1.5", _ENERGY),
            "sensor.house_load": ("1.5", _ENERGY),
            "sensor.anker_level": ("80", percent),
            _CAPACITY: ("800", _STORED_WH),
        },
    )
    freezer.move_to(datetime(2026, 7, 9, 23, 20, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} was never created"
    return state.state


async def test_a_capacity_sensor_that_falls_books_no_loss(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When - the second battery's capacity falls by a fifth mid-span
    await _a_span_whose_capacity_falls(hass, freezer, _metered_house())

    # Then - the pool and each share are what an unchanged capacity gives: the
    # 0.1 kWh the fall took off the second battery is not a loss
    assert _state(hass, "sensor.battery_losses_energy_used") == "0.300000"
    assert _state(hass, "sensor.battery_losses_anker_solix_energy_used") == "0.112500"
    assert _state(hass, "sensor.battery_losses_growatt_energy_used") == "0.187500"


async def test_the_download_says_which_capacity_is_in_force(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given / When
    entry = _metered_house()
    await _a_span_whose_capacity_falls(hass, freezer, entry)

    # Then - each battery's capacity, where it came from, and the revaluation
    diagnostics = entry.runtime_data.diagnostics()
    batteries = {b["name"]: b for b in diagnostics["config"]["batteries"]}
    assert batteries["Growatt"]["capacity_entity"] == _CAPACITY
    assert batteries["Growatt"]["capacity_in_force"] == {
        "kwh": "0.8",
        "source": "sensor",
    }
    assert batteries["Anker Solix"]["capacity_entity"] is None
    assert batteries["Anker Solix"]["capacity_in_force"] == {
        "kwh": "4.0",
        "source": "typed",
    }
    revalued = diagnostics["battery"]["capacity"]["last_revaluation"]
    assert (revalued["from_kwh"], revalued["to_kwh"], revalued["kwh"]) == (
        "1.0",
        "0.8",
        "-0.1",
    )
