"""A tariff plan is entered as its own entry, band by band (HEA-255, ADR-0036).

The plan's own details first - its name, whether it is the plan the household is
on, its daily charge, its export price and an optional holiday calendar - then
one band at a time, each followed by a review of the bands so far and the hours
they leave uncovered. A plan is saved only once every hour of both kinds of day
is covered exactly once.
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_EXPORT_PRICE,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_HOLIDAYS,
    DOMAIN,
    SUBENTRY_TYPE_GRID,
    SUBENTRY_TYPE_PLAN,
)
from custom_components.home_energy_advisor.engine.plan_pricing import (
    Band,
    Days,
    Plan,
)
from custom_components.home_energy_advisor.tariff_plans import plans_of

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_FLAT = {
    CONF_NAME: "Flat rate",
    CONF_PLAN_CURRENT: True,
    CONF_PLAN_DAILY_CHARGE: 0.45,
    CONF_PLAN_EXPORT_PRICE: 0.05,
}
_ALL_DAY = {
    CONF_BAND_DAYS: "every_day",
    CONF_BAND_START: 0,
    CONF_BAND_END: 24,
    CONF_BAND_IMPORT_PRICE: 0.234,
}
_WEEKDAY_PEAK = {
    CONF_BAND_DAYS: "weekdays",
    CONF_BAND_START: 8,
    CONF_BAND_END: 22,
    CONF_BAND_IMPORT_PRICE: 0.31,
    CONF_BAND_EXPORT_PRICE: 0.12,
}
_WEEKDAY_NIGHT = {
    CONF_BAND_DAYS: "weekdays",
    CONF_BAND_START: 22,
    CONF_BAND_END: 8,
    CONF_BAND_IMPORT_PRICE: 0.09,
}
_REST_DAYS = {
    CONF_BAND_DAYS: "rest_days",
    CONF_BAND_START: 0,
    CONF_BAND_END: 24,
    CONF_BAND_IMPORT_PRICE: 0.09,
}


def _house(hass: HomeAssistant, *plans: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_PLAN,
                title=plan[CONF_NAME],
                data=plan,
                unique_id=None,
            )
            for plan in plans
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def _start(hass: HomeAssistant, entry: MockConfigEntry) -> Any:  # noqa: ANN401 - a flow result
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN), context={"source": SOURCE_USER}
    )


async def _answer(hass: HomeAssistant, result: Any, answers: dict[str, Any]) -> Any:  # noqa: ANN401 - flow results
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], answers
    )


async def _enter(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    details: dict[str, Any],
    *bands: dict[str, Any],
) -> Any:  # noqa: ANN401 - a flow result
    """Enter a plan's details and these bands, stopping at the review."""
    result = await _start(hass, entry)
    if result["step_id"] == "user":
        # A household with plans already is asked what to start from first.
        result = await _answer(hass, result, {"start_from": "none"})
    result = await _answer(hass, result, details)
    for index, band in enumerate(bands):
        if index:
            result = await _answer(hass, result, _review(result, "add_band"))
        assert result["step_id"] == "band"
        result = await _answer(hass, result, band)
    assert result["step_id"] == "bands"
    return result


def _review(result: Any, action: str, keep: list[str] | None = None) -> dict[str, Any]:  # noqa: ANN401 - a flow result
    """The review's answer, keeping every band listed unless told otherwise."""
    listed = [option["value"] for option in _options(result, "keep")]
    return {"keep": listed if keep is None else keep, "action": action}


def _options(result: Any, field: str) -> list[dict[str, str]]:  # noqa: ANN401 - a flow result
    schema = result["data_schema"].schema
    marker = next(key for key in schema if str(key) == field)
    options: list[dict[str, str]] = schema[marker].config["options"]
    return options


async def test_a_plan_is_entered_band_by_band_and_saved_once_every_hour_is_covered(
    hass: HomeAssistant,
) -> None:
    # Given - a household entering the plan it is on: three bands on weekdays
    # and one for weekends and holidays
    entry = _house(hass)
    result = await _enter(hass, entry, _FLAT, _WEEKDAY_PEAK, _WEEKDAY_NIGHT, _REST_DAYS)

    # When
    result = await _answer(hass, result, _review(result, "save"))

    # Then - saved as an entry of its own, and read back as the plan it describes
    assert result["type"] is FlowResultType.CREATE_ENTRY
    ((plan_id, plan),) = plans_of(entry).items()
    assert entry.subentries[plan_id].title == "Flat rate"
    assert plan.current is True
    assert plan.holidays is None
    assert plan.plan == Plan(
        name="Flat rate",
        bands=(
            Band(Days.WEEKDAYS, 8, 22, Decimal("0.31"), Decimal("0.12")),
            Band(Days.WEEKDAYS, 22, 8, Decimal("0.09")),
            Band(Days.REST_DAYS, 0, 24, Decimal("0.09")),
        ),
        daily_charge=Decimal("0.45"),
        export_price=Decimal("0.05"),
    )


async def test_the_review_says_which_hours_are_not_covered_yet(
    hass: HomeAssistant,
) -> None:
    # Given / When - weekdays from 08:00 to 22:00 only
    result = await _enter(hass, _house(hass), _FLAT, _WEEKDAY_PEAK)

    # Then - what is left, for each kind of day
    assert result["description_placeholders"]["uncovered"] == (
        "Not priced yet:\n"
        "Weekdays: 00:00-08:00, 22:00-24:00\n"
        "Weekends and holidays: 00:00-24:00"
    )


async def test_the_review_says_when_every_hour_is_covered(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await _enter(hass, _house(hass), _FLAT, _ALL_DAY)

    # Then
    assert result["description_placeholders"]["uncovered"] == ("Every hour is covered.")


async def test_saving_a_plan_that_leaves_hours_uncovered_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _house(hass)
    result = await _enter(hass, entry, _FLAT, _WEEKDAY_PEAK)

    # When
    result = await _answer(hass, result, _review(result, "save"))

    # Then - an hour no band prices would otherwise be a guess
    assert result["step_id"] == "bands"
    assert result["errors"] == {"base": "plan_incomplete"}
    assert plans_of(entry) == {}


async def test_a_band_overlapping_one_already_entered_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given - weekdays from 08:00 to 22:00 already entered
    result = await _enter(hass, _house(hass), _FLAT, _WEEKDAY_PEAK)
    result = await _answer(hass, result, _review(result, "add_band"))

    # When - an every-day band that reaches into those hours
    result = await _answer(
        hass, result, {**_ALL_DAY, CONF_BAND_START: 20, CONF_BAND_END: 23}
    )

    # Then - refused, with which price applies at 20:00 left unanswered
    assert result["step_id"] == "band"
    assert result["errors"] == {"base": "band_overlaps"}


async def test_a_band_must_cover_at_least_one_hour(hass: HomeAssistant) -> None:
    # Given
    result = await _answer(hass, await _start(hass, _house(hass)), _FLAT)

    # When - from 08:00 to 08:00
    result = await _answer(
        hass, result, {**_ALL_DAY, CONF_BAND_START: 8, CONF_BAND_END: 8}
    )

    # Then
    assert result["step_id"] == "band"
    assert result["errors"] == {"base": "band_hours"}


async def test_unticking_a_band_removes_it(hass: HomeAssistant) -> None:
    # Given - a weekday band entered by mistake before the every-day one
    result = await _enter(hass, _house(hass), _FLAT, _WEEKDAY_PEAK)
    result = await _answer(hass, result, _review(result, "add_band", keep=[]))

    # When
    result = await _answer(hass, result, _ALL_DAY)

    # Then - only the every-day band is left, so nothing overlaps
    assert result["step_id"] == "bands"
    assert len(_options(result, "keep")) == 1
    assert result["description_placeholders"]["uncovered"] == ("Every hour is covered.")


async def test_making_a_plan_current_makes_the_previous_one_not(
    hass: HomeAssistant,
) -> None:
    # Given - the household's current plan already entered
    entry = _house(hass, {**_FLAT, CONF_BANDS: [_ALL_DAY]})

    # When - an offer is entered as the plan it is moving to
    result = await _enter(
        hass,
        entry,
        {**_FLAT, CONF_NAME: "New offer", CONF_PLAN_CURRENT: True},
        _ALL_DAY,
    )
    await _answer(hass, result, _review(result, "save"))

    # Then - one current plan, never two
    current = {plan.plan.name: plan.current for plan in plans_of(entry).values()}
    assert current == {"Flat rate": False, "New offer": True}


async def test_a_plan_names_the_calendar_its_holidays_come_from(
    hass: HomeAssistant,
) -> None:
    # Given / When
    entry = _house(hass)
    result = await _enter(
        hass, entry, {**_FLAT, CONF_PLAN_HOLIDAYS: "calendar.public_holidays"}, _ALL_DAY
    )
    await _answer(hass, result, _review(result, "save"))

    # Then
    (plan,) = plans_of(entry).values()
    assert plan.holidays == "calendar.public_holidays"


async def _running(hass: HomeAssistant) -> MockConfigEntry:
    """A household whose accounting is running, with one grid meter."""
    hass.states.async_set(
        "sensor.grid_import",
        "100",
        {
            "device_class": "energy",
            "state_class": "total_increasing",
            "unit_of_measurement": "kWh",
        },
    )
    entry = _house(hass)
    hass.config_entries.async_add_subentry(entry, _grid())
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _grid() -> ConfigSubentry:
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_NAME: "Grid",
                CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
                CONF_FIXED_PRICE: 0.2,
            }
        ),
        subentry_type=SUBENTRY_TYPE_GRID,
        title="Grid",
        unique_id=None,
    )


async def test_adding_a_plan_leaves_the_accounting_running(hass: HomeAssistant) -> None:
    # Given - a household whose accounting is running
    entry = await _running(hass)
    running = entry.runtime_data

    # When - a plan is added
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType({**_FLAT, CONF_BANDS: [_ALL_DAY]}),
            subentry_type=SUBENTRY_TYPE_PLAN,
            title="Flat rate",
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()

    # Then - not reloaded: a plan is read by the comparison and nothing else, and
    # a reload would make every figure unavailable for nothing (HEA-255)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is running


async def test_adding_a_grid_meter_still_reloads_the_accounting(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = await _running(hass)
    running = entry.runtime_data

    # When - something the accounting reads changes
    hass.config_entries.async_add_subentry(entry, _grid())
    await hass.async_block_till_done()

    # Then
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not running


async def test_a_plan_is_edited_by_reconfiguring_it(hass: HomeAssistant) -> None:
    # Given - a plan whose daily charge went up
    entry = _house(hass, {**_FLAT, CONF_BANDS: [_ALL_DAY]})
    (plan_id,) = plans_of(entry)

    # When - the new charge is entered, and its band kept
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN),
        context={"source": "reconfigure", "subentry_id": plan_id},
    )
    result = await _answer(hass, result, {**_FLAT, CONF_PLAN_DAILY_CHARGE: 0.52})
    assert result["step_id"] == "bands"
    result = await _answer(hass, result, _review(result, "save"))

    # Then - the same entry, with the new charge and the band it had
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    plan = plans_of(entry)[plan_id].plan
    assert plan.daily_charge == Decimal("0.52")
    assert plan.bands == (Band(Days.EVERY_DAY, 0, 24, Decimal("0.234")),)


# Starting from a copy of another plan (HEA-259)

# The plan the household is on: dear by day on weekdays, with its own export
# price then, and cheap overnight and all weekend.
_CURRENT = {
    **_FLAT,
    CONF_NAME: "Current plan",
    CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    CONF_BANDS: [_WEEKDAY_PEAK, _WEEKDAY_NIGHT, _REST_DAYS],
}
# An offer with the same bands at its own prices.
_OFFER = {
    CONF_NAME: "Offer",
    CONF_PLAN_CURRENT: False,
    CONF_PLAN_DAILY_CHARGE: 2.87,
    CONF_PLAN_EXPORT_PRICE: 0.035,
    CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    "price_1": 0.2319,
    "price_2": 0.1552,
    "band_export_1": 0.10,
}


async def _copy(hass: HomeAssistant, entry: MockConfigEntry) -> Any:  # noqa: ANN401 - a flow result
    """Start a plan from a copy of the household's current one."""
    (source_id,) = plans_of(entry)
    result = await _start(hass, entry)
    assert result["step_id"] == "user"
    return await _answer(hass, result, {"start_from": source_id})


async def test_a_plan_can_start_from_a_copy_of_another(hass: HomeAssistant) -> None:
    # Given - the household's current plan
    entry = _house(hass, _CURRENT)
    (source_id,) = plans_of(entry)

    # When - an offer is entered from it: one screen of prices, then the review
    result = await _copy(hass, entry)
    assert result["step_id"] == "prices"
    result = await _answer(hass, result, _OFFER)
    assert result["step_id"] == "bands"
    result = await _answer(hass, result, _review(result, "save"))

    # Then - the offer has the current plan's bands at its own prices, and its
    # holiday calendar
    assert result["type"] is FlowResultType.CREATE_ENTRY
    offer = next(
        plan for plan_id, plan in plans_of(entry).items() if plan_id != source_id
    )
    assert offer.current is False
    assert offer.holidays == "calendar.public_holidays"
    assert offer.plan == Plan(
        name="Offer",
        bands=(
            Band(Days.WEEKDAYS, 8, 22, Decimal("0.2319"), Decimal("0.1")),
            Band(Days.WEEKDAYS, 22, 8, Decimal("0.1552")),
            Band(Days.REST_DAYS, 0, 24, Decimal("0.1552")),
        ),
        daily_charge=Decimal("2.87"),
        export_price=Decimal("0.035"),
    )


async def test_the_copy_leaves_the_plan_it_came_from_as_it_was(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _house(hass, _CURRENT)
    (source_id,) = plans_of(entry)
    before = plans_of(entry)[source_id]

    # When
    result = await _answer(hass, await _copy(hass, entry), _OFFER)
    await _answer(hass, result, _review(result, "save"))

    # Then - still the current plan, at its own prices
    assert plans_of(entry)[source_id] == before


async def test_the_copy_asks_each_price_once_and_says_where_it_applies(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await _copy(hass, _house(hass, _CURRENT))

    # Then - one field per price, the overnight and weekend bands sharing one,
    # each filled in with the price it has now
    fields = {str(marker): marker for marker in result["data_schema"].schema}
    assert {"price_1", "price_2", "band_export_1"} <= fields.keys()
    assert "price_3" not in fields
    assert [fields[name].default() for name in ("price_1", "price_2")] == [0.31, 0.09]
    assert result["description_placeholders"]["prices"] == (
        "Price 1 (0.31): Weekdays 08:00-22:00\n"
        "Price 2 (0.09): Weekdays 22:00-08:00, Weekends and holidays 00:00-24:00\n"
        "Band export price 1 (0.12): Weekdays 08:00-22:00"
    )


async def test_the_copy_is_filled_in_from_the_plan_it_came_from(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await _copy(hass, _house(hass, _CURRENT))

    # Then - everything but whether it is the plan the household is on, since a
    # copy is most often an offer being weighed up
    suggested = {
        str(marker): marker.description["suggested_value"]
        for marker in result["data_schema"].schema
        if marker.description and "suggested_value" in marker.description
    }
    assert suggested == {
        CONF_NAME: "Current plan",
        CONF_PLAN_CURRENT: False,
        CONF_PLAN_DAILY_CHARGE: 0.45,
        CONF_PLAN_EXPORT_PRICE: 0.05,
        CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    }


async def test_starting_from_nothing_enters_bands_one_at_a_time(
    hass: HomeAssistant,
) -> None:
    # Given - a household with a plan already, choosing not to copy it
    result = await _start(hass, _house(hass, _CURRENT))

    # When
    result = await _answer(hass, result, {"start_from": "none"})

    # Then - the plan's details, and then its first band, as before
    assert result["step_id"] == "details"
    result = await _answer(hass, result, {**_FLAT, CONF_NAME: "From scratch"})
    assert result["step_id"] == "band"


async def test_a_first_plan_goes_straight_to_its_details(hass: HomeAssistant) -> None:
    # Given / When - nothing to copy
    result = await _start(hass, _house(hass))

    # Then - no question about what to start from
    assert result["step_id"] == "details"


async def test_a_renewal_is_one_screen_of_new_prices(hass: HomeAssistant) -> None:
    # Given - the current plan, about to be renewed at new prices
    entry = _house(hass, _CURRENT)
    (plan_id,) = plans_of(entry)

    # When - edited: its details and prices on one screen, then the review
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN),
        context={"source": "reconfigure", "subentry_id": plan_id},
    )
    placeholders = result["description_placeholders"]
    assert placeholders is not None
    assert placeholders["prices"].startswith("Price 1 (0.31)")
    details = {key: value for key, value in _CURRENT.items() if key != CONF_BANDS}
    result = await _answer(
        hass, result, {**details, CONF_PLAN_DAILY_CHARGE: 2.87, "price_1": 0.35}
    )
    result = await _answer(hass, result, _review(result, "save"))

    # Then - the same plan, with the new peak price and charge, the overnight
    # price it kept, and still the one the household is on
    assert result["reason"] == "reconfigure_successful"
    plan = plans_of(entry)[plan_id]
    assert plan.current is True
    assert plan.plan.daily_charge == Decimal("2.87")
    assert [band.import_price for band in plan.plan.bands] == [
        Decimal("0.35"),
        Decimal("0.09"),
        Decimal("0.09"),
    ]
