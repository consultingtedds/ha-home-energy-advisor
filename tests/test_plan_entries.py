"""A tariff plan is entered as its own entry, band by band (HEA-255, ADR-0036).

The plan's own details first - its name, whether it is the plan the household is
on, its daily charge, its export price and an optional holiday calendar - then
one band at a time, each followed by a review of the bands so far and the hours
they leave uncovered. A plan is saved only once every hour of both kinds of day
is covered exactly once.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
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
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_HOLIDAYS,
    DOMAIN,
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
    result = await _answer(hass, await _start(hass, entry), details)
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
