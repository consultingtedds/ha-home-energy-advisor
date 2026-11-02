"""Entering a tariff plan: its details, then its bands one at a time (ADR-0036).

Home Assistant's forms have no timetable editor, so a plan is built a band at a
time. After each band a review lists the bands so far, which can be unticked to
remove them, and says which hours of a weekday and of a rest day are still
uncovered. A band that overlaps one already entered is refused on its own form,
and the plan is saved only once every hour is covered: an hour priced twice or
not at all would be a guess.

Exactly one plan is the household's current plan, which every other is compared
with, so saving one as current makes the previous one not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector, translation

from .const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_EXPORT_PRICE,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_HOLIDAYS,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)
from .engine.plan_pricing import Band, DayKind, Days, Plan
from .schemas import vol
from .tariff_plans import band_from, tariff_plan_from

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_KEEP = "keep"
_ACTION = "action"
_ADD_BAND = "add_band"
_SAVE = "save"

# A price per kWh, or per day, as it is printed on an offer. Any sign: a
# wholesale-linked plan can charge less than nothing for an hour (HEA-165).
_PRICE = selector.NumberSelector(
    selector.NumberSelectorConfig(step="any", mode=selector.NumberSelectorMode.BOX)
)
_HOUR_FROM = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX
    )
)
_HOUR_TO = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=1, max=24, step=1, mode=selector.NumberSelectorMode.BOX
    )
)

_DETAILS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_PLAN_CURRENT, default=False): selector.BooleanSelector(),
        vol.Required(CONF_PLAN_DAILY_CHARGE, default=0): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, step="any", mode=selector.NumberSelectorMode.BOX
            )
        ),
        vol.Required(CONF_PLAN_EXPORT_PRICE, default=0): _PRICE,
        vol.Optional(CONF_PLAN_HOLIDAYS): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="calendar")
        ),
    }
)

_BAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BAND_DAYS, default=Days.EVERY_DAY.value): (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[days.value for days in Days],
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=CONF_BAND_DAYS,
                )
            )
        ),
        vol.Required(CONF_BAND_START): _HOUR_FROM,
        vol.Required(CONF_BAND_END): _HOUR_TO,
        vol.Required(CONF_BAND_IMPORT_PRICE): _PRICE,
        vol.Optional(CONF_BAND_EXPORT_PRICE): _PRICE,
    }
)

_DAY_LABELS = {
    DayKind.WEEKDAY: ("plan_weekdays", "Weekdays"),
    DayKind.REST_DAY: ("plan_rest_days", "Weekends and holidays"),
}
_DAYS_LABELS = {
    Days.WEEKDAYS: ("plan_weekdays", "Weekdays"),
    Days.REST_DAYS: ("plan_rest_days", "Weekends and holidays"),
    Days.EVERY_DAY: ("plan_every_day", "Every day"),
}


class PlanSubentryFlowHandler(ConfigSubentryFlow):
    """Add or edit one tariff plan, a band at a time."""

    def __init__(self) -> None:
        """Start with no details and no bands."""
        self._details: dict[str, Any] = {}
        self._bands: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """The plan's own details, before any band."""
        if user_input is not None:
            self._details = user_input
            return await self.async_step_band()
        return self.async_show_form(step_id="user", data_schema=_DETAILS_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a plan's details, then review the bands it already has."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            self._details = user_input
            self._bands = [dict(band) for band in subentry.data.get(CONF_BANDS, ())]
            return await self.async_step_bands()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _DETAILS_SCHEMA, subentry.data
            ),
        )

    async def async_step_band(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """One band: which days, which hours, and its prices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = self._band_error(user_input)
            if error is None:
                self._bands.append(user_input)
                return await self.async_step_bands()
            errors["base"] = error
        return self.async_show_form(
            step_id="band",
            data_schema=self.add_suggested_values_to_schema(
                _BAND_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_bands(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """The bands so far, the hours still uncovered, and what to do next."""
        errors: dict[str, str] = {}
        if user_input is not None:
            kept = set(user_input.get(_KEEP, []))
            self._bands = [
                band for index, band in enumerate(self._bands) if str(index) in kept
            ]
            if user_input[_ACTION] == _ADD_BAND:
                return await self.async_step_band()
            if not self._plan().gaps():
                return self._save()
            errors["base"] = "plan_incomplete"
        labels = await _common_strings(self.hass)
        return self.async_show_form(
            step_id="bands",
            data_schema=self._review_schema(labels),
            errors=errors,
            description_placeholders={"uncovered": _uncovered(self._plan(), labels)},
        )

    def _band_error(self, answers: dict[str, Any]) -> str | None:
        """Why a band cannot join the plan, or ``None`` if it can."""
        try:
            band = band_from(answers)
        except ValueError:
            return "band_hours"
        entered = [band_from(existing) for existing in self._bands]
        if any(_overlap(band, other) for other in entered):
            return "band_overlaps"
        return None

    def _plan(self) -> Plan:
        return tariff_plan_from(self._details.get(CONF_NAME, ""), self._data()).plan

    def _data(self) -> dict[str, Any]:
        return {**self._details, CONF_BANDS: self._bands}

    def _review_schema(self, labels: dict[str, str]) -> vol.Schema:
        options = [
            selector.SelectOptionDict(
                value=str(index), label=_band_label(band_from(band), labels)
            )
            for index, band in enumerate(self._bands)
        ]
        return vol.Schema(
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
                vol.Required(_ACTION, default=_ADD_BAND): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[_ADD_BAND, _SAVE],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="plan_action",
                    )
                ),
            }
        )

    def _save(self) -> SubentryFlowResult:
        """Save the plan, making it the only current one if it is current."""
        data = self._data()
        entry = self._get_entry()
        reconfiguring = self.source == "reconfigure"
        own = self._get_reconfigure_subentry().subentry_id if reconfiguring else None
        if data.get(CONF_PLAN_CURRENT):
            for subentry_id, subentry in entry.subentries.items():
                if (
                    subentry.subentry_type == SUBENTRY_TYPE_PLAN
                    and subentry_id != own
                    and subentry.data.get(CONF_PLAN_CURRENT)
                ):
                    self.hass.config_entries.async_update_subentry(
                        entry,
                        subentry,
                        data={**subentry.data, CONF_PLAN_CURRENT: False},
                    )
        if reconfiguring:
            return self.async_update_and_abort(
                entry,
                self._get_reconfigure_subentry(),
                title=data[CONF_NAME],
                data=data,
            )
        return self.async_create_entry(title=data[CONF_NAME], data=data)


def _overlap(band: Band, other: Band) -> bool:
    """Whether two bands price some hour of some kind of day both at once."""
    return any(
        band.applies_to(kind) and other.applies_to(kind) for kind in DayKind
    ) and bool(band.hours & other.hours)


def _uncovered(plan: Plan, labels: dict[str, str]) -> str:
    """Each kind of day's hours no band covers yet, as a line each."""
    lines = [
        f"{_label(_DAY_LABELS[gap.kind], labels)}: {_hour_ranges(gap.hours)}"
        for gap in plan.gaps()
        if gap.covered_by == 0
    ]
    if not lines:
        return labels.get("plan_all_covered", "Every hour is covered.")
    template = labels.get("plan_uncovered", "Not priced yet:\n{hours}")
    return template.format(hours="\n".join(lines))


def _band_label(band: Band, labels: dict[str, str]) -> str:
    """A band as the review lists it: its days, hours and prices."""
    label = (
        f"{_label(_DAYS_LABELS[band.days], labels)} "
        f"{band.start:02d}:00-{band.end:02d}:00: {band.import_price}"
    )
    if band.export_price is None:
        return label
    template = labels.get("plan_band_export", "export {price}")
    return f"{label}, {template.format(price=band.export_price)}"


def _hour_ranges(hours: tuple[int, ...]) -> str:
    """Consecutive hours as ranges: 0-7 and 22-23 read 00:00-08:00, 22:00-24:00."""
    ranges: list[tuple[int, int]] = []
    for hour in hours:
        if ranges and ranges[-1][1] == hour:
            ranges[-1] = (ranges[-1][0], hour + 1)
        else:
            ranges.append((hour, hour + 1))
    return ", ".join(f"{start:02d}:00-{end:02d}:00" for start, end in ranges)


def _label(key_and_default: tuple[str, str], labels: dict[str, str]) -> str:
    key, default = key_and_default
    return labels.get(key, default)


async def _common_strings(hass: HomeAssistant) -> dict[str, str]:
    """The integration's ``common`` strings, translated, keyed by name.

    A review is built from the bands entered, so its wording cannot live in the
    step's own strings and is looked up here instead, as discovery's rows are.
    """
    strings = await translation.async_get_translations(
        hass, hass.config.language, "common", {DOMAIN}
    )
    prefix = f"component.{DOMAIN}.common."
    return {
        key.removeprefix(prefix): value
        for key, value in strings.items()
        if key.startswith(prefix)
    }
