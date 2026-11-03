"""Entering a tariff plan: its details, then its bands one at a time (ADR-0036).

Home Assistant's forms have no timetable editor, so a plan is built a band at a
time. After each band a review lists the bands so far, which can be unticked to
remove them, and says which hours of a weekday and of a rest day are still
uncovered. A band that overlaps one already entered is refused on its own form,
and the plan is saved only once every hour is covered: an hour priced twice or
not at all would be a guess.

Exactly one plan is the household's current plan, which every other is compared
with, so saving one as current makes the previous one not.

Most offers share their bands with a plan already entered and differ only in
price, so a new plan can start from a copy of another (HEA-259). The copy's
details and prices are then one screen, a field per distinct price rather than
per band, before the same review. Editing a plan is that same screen, which is
what a renewal at new prices needs.
"""

from __future__ import annotations

from decimal import Decimal
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
from .engine.plan_pricing import (
    Band,
    DayKind,
    Days,
    Plan,
    PriceGroup,
    export_price_groups,
    import_price_groups,
    repriced,
)
from .schemas import vol
from .tariff_plans import band_as_data, band_from, plans_of, tariff_plan_from

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

_KEEP = "keep"
_ACTION = "action"
_ADD_BAND = "add_band"
_SAVE = "save"
_START_FROM = "start_from"
_NOTHING = "none"
# One field per distinct price, numbered in the order the bands first use them:
# a field's label is fixed in the translations, so where it applies is said in
# the step's description instead.
_IMPORT_FIELD = "price_{}"
_EXPORT_FIELD = "band_export_{}"
_DETAIL_KEYS = (
    CONF_NAME,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_HOLIDAYS,
)

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
        """What to start from: a copy of a plan already entered, or nothing.

        A household with no plan yet has nothing to copy, so is not asked.
        """
        plans = plans_of(self._get_entry())
        if not plans:
            return await self.async_step_details()
        if user_input is not None:
            source = user_input.get(_START_FROM, _NOTHING)
            if source not in plans:
                return await self.async_step_details()
            self._start_from(self._get_entry().subentries[source].data)
            return await self.async_step_prices()
        labels = await _common_strings(self.hass)
        options = [
            selector.SelectOptionDict(
                value=_NOTHING,
                label=labels.get("plan_start_nothing", "Nothing: enter its bands"),
            ),
            *(
                selector.SelectOptionDict(value=plan_id, label=tariff.plan.name)
                for plan_id, tariff in plans.items()
            ),
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        _START_FROM, default=_NOTHING
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options, mode=selector.SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """The plan's own details, before any band."""
        if user_input is not None:
            self._details = user_input
            return await self.async_step_band()
        return self.async_show_form(step_id="details", data_schema=_DETAILS_SCHEMA)

    async def async_step_prices(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """A copy's details and prices on one screen, then the review."""
        if user_input is not None:
            return await self._take_prices(user_input)
        return await self._prices_form("prices")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a plan's details and prices on one screen, then review its bands."""
        if user_input is not None:
            return await self._take_prices(user_input)
        subentry = self._get_reconfigure_subentry()
        self._details = {
            key: subentry.data[key] for key in _DETAIL_KEYS if key in subentry.data
        }
        self._bands = [dict(band) for band in subentry.data.get(CONF_BANDS, ())]
        return await self._prices_form("reconfigure")

    def _start_from(self, source: Mapping[str, Any]) -> None:
        """Take a plan's details and bands as the copy's starting point.

        Not as the household's current plan: a copy is most often an offer being
        weighed up, and marking it current would unmark the one they are on.
        """
        self._details = {key: source[key] for key in _DETAIL_KEYS if key in source}
        self._details[CONF_PLAN_CURRENT] = False
        self._bands = [dict(band) for band in source.get(CONF_BANDS, ())]

    async def _prices_form(self, step_id: str) -> SubentryFlowResult:
        plan = self._plan()
        imports, exports = import_price_groups(plan), export_price_groups(plan)
        fields = dict(_DETAILS_SCHEMA.schema)
        for template, groups in ((_IMPORT_FIELD, imports), (_EXPORT_FIELD, exports)):
            for field, group in _numbered(template, groups):
                fields[vol.Required(field, default=float(group.price))] = _PRICE
        labels = await _common_strings(self.hass)
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(fields), self._details
            ),
            description_placeholders={"prices": _price_lines(imports, exports, labels)},
        )

    async def _take_prices(self, user_input: dict[str, Any]) -> SubentryFlowResult:
        """Re-price the bands from the answers, then review them."""
        plan = self._plan()
        copy = repriced(
            plan,
            imports=_answered(_IMPORT_FIELD, import_price_groups(plan), user_input),
            exports=_answered(_EXPORT_FIELD, export_price_groups(plan), user_input),
        )
        self._details = {
            key: user_input[key] for key in _DETAIL_KEYS if key in user_input
        }
        self._bands = [band_as_data(band) for band in copy.bands]
        return await self.async_step_bands()

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


def _numbered(
    template: str, groups: tuple[PriceGroup, ...]
) -> list[tuple[str, PriceGroup]]:
    """Each price group with the field that asks for it."""
    return [(template.format(n), group) for n, group in enumerate(groups, 1)]


def _answered(
    template: str, groups: tuple[PriceGroup, ...], answers: Mapping[str, Any]
) -> dict[Decimal, Decimal]:
    """Each group's old price, to the new one typed in its field."""
    return {
        group.price: Decimal(str(answers[field]))
        for field, group in _numbered(template, groups)
        if field in answers
    }


def _price_lines(
    imports: tuple[PriceGroup, ...],
    exports: tuple[PriceGroup, ...],
    labels: dict[str, str],
) -> str:
    """Which bands each price field covers, a line each, for the step's description."""
    import_line = labels.get("plan_price_line", "Price {number} ({price}): {where}")
    export_line = labels.get(
        "plan_export_line", "Band export price {number} ({price}): {where}"
    )
    lines = [
        template.format(number=n, price=group.price, where=_where(group, labels))
        for template, groups in ((import_line, imports), (export_line, exports))
        for n, group in enumerate(groups, 1)
    ]
    return "\n".join(lines)


def _where(group: PriceGroup, labels: dict[str, str]) -> str:
    return ", ".join(
        f"{_label(_DAYS_LABELS[band.days], labels)} "
        f"{band.start:02d}:00-{band.end:02d}:00"
        for band in group.bands
    )


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
