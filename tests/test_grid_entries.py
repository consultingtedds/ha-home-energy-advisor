"""A grid meter is entered one per grid source, as the Energy Dashboard holds them.

Home Assistant's Energy Dashboard holds any number of grid sources, each with
its own import meter, price and export meter; a dual-rate meter is two of them,
one per register. So does this integration, as a grid entry beside the device
and battery entries, prefilled from the Energy Dashboard, each register's import
priced at its own rate (ADR-0032).
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
    CONF_CURRENCY,
    CONF_ENERGY_DASHBOARD_ANSWERED,
    CONF_ENERGY_ENTITY,
    CONF_FIXED_PRICE,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
    SUBENTRY_TYPE_GRID,
)
from custom_components.home_energy_advisor.house_inputs import grid_meters_of

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
_HOUSE = {CONF_CURRENCY: "EUR"}
# A dual-rate meter as the Energy Dashboard holds it from 2026.9: one grid source
# per register, each with its own price, the night one a fixed number.
_DAY = {
    "type": "grid",
    "stat_energy_from": "sensor.day_register",
    "stat_energy_to": "sensor.grid_export",
    "entity_energy_price": "sensor.day_price",
}
_NIGHT = {
    "type": "grid",
    "stat_energy_from": "sensor.night_register",
    "entity_energy_price": None,
    "number_energy_price": 0.1,
}
# A daily standing charge, declared as a grid source so that it can be priced.
_STANDING_CHARGE = {
    "type": "grid",
    "stat_energy_from": "sensor.daily_standing_charge",
    "entity_energy_price": "sensor.standing_charge_price",
}


@pytest.fixture(autouse=True)
def _meters(hass: HomeAssistant) -> Iterator[None]:
    for price in ("sensor.day_price", "sensor.standing_charge_price"):
        hass.states.async_set(price, "0.30", {"unit_of_measurement": "EUR/kWh"})
    for meter in ("sensor.day_register", "sensor.night_register", "sensor.grid_export"):
        hass.states.async_set(meter, "100", _ENERGY)
    # A fee, counted in money rather than energy, as a standing charge is.
    hass.states.async_set(
        "sensor.daily_standing_charge",
        "0.45",
        {"state_class": "total_increasing", "unit_of_measurement": "EUR"},
    )
    with patch(_PATH, AsyncMock(return_value=SimpleNamespace(data=None))):
        yield


def _with_energy_dashboard(*sources: dict[str, Any]) -> Any:  # noqa: ANN401 - a patch
    prefs = SimpleNamespace(data={"energy_sources": list(sources)})
    return patch(_PATH, AsyncMock(return_value=prefs))


async def _house_screen(hass: HomeAssistant) -> Any:  # noqa: ANN401 - a flow result
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"], _HOUSE)


def _suggested(result: Any) -> dict[str, Any]:  # noqa: ANN401 - a flow result
    data_schema = result["data_schema"]
    assert data_schema is not None
    return {
        str(marker.schema): marker.description["suggested_value"]
        for marker in data_schema.schema
        if marker.description
    }


# Setup


async def test_setup_offers_each_register_with_its_own_price(
    hass: HomeAssistant,
) -> None:
    # Given - a dual-rate meter in the Energy Dashboard
    with _with_energy_dashboard(_DAY, _NIGHT):
        result = await _house_screen(hass)
        assert result["step_id"] == "grid_meters"

        # When - both are taken
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"grid_meters": ["0", "1"]}
        )

    # Then - one grid entry each, priced as the Energy Dashboard prices it: the
    # day register by its sensor, the night one by its number
    assert result["type"] is FlowResultType.CREATE_ENTRY
    day, night = grid_meters_of(result["result"]).values()
    assert (day.name, day.imported, day.price_entity, day.exported) == (
        "Grid",
        "sensor.day_register",
        "sensor.day_price",
        "sensor.grid_export",
    )
    assert (night.name, night.imported, night.fixed_price, night.exported) == (
        "Grid 2",
        "sensor.night_register",
        Decimal("0.1"),
        None,
    )


async def test_setup_reads_the_older_flow_arrays_just_the_same(
    hass: HomeAssistant,
) -> None:
    """Home Assistant before 2026.9 held the flows, and their prices, in arrays.

    `hacs.json` supports instances from 2026.7, whose stored preferences carry
    this shape until they are next loaded, and the prices are named differently
    in it (HEA-117, HEA-209).
    """
    # Given
    older = {
        "type": "grid",
        "flow_from": [
            {
                "stat_energy_from": "sensor.day_register",
                "entity_energy_price": "sensor.day_price",
            }
        ],
        "flow_to": [
            {
                "stat_energy_to": "sensor.grid_export",
                "entity_energy_price": "sensor.export_price",
            }
        ],
    }

    # When
    with _with_energy_dashboard(older):
        result = await _house_screen(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"grid_meters": ["0"]}
        )

    # Then - the import price is the import flow's, never the export flow's
    (grid,) = grid_meters_of(result["result"]).values()
    assert (grid.imported, grid.price_entity, grid.exported) == (
        "sensor.day_register",
        "sensor.day_price",
        "sensor.grid_export",
    )


async def test_a_standing_charge_is_not_offered(hass: HomeAssistant) -> None:
    # Given - the real meter, and a standing charge declared as a second grid
    # source, as the reference home has it
    with _with_energy_dashboard(_STANDING_CHARGE, _DAY):
        result = await _house_screen(hass)

    # Then - only the energy counter is offered. A fee is not energy, and the
    # figures are the cost of the energy used, not the bill (ADR-0032)
    options = result["data_schema"].schema["grid_meters"].config["options"]
    assert [option["label"] for option in options] == [
        "Grid: sensor.day_register (sensor.day_price)"
    ]


async def test_ticking_none_goes_on_to_enter_a_grid_meter_by_hand(
    hass: HomeAssistant,
) -> None:
    # Given - a household who keeps different meters here on purpose
    with _with_energy_dashboard(_DAY):
        result = await _house_screen(hass)

        # When - none of the Energy Dashboard's is ticked, and their own is
        # entered instead
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"grid_meters": []}
        )
        assert result["step_id"] == "grid_meter"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Mains",
                CONF_GRID_IMPORT_ENTITY: "sensor.night_register",
                CONF_FIXED_PRICE: 0.25,
            },
        )

    # Then
    (grid,) = grid_meters_of(result["result"]).values()
    assert (grid.name, grid.imported, grid.fixed_price) == (
        "Mains",
        "sensor.night_register",
        Decimal("0.25"),
    )


async def test_an_unpriced_grid_source_is_suggested_on_the_form_instead(
    hass: HomeAssistant,
) -> None:
    # Given - a grid source tracked by a cost statistic, so it carries no price
    unpriced = {"type": "grid", "stat_energy_from": "sensor.day_register"}

    # When
    with _with_energy_dashboard(unpriced):
        result = await _house_screen(hass)

    # Then - nothing to take as it stands, so the form opens with its meter in
    # and the price left for the household
    assert result["step_id"] == "grid_meter"
    assert _suggested(result) == {
        CONF_NAME: "Grid",
        CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
    }


async def test_a_register_that_cannot_be_counted_is_refused_at_setup(
    hass: HomeAssistant,
) -> None:
    # Given - the night register published as a `total` net counter
    hass.states.async_set(
        "sensor.night_register", "100", {**_ENERGY, "state_class": "total"}
    )
    with _with_energy_dashboard(_DAY, _NIGHT):
        result = await _house_screen(hass)

        # When - both are ticked
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"grid_meters": ["0", "1"]}
        )

    # Then - refused as a hand-entered one would be, and nothing is created
    assert result["step_id"] == "grid_meters"
    assert result["errors"] == {"grid_meters": "grid_meter_not_countable"}


# Add grid meter


async def _house(
    hass: HomeAssistant,
    *grids: dict[str, Any],
    devices: tuple[dict[str, Any], ...] = (),
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data=dict(_HOUSE),
        subentries_data=[
            *(
                ConfigSubentryData(
                    subentry_type=SUBENTRY_TYPE_GRID,
                    title=grid[CONF_NAME],
                    data=grid,
                    unique_id=None,
                )
                for grid in grids
            ),
            *(
                ConfigSubentryData(
                    subentry_type=SUBENTRY_TYPE_DEVICE,
                    title=device[CONF_NAME],
                    data=device,
                    unique_id=None,
                )
                for device in devices
            ),
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def _add_grid_meter(
    hass: HomeAssistant, entry: MockConfigEntry, answers: dict[str, Any]
) -> Any:  # noqa: ANN401 - a flow result
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GRID), context={"source": SOURCE_USER}
    )
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], answers
    )


@pytest.mark.parametrize(
    "price",
    [
        pytest.param({}, id="neither"),
        pytest.param(
            {CONF_PRICE_ENTITY: "sensor.day_price", CONF_FIXED_PRICE: 0.1},
            id="both",
        ),
    ],
)
async def test_a_grid_meter_needs_exactly_one_price(
    hass: HomeAssistant, price: dict[str, Any]
) -> None:
    # Given / When
    entry = await _house(hass)
    result = await _add_grid_meter(
        hass,
        entry,
        {CONF_NAME: "Day", CONF_GRID_IMPORT_ENTITY: "sensor.day_register", **price},
    )

    # Then - with neither there is nothing to price it at, and with both it is
    # unclear which is meant
    assert result["errors"] == {"base": "select_one_price"}
    assert grid_meters_of(entry) == {}


async def test_add_grid_meter_offers_the_next_register(hass: HomeAssistant) -> None:
    # Given - the day register is already entered
    entry = await _house(
        hass,
        {
            CONF_NAME: "Day",
            CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
            CONF_PRICE_ENTITY: "sensor.day_price",
        },
    )

    # When - Add grid meter is opened
    with _with_energy_dashboard(_DAY, _NIGHT):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_GRID), context={"source": SOURCE_USER}
        )

    # Then - the night register is filled in, with its fixed price
    assert _suggested(result) == {
        CONF_NAME: "Grid 2",
        CONF_GRID_IMPORT_ENTITY: "sensor.night_register",
        CONF_FIXED_PRICE: 0.1,
    }


async def test_a_grid_meter_is_edited_to_a_fixed_price(hass: HomeAssistant) -> None:
    # Given - a register priced by a sensor
    day = {
        CONF_NAME: "Day",
        CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
        CONF_PRICE_ENTITY: "sensor.day_price",
    }
    entry = await _house(hass, day)
    (grid_id,) = grid_meters_of(entry)

    # When - it is edited to a fixed price, and given both on the way
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GRID),
        context={"source": "reconfigure", "subentry_id": grid_id},
    )
    refused = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**day, CONF_FIXED_PRICE: 0.28}
    )
    result = await hass.config_entries.subentries.async_configure(
        refused["flow_id"],
        {
            CONF_NAME: "Day",
            CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
            CONF_FIXED_PRICE: 0.28,
        },
    )

    # Then - both at once was refused, and the fixed price alone is kept
    assert refused["errors"] == {"base": "select_one_price"}
    assert result["reason"] == "reconfigure_successful"
    grid = grid_meters_of(entry)[grid_id]
    assert (grid.price_entity, grid.fixed_price) == (None, Decimal("0.28"))


# The export price, which is the Energy Dashboard's and only shown here


_DAY_REGISTER = {
    CONF_NAME: "Day",
    CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
    CONF_PRICE_ENTITY: "sensor.day_price",
}


async def _edit_grid_meter(hass: HomeAssistant) -> Any:  # noqa: ANN401 - a flow result
    entry = await _house(hass, _DAY_REGISTER)
    (grid_id,) = grid_meters_of(entry)
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GRID),
        context={"source": "reconfigure", "subentry_id": grid_id},
    )


@pytest.mark.parametrize(
    ("export", "said"),
    [
        pytest.param(
            {"entity_energy_price_export": "sensor.grid_sell_price"},
            "Exports are priced by sensor.grid_sell_price, from your Energy "
            "Dashboard's grid settings. Change it there.",
            id="a sensor",
        ),
        pytest.param(
            {"number_energy_price_export": 0.08},
            "Exports are priced at 0.08 per kWh, from your Energy Dashboard's "
            "grid settings. Change it there.",
            id="a fixed price",
        ),
        pytest.param(
            {},
            "No export price is set in your Energy Dashboard, so Could have "
            "earned stays at zero. Set one in its grid settings to see it.",
            id="none",
        ),
    ],
)
async def test_editing_a_grid_meter_says_which_export_price_is_used(
    hass: HomeAssistant, export: dict[str, Any], said: str
) -> None:
    # Given - the Energy Dashboard's grid source, with its export price or none.
    # A household looking for it in Edit grid meter found only the import price
    # and could not tell which export price was in use (discussion 48)
    with _with_energy_dashboard({**_DAY, **export}):
        # When
        result = await _edit_grid_meter(hass)

    # Then - said where they look, and where to change it (HEA-250)
    assert result["description_placeholders"] == {"export_price": said}


async def test_the_older_flow_arrays_name_the_export_price_just_the_same(
    hass: HomeAssistant,
) -> None:
    # Given - the shape before 2026.9, where the export price sits on the flow_to
    # entry under the name the source uses for the import price (HEA-209)
    older = {
        "type": "grid",
        "flow_from": [
            {
                "stat_energy_from": "sensor.day_register",
                "entity_energy_price": "sensor.day_price",
            }
        ],
        "flow_to": [
            {
                "stat_energy_to": "sensor.grid_export",
                "entity_energy_price": "sensor.grid_sell_price",
            }
        ],
    }
    with _with_energy_dashboard(older):
        # When
        result = await _edit_grid_meter(hass)

    # Then - the export price, never the import one
    assert result["description_placeholders"] == {
        "export_price": "Exports are priced by sensor.grid_sell_price, from your "
        "Energy Dashboard's grid settings. Change it there."
    }


_SELL_PRICE_SAID = {
    "export_price": "Exports are priced by sensor.grid_sell_price, from your "
    "Energy Dashboard's grid settings. Change it there."
}
_SELLING = {**_DAY, "entity_energy_price_export": "sensor.grid_sell_price"}


async def test_add_grid_meter_and_reconfigure_say_it_too(hass: HomeAssistant) -> None:
    # Given - an export price in the Energy Dashboard
    entry = await _house(hass, _DAY_REGISTER)
    with _with_energy_dashboard(_SELLING):
        # When - Add grid meter, and Reconfigure, the other place a household
        # looked for it
        added = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_GRID), context={"source": SOURCE_USER}
        )
        reconfigured = await entry.start_reconfigure_flow(hass)

    # Then
    assert added["description_placeholders"] == _SELL_PRICE_SAID
    assert reconfigured["description_placeholders"] == _SELL_PRICE_SAID


async def test_setup_s_grid_meter_screens_say_it_too(hass: HomeAssistant) -> None:
    # Given - an export price in the Energy Dashboard, at first setup
    with _with_energy_dashboard(_SELLING):
        # When - the grid meters offered, and the form to enter one by hand
        offered = await _house_screen(hass)
        by_hand = await hass.config_entries.flow.async_configure(
            offered["flow_id"], {"grid_meters": []}
        )

    # Then
    assert (offered["step_id"], by_hand["step_id"]) == ("grid_meters", "grid_meter")
    assert offered["description_placeholders"] == _SELL_PRICE_SAID
    assert by_hand["description_placeholders"] == _SELL_PRICE_SAID


# Migration


async def test_the_existing_grid_meter_moves_into_its_own_entry(
    hass: HomeAssistant,
) -> None:
    # Given - an entry from 0.13 holding the grid on the house screen
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={
            **_HOUSE,
            CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
            CONF_PRICE_ENTITY: "sensor.day_price",
            CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
        },
    )
    entry.add_to_hass(hass)

    # When
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the same meters at the same price, now an entry of their own
    assert entry.version == 7
    (grid,) = grid_meters_of(entry).values()
    assert (grid.name, grid.imported, grid.price_entity, grid.exported) == (
        "Grid",
        "sensor.day_register",
        "sensor.day_price",
        "sensor.grid_export",
    )
    assert {
        key: value
        for key, value in entry.data.items()
        if key != CONF_ENERGY_DASHBOARD_ANSWERED
    } == _HOUSE


# The registers, as the running integration prices them


async def test_each_register_is_priced_at_its_own_rate(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a dual-rate home, the day register priced by a sensor at 0.30 and
    # the night one by a fixed 0.10, with a pump drawing everything
    freezer.move_to(datetime(2026, 10, 21, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.pump_energy", "0", _ENERGY)
    for meter in ("sensor.day_register", "sensor.night_register"):
        hass.states.async_set(meter, "0", _ENERGY)
    entry = await _house(
        hass,
        {
            CONF_NAME: "Day",
            CONF_GRID_IMPORT_ENTITY: "sensor.day_register",
            CONF_PRICE_ENTITY: "sensor.day_price",
        },
        {
            CONF_NAME: "Night",
            CONF_GRID_IMPORT_ENTITY: "sensor.night_register",
            CONF_FIXED_PRICE: 0.1,
        },
        devices=({CONF_NAME: "Pump", CONF_ENERGY_ENTITY: "sensor.pump_energy"},),
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the meter changes register part-way through an interval: 1 kWh on
    # the day register and 3 on the night one
    freezer.move_to(datetime(2026, 10, 21, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.day_register", "1", _ENERGY)
    hass.states.async_set("sensor.night_register", "3", _ENERGY)
    hass.states.async_set("sensor.pump_energy", "4", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 10, 21, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then - each register's energy at its own rate: 0.30 + 0.30. One price for
    # both would have put 1.20 or 0.40 here
    (pump,) = entry.runtime_data.data.devices.values()
    assert pump.energy_kwh == Decimal(4)
    assert pump.actual_cost == Decimal("0.60")
