"""The plan the household is on, which the integration keeps (ADR-0042).

It holds no prices: the comparison prices it at the prices Paid is priced at,
each grid meter's own and the Energy Dashboard's export price. It holds only the
billing rules no price sensor can: its daily charge and its monthly export cap.

The integration creates it rather than the household entering it. On upgrade it
takes those rules from the plan the household had marked as the one it is on,
which stays as an ordinary plan; on any setup that finds none, as after the
household deleted it, it is created without a daily charge, for the household
to give.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import issues
from .common_strings import async_common_strings
from .const import (
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_HISTORY_FROM,
    CONF_PLAN_REPLACED,
    SUBENTRY_TYPE_PLAN,
)
from .energy_dashboard import async_energy_prefs, grid_import_costs
from .engine.plan_pricing import ExportCap
from .engine.plan_schedule import follows_the_clock
from .house_inputs import grid_meters_of
from .schemas import vol
from .tariff_plans import plans_of, tariff_plan_from

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# Its name where the household's language has none.
_NAME = "Your current plan"
# What the form asks: the billing rules no price sensor holds (ADR-0042), and
# the plan whose prices stand in where the sensors have no statistics (HEA-311).
_RULES = (
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_HISTORY_FROM,
)


async def async_daily_charge_sources(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[selector.SelectOptionDict]:
    """The Energy Dashboard grid sources a daily charge can follow.

    Each whose cost Home Assistant records, by the source's name. Never one of
    the grid meters this integration prices: its energy is no daily charge.
    Which source is the standing charge is the household's to say, since
    nothing tells it apart from a grid meter.
    """
    priced = {meter.imported for meter in grid_meters_of(entry).values()}
    costs = grid_import_costs(
        await async_energy_prefs(hass),
        hass.data.get("energy", {}).get("cost_sensors", {}),
    )
    options = []
    for meter, (_, name) in costs.items():
        if meter in priced:
            continue
        state = hass.states.get(meter)
        label = name or (state.name if state else None) or meter
        options.append(selector.SelectOptionDict(value=meter, label=label))
    return options


def history_plans(entry: ConfigEntry) -> list[selector.SelectOptionDict]:
    """The typed plans the current plan's price history can be read from.

    Each priced by the clock alone, by its name: a plan with an allowance
    charges by how much was used, which no single hour's price says (HEA-311).
    """
    return [
        selector.SelectOptionDict(value=plan_id, label=tariff.plan.name)
        for plan_id, tariff in plans_of(entry).items()
        if follows_the_clock(tariff.plan)
    ]


def rules_schema(
    per_day: str,
    sources: list[selector.SelectOptionDict],
    plans: list[selector.SelectOptionDict],
) -> vol.Schema:
    """The current plan's form: its daily charge, its cap, and its price history.

    Both ways of giving the daily charge are optional to the form, which checks
    that exactly one was given (`rules_errors`). A source to follow is offered
    only where the Energy Dashboard has one, and a plan to read price history
    from only where one has been entered.
    """
    following = (
        {
            vol.Optional(CONF_PLAN_DAILY_CHARGE_SOURCE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sources, mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }
        if sources
        else {}
    )
    history = (
        {
            vol.Optional(CONF_PLAN_HISTORY_FROM): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=plans, mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }
        if plans
        else {}
    )
    return vol.Schema(
        {
            vol.Optional(CONF_PLAN_DAILY_CHARGE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    step="any",
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement=per_day,
                )
            ),
            **following,
            vol.Required(
                CONF_PLAN_EXPORT_CAP, default=ExportCap.NONE.value
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[cap.value for cap in ExportCap],
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=CONF_PLAN_EXPORT_CAP,
                )
            ),
            **history,
        }
    )


def rules_errors(answer: Mapping[str, Any]) -> dict[str, str]:
    """A daily charge given one way: none reads cheaper, two fall out of step."""
    typed = answer.get(CONF_PLAN_DAILY_CHARGE) is not None
    followed = bool(answer.get(CONF_PLAN_DAILY_CHARGE_SOURCE))
    if typed == followed:
        return {"base": "daily_charge_one" if typed else "daily_charge_needed"}
    return {}


def rules_of(data: Mapping[str, Any]) -> dict[str, Any]:
    """The billing rules a current plan or an answer holds, and nothing else."""
    return {key: data[key] for key in _RULES if data.get(key) not in (None, "")}


def plan_data(name: str, answer: Mapping[str, Any]) -> dict[str, Any]:
    """What the current plan's entry holds after this answer."""
    return {CONF_NAME: name, CONF_PLAN_FOLLOWS: True, **rules_of(answer)}


def is_current_plan(subentry: ConfigSubentry) -> bool:
    """Whether a subentry is the plan the household is on."""
    return subentry.subentry_type == SUBENTRY_TYPE_PLAN and bool(
        subentry.data.get(CONF_PLAN_FOLLOWS)
    )


def has_current_plan(entry: ConfigEntry) -> bool:
    """Whether the household's current plan exists."""
    return current_plan_of(entry) is not None


def current_plan_of(entry: ConfigEntry) -> ConfigSubentry | None:
    """The household's current plan, if it has one yet."""
    return next(
        (
            subentry
            for subentry in entry.subentries.values()
            if is_current_plan(subentry)
        ),
        None,
    )


async def async_ensure_current_plan(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create the current plan if there is none, its daily charge left to give."""
    if not has_current_plan(entry):
        await async_create_current_plan(hass, entry, {})


async def async_create_current_plan(
    hass: HomeAssistant, entry: ConfigEntry, rules: dict[str, Any]
) -> None:
    """Add the current plan, holding these billing rules and nothing else."""
    name = (await async_common_strings(hass)).get("current_plan_name") or _NAME
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_NAME: name,
                    CONF_PLAN_FOLLOWS: True,
                    CONF_PLAN_EXPORT_CAP: ExportCap.NONE.value,
                    **rules,
                }
            ),
            subentry_type=SUBENTRY_TYPE_PLAN,
            title=name,
            unique_id=None,
        ),
    )


def take_the_marked_plan_s_rules(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Unmark the plan marked as the one the household is on, and return its rules.

    The plan stays, prices and all, as an ordinary plan: its row beside the
    current plan's shows where its typed prices and the household's own disagree.
    Only its daily charge and cap go to the current plan, with its name, so the
    Repair can tell the household it now duplicates the current plan. Its prices
    still stand in where the household's price sensors have no statistics, as
    they priced every hour before (HEA-311).
    """
    # Only one plan is ever marked, so nothing is read after it is changed.
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_PLAN or not subentry.data.get(
            CONF_PLAN_CURRENT
        ):
            continue
        hass.config_entries.async_update_subentry(
            entry, subentry, data={**subentry.data, CONF_PLAN_CURRENT: False}
        )
        return {
            **{
                key: subentry.data[key]
                for key in (CONF_PLAN_DAILY_CHARGE, CONF_PLAN_EXPORT_CAP)
                if key in subentry.data
            },
            CONF_PLAN_REPLACED: subentry.title,
            **_history_from(subentry),
        }
    return {}


def _history_from(plan: ConfigSubentry) -> dict[str, str]:
    """The current plan's price history read from this plan, where it can be."""
    if not follows_the_clock(tariff_plan_from(plan.title, plan.data).plan):
        return {}
    return {CONF_PLAN_HISTORY_FROM: plan.subentry_id}


@callback
def link_the_replaced_plan(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Read the price history from the plan the current plan replaced.

    For a current plan made before it could be: 1.7.0 kept only the replaced
    plan's name, and priced no hour its sensors had no statistics for. Only
    until the household has answered for it, since an answer chose for itself.
    """
    current = current_plan_of(entry)
    if current is None or CONF_PLAN_HISTORY_FROM in current.data:
        return
    replaced = current.data.get(CONF_PLAN_REPLACED)
    if not replaced:
        return
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_PLAN and subentry.title == replaced:
            if link := _history_from(subentry):
                hass.config_entries.async_update_subentry(
                    entry, current, data={**current.data, **link}
                )
            return


def needs_answer(plan: ConfigSubentry) -> bool:
    """Whether the household is asked about its current plan.

    Asked for its daily charge where it has none, and told once that a plan it
    had marked as its own now duplicates it.
    """
    given = plan.data.get(CONF_PLAN_DAILY_CHARGE) is not None or bool(
        plan.data.get(CONF_PLAN_DAILY_CHARGE_SOURCE)
    )
    return not given or bool(plan.data.get(CONF_PLAN_REPLACED))


@callback
def async_check(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise the current plan's Repair where it needs an answer, or clear it."""
    plan = current_plan_of(entry)
    if plan is not None and needs_answer(plan):
        issues.async_ask(
            hass,
            issues.ISSUE_CURRENT_PLAN,
            issues.ISSUE_CURRENT_PLAN,
            {},
            {"entry_id": entry.entry_id},
        )
    else:
        issues.async_clear(hass, issues.ISSUE_CURRENT_PLAN)
