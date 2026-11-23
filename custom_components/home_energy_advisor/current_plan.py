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

from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from . import issues
from .common_strings import async_common_strings
from .const import (
    CONF_PERIOD_FROM,
    CONF_PERIOD_GONE_KNOWN,
    CONF_PERIOD_PLAN,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_PERIODS,
    CONF_PLAN_PROVIDES_PRICES,
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

    from .tariff_plans import TariffPlan

# Its name where the household's language has none.
_NAME = "Your current plan"
# What the form asks: the billing rules no price sensor holds (ADR-0042),
# whether this integration provides the price sensors, and the plans the
# household has been on, whose prices stand in where the sensors have no
# statistics and feed them where provided (HEA-311, HEA-307).
_RULES = (
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_SOURCE,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_PROVIDES_PRICES,
    CONF_PLAN_PERIODS,
)
# Where 1.7.1 kept the one plan its price history was read from.
_HISTORY_FROM = "price_history_from"


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


def rules_schema(per_day: str, sources: list[selector.SelectOptionDict]) -> vol.Schema:
    """The current plan's form: its daily charge, its cap, and its price sensors.

    Both ways of giving the daily charge are optional to the form, which checks
    that exactly one was given (`rules_errors`). A source to follow is offered
    only where the Energy Dashboard has one. Ticked, this integration provides
    the household's price sensors (ADR-0048). The plans the household has been
    on follow in steps of their own (`PlansBeenOnSteps`).
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
            vol.Optional(
                CONF_PLAN_PROVIDES_PRICES, default=False
            ): selector.BooleanSelector(),
        }
    )


def rules_errors(answer: Mapping[str, Any]) -> dict[str, str]:
    """A daily charge given one way: none reads cheaper, two fall out of step."""
    typed = answer.get(CONF_PLAN_DAILY_CHARGE) is not None
    followed = bool(answer.get(CONF_PLAN_DAILY_CHARGE_SOURCE))
    if typed == followed:
        return {"base": "daily_charge_one" if typed else "daily_charge_needed"}
    return {}


def period_errors(
    periods: list[dict[str, Any]], added: Mapping[str, Any]
) -> dict[str, str]:
    """Why a plan cannot join the plans been on, if it cannot.

    Only one can go back before any other, and no two can start the same day:
    the other would never price an hour.
    """
    start = added.get(CONF_PERIOD_FROM) or None
    if any(period.get(CONF_PERIOD_FROM) == start for period in periods):
        return {"base": "periods_one_always" if start is None else "periods_same_day"}
    return {}


def _periods_in(answer: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The plans been on in an answer, each its plan and any start, earliest first.

    The one going back to always comes first; a start left empty is none. A
    period whose plan the household deleted on purpose keeps saying so.
    """
    periods = [
        {CONF_PERIOD_PLAN: period[CONF_PERIOD_PLAN]}
        | ({CONF_PERIOD_FROM: start} if (start := period.get(CONF_PERIOD_FROM)) else {})
        | ({CONF_PERIOD_GONE_KNOWN: True} if period.get(CONF_PERIOD_GONE_KNOWN) else {})
        for period in answer.get(CONF_PLAN_PERIODS) or ()
        if period.get(CONF_PERIOD_PLAN)
    ]
    return sorted(periods, key=lambda period: period.get(CONF_PERIOD_FROM, ""))


def _gone(entry: ConfigEntry, periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The periods whose plan is deleted, and not known to be on purpose."""
    plans = plans_of(entry)
    return [
        period
        for period in periods
        if period[CONF_PERIOD_PLAN] not in plans
        and not period.get(CONF_PERIOD_GONE_KNOWN)
    ]


def deleted_on_purpose(entry: ConfigEntry) -> dict[str, Any] | None:
    """The current plan's data with each period whose plan is gone marked as known.

    None where there is no current plan.
    """
    current = current_plan_of(entry)
    if current is None:
        return None
    periods = _periods_in(current.data)
    for period in _gone(entry, periods):
        period[CONF_PERIOD_GONE_KNOWN] = True
    return {**current.data, CONF_PLAN_PERIODS: periods}


def rules_of(data: Mapping[str, Any]) -> dict[str, Any]:
    """The billing rules a current plan or an answer holds, and nothing else."""
    rules = {key: data[key] for key in _RULES if data.get(key) not in (None, "")}
    if periods := _periods_in(data):
        rules[CONF_PLAN_PERIODS] = periods
    else:
        rules.pop(CONF_PLAN_PERIODS, None)
    if not rules.get(CONF_PLAN_PROVIDES_PRICES):
        rules.pop(CONF_PLAN_PROVIDES_PRICES, None)
    return rules


def provides_prices(entry: ConfigEntry) -> bool:
    """Whether this integration provides the household's price sensors."""
    current = current_plan_of(entry)
    return current is not None and bool(current.data.get(CONF_PLAN_PROVIDES_PRICES))


def plan_on(entry: ConfigEntry, day: date) -> TariffPlan | None:
    """The typed plan of the period the household is in on `day`, if any.

    The last period started by then; the one before any other counts as started
    from always. None before the first dated period with none before it, or
    where that period's plan is gone.
    """
    current = current_plan_of(entry)
    if current is None:
        return None
    started = [
        period
        for period in _periods_in(current.data)
        if CONF_PERIOD_FROM not in period
        or date.fromisoformat(period[CONF_PERIOD_FROM]) <= day
    ]
    if not started:
        return None
    return plans_of(entry).get(started[-1][CONF_PERIOD_PLAN])


def plan_data(name: str, answer: Mapping[str, Any]) -> dict[str, Any]:
    """What the current plan's entry holds after this answer."""
    return {CONF_NAME: name, CONF_PLAN_FOLLOWS: True, **rules_of(answer)}


_KEEP = "keep"
_ACTION = "action"
_ADD_PERIOD = "add_period"
_SAVE = "save"


class PlansBeenOnSteps:
    """The steps after the current plan's rules: the plans it has been on.

    One lists them in words, to untick any or add one; the other adds a plan
    from a day, or from before any other. Shared by the current plan's own form
    and its Repair (HEA-307). The flow gives `hass`, how to show a form, which
    entry the plans are in, and how to save.
    """

    hass: HomeAssistant
    _rules: dict[str, Any]
    _periods: list[dict[str, Any]]

    def _periods_entry(self) -> ConfigEntry:
        raise NotImplementedError

    def _periods_show(
        self, step_id: str, schema: vol.Schema, errors: dict[str, str]
    ) -> Any:  # noqa: ANN401 - each flow's own result type
        raise NotImplementedError

    def _periods_save(self, answer: dict[str, Any]) -> Any:  # noqa: ANN401 - as _periods_show
        raise NotImplementedError

    async def _after_rules(
        self, rules: Mapping[str, Any], held: Mapping[str, Any]
    ) -> Any:  # noqa: ANN401 - as _periods_show
        """On to the plans been on, where a plan could be one; else saved."""
        self._rules = dict(rules)
        self._periods = _periods_in(held)
        if not history_plans(self._periods_entry()) and not self._periods:
            return self._periods_save(self._rules)
        return await self.async_step_periods()

    async def async_step_periods(self, user_input: dict[str, Any] | None = None) -> Any:  # noqa: ANN401 - as _periods_show
        """The plans been on, in words: untick any, add one, or save."""
        if user_input is not None:
            kept = set(user_input.get(_KEEP, ()))
            self._periods = [
                period
                for index, period in enumerate(self._periods)
                if str(index) in kept
            ]
            if user_input[_ACTION] == _ADD_PERIOD:
                return await self.async_step_period()
            return self._periods_save({**self._rules, CONF_PLAN_PERIODS: self._periods})
        labels = await async_common_strings(self.hass)
        names = {
            option["value"]: option["label"]
            for option in history_plans(self._periods_entry())
        }
        options = [
            selector.SelectOptionDict(
                value=str(index), label=_period_label(period, names, labels)
            )
            for index, period in enumerate(self._periods)
        ]
        return self._periods_show(
            "periods",
            vol.Schema(
                {
                    vol.Optional(
                        _KEEP, default=[option["value"] for option in options]
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Required(_ACTION, default=_SAVE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[_ADD_PERIOD, _SAVE],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="period_action",
                        )
                    ),
                }
            ),
            {},
        )

    async def async_step_period(self, user_input: dict[str, Any] | None = None) -> Any:  # noqa: ANN401 - as _periods_show
        """A plan the household has been on, and the day it started, if any."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = period_errors(self._periods, user_input)
            if not errors:
                self._periods = _periods_in(
                    {CONF_PLAN_PERIODS: [*self._periods, user_input]}
                )
                return await self.async_step_periods()
        return self._periods_show(
            "period",
            vol.Schema(
                {
                    vol.Required(CONF_PERIOD_PLAN): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=history_plans(self._periods_entry()),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_PERIOD_FROM): selector.DateSelector(),
                }
            ),
            errors,
        )


def _period_label(
    period: Mapping[str, str], names: Mapping[str, str], labels: Mapping[str, str]
) -> str:
    """A plan been on, in words: "Naturgy, from 2025-03-01", or before any other."""
    name = names.get(period[CONF_PERIOD_PLAN]) or labels.get(
        "plan_period_gone", "A plan no longer entered"
    )
    if start := period.get(CONF_PERIOD_FROM):
        return (
            labels.get("plan_period_from", "{plan}, from {date}")
            .replace("{plan}", name)
            .replace("{date}", start)
        )
    return labels.get("plan_period_first", "{plan}, before any other").replace(
        "{plan}", name
    )


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
            **_been_on_always(subentry),
        }
    return {}


def _been_on_always(plan: ConfigSubentry) -> dict[str, list[dict[str, str]]]:
    """This plan as the one the household has always been on, where it can be."""
    if not follows_the_clock(tariff_plan_from(plan.title, plan.data).plan):
        return {}
    return {CONF_PLAN_PERIODS: [{CONF_PERIOD_PLAN: plan.subentry_id}]}


@callback
def fill_the_plans_been_on(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Give a current plan made before the list existed the plans it has been on.

    1.7.1 kept one plan for the price history, which becomes the first period.
    1.7.0 kept only the replaced plan's name, which is linked until the
    household has answered for it, since an answer chose for itself.
    """
    current = current_plan_of(entry)
    if current is None or CONF_PLAN_PERIODS in current.data:
        return
    data = {key: value for key, value in current.data.items() if key != _HISTORY_FROM}
    if history := current.data.get(_HISTORY_FROM):
        data[CONF_PLAN_PERIODS] = [{CONF_PERIOD_PLAN: history}]
    elif replaced := current.data.get(CONF_PLAN_REPLACED):
        data |= next(
            (
                _been_on_always(subentry)
                for subentry in entry.subentries.values()
                if subentry.subentry_type == SUBENTRY_TYPE_PLAN
                and subentry.title == replaced
            ),
            {},
        )
    if data != dict(current.data):
        hass.config_entries.async_update_subentry(entry, current, data=data)


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
    """Raise the current plan's Repairs where they need an answer, or clear them.

    One for its daily charge (ADR-0042), one for a plan named in its periods
    that was deleted without the household saying it meant to (HEA-307).
    """
    plan = current_plan_of(entry)
    for issue_id, needed in (
        (issues.ISSUE_CURRENT_PLAN, plan is not None and needs_answer(plan)),
        (
            issues.ISSUE_PERIOD_PLAN_GONE,
            plan is not None and bool(_gone(entry, _periods_in(plan.data))),
        ),
    ):
        if needed:
            issues.async_ask(hass, issue_id, issue_id, {}, {"entry_id": entry.entry_id})
        else:
            issues.async_clear(hass, issue_id)
