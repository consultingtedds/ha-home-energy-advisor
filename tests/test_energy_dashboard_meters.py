"""A `total` house meter the Energy Dashboard already uses is accepted (HEA-279).

House inputs must be `total_increasing`, because `total` is also how a net
meter is marked, and the engine reads a falling counter as a reset. Some
integrations mark lifetime counters that only ever rise as `total` too, and a
household using one in their Energy Dashboard was told HEA could not count it
(discussion 58).

The Energy Dashboard's own roles say what such a sensor is: its grid import is
energy from the grid, not a net figure. So a `total` sensor is accepted for the
role the Energy Dashboard uses it in, and for no other. One picked by hand is
still refused.

These drive Home Assistant's own Energy Dashboard store, as the Repair tests do,
so the preferences read are the real ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_CURRENCY,
    CONF_ENERGY_DASHBOARD_ANSWERED,
    CONF_GENERATION_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
)
from custom_components.home_energy_advisor.energy_dashboard import dashboard_meters
from custom_components.home_energy_advisor.house_inputs import (
    batteries_of,
    grid_meters_of,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_COUNTER = {
    "device_class": "energy",
    "state_class": "total_increasing",
    "unit_of_measurement": "kWh",
}
# A lifetime counter that only ever rises, marked `total` by the integration
# that publishes it.
_RISING_TOTAL = {**_COUNTER, "state_class": "total"}

LIFETIME_IMPORT = "sensor.lifetime_grid_import"
LIFETIME_EXPORT = "sensor.lifetime_grid_export"
LIFETIME_GENERATION = "sensor.lifetime_pv_generation"
LIFETIME_CHARGE = "sensor.lifetime_battery_charge"
LIFETIME_DISCHARGE = "sensor.lifetime_battery_discharge"
PRICE = "sensor.grid_buy_price"

_GRID = {
    "type": "grid",
    "stat_energy_from": LIFETIME_IMPORT,
    "stat_energy_to": LIFETIME_EXPORT,
    "entity_energy_price": PRICE,
}
_SOLAR = {"type": "solar", "stat_energy_from": LIFETIME_GENERATION}
_BATTERY = {
    "type": "battery",
    "stat_energy_to": LIFETIME_CHARGE,
    "stat_energy_from": LIFETIME_DISCHARGE,
}


@pytest.fixture(autouse=True)
def _meters(hass: HomeAssistant) -> None:
    hass.states.async_set(PRICE, "0.45", {"unit_of_measurement": "AUD/kWh"})
    for meter in (
        LIFETIME_IMPORT,
        LIFETIME_EXPORT,
        LIFETIME_GENERATION,
        LIFETIME_CHARGE,
        LIFETIME_DISCHARGE,
    ):
        hass.states.async_set(meter, "100", _RISING_TOTAL)


async def _energy_dashboard(hass: HomeAssistant, *sources: dict[str, Any]) -> None:
    """Save the Energy Dashboard's sources, as its own editor does."""
    manager = await async_get_manager(hass)
    update: Any = {"energy_sources": [dict(source) for source in sources]}
    await manager.async_update(update)
    await hass.async_block_till_done()


async def _house_screen(
    hass: HomeAssistant, house: dict[str, Any] | None = None
) -> Any:  # noqa: ANN401 - a flow result
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], house or {CONF_CURRENCY: "AUD"}
    )


# What the Energy Dashboard uses each meter for


def test_the_energy_dashboard_says_which_meter_is_used_for_what() -> None:
    # Given / When
    used = dashboard_meters({"energy_sources": [_GRID, _SOLAR, _BATTERY]})

    # Then
    assert used == {
        CONF_GRID_IMPORT_ENTITY: frozenset({LIFETIME_IMPORT}),
        CONF_GRID_EXPORT_ENTITY: frozenset({LIFETIME_EXPORT}),
        CONF_GENERATION_ENTITY: frozenset({LIFETIME_GENERATION}),
        CONF_BATTERY_CHARGE_ENTITY: frozenset({LIFETIME_CHARGE}),
        CONF_BATTERY_DISCHARGE_ENTITY: frozenset({LIFETIME_DISCHARGE}),
    }


def test_the_older_flow_arrays_say_it_just_the_same() -> None:
    # Given - a dual-rate meter in the lists Home Assistant kept before 2026.9,
    # every register of it, not just the first
    prefs = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [
                    {"stat_energy_from": "sensor.day_register"},
                    {"stat_energy_from": "sensor.night_register"},
                ],
                "flow_to": [{"stat_energy_to": LIFETIME_EXPORT}],
            }
        ]
    }

    # When
    used = dashboard_meters(prefs)

    # Then
    assert used[CONF_GRID_IMPORT_ENTITY] == frozenset(
        {"sensor.day_register", "sensor.night_register"}
    )
    assert used[CONF_GRID_EXPORT_ENTITY] == frozenset({LIFETIME_EXPORT})


def test_a_household_without_an_energy_dashboard_uses_nothing() -> None:
    # Given / When / Then
    assert set(dashboard_meters(None).values()) == {frozenset()}


# Setup


async def test_a_rising_total_the_energy_dashboard_imports_through_is_accepted(
    hass: HomeAssistant,
) -> None:
    # Given - the Energy Dashboard imports through a `total` lifetime counter
    await _energy_dashboard(hass, _GRID)
    result = await _house_screen(hass)

    # When - setup offers it, and it is taken
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"grid_meters": ["0"]}
    )

    # Then - counted, where it was once refused as "cannot count"
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert [grid.imported for grid in grid_meters_of(entry).values()] == [
        LIFETIME_IMPORT
    ]


async def test_the_same_meter_picked_by_hand_for_another_role_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given - the Energy Dashboard uses the counter for export, not import
    await _energy_dashboard(
        hass,
        {
            "type": "grid",
            "stat_energy_from": "sensor.daily_grid_import",
            "stat_energy_to": LIFETIME_IMPORT,
            "entity_energy_price": PRICE,
        },
    )
    hass.states.async_set("sensor.daily_grid_import", "1", _COUNTER)
    result = await _house_screen(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"grid_meters": []}
    )

    # When - it is typed in as the import meter
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Grid",
            CONF_GRID_IMPORT_ENTITY: LIFETIME_IMPORT,
            CONF_PRICE_ENTITY: PRICE,
        },
    )

    # Then - refused: what the Energy Dashboard vouches for is one role, and a
    # `total` sensor in any other is as unknown as it ever was
    assert result["errors"] == {CONF_GRID_IMPORT_ENTITY: "house_not_total_increasing"}


async def test_a_rising_total_the_energy_dashboard_generates_through_is_accepted(
    hass: HomeAssistant,
) -> None:
    # Given - no house meter, so generation is read and checked, and the Energy
    # Dashboard's solar is a `total` lifetime counter
    await _energy_dashboard(hass, _GRID, _SOLAR)

    # When
    result = await _house_screen(
        hass, {CONF_CURRENCY: "AUD", CONF_GENERATION_ENTITY: [LIFETIME_GENERATION]}
    )

    # Then - on to the grid meters, not back to the house screen
    assert result["step_id"] == "grid_meters"


async def test_a_battery_the_energy_dashboard_counts_in_totals_is_taken(
    hass: HomeAssistant,
) -> None:
    # Given
    await _energy_dashboard(hass, _GRID, _BATTERY)
    result = await _house_screen(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"grid_meters": ["0"]}
    )

    # When
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"batteries": ["0"]}
    )

    # Then
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (battery,) = batteries_of(result["result"]).values()
    assert (battery.charge, battery.discharge) == (LIFETIME_CHARGE, LIFETIME_DISCHARGE)


# The Repair offering a change in the Energy Dashboard


async def test_a_rising_total_offered_by_the_repair_is_taken(
    hass: HomeAssistant,
) -> None:
    # Given - a household whose grid meter here is the daily counter, and an
    # Energy Dashboard that has moved to the lifetime one
    hass.states.async_set("sensor.daily_grid_import", "1", _COUNTER)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={
            CONF_PRICE_ENTITY: PRICE,
            CONF_CURRENCY: "AUD",
            CONF_GRID_IMPORT_ENTITY: "sensor.daily_grid_import",
            CONF_ENERGY_DASHBOARD_ANSWERED: {"batteries": [], "grid": []},
        },
    )
    entry.add_to_hass(hass)
    await _energy_dashboard(hass, _GRID)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the Repair is answered with take
    await async_setup_component(hass, "repairs", {})
    manager = repairs_flow_manager(hass)
    assert manager is not None
    opened = await manager.async_init(
        DOMAIN, data={"issue_id": f"energy_dashboard_changed_{entry.entry_id}"}
    )
    result = await manager.async_configure(opened["flow_id"], {"next_step_id": "take"})
    await hass.async_block_till_done()

    # Then
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [grid.imported for grid in grid_meters_of(entry).values()] == [
        LIFETIME_IMPORT
    ]
