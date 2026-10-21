"""The one Repair this integration fixes itself: an Energy Dashboard change.

Every other issue is fixed in Home Assistant. This one is a question only this
integration can act on: the Energy Dashboard's house differs from the one
entered here, and the household takes theirs or keeps their own (ADR-0030).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.const import CONF_NAME

from .config_flow import validate_battery
from .energy_dashboard import (
    async_energy_prefs,
    async_keep,
    async_listed_differences,
    async_take,
    differences_from,
    taken,
)
from .house_inputs import batteries_of

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001 - HA signature
    issue_id: str,  # noqa: ARG001 - HA signature; the entry travels in the data
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Start answering the Energy Dashboard change the issue was raised for."""
    return EnergyDashboardChangedFlow(str((data or {}).get("entry_id")))


class EnergyDashboardChangedFlow(RepairsFlow):
    """Take the Energy Dashboard's batteries, or keep the ones entered here."""

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
                self.hass, differences_from(prefs, entry), batteries_of(entry)
            ),
        )

    async def async_step_take(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - HA signature
    ) -> RepairsFlowResult:
        """Take them, unless one would be refused on the form.

        Checked before anything changes, as a battery added by hand is, so the
        form's refusals stay refusals and nothing is half taken.
        """
        entry = self._entry()
        if entry is None:
            return self.async_abort(reason="entry_removed")
        prefs = await async_energy_prefs(self.hass)
        for answers in differences_from(prefs, entry).theirs:
            if validate_battery(self.hass, taken(answers)):
                return self.async_abort(
                    reason="battery_not_countable",
                    description_placeholders={"battery": answers[CONF_NAME]},
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
