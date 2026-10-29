"""A change in the Energy Dashboard is offered, never imposed (ADR-0030).

The house inputs are this integration's own. When the Energy Dashboard's
batteries differ from the ones entered here, a Repair lists both and the
household takes the Energy Dashboard's or keeps their own; keeping is
remembered until the Energy Dashboard changes again.

These drive Home Assistant's own Energy Dashboard store and Repairs flow rather
than doubles of them, so the listener, the issue and the fix are the real ones.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENCY,
    CONF_ENERGY_DASHBOARD_ANSWERED,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
)
from custom_components.home_energy_advisor.house_inputs import (
    batteries_of,
    grid_meters_of,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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
# Discussion 42's household: two battery systems in the Energy Dashboard, the
# second with a level but no capacity.
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
    "stat_soc": "sensor.growatt_level",
}
# ...and the one battery they had to enter here before, two summed by a helper.
_SUMMED = {
    CONF_NAME: "Battery",
    CONF_BATTERY_CHARGE_ENTITY: "sensor.batteries_charge",
    CONF_BATTERY_DISCHARGE_ENTITY: "sensor.batteries_discharge",
}
# A dual-rate meter in the Energy Dashboard, the night register at a fixed rate,
# and a standing charge declared beside it as a grid source of its own.
_DAY = {
    "type": "grid",
    "stat_energy_from": "sensor.day_register",
    "entity_energy_price": "sensor.day_price",
}
_NIGHT = {
    "type": "grid",
    "stat_energy_from": "sensor.night_register",
    "number_energy_price": 0.1,
}
_STANDING_CHARGE = {
    "type": "grid",
    "stat_energy_from": "sensor.daily_standing_charge",
    "entity_energy_price": "sensor.day_price",
}
# What a household that set up before the grid was compared answered for: its
# batteries alone, here none.
_ANSWERED_BEFORE_THE_GRID: list[Any] = []


@pytest.fixture(autouse=True)
def _meters(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "sensor.electricity_price_import", "0.234", {"unit_of_measurement": "EUR/kWh"}
    )
    for meter in (
        "sensor.grid_import",
        "sensor.anker_charge",
        "sensor.anker_discharge",
        "sensor.growatt_charge",
        "sensor.growatt_discharge",
        "sensor.batteries_charge",
        "sensor.batteries_discharge",
    ):
        hass.states.async_set(meter, "100", _ENERGY)
    for level in ("sensor.anker_level", "sensor.growatt_level"):
        hass.states.async_set(
            level, "50", {"device_class": "battery", "unit_of_measurement": "%"}
        )
    for register in ("sensor.day_register", "sensor.night_register"):
        hass.states.async_set(register, "100", _ENERGY)
    hass.states.async_set(
        "sensor.day_price", "0.30", {"unit_of_measurement": "EUR/kWh"}
    )
    # A fee, counted in money rather than energy, as a standing charge is.
    hass.states.async_set(
        "sensor.daily_standing_charge", "0.45", {"unit_of_measurement": "EUR"}
    )


async def _energy_dashboard(hass: HomeAssistant, *sources: dict[str, Any]) -> None:
    """Save the Energy Dashboard's sources, as its own editor does."""
    manager = await async_get_manager(hass)
    # Only the sources, as the editor's save sends: the update merges by key,
    # though its type declares every key required.
    update: Any = {"energy_sources": [dict(source) for source in sources]}
    await manager.async_update(update)
    await hass.async_block_till_done()


async def _set_up(
    hass: HomeAssistant,
    *batteries: dict[str, Any],
    answered: list[Any] | dict[str, Any] | None = None,
) -> MockConfigEntry:
    """A running household with these batteries, at version 6.

    ``answered`` is what it last answered for, where it has answered at all.
    """
    data: dict[str, Any] = dict(_HOUSE)
    if answered is not None:
        data[CONF_ENERGY_DASHBOARD_ANSWERED] = answered
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data=data,
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
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _issue(hass: HomeAssistant, entry: MockConfigEntry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"energy_dashboard_changed_{entry.entry_id}"
    )


async def _open(hass: HomeAssistant, entry: MockConfigEntry) -> Any:  # noqa: ANN401
    """Open the Repair, as selecting it in Settings does."""
    await async_setup_component(hass, "repairs", {})
    manager = repairs_flow_manager(hass)
    assert manager is not None
    return await manager.async_init(
        DOMAIN, data={"issue_id": f"energy_dashboard_changed_{entry.entry_id}"}
    )


async def _answer(hass: HomeAssistant, entry: MockConfigEntry, answer: str) -> Any:  # noqa: ANN401
    opened = await _open(hass, entry)
    manager = repairs_flow_manager(hass)
    assert manager is not None
    result = await manager.async_configure(opened["flow_id"], {"next_step_id": answer})
    await hass.async_block_till_done()
    return result


async def test_a_household_summing_two_batteries_is_offered_them(
    hass: HomeAssistant,
) -> None:
    # Given - two batteries in the Energy Dashboard, one summed battery here
    await _energy_dashboard(hass, _ANKER, _GROWATT)

    # When
    entry = await _set_up(hass, _SUMMED)

    # Then - a Repair the household can answer, listing both sides as they will
    # be taken. The second battery's level has no capacity to make kWh of, so it
    # is left behind on take, and the line says so rather than listing it, as
    # HEA-236 found it did
    issue = _issue(hass, entry)
    assert issue is not None
    assert issue.is_fixable
    opened = await _open(hass, entry)
    assert opened["type"] is FlowResultType.MENU
    assert opened["menu_options"] == ["take", "keep"]
    assert opened["description_placeholders"] == {
        "theirs": (
            "- Anker Solix: sensor.anker_charge, sensor.anker_discharge, "
            "sensor.anker_level, 2.7 kWh\n"
            "- Battery 2: sensor.growatt_charge, sensor.growatt_discharge "
            "(level left out: add its capacity)"
        ),
        "ours": "- Battery: sensor.batteries_charge, sensor.batteries_discharge",
    }


async def test_taking_them_enters_the_energy_dashboards_batteries(
    hass: HomeAssistant,
) -> None:
    # Given
    await _energy_dashboard(hass, _ANKER, _GROWATT)
    entry = await _set_up(hass, _SUMMED)

    # When
    result = await _answer(hass, entry, "take")

    # Then - the summed battery gives way to the two, each as the Energy
    # Dashboard holds it; a level with no capacity to make kWh of is left
    # behind, as the form would refuse it
    assert result["type"] is FlowResultType.CREATE_ENTRY
    batteries = sorted(batteries_of(entry).values(), key=lambda b: b.name)
    assert [
        (b.name, b.charge, b.discharge, b.level, str(b.capacity)) for b in batteries
    ] == [
        (
            "Anker Solix",
            "sensor.anker_charge",
            "sensor.anker_discharge",
            "sensor.anker_level",
            "2.7",
        ),
        (
            "Battery 2",
            "sensor.growatt_charge",
            "sensor.growatt_discharge",
            None,
            "None",
        ),
    ]
    # ...and nothing is left to ask about, after the reload it caused too
    assert _issue(hass, entry) is None


async def test_keeping_mine_is_remembered_until_the_energy_dashboard_changes(
    hass: HomeAssistant,
) -> None:
    # Given
    await _energy_dashboard(hass, _ANKER, _GROWATT)
    entry = await _set_up(hass, _SUMMED)

    # When - the household keeps the battery they entered
    result = await _answer(hass, entry, "keep")

    # Then - nothing changes and nothing is asked, across a reload as well
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [b.name for b in batteries_of(entry).values()] == ["Battery"]
    assert _issue(hass, entry) is None
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _issue(hass, entry) is None

    # When - the Energy Dashboard changes again: the second battery's capacity
    await _energy_dashboard(hass, _ANKER, {**_GROWATT, "capacity": 5.0})

    # Then - it is asked about once more
    assert _issue(hass, entry) is not None


async def test_keeping_mine_survives_a_restart_whose_meters_report_late(
    hass: HomeAssistant,
) -> None:
    # Given - batteries that differ from the Energy Dashboard's on purpose, kept,
    # beside a grid meter the Energy Dashboard holds too (discussion 51)
    await _energy_dashboard(hass, _ANKER, _GROWATT, _DAY)
    entry = await _set_up(hass, _SUMMED)
    await _answer(hass, entry, "keep")
    assert _issue(hass, entry) is None

    # When - Home Assistant restarts, and the grid's import meter, a template
    # sensor with no registry entry, has not published anything yet while this
    # integration sets up
    hass.set_state(CoreState.starting)
    hass.states.async_remove("sensor.day_register")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # ...and has by the time Home Assistant has started
    hass.states.async_set("sensor.day_register", "100", _ENERGY)
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Then - nothing is asked: the Energy Dashboard has not changed, only how
    # far through starting Home Assistant was when it was read (HEA-252)
    assert _issue(hass, entry) is None


async def test_a_change_made_while_home_assistant_was_down_is_still_asked(
    hass: HomeAssistant,
) -> None:
    # Given - batteries kept, as above
    await _energy_dashboard(hass, _ANKER, _GROWATT, _DAY)
    entry = await _set_up(hass, _SUMMED)
    await _answer(hass, entry, "keep")

    # When - a restart, after the Energy Dashboard gained a capacity
    hass.set_state(CoreState.starting)
    await _energy_dashboard(hass, _ANKER, {**_GROWATT, "capacity": 5.0}, _DAY)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Then - asked about, once Home Assistant has started
    assert _issue(hass, entry) is not None


async def test_a_capacity_added_there_is_taken_by_the_battery_already_here(
    hass: HomeAssistant,
) -> None:
    # Given - the household's own name for a battery the Energy Dashboard
    # holds with the same meters, and now a level and capacity there
    garage = {
        CONF_NAME: "Garage",
        CONF_BATTERY_CHARGE_ENTITY: "sensor.growatt_charge",
        CONF_BATTERY_DISCHARGE_ENTITY: "sensor.growatt_discharge",
    }
    await _energy_dashboard(hass, {**_GROWATT, "capacity": 5.0})
    entry = await _set_up(hass, garage)
    (battery_id,) = batteries_of(entry)

    # When
    await _answer(hass, entry, "take")

    # Then - the same entry, so its figures carry on, under the same name
    battery = batteries_of(entry)[battery_id]
    assert (battery.name, battery.level, str(battery.capacity)) == (
        "Garage",
        "sensor.growatt_level",
        "5.0",
    )
    assert _issue(hass, entry) is None


@pytest.mark.parametrize(
    "energy_dashboard",
    [
        pytest.param([_ANKER], id="the same battery"),
        pytest.param(
            [{k: v for k, v in _ANKER.items() if k not in {"stat_soc", "capacity"}}],
            id="the same meters, with no level there to take",
        ),
        pytest.param([], id="no batteries there at all"),
    ],
)
async def test_nothing_is_asked_where_there_is_nothing_to_take(
    hass: HomeAssistant, energy_dashboard: list[dict[str, Any]]
) -> None:
    # Given / When
    await _energy_dashboard(hass, *energy_dashboard)
    entry = await _set_up(
        hass,
        {
            CONF_NAME: "Anker Solix",
            CONF_BATTERY_CHARGE_ENTITY: "sensor.anker_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.anker_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.anker_level",
            CONF_BATTERY_CAPACITY_KWH: 2.7,
        },
    )

    # Then
    assert _issue(hass, entry) is None


async def test_a_battery_the_form_would_refuse_is_not_taken(
    hass: HomeAssistant,
) -> None:
    # Given - the Energy Dashboard's battery reads a net meter, which the form
    # refuses because it would skew every figure (HEA-67)
    hass.states.async_set(
        "sensor.growatt_charge", "100", {**_ENERGY, "state_class": "measurement"}
    )
    await _energy_dashboard(hass, _ANKER, _GROWATT)
    entry = await _set_up(hass, _SUMMED)

    # When
    result = await _answer(hass, entry, "take")

    # Then - nothing is half taken, and the question stays open
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "battery_not_countable"
    assert result["description_placeholders"] == {"battery": "Battery 2"}
    assert [b.name for b in batteries_of(entry).values()] == ["Battery"]
    assert _issue(hass, entry) is not None


async def test_setup_is_the_answer_for_the_energy_dashboard_as_it_stands(
    hass: HomeAssistant,
) -> None:
    # Given - two batteries in the Energy Dashboard
    await _energy_dashboard(hass, _ANKER, _GROWATT)

    # When - setup takes only the first
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CURRENCY: "EUR"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Grid",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            CONF_PRICE_ENTITY: "sensor.electricity_price_import",
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"batteries": ["0"]}
    )
    await hass.async_block_till_done()

    # Then - leaving the second out was a choice, and is not asked about again
    entry = result["result"]
    assert [b.name for b in batteries_of(entry).values()] == ["Anker Solix"]
    assert _issue(hass, entry) is None


# Grid meters (HEA-221)


async def test_an_upgrade_counts_as_the_answer_for_the_grid(
    hass: HomeAssistant,
) -> None:
    # Given - a household that answered before grid meters were compared, whose
    # grid meter here is not the Energy Dashboard's, on purpose
    await _energy_dashboard(hass, _DAY)

    # When - it upgrades
    entry = await _set_up(hass, answered=_ANSWERED_BEFORE_THE_GRID)

    # Then - nothing is asked: nothing in the Energy Dashboard has changed, and
    # the household chose its grid meter at setup
    assert _issue(hass, entry) is None

    # When - the Energy Dashboard then gains the night register
    await _energy_dashboard(hass, _DAY, _NIGHT)

    # Then - that change is asked about, listing both sides' grid meters
    assert _issue(hass, entry) is not None
    opened = await _open(hass, entry)
    assert opened["description_placeholders"] == {
        "theirs": (
            "- Grid: sensor.day_register, sensor.day_price\n"
            "- Grid 2: sensor.night_register, 0.1"
        ),
        "ours": "- Grid: sensor.grid_import, sensor.electricity_price_import",
    }


async def test_taking_them_enters_each_register_and_drops_the_old_meter(
    hass: HomeAssistant,
) -> None:
    # Given - a change in the Energy Dashboard's grid since it was answered for
    await _energy_dashboard(hass, _DAY, _NIGHT)
    entry = await _set_up(hass, answered={"batteries": [], "grid": []})
    assert _issue(hass, entry) is not None

    # When
    result = await _answer(hass, entry, "take")

    # Then - the two registers, each at its own price, and nothing left to ask
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [
        (grid.name, grid.imported, grid.price_entity, grid.fixed_price)
        for grid in grid_meters_of(entry).values()
    ] == [
        ("Grid", "sensor.day_register", "sensor.day_price", None),
        ("Grid 2", "sensor.night_register", None, Decimal("0.1")),
    ]
    assert _issue(hass, entry) is None


async def test_a_new_price_there_is_taken_by_the_meter_already_here(
    hass: HomeAssistant,
) -> None:
    # Given - the same import meter on both sides, priced differently there
    await _energy_dashboard(
        hass,
        {
            "type": "grid",
            "stat_energy_from": "sensor.grid_import",
            "number_energy_price": 0.21,
        },
    )
    entry = await _set_up(hass, answered={"batteries": [], "grid": []})
    (grid_id,) = grid_meters_of(entry)

    # When
    await _answer(hass, entry, "take")

    # Then - the same entry under the same name, so its figures carry on, at
    # the Energy Dashboard's price
    grid = grid_meters_of(entry)[grid_id]
    assert (grid.name, grid.price_entity, grid.fixed_price) == (
        "Grid",
        None,
        Decimal("0.21"),
    )


async def test_a_standing_charge_alone_asks_nothing(hass: HomeAssistant) -> None:
    # Given / When - the only grid source there is a fee
    await _energy_dashboard(hass, _STANDING_CHARGE)
    entry = await _set_up(hass, answered={"batteries": [], "grid": []})

    # Then - nothing to take, so nothing is asked (ADR-0032)
    assert _issue(hass, entry) is None


async def test_a_register_the_form_would_refuse_is_not_taken(
    hass: HomeAssistant,
) -> None:
    # Given - the night register is a net meter
    hass.states.async_set(
        "sensor.night_register", "100", {**_ENERGY, "state_class": "total"}
    )
    await _energy_dashboard(hass, _DAY, _NIGHT)
    entry = await _set_up(hass, answered={"batteries": [], "grid": []})

    # When
    result = await _answer(hass, entry, "take")

    # Then - nothing is half taken, and the question stays open
    assert result["reason"] == "grid_meter_not_countable"
    assert result["description_placeholders"] == {"grid": "Grid 2"}
    assert [grid.imported for grid in grid_meters_of(entry).values()] == [
        "sensor.grid_import"
    ]
    assert _issue(hass, entry) is not None
