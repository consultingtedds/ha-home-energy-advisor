"""Every household has a current plan, following the prices Paid uses (ADR-0042).

The integration creates it rather than the household entering it: on upgrade,
from the plan the household had marked as the one it is on, carrying that plan's
daily charge and monthly export cap over and leaving the marked plan as an
ordinary one; and on any setup that finds none, as after the household deleted
it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_ENTITY,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_FOLLOWS,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)
from custom_components.home_energy_advisor.engine.plan_pricing import ExportCap
from custom_components.home_energy_advisor.tariff_plans import plans_of

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.core import HomeAssistant

# A banded plan as 1.6 stored it, marked as the one the household is on.
_MARKED = {
    CONF_NAME: "Octopus Current",
    CONF_PLAN_CURRENT: True,
    CONF_PLAN_DAILY_CHARGE: 0.4521,
    CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value,
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.1386,
        }
    ],
}
_OFFER = {
    CONF_NAME: "Naturgy",
    CONF_PLAN_CURRENT: False,
    CONF_PLAN_DAILY_CHARGE: 0.31,
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.149,
        }
    ],
}


def _entry(
    hass: HomeAssistant, *plans: dict[str, Any], version: int
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=version,
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


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _plans(entry: MockConfigEntry) -> dict[str, ConfigSubentry]:
    return {
        subentry.title: subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_PLAN
    }


def _following(entry: MockConfigEntry) -> list[ConfigSubentry]:
    return [plan for plan in _plans(entry).values() if plan.data.get(CONF_PLAN_FOLLOWS)]


# Upgrading


async def test_the_marked_plan_s_billing_rules_move_to_the_current_plan(
    hass: HomeAssistant,
) -> None:
    # Given - 1.6's entry, one plan marked as the one the household is on
    entry = _entry(hass, _MARKED, _OFFER, version=7)

    # When
    await _set_up(hass, entry)

    # Then - a current plan following the household's prices, holding only the
    # marked plan's daily charge and cap: no prices of its own
    assert entry.version == 8
    (current,) = _following(entry)
    assert current.title == "Your current plan"
    assert dict(current.data) == {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 0.4521,
        CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value,
    }


async def test_the_marked_plan_stays_as_an_ordinary_plan(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _MARKED, _OFFER, version=7)

    # When
    await _set_up(hass, entry)

    # Then - its prices kept, so its row can still be set against the current
    # plan's, and no longer marked; the other plan untouched
    plans = _plans(entry)
    assert dict(plans["Octopus Current"].data) == {**_MARKED, CONF_PLAN_CURRENT: False}
    assert dict(plans["Naturgy"].data) == _OFFER


async def test_with_no_plan_marked_the_current_plan_has_no_daily_charge_yet(
    hass: HomeAssistant,
) -> None:
    # Given - plans entered, none marked as the one the household is on
    entry = _entry(hass, _OFFER, version=7)

    # When
    await _set_up(hass, entry)

    # Then - created, its daily charge left for the household to give
    (current,) = _following(entry)
    assert CONF_PLAN_DAILY_CHARGE not in current.data
    assert current.data[CONF_PLAN_EXPORT_CAP] == ExportCap.NONE.value


# Any setup


async def test_a_setup_that_finds_no_current_plan_creates_one(
    hass: HomeAssistant,
) -> None:
    # Given - an entry already on the current schema with no current plan, as
    # after the household deleted it
    entry = _entry(hass, _OFFER, version=8)

    # When
    await _set_up(hass, entry)

    # Then
    (current,) = _following(entry)
    assert CONF_PLAN_DAILY_CHARGE not in current.data


async def test_a_restart_never_makes_a_second_current_plan(
    hass: HomeAssistant,
) -> None:
    # Given - set up once, so the current plan exists
    entry = _entry(hass, _MARKED, version=7)
    await _set_up(hass, entry)

    # When
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Then
    assert len(_following(entry)) == 1


async def test_the_current_plan_is_not_priced_as_a_typed_plan(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _MARKED, _OFFER, version=7)

    # When
    await _set_up(hass, entry)

    # Then - it has no schedule to price; the comparison prices it at Paid's
    # prices instead (ADR-0042)
    assert {tariff.plan.name for tariff in plans_of(entry).values()} == {
        "Octopus Current",
        "Naturgy",
    }


# Editing it


async def _edit_current(hass: HomeAssistant, entry: MockConfigEntry) -> Any:  # noqa: ANN401 - a flow result
    (current,) = _following(entry)
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN),
        context={"source": "reconfigure", "subentry_id": current.subentry_id},
    )


async def _answer(hass: HomeAssistant, flow_id: str, answer: dict[str, Any]) -> Any:  # noqa: ANN401 - a flow result
    return await hass.config_entries.subentries.async_configure(flow_id, answer)


async def test_editing_the_current_plan_asks_only_for_its_billing_rules(
    hass: HomeAssistant,
) -> None:
    # Given - upgraded, the marked plan's daily charge carried over
    entry = _entry(hass, _MARKED, version=7)
    await _set_up(hass, entry)

    # When
    form = await _edit_current(hass, entry)

    # Then - its daily charge and cap, with what it holds filled in, and no
    # prices: those are Paid's
    assert form["step_id"] == "current"
    fields = {str(key): key for key in form["data_schema"].schema}
    assert set(fields) == {
        CONF_PLAN_DAILY_CHARGE,
        CONF_PLAN_DAILY_CHARGE_ENTITY,
        CONF_PLAN_EXPORT_CAP,
    }
    assert fields[CONF_PLAN_DAILY_CHARGE].description == {"suggested_value": 0.4521}
    assert fields[CONF_PLAN_EXPORT_CAP].description == {
        "suggested_value": ExportCap.MONTHLY.value
    }


async def test_a_typed_daily_charge_is_kept(hass: HomeAssistant) -> None:
    # Given - a current plan with no daily charge yet
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    form = await _edit_current(hass, entry)

    # When
    done = await _answer(
        hass,
        form["flow_id"],
        {CONF_PLAN_DAILY_CHARGE: 0.38, CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value},
    )

    # Then
    assert done["reason"] == "reconfigure_successful"
    (current,) = _following(entry)
    assert dict(current.data) == {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 0.38,
        CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value,
    }


async def test_a_daily_charge_can_follow_the_household_s_own_price(
    hass: HomeAssistant,
) -> None:
    # Given - a typed daily charge, then the household's standing-charge price
    # chosen instead, the one its Energy Dashboard already uses
    entry = _entry(hass, _MARKED, version=7)
    await _set_up(hass, entry)
    form = await _edit_current(hass, entry)

    # When
    await _answer(
        hass,
        form["flow_id"],
        {
            CONF_PLAN_DAILY_CHARGE_ENTITY: "sensor.standing_charge_price",
            CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value,
        },
    )

    # Then - the sensor alone, so there is one daily charge to keep in step
    (current,) = _following(entry)
    assert dict(current.data) == {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE_ENTITY: "sensor.standing_charge_price",
        CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value,
    }


async def test_the_daily_charge_is_one_or_the_other(hass: HomeAssistant) -> None:
    # Given
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    form = await _edit_current(hass, entry)
    cap = {CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value}

    # When - neither given, then both
    neither = await _answer(hass, form["flow_id"], cap)
    both = await _answer(
        hass,
        neither["flow_id"],
        {
            **cap,
            CONF_PLAN_DAILY_CHARGE: 0.38,
            CONF_PLAN_DAILY_CHARGE_ENTITY: "sensor.standing_charge_price",
        },
    )

    # Then - a plan with no daily charge would read cheaper than the rest, and
    # two would leave one to fall out of step
    assert neither["errors"] == {"base": "daily_charge_needed"}
    assert both["errors"] == {"base": "daily_charge_one"}
    (current,) = _following(entry)
    assert CONF_PLAN_DAILY_CHARGE not in current.data


async def test_a_new_plan_cannot_start_from_the_current_plan(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)

    # When
    start = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN), context={"source": SOURCE_USER}
    )

    # Then - it has no prices to copy
    schema = start["data_schema"]
    assert schema is not None
    (field,) = schema.schema.values()
    offered = {option["label"] for option in field.config["options"]}
    assert "Your current plan" not in offered
    assert "Naturgy" in offered
