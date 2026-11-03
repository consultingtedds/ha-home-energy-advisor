"""A tariff plan is entered as its own entry: named prices, then its bands.

The plan's own details first - its name, whether it is the plan the household is
on, its daily charge, its export price, an optional holiday calendar, and the
prices it charges, each named as the offer names it (HEA-262). Then one band at a
time, each picking one of those prices by name and followed by a review of the
bands so far and the hours they leave uncovered. A plan is saved only once every
hour of both kinds of day is covered exactly once (HEA-255, ADR-0036).
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
    CONF_BAND_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_HOLIDAYS,
    CONF_PRICES,
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

# The plan the household is on: dear by day on weekdays, paying more for export
# then, and cheap overnight and all weekend.
_PEAK = {CONF_NAME: "Peak", CONF_BAND_IMPORT_PRICE: 0.31, CONF_BAND_EXPORT_PRICE: 0.12}
_OFF_PEAK = {CONF_NAME: "Off-peak", CONF_BAND_IMPORT_PRICE: 0.09}
_DETAILS = {
    CONF_NAME: "Current plan",
    CONF_PLAN_CURRENT: True,
    CONF_PLAN_DAILY_CHARGE: 0.45,
    CONF_PLAN_EXPORT_PRICE: 0.05,
    CONF_PRICES: [_PEAK, _OFF_PEAK],
}
_WEEKDAY_PEAK = {
    CONF_BAND_DAYS: "weekdays",
    CONF_BAND_START: 8,
    CONF_BAND_END: 22,
    CONF_BAND_PRICE: "Peak",
}
_WEEKDAY_NIGHT = {
    CONF_BAND_DAYS: "weekdays",
    CONF_BAND_START: 22,
    CONF_BAND_END: 8,
    CONF_BAND_PRICE: "Off-peak",
}
_REST_DAYS = {
    CONF_BAND_DAYS: "rest_days",
    CONF_BAND_START: 0,
    CONF_BAND_END: 24,
    CONF_BAND_PRICE: "Off-peak",
}
_ALL_DAY = {
    CONF_BAND_DAYS: "every_day",
    CONF_BAND_START: 0,
    CONF_BAND_END: 24,
    CONF_BAND_PRICE: "Off-peak",
}
_CURRENT = {
    **_DETAILS,
    CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    CONF_BANDS: [_WEEKDAY_PEAK, _WEEKDAY_NIGHT, _REST_DAYS],
}
_CURRENT_PLAN = Plan(
    name="Current plan",
    bands=(
        Band(Days.WEEKDAYS, 8, 22, Decimal("0.31"), Decimal("0.12")),
        Band(Days.WEEKDAYS, 22, 8, Decimal("0.09")),
        Band(Days.REST_DAYS, 0, 24, Decimal("0.09")),
    ),
    daily_charge=Decimal("0.45"),
    export_price=Decimal("0.05"),
)


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


async def _edit(hass: HomeAssistant, entry: MockConfigEntry, plan_id: str) -> Any:  # noqa: ANN401 - a flow result
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN),
        context={"source": "reconfigure", "subentry_id": plan_id},
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
    options: list[dict[str, str]] = _field(result, field).config["options"]
    return options


def _field(result: Any, field: str) -> Any:  # noqa: ANN401 - a selector
    schema = result["data_schema"].schema
    marker = next(key for key in schema if str(key) == field)
    return schema[marker]


def _suggested(result: Any) -> dict[str, Any]:  # noqa: ANN401 - a flow result
    """What a form is filled in with, by field."""
    return {
        str(marker): marker.description["suggested_value"]
        for marker in result["data_schema"].schema
        if marker.description and "suggested_value" in marker.description
    }


def _details_of(plan: dict[str, Any]) -> dict[str, Any]:
    """A plan's details form answers: everything but its bands."""
    return {key: value for key, value in plan.items() if key != CONF_BANDS}


async def test_a_plan_is_entered_band_by_band_and_saved_once_every_hour_is_covered(
    hass: HomeAssistant,
) -> None:
    # Given - a household entering the plan it is on: its two prices, then three
    # bands on weekdays and one for weekends and holidays
    entry = _house(hass)
    result = await _enter(
        hass, entry, _DETAILS, _WEEKDAY_PEAK, _WEEKDAY_NIGHT, _REST_DAYS
    )

    # When
    result = await _answer(hass, result, _review(result, "save"))

    # Then - saved as an entry of its own, and read back as the plan it describes
    assert result["type"] is FlowResultType.CREATE_ENTRY
    ((plan_id, plan),) = plans_of(entry).items()
    assert entry.subentries[plan_id].title == "Current plan"
    assert plan.current is True
    assert plan.holidays is None
    assert plan.plan == _CURRENT_PLAN


async def test_a_band_picks_one_of_the_plans_prices_by_name(
    hass: HomeAssistant,
) -> None:
    # Given / When - the details entered, at the first band
    result = await _answer(hass, await _start(hass, _house(hass)), _DETAILS)

    # Then - the prices just named, each with what it charges, in the plan's
    # currency, and nothing typed per band
    assert result["step_id"] == "band"
    assert _options(result, CONF_BAND_PRICE) == [
        {"value": "Peak", "label": "Peak (0.31 EUR/kWh, export 0.12 EUR/kWh)"},
        {"value": "Off-peak", "label": "Off-peak (0.09 EUR/kWh)"},
    ]
    fields = {str(marker) for marker in result["data_schema"].schema}
    assert CONF_BAND_IMPORT_PRICE not in fields


async def test_the_review_names_each_bands_price(hass: HomeAssistant) -> None:
    # Given / When
    result = await _enter(hass, _house(hass), _DETAILS, _WEEKDAY_PEAK, _WEEKDAY_NIGHT)

    # Then
    assert [option["label"] for option in _options(result, "keep")] == [
        "Weekdays 08:00-22:00: Peak (0.31 EUR/kWh, export 0.12 EUR/kWh)",
        "Weekdays 22:00-08:00: Off-peak (0.09 EUR/kWh)",
    ]


async def test_the_plan_names_its_prices_once_each(hass: HomeAssistant) -> None:
    # Given / When - two prices called the same, so a band could not say which
    result = await _answer(
        hass,
        await _start(hass, _house(hass)),
        {**_DETAILS, CONF_PRICES: [_PEAK, {**_OFF_PEAK, CONF_NAME: "Peak"}]},
    )

    # Then
    assert result["step_id"] == "details"
    assert result["errors"] == {CONF_PRICES: "price_names"}


async def test_a_plan_has_at_least_one_price(hass: HomeAssistant) -> None:
    # Given / When
    result = await _answer(
        hass, await _start(hass, _house(hass)), {**_DETAILS, CONF_PRICES: []}
    )

    # Then - a band would have nothing to pick
    assert result["step_id"] == "details"
    assert result["errors"] == {CONF_PRICES: "no_prices"}


async def test_the_review_says_which_hours_are_not_covered_yet(
    hass: HomeAssistant,
) -> None:
    # Given / When - weekdays from 08:00 to 22:00 only
    result = await _enter(hass, _house(hass), _DETAILS, _WEEKDAY_PEAK)

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
    result = await _enter(hass, _house(hass), _DETAILS, _ALL_DAY)

    # Then
    assert result["description_placeholders"]["uncovered"] == ("Every hour is covered.")


async def test_saving_a_plan_that_leaves_hours_uncovered_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _house(hass)
    result = await _enter(hass, entry, _DETAILS, _WEEKDAY_PEAK)

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
    result = await _enter(hass, _house(hass), _DETAILS, _WEEKDAY_PEAK)
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
    result = await _answer(hass, await _start(hass, _house(hass)), _DETAILS)

    # When - from 08:00 to 08:00
    result = await _answer(
        hass, result, {**_ALL_DAY, CONF_BAND_START: 8, CONF_BAND_END: 8}
    )

    # Then
    assert result["step_id"] == "band"
    assert result["errors"] == {"base": "band_hours"}


async def test_unticking_a_band_removes_it(hass: HomeAssistant) -> None:
    # Given - a weekday band entered by mistake before the every-day one
    result = await _enter(hass, _house(hass), _DETAILS, _WEEKDAY_PEAK)
    result = await _answer(hass, result, _review(result, "add_band", keep=[]))

    # When
    result = await _answer(hass, result, _ALL_DAY)

    # Then - only the every-day band is left, so nothing overlaps
    assert result["step_id"] == "bands"
    assert len(_options(result, "keep")) == 1
    assert result["description_placeholders"]["uncovered"] == ("Every hour is covered.")


async def test_a_price_forgotten_until_the_bands_can_still_be_added(
    hass: HomeAssistant,
) -> None:
    # Given - partway through the bands, with no price for the weekend yet
    result = await _enter(
        hass, _house(hass), {**_DETAILS, CONF_PRICES: [_PEAK]}, _WEEKDAY_PEAK
    )

    # When - back to the prices from the review, to add it
    result = await _answer(hass, result, _review(result, "prices"))
    assert result["step_id"] == "details"
    assert _suggested(result)[CONF_PRICES] == [_PEAK]
    result = await _answer(hass, result, _DETAILS)

    # Then - back at the review with the band entered so far, and the new price
    # offered for the next one
    assert result["step_id"] == "bands"
    assert len(_options(result, "keep")) == 1
    result = await _answer(hass, result, _review(result, "add_band"))
    assert [option["value"] for option in _options(result, CONF_BAND_PRICE)] == [
        "Peak",
        "Off-peak",
    ]


async def test_making_a_plan_current_makes_the_previous_one_not(
    hass: HomeAssistant,
) -> None:
    # Given - the household's current plan already entered
    entry = _house(hass, _CURRENT)

    # When - an offer is entered as the plan it is moving to
    result = await _enter(
        hass,
        entry,
        {**_DETAILS, CONF_NAME: "New offer", CONF_PLAN_CURRENT: True},
        _ALL_DAY,
    )
    await _answer(hass, result, _review(result, "save"))

    # Then - one current plan, never two
    current = {plan.plan.name: plan.current for plan in plans_of(entry).values()}
    assert current == {"Current plan": False, "New offer": True}


async def test_a_plan_names_the_calendar_its_holidays_come_from(
    hass: HomeAssistant,
) -> None:
    # Given / When
    entry = _house(hass)
    result = await _enter(
        hass,
        entry,
        {**_DETAILS, CONF_PLAN_HOLIDAYS: "calendar.public_holidays"},
        _ALL_DAY,
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
            data=MappingProxyType(_CURRENT),
            subentry_type=SUBENTRY_TYPE_PLAN,
            title="Current plan",
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


# Editing a plan, and starting one from a copy of another (HEA-259, HEA-262)

# An offer with the same bands at its own prices.
_OFFER = {
    CONF_NAME: "Offer",
    CONF_PLAN_CURRENT: False,
    CONF_PLAN_DAILY_CHARGE: 2.87,
    CONF_PLAN_EXPORT_PRICE: 0.035,
    CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
    CONF_PRICES: [
        {**_PEAK, CONF_BAND_IMPORT_PRICE: 0.2319, CONF_BAND_EXPORT_PRICE: 0.10},
        {**_OFF_PEAK, CONF_BAND_IMPORT_PRICE: 0.1552},
    ],
}


async def _copy(hass: HomeAssistant, entry: MockConfigEntry) -> Any:  # noqa: ANN401 - a flow result
    """Start a plan from a copy of the household's current one."""
    (source_id,) = plans_of(entry)
    result = await _start(hass, entry)
    assert result["step_id"] == "user"
    return await _answer(hass, result, {"start_from": source_id})


async def test_a_plan_is_edited_by_reconfiguring_it(hass: HomeAssistant) -> None:
    # Given - a plan whose daily charge went up
    entry = _house(hass, _CURRENT)
    (plan_id,) = plans_of(entry)

    # When - the new charge is entered, and its bands kept
    result = await _edit(hass, entry, plan_id)
    assert result["step_id"] == "reconfigure"
    result = await _answer(
        hass, result, {**_details_of(_CURRENT), CONF_PLAN_DAILY_CHARGE: 0.52}
    )
    assert result["step_id"] == "bands"
    result = await _answer(hass, result, _review(result, "save"))

    # Then - the same entry, with the new charge and the bands it had
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    plan = plans_of(entry)[plan_id]
    assert plan.current is True
    assert plan.plan.daily_charge == Decimal("0.52")
    assert plan.plan.bands == _CURRENT_PLAN.bands


async def test_a_renewal_is_its_prices_changed_in_the_list(hass: HomeAssistant) -> None:
    # Given - the current plan, about to be renewed at a new peak price
    entry = _house(hass, _CURRENT)
    (plan_id,) = plans_of(entry)

    # When - edited: the list shows its named prices, and one is changed
    result = await _edit(hass, entry, plan_id)
    assert _suggested(result)[CONF_PRICES] == [_PEAK, _OFF_PEAK]
    result = await _answer(
        hass,
        result,
        {
            **_details_of(_CURRENT),
            CONF_PRICES: [{**_PEAK, CONF_BAND_IMPORT_PRICE: 0.35}, _OFF_PEAK],
        },
    )
    result = await _answer(hass, result, _review(result, "save"))

    # Then - every band at the peak price moved with it, the rest as they were
    assert [band.import_price for band in plans_of(entry)[plan_id].plan.bands] == [
        Decimal("0.35"),
        Decimal("0.09"),
        Decimal("0.09"),
    ]


async def test_renaming_a_price_keeps_the_bands_that_charge_it(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _house(hass, _CURRENT)
    (plan_id,) = plans_of(entry)

    # When - Off-peak renamed where it stands in the list
    result = await _answer(
        hass,
        await _edit(hass, entry, plan_id),
        {
            **_details_of(_CURRENT),
            CONF_PRICES: [_PEAK, {**_OFF_PEAK, CONF_NAME: "Valle"}],
        },
    )

    # Then - its two bands still charge it, under the new name
    assert [option["label"] for option in _options(result, "keep")] == [
        "Weekdays 08:00-22:00: Peak (0.31 EUR/kWh, export 0.12 EUR/kWh)",
        "Weekdays 22:00-08:00: Valle (0.09 EUR/kWh)",
        "Weekends and holidays 00:00-24:00: Valle (0.09 EUR/kWh)",
    ]
    result = await _answer(hass, result, _review(result, "save"))
    assert plans_of(entry)[plan_id].plan == _CURRENT_PLAN


async def test_removing_a_price_removes_the_bands_that_charged_it(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _house(hass, _CURRENT)
    (plan_id,) = plans_of(entry)

    # When - the peak price taken out of the list
    result = await _answer(
        hass,
        await _edit(hass, entry, plan_id),
        {**_details_of(_CURRENT), CONF_PRICES: [_OFF_PEAK]},
    )

    # Then - its band went with it, and the review says which hours that leaves
    assert len(_options(result, "keep")) == 2
    assert result["description_placeholders"]["uncovered"] == (
        "Not priced yet:\nWeekdays: 08:00-22:00"
    )


async def test_a_plan_can_start_from_a_copy_of_another(hass: HomeAssistant) -> None:
    # Given - the household's current plan
    entry = _house(hass, _CURRENT)
    (source_id,) = plans_of(entry)

    # When - an offer is entered from it: its details and prices, then the review
    result = await _copy(hass, entry)
    assert result["step_id"] == "details"
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


async def test_the_copy_is_filled_in_from_the_plan_it_came_from(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await _copy(hass, _house(hass, _CURRENT))

    # Then - everything but whether it is the plan the household is on, since a
    # copy is most often an offer being weighed up
    assert _suggested(result) == {
        CONF_NAME: "Current plan",
        CONF_PLAN_CURRENT: False,
        CONF_PLAN_DAILY_CHARGE: 0.45,
        CONF_PLAN_EXPORT_PRICE: 0.05,
        CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
        CONF_PRICES: [_PEAK, _OFF_PEAK],
    }


async def test_starting_from_nothing_enters_bands_one_at_a_time(
    hass: HomeAssistant,
) -> None:
    # Given - a household with a plan already, choosing not to copy it
    result = await _start(hass, _house(hass, _CURRENT))

    # When
    result = await _answer(hass, result, {"start_from": "none"})

    # Then - the plan's details, empty, and then its first band
    assert result["step_id"] == "details"
    assert CONF_PRICES not in _suggested(result)
    result = await _answer(hass, result, {**_DETAILS, CONF_NAME: "From scratch"})
    assert result["step_id"] == "band"


async def test_a_first_plan_goes_straight_to_its_details(hass: HomeAssistant) -> None:
    # Given / When - nothing to copy
    result = await _start(hass, _house(hass))

    # Then - no question about what to start from
    assert result["step_id"] == "details"


async def test_the_prices_are_entered_in_the_plans_currency(
    hass: HomeAssistant,
) -> None:
    # Given / When
    result = await _start(hass, _house(hass))

    # Then - each price's figures are per kWh in the household's currency
    fields = _field(result, CONF_PRICES).config["fields"]
    units = {
        name: field["selector"]["number"].get("unit_of_measurement")
        for name, field in fields.items()
        if "number" in field["selector"]
    }
    assert units == {
        CONF_BAND_IMPORT_PRICE: "EUR/kWh",
        CONF_BAND_EXPORT_PRICE: "EUR/kWh",
    }


# A plan entered before its prices were named (the 1.3.0 betas) carries each
# band's figures itself.
_UNNAMED = {
    **{key: value for key, value in _CURRENT.items() if key != CONF_PRICES},
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "weekdays",
            CONF_BAND_START: 8,
            CONF_BAND_END: 22,
            CONF_BAND_IMPORT_PRICE: 0.31,
            CONF_BAND_EXPORT_PRICE: 0.12,
        },
        {
            CONF_BAND_DAYS: "weekdays",
            CONF_BAND_START: 22,
            CONF_BAND_END: 8,
            CONF_BAND_IMPORT_PRICE: 0.09,
        },
        {
            CONF_BAND_DAYS: "rest_days",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.09,
        },
    ],
}


async def test_a_plan_without_named_prices_prices_as_it_did(
    hass: HomeAssistant,
) -> None:
    # Given / When
    entry = _house(hass, _UNNAMED)

    # Then
    (plan,) = plans_of(entry).values()
    assert plan.plan == _CURRENT_PLAN


async def test_a_plan_without_named_prices_is_given_names_when_edited(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _house(hass, _UNNAMED)
    (plan_id,) = plans_of(entry)

    # When
    result = await _edit(hass, entry, plan_id)

    # Then - one per price its bands charge, numbered in the order they are used,
    # for the household to rename
    assert _suggested(result)[CONF_PRICES] == [
        {**_PEAK, CONF_NAME: "Price 1"},
        {**_OFF_PEAK, CONF_NAME: "Price 2"},
    ]
    result = await _answer(
        hass, result, {**_details_of(_CURRENT), CONF_PRICES: [_PEAK, _OFF_PEAK]}
    )
    result = await _answer(hass, result, _review(result, "save"))
    assert entry.subentries[plan_id].data[CONF_BANDS] == _CURRENT[CONF_BANDS]
    assert plans_of(entry)[plan_id].plan == _CURRENT_PLAN
