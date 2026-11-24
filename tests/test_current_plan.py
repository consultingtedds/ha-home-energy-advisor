"""Every household has a current plan, following the prices Paid uses (ADR-0042).

The integration creates it rather than the household entering it: on upgrade,
from the plan the household had marked as the one it is on, carrying that plan's
daily charge and monthly export cap over and leaving the marked plan as an
ordinary one; and on any setup that finds none, as after the household deleted
it.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry, ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor import current_plan
from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PERIOD_FROM,
    CONF_PERIOD_GONE_KNOWN,
    CONF_PERIOD_PLAN,
    CONF_PLAN_CARRY_IN,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_ENTITY,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_EXPORT_ALLOWANCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_EXPORT_PRICE_AFTER,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_PERIODS,
    CONF_PLAN_PROVIDES_PRICES,
    CONF_PLAN_REPLACED,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_GRID,
    SUBENTRY_TYPE_PLAN,
)
from custom_components.home_energy_advisor.engine.plan_pricing import ExportCap
from custom_components.home_energy_advisor.issues import (
    ISSUE_CURRENT_PLAN,
    ISSUE_PERIOD_PLAN_GONE,
)
from custom_components.home_energy_advisor.tariff_plans import plans_of

if TYPE_CHECKING:
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
        # So the household can be told the marked plan now duplicates it
        CONF_PLAN_REPLACED: "Octopus Current",
        # Its prices still price the hours the household's price sensors have
        # no statistics for, as they did before (HEA-311): the plan the
        # household has been on, from always (HEA-307)
        CONF_PLAN_PERIODS: [
            {CONF_PERIOD_PLAN: _plans(entry)["Octopus Current"].subentry_id}
        ],
    }


async def test_a_marked_plan_with_an_allowance_is_not_read_for_price_history(
    hass: HomeAssistant,
) -> None:
    # Given - the marked plan pays its export price on the first 8 kWh a day
    # only, which no single hour's price can say
    entry = _entry(
        hass,
        {**_MARKED, CONF_PLAN_EXPORT_ALLOWANCE: 8, CONF_PLAN_EXPORT_PRICE_AFTER: 0.01},
        version=7,
    )

    # When
    await _set_up(hass, entry)

    # Then
    (current,) = _following(entry)
    assert CONF_PLAN_PERIODS not in current.data


async def test_a_1_7_0_current_plan_is_linked_to_the_plan_it_replaced(
    hass: HomeAssistant,
) -> None:
    # Given - upgraded by 1.7.0, which kept only the replaced plan's name, and
    # the household not yet told
    entry = _entry(
        hass,
        {**_MARKED, CONF_PLAN_CURRENT: False},
        {
            CONF_NAME: "Your current plan",
            CONF_PLAN_FOLLOWS: True,
            CONF_PLAN_DAILY_CHARGE: 0.4521,
            CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value,
            CONF_PLAN_REPLACED: "Octopus Current",
        },
        version=8,
    )

    # When
    await _set_up(hass, entry)

    # Then - its prices read where the sensors have no statistics
    (current,) = _following(entry)
    assert current.data[CONF_PLAN_PERIODS] == [
        {CONF_PERIOD_PLAN: _plans(entry)["Octopus Current"].subentry_id}
    ]


async def test_1_7_1_s_price_history_plan_becomes_the_first_period(
    hass: HomeAssistant,
) -> None:
    # Given - the reference home's current plan as 1.7.1 left it, its Repair
    # answered: a daily charge, a carried cap, and one plan for its price
    # history
    entry = _entry(hass, {**_MARKED, CONF_PLAN_CURRENT: False}, version=8)
    octopus = _plans(entry)["Octopus Current"].subentry_id
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_NAME: "Your current plan",
                    CONF_PLAN_FOLLOWS: True,
                    CONF_PLAN_DAILY_CHARGE: 1.4736,
                    CONF_PLAN_EXPORT_CAP: ExportCap.CARRIED.value,
                    "price_history_from": octopus,
                }
            ),
            subentry_type=SUBENTRY_TYPE_PLAN,
            title="Your current plan",
            unique_id=None,
        ),
    )

    # When
    await _set_up(hass, entry)

    # Then - that plan from always, entered once, and the old setting gone
    (current,) = _following(entry)
    assert dict(current.data) == {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 1.4736,
        CONF_PLAN_EXPORT_CAP: ExportCap.CARRIED.value,
        CONF_PLAN_PERIODS: [{CONF_PERIOD_PLAN: octopus}],
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


async def _answer(
    hass: HomeAssistant,
    flow_id: str,
    answer: dict[str, Any],
    *,
    through: bool = True,
) -> Any:  # noqa: ANN401 - a flow result
    """Answer a step; `through` saves the plans been on as they stand."""
    result = await hass.config_entries.subentries.async_configure(flow_id, answer)
    if through and result.get("step_id") == "periods":
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"action": "save"}
        )
    return result


async def test_editing_the_current_plan_asks_first_for_its_billing_rules(
    hass: HomeAssistant,
) -> None:
    # Given - upgraded, the marked plan's daily charge carried over
    entry = _entry(hass, _MARKED, version=7)
    await _set_up(hass, entry)

    # When
    form = await _edit_current(hass, entry)

    # Then - its daily charge, typed or from a sensor, and cap, with what it
    # holds filled in, and whether to provide its price sensors; no prices:
    # those are Paid's. With no grid source in the Energy Dashboard to follow,
    # there is nothing else
    assert form["step_id"] == "current"
    fields = _fields(form)
    assert set(fields) == {
        CONF_PLAN_DAILY_CHARGE,
        CONF_PLAN_DAILY_CHARGE_ENTITY,
        CONF_PLAN_EXPORT_CAP,
        CONF_PLAN_PROVIDES_PRICES,
    }
    assert fields[CONF_PLAN_DAILY_CHARGE].description == {"suggested_value": 0.4521}
    assert fields[CONF_PLAN_EXPORT_CAP].description == {
        "suggested_value": ExportCap.MONTHLY.value
    }


_RULES_ANSWER = {
    CONF_PLAN_DAILY_CHARGE: 0.4521,
    CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value,
}


async def _at_the_plans_been_on(hass: HomeAssistant, entry: MockConfigEntry) -> Any:  # noqa: ANN401 - a flow result
    form = await _edit_current(hass, entry)
    return await _answer(hass, form["flow_id"], _RULES_ANSWER, through=False)


def _kept(form: Any) -> list[str]:  # noqa: ANN401 - a flow result
    """The plans been on a review step lists, by their words."""
    selector = _fields(form)["keep"]
    return [
        option["label"]
        for option in form["data_schema"].schema[selector].config["options"]
    ]


async def test_then_it_lists_the_plans_been_on_in_words(
    hass: HomeAssistant,
) -> None:
    # Given - upgraded, the marked plan the one the household has always been on
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)

    # When
    form = await _at_the_plans_been_on(hass, entry)

    # Then - by name, never by the id it is kept as
    assert form["step_id"] == "periods"
    assert _kept(form) == ["Octopus Current, before any other"]


async def test_a_plan_been_on_is_added_from_its_day_and_kept_in_order(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    octopus = _plans(entry)["Octopus Current"].subentry_id
    naturgy = _plans(entry)["Naturgy"].subentry_id
    form = await _at_the_plans_been_on(hass, entry)

    # When - Naturgy from 1 March 2025, then saved
    form = await _answer(hass, form["flow_id"], {"action": "add_period"})
    assert form["step_id"] == "period"
    form = await _answer(
        hass,
        form["flow_id"],
        {CONF_PERIOD_PLAN: naturgy, CONF_PERIOD_FROM: "2025-03-01"},
        through=False,
    )
    assert _kept(form) == [
        "Octopus Current, before any other",
        "Naturgy, from 2025-03-01",
    ]
    done = await _answer(hass, form["flow_id"], {"action": "save"})

    # Then - kept from the one before any other on, with the rules answered
    assert done["reason"] == "reconfigure_successful"
    (current,) = _following(entry)
    assert current.data[CONF_PLAN_PERIODS] == [
        {CONF_PERIOD_PLAN: octopus},
        {CONF_PERIOD_PLAN: naturgy, CONF_PERIOD_FROM: "2025-03-01"},
    ]
    assert current.data[CONF_PLAN_DAILY_CHARGE] == 0.4521


async def test_a_plan_been_on_unticked_is_removed(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    form = await _at_the_plans_been_on(hass, entry)

    # When - nothing kept
    await _answer(hass, form["flow_id"], {"keep": [], "action": "save"})

    # Then
    (current,) = _following(entry)
    assert CONF_PLAN_PERIODS not in current.data


async def test_only_one_plan_been_on_can_go_back_before_any_other(
    hass: HomeAssistant,
) -> None:
    # Given - the marked plan already before any other
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    form = await _at_the_plans_been_on(hass, entry)
    form = await _answer(hass, form["flow_id"], {"action": "add_period"})

    # When - another with no date
    result = await _answer(
        hass,
        form["flow_id"],
        {CONF_PERIOD_PLAN: _plans(entry)["Naturgy"].subentry_id},
        through=False,
    )

    # Then - one of them would never price an hour
    assert result["step_id"] == "period"
    assert result["errors"] == {"base": "periods_one_always"}


async def test_two_plans_been_on_cannot_start_the_same_day(
    hass: HomeAssistant,
) -> None:
    # Given - Naturgy from 1 March 2025
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    naturgy = _plans(entry)["Naturgy"].subentry_id
    octopus = _plans(entry)["Octopus Current"].subentry_id
    form = await _at_the_plans_been_on(hass, entry)
    form = await _answer(hass, form["flow_id"], {"action": "add_period"})
    form = await _answer(
        hass,
        form["flow_id"],
        {CONF_PERIOD_PLAN: naturgy, CONF_PERIOD_FROM: "2025-03-01"},
        through=False,
    )
    form = await _answer(hass, form["flow_id"], {"action": "add_period"})

    # When - another from the same day
    result = await _answer(
        hass,
        form["flow_id"],
        {CONF_PERIOD_PLAN: octopus, CONF_PERIOD_FROM: "2025-03-01"},
        through=False,
    )

    # Then
    assert result["errors"] == {"base": "periods_same_day"}


async def test_only_plans_priced_by_the_clock_can_be_added(
    hass: HomeAssistant,
) -> None:
    # Given - a plan priced by the clock, and one with an export allowance
    allowance = {
        **_OFFER,
        CONF_NAME: "Capped export",
        CONF_PLAN_EXPORT_ALLOWANCE: 8,
        CONF_PLAN_EXPORT_PRICE_AFTER: 0.01,
    }
    entry = _entry(hass, _OFFER, allowance, version=8)
    await _set_up(hass, entry)
    form = await _at_the_plans_been_on(hass, entry)

    # When
    form = await _answer(hass, form["flow_id"], {"action": "add_period"})

    # Then - only the one an hour's price can be read from, by its name
    selector = _fields(form)[CONF_PERIOD_PLAN]
    options = form["data_schema"].schema[selector].config["options"]
    assert options == [
        {"value": _plans(entry)["Naturgy"].subentry_id, "label": "Naturgy"}
    ]


async def test_with_no_typed_plan_the_rules_are_saved_at_once(
    hass: HomeAssistant,
) -> None:
    # Given - no plan entered beside the current one
    entry = _entry(hass, version=8)
    await _set_up(hass, entry)

    # When
    form = await _edit_current(hass, entry)
    done = await _answer(hass, form["flow_id"], _RULES_ANSWER, through=False)

    # Then - nothing to ask about the plans been on
    assert done["reason"] == "reconfigure_successful"


def _fields(form: Any) -> dict[str, Any]:  # noqa: ANN401 - a flow result
    schema = form["data_schema"]
    assert schema is not None
    return {str(key): key for key in schema.schema}


# The Energy Dashboard's grid sources: the grid meter HEA prices, and a
# standing charge entered as a source of its own, as households do, its cost
# recorded by a statistic.
_GRID_SOURCE = {"type": "grid", "stat_energy_from": "sensor.grid_import"}
_STANDING_CHARGE = {
    "type": "grid",
    "stat_energy_from": "sensor.daily_charge",
    "stat_cost": "sensor.daily_charge_cost",
    "name": "Standing charge",
}


async def _energy_dashboard(hass: HomeAssistant, *sources: dict[str, Any]) -> None:
    """Save the Energy Dashboard's sources, as its own editor does."""
    manager = await async_get_manager(hass)
    update: Any = {"energy_sources": [dict(source) for source in sources]}
    await manager.async_update(update)
    await hass.async_block_till_done()


def _with_grid_meter(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
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
        ),
    )


async def test_the_daily_charge_can_follow_a_grid_source_s_recorded_cost(
    hass: HomeAssistant,
) -> None:
    # Given - the standing charge in the Energy Dashboard beside the grid meter
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    _with_grid_meter(hass, entry)
    await _energy_dashboard(hass, _GRID_SOURCE, _STANDING_CHARGE)

    # When
    form = await _edit_current(hass, entry)

    # Then - the standing charge offered by its name, and never the grid meter
    # HEA already prices, whose energy is no daily charge
    selector = _fields(form)[CONF_PLAN_DAILY_CHARGE_SOURCE]
    offered = form["data_schema"].schema[selector].config["options"]
    assert offered == [{"value": "sensor.daily_charge", "label": "Standing charge"}]

    # When - chosen
    await _answer(
        hass,
        form["flow_id"],
        {
            CONF_PLAN_DAILY_CHARGE_SOURCE: "sensor.daily_charge",
            CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value,
        },
    )

    # Then - followed, and nothing typed beside it to fall out of step
    (current,) = _following(entry)
    assert dict(current.data) == {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE_SOURCE: "sensor.daily_charge",
        CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value,
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


async def test_the_daily_charge_is_one_or_the_other(hass: HomeAssistant) -> None:
    # Given
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    await _energy_dashboard(hass, _GRID_SOURCE, _STANDING_CHARGE)
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
            CONF_PLAN_DAILY_CHARGE_SOURCE: "sensor.daily_charge",
        },
    )

    # Then - a plan with no daily charge would read cheaper than the rest, and
    # two would leave one to fall out of step
    assert neither["errors"] == {"base": "daily_charge_needed"}
    assert both["errors"] == {"base": "daily_charge_one"}
    (current,) = _following(entry)
    assert CONF_PLAN_DAILY_CHARGE not in current.data


async def test_a_daily_charge_from_a_sensor_is_kept_and_is_one_way_of_three(
    hass: HomeAssistant,
) -> None:
    # Given - a supplier's integration publishing the daily charge (HEA-317)
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    hass.states.async_set("sensor.supplier_daily_charge", "2.86")
    form = await _edit_current(hass, entry)
    cap = {CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value}
    sensor = {CONF_PLAN_DAILY_CHARGE_ENTITY: "sensor.supplier_daily_charge"}

    # When - with a typed one too, then alone
    both = await _answer(
        hass, form["flow_id"], {**cap, **sensor, CONF_PLAN_DAILY_CHARGE: 2.86}
    )
    done = await _answer(hass, both["flow_id"], {**cap, **sensor})

    # Then - two would fall out of step; the sensor alone is the plan's
    assert both["errors"] == {"base": "daily_charge_one"}
    assert done["reason"] == "reconfigure_successful"
    (current,) = _following(entry)
    assert dict(current.data) == {
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        **sensor,
        **cap,
    }
    assert not current_plan.needs_answer(current)


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


# The Repair that asks for what it holds


def _repair(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_CURRENT_PLAN)


async def _open_repair(hass: HomeAssistant) -> Any:  # noqa: ANN401 - a flow result
    await async_setup_component(hass, "repairs", {})
    manager = repairs_flow_manager(hass)
    assert manager is not None
    return await manager.async_init(DOMAIN, data={"issue_id": ISSUE_CURRENT_PLAN})


async def _answer_repair(
    hass: HomeAssistant,
    flow_id: str,
    answer: dict[str, Any],
    *,
    through: bool = True,
) -> Any:  # noqa: ANN401 - a flow result
    """Answer the Repair; `through` saves the plans been on as they stand."""
    manager = repairs_flow_manager(hass)
    assert manager is not None
    result = await manager.async_configure(flow_id, answer)
    if through and result.get("step_id") == "periods":
        result = await manager.async_configure(flow_id, {"action": "save"})
    await hass.async_block_till_done()
    return result


async def test_a_current_plan_without_a_daily_charge_raises_a_repair(
    hass: HomeAssistant,
) -> None:
    # Given - created with nothing to carry over
    entry = _entry(hass, _OFFER, version=8)

    # When
    await _set_up(hass, entry)

    # Then - asked for, since every plan's difference from it is held until then
    repair = _repair(hass)
    assert repair is not None
    assert repair.is_fixable is True


async def test_answering_the_repair_gives_the_current_plan_its_daily_charge(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    form = await _open_repair(hass)
    assert form["step_id"] == "init"
    assert form["description_placeholders"]["replaced"] == ""

    # When
    done = await _answer_repair(
        hass,
        form["flow_id"],
        {CONF_PLAN_DAILY_CHARGE: 0.38, CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value},
    )

    # Then - held, and the Repair gone
    assert done["type"] == "create_entry"
    (current,) = _following(entry)
    assert current.data[CONF_PLAN_DAILY_CHARGE] == 0.38
    assert _repair(hass) is None


async def test_an_upgrade_is_told_its_marked_plan_now_duplicates_the_current_one(
    hass: HomeAssistant,
) -> None:
    # Given - upgraded from a plan marked as the household's, its daily charge
    # carried over
    entry = _entry(hass, _MARKED, version=7)
    await _set_up(hass, entry)

    # When
    form = await _open_repair(hass)

    # Then - told which plan, with what was carried over filled in to check
    assert "Octopus Current" in form["description_placeholders"]["replaced"]
    fields = _fields(form)
    assert fields[CONF_PLAN_DAILY_CHARGE].description == {"suggested_value": 0.4521}

    # When - confirmed as it is
    await _answer_repair(
        hass,
        form["flow_id"],
        {
            CONF_PLAN_DAILY_CHARGE: 0.4521,
            CONF_PLAN_EXPORT_CAP: ExportCap.MONTHLY.value,
        },
    )

    # Then - told once: the note goes with the Repair
    (current,) = _following(entry)
    assert CONF_PLAN_REPLACED not in current.data
    assert _repair(hass) is None


async def test_answering_the_repair_keeps_the_plan_price_history_is_read_from(
    hass: HomeAssistant,
) -> None:
    # Given - upgraded, the marked plan reading the price history
    entry = _entry(hass, _MARKED, version=7)
    await _set_up(hass, entry)
    octopus = _plans(entry)["Octopus Current"].subentry_id
    form = await _open_repair(hass)

    # When - the rules confirmed as filled in, then the plans been on, listed
    form = await _answer_repair(hass, form["flow_id"], _RULES_ANSWER, through=False)
    assert form["step_id"] == "periods"
    assert _kept(form) == ["Octopus Current, before any other"]
    await _answer_repair(hass, form["flow_id"], {"action": "save"})

    # Then - the note gone, the price history kept (discussion 58)
    (current,) = _following(entry)
    assert CONF_PLAN_REPLACED not in current.data
    assert current.data[CONF_PLAN_PERIODS] == [{CONF_PERIOD_PLAN: octopus}]


async def test_giving_the_daily_charge_on_the_plan_s_own_form_clears_the_repair(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    form = await _edit_current(hass, entry)

    # When
    await _answer(
        hass,
        form["flow_id"],
        {CONF_PLAN_DAILY_CHARGE: 0.38, CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value},
    )
    await hass.async_block_till_done()

    # Then
    assert _repair(hass) is None


async def test_a_current_plan_with_its_daily_charge_raises_nothing(
    hass: HomeAssistant,
) -> None:
    # Given - set up once and answered
    entry = _entry(hass, _OFFER, version=8)
    await _set_up(hass, entry)
    form = await _edit_current(hass, entry)
    await _answer(
        hass,
        form["flow_id"],
        {CONF_PLAN_DAILY_CHARGE: 0.38, CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value},
    )

    # When - restarted
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Then
    assert _repair(hass) is None


# A plan named in a period, deleted


def _gone_repair(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_PERIOD_PLAN_GONE)


async def _delete(hass: HomeAssistant, entry: MockConfigEntry, title: str) -> None:
    hass.config_entries.async_remove_subentry(entry, _plans(entry)[title].subentry_id)
    await hass.async_block_till_done()


async def _open_gone_repair(hass: HomeAssistant) -> Any:  # noqa: ANN401 - a flow result
    await async_setup_component(hass, "repairs", {})
    manager = repairs_flow_manager(hass)
    assert manager is not None
    return await manager.async_init(DOMAIN, data={"issue_id": ISSUE_PERIOD_PLAN_GONE})


async def test_deleting_a_plan_been_on_raises_a_repair(hass: HomeAssistant) -> None:
    # Given - upgraded, Octopus Current the plan before any other
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)

    # When - deleted
    await _delete(hass, entry, "Octopus Current")

    # Then - asked about, since the hours it covered can no longer be priced
    issue = _gone_repair(hass)
    assert issue is not None
    assert issue.is_fixable


async def test_deleting_a_plan_no_period_names_raises_nothing(
    hass: HomeAssistant,
) -> None:
    # Given
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)

    # When - Naturgy, in no period, deleted
    await _delete(hass, entry, "Naturgy")

    # Then
    assert _gone_repair(hass) is None


async def test_a_plan_deleted_on_purpose_is_left_missing_and_not_asked_again(
    hass: HomeAssistant,
) -> None:
    # Given - Octopus Current deleted, and asked about
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    octopus = _plans(entry)["Octopus Current"].subentry_id
    await _delete(hass, entry, "Octopus Current")
    menu = await _open_gone_repair(hass)
    assert menu["type"] == "menu"

    # When - deleted on purpose
    manager = repairs_flow_manager(hass)
    assert manager is not None
    await manager.async_configure(menu["flow_id"], {"next_step_id": "keep"})
    await hass.async_block_till_done()

    # Then - the period kept as missing, the Repair gone, and not raised again
    (current,) = _following(entry)
    assert current.data[CONF_PLAN_PERIODS] == [
        {CONF_PERIOD_PLAN: octopus, CONF_PERIOD_GONE_KNOWN: True}
    ]
    assert _gone_repair(hass) is None
    await _delete(hass, entry, "Naturgy")
    assert _gone_repair(hass) is None


async def test_the_repair_opens_the_plans_been_on_to_put_it_right(
    hass: HomeAssistant,
) -> None:
    # Given - Octopus Current deleted, and asked about
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    await _delete(hass, entry, "Octopus Current")
    menu = await _open_gone_repair(hass)
    manager = repairs_flow_manager(hass)
    assert manager is not None

    # When - choosing the plans been on, which list the missing one in words
    form = await manager.async_configure(menu["flow_id"], {"next_step_id": "choose"})
    assert form["step_id"] == "periods"
    assert _kept(form) == ["A plan no longer entered, before any other"]
    await manager.async_configure(form["flow_id"], {"keep": [], "action": "save"})
    await hass.async_block_till_done()

    # Then - removed, the daily charge kept, and nothing left to ask
    (current,) = _following(entry)
    assert CONF_PLAN_PERIODS not in current.data
    assert current.data[CONF_PLAN_DAILY_CHARGE] == 0.4521
    assert _gone_repair(hass) is None


# Offering to carry the old price history in, once (HEA-307, ADR-0048)


def _with_priced_grid_meter(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_NAME: "Grid",
                    CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
                    CONF_PRICE_ENTITY: "sensor.old_buy_price",
                }
            ),
            subentry_type=SUBENTRY_TYPE_GRID,
            title="Grid",
            unique_id=None,
        ),
    )


async def test_ticking_provide_my_price_sensors_offers_to_carry_the_history_in(
    hass: HomeAssistant,
) -> None:
    # Given - the grid meter priced by the household's own sensor
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    _with_priced_grid_meter(hass, entry)
    await _set_up(hass, entry)
    form = await _edit_current(hass, entry)

    # When - ticked for the first time, the plans been on saved as they are
    form = await _answer(
        hass,
        form["flow_id"],
        {**_RULES_ANSWER, CONF_PLAN_PROVIDES_PRICES: True},
        through=False,
    )
    form = await _answer(hass, form["flow_id"], {"action": "save"}, through=False)

    # Then - asked once, with the sensor it prices by now filled in
    assert form["step_id"] == "carry_in"
    assert _fields(form)["import_price_from"].description == {
        "suggested_value": "sensor.old_buy_price"
    }

    # When - carried in
    done = await _answer(
        hass, form["flow_id"], {"import_price_from": "sensor.old_buy_price"}
    )
    await hass.async_block_till_done()

    # Then - saved, provided, and the carry-in done on the reload that made the
    # sensors, so nothing is left waiting
    assert done["reason"] == "reconfigure_successful"
    (current,) = _following(entry)
    assert current.data[CONF_PLAN_PROVIDES_PRICES] is True
    assert CONF_PLAN_CARRY_IN not in current.data


async def test_already_providing_is_not_offered_the_history_again(
    hass: HomeAssistant,
) -> None:
    # Given - the price sensors already provided
    entry = _entry(hass, _MARKED, _OFFER, version=7)
    await _set_up(hass, entry)
    (current,) = _following(entry)
    hass.config_entries.async_update_subentry(
        entry, current, data={**current.data, CONF_PLAN_PROVIDES_PRICES: True}
    )
    await hass.async_block_till_done()
    form = await _edit_current(hass, entry)

    # When
    form = await _answer(
        hass,
        form["flow_id"],
        {**_RULES_ANSWER, CONF_PLAN_PROVIDES_PRICES: True},
        through=False,
    )
    done = await _answer(hass, form["flow_id"], {"action": "save"}, through=False)

    # Then - saved straight away
    assert done["reason"] == "reconfigure_successful"
