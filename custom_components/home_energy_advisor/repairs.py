"""The Repairs this integration answers itself.

Every other issue is fixed in Home Assistant. These two are answered here:

* the Energy Dashboard's house differs from the one entered here, and the
  household takes theirs or keeps their own (ADR-0030);
* an hour of a meter's statistics no home could use, which the household is
  offered a correction for, made only once they have confirmed exactly what it
  changes (ADR-0045).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.const import CONF_NAME, UnitOfEnergy
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import selector
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from . import issues
from .common_strings import async_common_strings
from .config_flow import validate_battery, validate_grid_meter
from .const import CONF_HOUSE_CONSUMPTION_ENTITY, DOMAIN
from .energy_dashboard import (
    async_energy_prefs,
    async_keep,
    async_listed_differences,
    async_take,
    dashboard_meters,
    differences_from,
    taken,
)
from .impossible_hours import (
    CAUSE_COUNTED_AGAIN,
    CAUSE_FELL,
    CAUSE_RESTARTED,
    MONEY,
    amount,
    sensor_name,
    when,
)
from .schemas import vol

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_VALUE = "value"


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001 - HA signature
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Start answering the issue: an impossible hour, or an Energy Dashboard change."""
    if issue_id.startswith(
        (f"{issues.ISSUE_IMPOSSIBLE_HOUR}_", f"{issues.ISSUE_IMPOSSIBLE_COST}_")
    ):
        return ImpossibleHourFlow(issue_id, data or {})
    return EnergyDashboardChangedFlow(str((data or {}).get("entry_id")))


class ImpossibleHourFlow(RepairsFlow):
    """Correct one impossible hour of one statistic, after saying what that changes.

    A meter's hour, or the Energy Dashboard's cost for it: each its own Repair,
    so the household chooses which to correct. Two steps, so nothing is written
    until the household has seen the change in full: first the value the hour
    should have recorded, suggested where the readings allow; then what will
    change, and how to undo it. Only then is the hour corrected, by the call
    Developer Tools' own Adjust makes, on that one statistic from that one
    moment (ADR-0045).
    """

    def __init__(
        self, issue_id: str, data: dict[str, str | int | float | None]
    ) -> None:
        """Answer for one statistic's hour."""
        self._issue_id = issue_id
        self._data = data
        self._value: float | None = None
        self._unit = str(data.get("unit") or UnitOfEnergy.KILO_WATT_HOUR)
        # The money's own strings begin "impossible_cost_", the energy's
        # "impossible_".
        money = data.get("kind") == MONEY
        self._strings = "impossible_cost_" if money else "impossible_"

    def _amount(self, value: float) -> str:
        return amount(value, self._unit)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA signature
    ) -> RepairsFlowResult:
        """The hour, what probably happened, and a choice: correct it or leave it.

        Home Assistant offers no Ignore on a Repair with a fix flow, so leaving
        the hour as it is has to be one of the Repair's own answers (ADR-0046).
        """
        return self.async_show_menu(
            step_id="init",
            menu_options=["correct", "leave"],
            description_placeholders={**self._named(), **await self._explained()},
        )

    async def async_step_leave(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA signature
    ) -> RepairsFlowResult:
        """Leave the hour as recorded, and ignore the Repair as Ignore would.

        Aborted rather than finished: Home Assistant deletes the issue of a
        finished fix, and the next check would raise it afresh. An ignored issue
        stays ignored when the check finds it again, and can be found under Show
        ignored repairs.
        """
        ir.async_ignore_issue(self.hass, DOMAIN, self._issue_id, ignore=True)
        return self.async_abort(reason="left_as_it_is")

    async def async_step_correct(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """What the hour should have recorded, the suggestion filled in."""
        if user_input is not None:
            self._value = float(user_input[_VALUE])
            return await self.async_step_confirm()
        suggested = self._data.get("suggestion")
        schema = vol.Schema(
            {
                vol.Required(_VALUE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        step="any",
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement=self._unit,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="correct",
            data_schema=self.add_suggested_values_to_schema(
                schema, {} if suggested is None else {_VALUE: suggested}
            ),
            description_placeholders={
                **self._named(),
                **await self._explained(),
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Say exactly what will change; correct the hour only once confirmed."""
        recorded = _number(self._data["change"])
        value = self._value if self._value is not None else recorded
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={
                    **self._named(),
                    "value": self._amount(value),
                    "difference": self._signed(value - recorded),
                },
            )
        statistic_id = str(self._data["statistic_id"])
        corrected_at = _time(str(self._data["corrected_at"]))
        get_instance(self.hass).async_adjust_statistics(
            statistic_id, corrected_at, value - recorded, self._unit
        )
        _LOGGER.warning(
            "Corrected %s for the hour from %s from %s to %s, at the household's "
            "request (Repairs). To undo it, set the same hour back to %s in "
            "Developer Tools > Statistics",
            statistic_id,
            when(_time(str(self._data["start"]))),
            self._amount(recorded),
            self._amount(value),
            self._amount(recorded),
        )
        issues.async_clear(self.hass, self._issue_id)
        return self.async_create_entry(data={})

    def _named(self) -> dict[str, str]:
        """The statistic, the hour and what it recorded, as every step says them."""
        return {
            "sensor": sensor_name(self.hass, str(self._data["statistic_id"])),
            "when": when(_time(str(self._data["start"]))),
            "recorded": self._amount(_number(self._data["change"])),
        }

    def _signed(self, value: float) -> str:
        """A change with its sign, so a fall reads as one."""
        return f"+{self._amount(value)}" if value > 0 else self._amount(value)

    async def _explained(self) -> dict[str, str]:
        """What probably happened, what it should have been, and its partner."""
        labels = await async_common_strings(self.hass)
        key = self._strings
        cause = {
            CAUSE_COUNTED_AGAIN: labels.get(f"{key}cause_counted_again", ""),
            CAUSE_FELL: labels.get(f"{key}cause_fell", ""),
            CAUSE_RESTARTED: labels.get(f"{key}cause_restarted", ""),
        }.get(str(self._data.get("cause")), labels.get(f"{key}cause_jumped", ""))
        return {
            "cause": cause,
            "suggestion": self._suggested(labels),
            "partner": self._partner(labels),
            "ceiling": self._amount(_number(self._data.get("ceiling"))),
        }

    def _suggested(self, labels: dict[str, str]) -> str:
        """What the hour should have been, and what that is worked out from."""
        data = self._data
        key = self._strings
        if data.get("suggestion") is None:
            return labels.get(f"{key}suggest_none", "")
        if data.get("cause") == CAUSE_RESTARTED:
            return labels.get(f"{key}suggest_restarted", "")
        suggestion = self._amount(_number(data["suggestion"]))
        if data.get("window"):
            return labels.get(f"{key}suggest_window", "").format(
                window=dt_util.as_local(_time(str(data["window"]))).strftime("%H:%M"),
                jump=self._amount(_number(data["jump"])),
                rest=self._amount(_number(data["rest"])),
                suggestion=suggestion,
            )
        if data.get("price") is not None:
            return labels.get(f"{key}suggest_price", "").format(
                energy=amount(_number(data["energy"])),
                price=f"{_number(data['price']):.4f} {self._unit}/kWh",
                suggestion=suggestion,
            )
        return labels.get(f"{key}suggest_days", "").format(
            low=self._amount(_number(data["low"])),
            high=self._amount(_number(data["high"])),
            suggestion=suggestion,
        )

    def _partner(self, labels: dict[str, str]) -> str:
        """The other statistic the same reading reached, which has its own Repair."""
        partner = self._data.get("partner")
        if not partner:
            return ""
        return labels.get(f"{self._strings}partner", "").format(
            sensor=sensor_name(self.hass, str(partner))
        )


def _time(text: str) -> datetime:
    moment = dt_util.parse_datetime(text)
    if moment is None:
        msg = f"Not a time: {text}"
        raise ValueError(msg)
    return moment


def _number(value: str | float | None) -> float:
    """A figure the issue carried, which the registry keeps as a plain value."""
    return 0.0 if value is None else float(value)


class EnergyDashboardChangedFlow(RepairsFlow):
    """Take the Energy Dashboard's batteries and grid meters, or keep these."""

    def __init__(self, entry_id: str) -> None:
        """Answer for one entry."""
        self._entry_id = entry_id

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA signature
    ) -> RepairsFlowResult:
        """Show both sides, and the two answers."""
        entry = self._entry()
        if entry is None:
            return self.async_abort(reason="entry_removed")
        prefs = await async_energy_prefs(self.hass)
        return self.async_show_menu(
            step_id="init",
            menu_options=["take", "keep"],
            description_placeholders=await async_listed_differences(
                self.hass, differences_from(self.hass, prefs, entry), entry
            ),
        )

    async def async_step_take(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA signature
    ) -> RepairsFlowResult:
        """Take them, unless one would be refused on the form.

        Checked before anything changes, as a battery or grid meter added by
        hand is, so the form's refusals stay refusals and nothing is half taken.
        """
        entry = self._entry()
        if entry is None:
            return self.async_abort(reason="entry_removed")
        prefs = await async_energy_prefs(self.hass)
        found = differences_from(self.hass, prefs, entry)
        # Taken from the Energy Dashboard, so it vouches for its own roles
        # exactly as it does on the forms (HEA-279).
        dashboard = dashboard_meters(prefs)
        for answers in found.theirs:
            if validate_battery(self.hass, taken(answers), dashboard=dashboard):
                return self.async_abort(
                    reason="battery_not_countable",
                    description_placeholders={"battery": answers[CONF_NAME]},
                )
        metered = bool(entry.data.get(CONF_HOUSE_CONSUMPTION_ENTITY))
        for answers in found.grid_theirs:
            if validate_grid_meter(
                self.hass, answers, house_metered=metered, dashboard=dashboard
            ):
                return self.async_abort(
                    reason="grid_meter_not_countable",
                    description_placeholders={"grid": answers[CONF_NAME]},
                )
        async_take(self.hass, entry, prefs)
        return self.async_create_entry(data={})

    async def async_step_keep(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA signature
    ) -> RepairsFlowResult:
        """Keep these, and do not ask again until the Energy Dashboard changes."""
        entry = self._entry()
        if entry is None:
            return self.async_abort(reason="entry_removed")
        async_keep(self.hass, entry, await async_energy_prefs(self.hass))
        return self.async_create_entry(data={})

    def _entry(self) -> ConfigEntry | None:
        return self.hass.config_entries.async_get_entry(self._entry_id)
