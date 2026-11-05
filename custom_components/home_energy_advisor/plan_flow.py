"""Entering a tariff plan: its details and named prices, then its bands (ADR-0036).

Offers name their prices - peak and off-peak, punta, llano and valle - and a
household thinks in those names, so a plan's prices are entered first, as a list
on the details screen, each with its name, its import price and optionally an
export price of its own (HEA-262). Its bands then pick a price by name.

Home Assistant's forms have no timetable editor, so the bands are entered one at
a time. After each band a review lists the bands so far, which can be unticked to
remove them, and says which hours of which days are still uncovered. A band
that overlaps one already entered is refused on its own form,
and the plan is saved only once every hour is covered: an hour priced twice or
not at all would be a guess.

A band's days are weekdays, weekends and holidays, or every day, as most offers
name them, or days ticked one by one on a step of their own (ADR-0038).

An export price, the plan's or a price's own, can pay only on the first kWh
exported in a day (ADR-0039). The plan's allowance is entered with the price
paid beyond it, since export beyond it would otherwise go unpaid unasked.

Most offers share their bands with a plan already entered and differ only in
price, so a new plan can start from a copy of another (HEA-259): the details
screen filled in from it, then straight to the review of its bands. Editing a
plan is that same screen, so a renewal at new prices is a change to the list.
A price renamed where it stands in the list keeps its bands; a price removed
takes its bands with it, and the review says which hours that leaves.

A plan can instead import, and separately export, at a market price entity
(ADR-0037). A plan importing at one has no prices or bands, so its details are
all there is to enter. A wholesale price is adjusted to what the supplier
charges, with an amount added per kWh and a multiplier for VAT (HEA-273).

Exactly one plan is the household's current plan, which every other is compared
with, so saving one as current makes the previous one not.
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
    CONF_BAND_EXPORT_ALLOWANCE,
    CONF_BAND_EXPORT_PRICE,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_ALLOWANCE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_EXPORT_PRICE_ADD,
    CONF_PLAN_EXPORT_PRICE_AFTER,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_EXPORT_PRICE_MULTIPLY,
    CONF_PLAN_HOLIDAYS,
    CONF_PLAN_IMPORT_PRICE_ADD,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PLAN_IMPORT_PRICE_MULTIPLY,
    CONF_PRICES,
    DEFAULT_CURRENCY,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)
from .engine.plan_pricing import Band, Day, Days, Plan
from .schemas import vol
from .tariff_plans import (
    band_from,
    named_prices,
    plans_of,
    prices_by_name,
    tariff_plan_from,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.core import HomeAssistant

_KEEP = "keep"
_ACTION = "action"
_CHOOSE_DAYS = "chosen"
_ADD_BAND = "add_band"
_EDIT_PRICES = "prices"
_SAVE = "save"
_START_FROM = "start_from"
_NOTHING = "none"
_DETAIL_KEYS = (
    CONF_NAME,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_ALLOWANCE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_EXPORT_PRICE_ADD,
    CONF_PLAN_EXPORT_PRICE_AFTER,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_EXPORT_PRICE_MULTIPLY,
    CONF_PLAN_HOLIDAYS,
    CONF_PLAN_IMPORT_PRICE_ADD,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PLAN_IMPORT_PRICE_MULTIPLY,
)
# What a plan does to each market price it takes, with the entity it adjusts.
_ADJUSTMENTS = (
    (
        CONF_PLAN_IMPORT_PRICE_ENTITY,
        CONF_PLAN_IMPORT_PRICE_ADD,
        CONF_PLAN_IMPORT_PRICE_MULTIPLY,
    ),
    (
        CONF_PLAN_EXPORT_PRICE_ENTITY,
        CONF_PLAN_EXPORT_PRICE_ADD,
        CONF_PLAN_EXPORT_PRICE_MULTIPLY,
    ),
)
_MULTIPLIER = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, step="any", mode=selector.NumberSelectorMode.BOX
    )
)
# A market price, as the accounting takes one (ADR-0037).
_MARKET_PRICE = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)

# A price per kWh, or per day, as it is printed on an offer. Any sign: a
# wholesale-linked plan can charge less than nothing for an hour (HEA-165).
_PRICE = selector.NumberSelector(
    selector.NumberSelectorConfig(step="any", mode=selector.NumberSelectorMode.BOX)
)
# The kWh a day an export price pays on (ADR-0039).
_ALLOWANCE = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0,
        step="any",
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="kWh",
    )
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

_DAY_LABELS = {
    Day.MONDAY: ("plan_monday", "Monday"),
    Day.TUESDAY: ("plan_tuesday", "Tuesday"),
    Day.WEDNESDAY: ("plan_wednesday", "Wednesday"),
    Day.THURSDAY: ("plan_thursday", "Thursday"),
    Day.FRIDAY: ("plan_friday", "Friday"),
    Day.SATURDAY: ("plan_saturday", "Saturday"),
    Day.SUNDAY: ("plan_sunday", "Sunday"),
    Day.HOLIDAY: ("plan_holidays", "Public holidays"),
}
_DAYS_LABELS = {
    Days.WEEKDAYS: ("plan_weekdays", "Weekdays"),
    Days.REST_DAYS: ("plan_rest_days", "Weekends and holidays"),
    Days.EVERY_DAY: ("plan_every_day", "Every day"),
}
# Days said in a word rather than one by one, wherever a band or gap has them.
_NAMED_DAYS = {
    **{days.days: label for days, label in _DAYS_LABELS.items()},
    frozenset({Day.SATURDAY, Day.SUNDAY}): ("plan_weekends", "Weekends"),
    Days.EVERY_DAY.days - {Day.HOLIDAY}: _DAYS_LABELS[Days.EVERY_DAY],
}


class PlanSubentryFlowHandler(ConfigSubentryFlow):
    """Add or edit one tariff plan: its prices, then its bands one at a time."""

    def __init__(self) -> None:
        """Start with no details, no prices and no bands."""
        self._details: dict[str, Any] = {}
        self._prices: list[dict[str, Any]] = []
        self._bands: list[dict[str, Any]] = []
        # The band whose days are being ticked, and the days last ticked for it.
        self._band: dict[str, Any] = {}
        self._chosen: list[str] = []

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
            if source in plans:
                await self._take(self._get_entry().subentries[source].data)
                # A copy is most often an offer being weighed up, and marking it
                # current would unmark the plan the household is on.
                self._details[CONF_PLAN_CURRENT] = False
            return await self.async_step_details()
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
                    vol.Required(_START_FROM, default=_NOTHING): (
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=options, mode=selector.SelectSelectorMode.LIST
                            )
                        )
                    )
                }
            ),
        )

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """The plan's own details and its named prices."""
        return await self._details_step("details", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a plan's details and prices, then review its bands."""
        if user_input is None and not self._details:
            await self._take(self._get_reconfigure_subentry().data)
        return await self._details_step("reconfigure", user_input)

    async def _details_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            prices = [dict(price) for price in user_input.get(CONF_PRICES) or ()]
            at_market = bool(user_input.get(CONF_PLAN_IMPORT_PRICE_ENTITY))
            errors = _details_errors(user_input, prices, at_market=at_market)
            if not errors:
                self._details = {
                    key: user_input[key] for key in _DETAIL_KEYS if key in user_input
                }
                if at_market:
                    # Every interval is charged at the market, so the plan has
                    # no prices or bands of its own and nothing more to ask.
                    self._prices, self._bands = [], []
                    return self._save()
                self._bands = _renamed(self._prices, prices, self._bands)
                self._prices = prices
                if self._bands:
                    return await self.async_step_bands()
                return await self.async_step_band()
        suggested = {**self._details}
        if self._prices:
            suggested[CONF_PRICES] = self._prices
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                self._details_schema(), user_input or suggested
            ),
            errors=errors,
        )

    async def _take(self, data: Mapping[str, Any]) -> None:
        """Start from what a plan's entry holds: its details, prices and bands."""
        labels = await _common_strings(self.hass)
        self._details = {key: data[key] for key in _DETAIL_KEYS if key in data}
        self._prices, self._bands = named_prices(
            data, labels.get("plan_price_name", "Price {number}")
        )

    async def async_step_band(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """One band: which days, which hours, and which of the plan's prices."""
        if user_input is None:
            return await self._band_form({}, {})
        if user_input[CONF_BAND_DAYS] != _CHOOSE_DAYS:
            error = self._band_error(user_input)
        elif (error := _hours_error(user_input)) is None:
            # Its days are ticked next, and only then can it overlap another.
            self._band = user_input
            return await self.async_step_band_days()
        if error is None:
            return await self._add(user_input)
        return await self._band_form(user_input, {"base": error})

    async def async_step_band_days(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """The days a band applies to, ticked one by one."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ticked = set(user_input.get(CONF_BAND_DAYS, ()))
            self._chosen = [day.value for day in Day if day.value in ticked]
            band = {**self._band, CONF_BAND_DAYS: self._chosen}
            if not self._chosen:
                errors["base"] = "band_no_days"
            elif (error := self._band_error(band)) is None:
                return await self._add(band)
            else:
                # Back to the band's own form, where its hours can change too.
                return await self._band_form(self._band, {"base": error})
        return self.async_show_form(
            step_id="band_days",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_BAND_DAYS): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[day.value for day in Day],
                                multiple=True,
                                mode=selector.SelectSelectorMode.LIST,
                                translation_key="band_day",
                            )
                        )
                    }
                ),
                {CONF_BAND_DAYS: self._chosen} if self._chosen else {},
            ),
            errors=errors,
        )

    async def _band_form(
        self, suggested: dict[str, Any], errors: dict[str, str]
    ) -> SubentryFlowResult:
        labels = await _common_strings(self.hass)
        return self.async_show_form(
            step_id="band",
            data_schema=self.add_suggested_values_to_schema(
                self._band_schema(labels), suggested
            ),
            errors=errors,
        )

    async def _add(self, band: dict[str, Any]) -> SubentryFlowResult:
        """Add a band to the plan, and review the bands so far."""
        self._bands.append(band)
        self._chosen = []
        return await self.async_step_bands()

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
            if user_input[_ACTION] == _EDIT_PRICES:
                if self.source == "reconfigure":
                    return await self.async_step_reconfigure()
                return await self.async_step_details()
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
        prices = prices_by_name(self._prices)
        try:
            band = band_from(answers, prices)
        except ValueError:
            return "band_hours"
        entered = [band_from(existing, prices) for existing in self._bands]
        if any(_overlap(band, other) for other in entered):
            return "band_overlaps"
        return None

    def _plan(self) -> Plan:
        return tariff_plan_from(self._details.get(CONF_NAME, ""), self._data()).plan

    def _data(self) -> dict[str, Any]:
        return {**self._details, CONF_PRICES: self._prices, CONF_BANDS: self._bands}

    def _unit(self) -> str:
        """What a price is per, in the household's currency."""
        currency = self._get_entry().data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
        return f"{currency}/kWh"

    def _details_schema(self) -> vol.Schema:
        per_kwh = selector.NumberSelector(
            selector.NumberSelectorConfig(
                step="any",
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=self._unit(),
            )
        )
        return vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_PLAN_CURRENT, default=False): (
                    selector.BooleanSelector()
                ),
                vol.Required(CONF_PLAN_DAILY_CHARGE, default=0): (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, step="any", mode=selector.NumberSelectorMode.BOX
                        )
                    )
                ),
                vol.Required(CONF_PLAN_EXPORT_PRICE, default=0): per_kwh,
                vol.Optional(CONF_PLAN_EXPORT_ALLOWANCE): _ALLOWANCE,
                vol.Optional(CONF_PLAN_EXPORT_PRICE_AFTER): per_kwh,
                vol.Optional(CONF_PLAN_EXPORT_PRICE_ENTITY): _MARKET_PRICE,
                vol.Optional(CONF_PLAN_EXPORT_PRICE_ADD): per_kwh,
                vol.Optional(CONF_PLAN_EXPORT_PRICE_MULTIPLY): _MULTIPLIER,
                vol.Optional(CONF_PLAN_HOLIDAYS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="calendar")
                ),
                vol.Optional(CONF_PLAN_IMPORT_PRICE_ENTITY): _MARKET_PRICE,
                vol.Optional(CONF_PLAN_IMPORT_PRICE_ADD): per_kwh,
                vol.Optional(CONF_PLAN_IMPORT_PRICE_MULTIPLY): _MULTIPLIER,
                vol.Optional(CONF_PRICES): selector.ObjectSelector(
                    selector.ObjectSelectorConfig(
                        fields={
                            CONF_NAME: selector.ObjectSelectorField(
                                selector=selector.TextSelector().serialize()[
                                    "selector"
                                ],
                                required=True,
                            ),
                            CONF_BAND_IMPORT_PRICE: selector.ObjectSelectorField(
                                selector=per_kwh.serialize()["selector"],
                                required=True,
                            ),
                            CONF_BAND_EXPORT_PRICE: selector.ObjectSelectorField(
                                selector=per_kwh.serialize()["selector"],
                            ),
                            CONF_BAND_EXPORT_ALLOWANCE: selector.ObjectSelectorField(
                                selector=_ALLOWANCE.serialize()["selector"],
                            ),
                        },
                        multiple=True,
                        label_field=CONF_NAME,
                        translation_key="plan_price",
                    )
                ),
            }
        )

    def _band_schema(self, labels: dict[str, str]) -> vol.Schema:
        options = [
            selector.SelectOptionDict(
                value=price[CONF_NAME], label=self._price_label(price, labels)
            )
            for price in self._prices
        ]
        return vol.Schema(
            {
                vol.Required(CONF_BAND_DAYS, default=Days.EVERY_DAY.value): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[*(days.value for days in Days), _CHOOSE_DAYS],
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=CONF_BAND_DAYS,
                        )
                    )
                ),
                vol.Required(CONF_BAND_START): _HOUR_FROM,
                vol.Required(CONF_BAND_END): _HOUR_TO,
                vol.Required(CONF_BAND_PRICE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            }
        )

    def _review_schema(self, labels: dict[str, str]) -> vol.Schema:
        prices = prices_by_name(self._prices)
        options = [
            selector.SelectOptionDict(
                value=str(index),
                label=_band_label(
                    band_from(band, prices),
                    self._price_label(prices[band[CONF_BAND_PRICE]], labels),
                    labels,
                ),
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
                        options=[_ADD_BAND, _EDIT_PRICES, _SAVE],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="plan_action",
                    )
                ),
            }
        )

    def _price_label(self, price: Mapping[str, Any], labels: dict[str, str]) -> str:
        """A price as a band offers it: "Peak (0.31 EUR/kWh, export 0.12 EUR/kWh)"."""
        unit = self._unit()
        figures = f"{_figure(price[CONF_BAND_IMPORT_PRICE])} {unit}"
        export = price.get(CONF_BAND_EXPORT_PRICE)
        allowance = price.get(CONF_BAND_EXPORT_ALLOWANCE)
        if export is not None and allowance is not None:
            template = labels.get(
                "plan_band_export_allowance",
                "export {price} on the first {allowance} kWh a day",
            )
            figures += ", " + template.format(
                price=f"{_figure(export)} {unit}", allowance=_figure(allowance)
            )
        elif export is not None:
            template = labels.get("plan_band_export", "export {price}")
            figures += f", {template.format(price=f'{_figure(export)} {unit}')}"
        return f"{price[CONF_NAME]} ({figures})"

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


def _details_errors(
    answers: Mapping[str, Any], prices: list[dict[str, Any]], *, at_market: bool
) -> dict[str, str]:
    """Why a plan's details cannot be saved, by field; empty if they can."""
    errors: dict[str, str] = {}
    if (answers.get(CONF_PLAN_EXPORT_ALLOWANCE) is None) != (
        answers.get(CONF_PLAN_EXPORT_PRICE_AFTER) is None
    ):
        # Export beyond an allowance would otherwise go unpaid unasked.
        errors[CONF_PLAN_EXPORT_ALLOWANCE] = "export_allowance"
    for entity, add, multiply in _ADJUSTMENTS:
        if not answers.get(entity) and (
            answers.get(add) is not None or answers.get(multiply) is not None
        ):
            # A plan's own prices are typed as charged, so there is nothing to
            # adjust, and an adjustment kept silently would wait for an entity.
            errors[add] = "market_adjustment"
    if not at_market and (error := _prices_error(prices)) is not None:
        errors[CONF_PRICES] = error
    return errors


def _prices_error(prices: list[dict[str, Any]]) -> str | None:
    """Why a list of prices cannot be a plan's, or ``None`` if it can."""
    if not prices:
        return "no_prices"
    names = [price[CONF_NAME] for price in prices]
    if len(set(names)) != len(names):
        return "price_names"
    if any(
        price.get(CONF_BAND_EXPORT_ALLOWANCE) is not None
        and price.get(CONF_BAND_EXPORT_PRICE) is None
        for price in prices
    ):
        # An allowance limits the price's own export price, so needs one.
        return "price_allowance"
    return None


def _renamed(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    bands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The bands, each naming its price as the edited list names it.

    A name still in the list is kept. A name gone from it was renamed if the
    price where it stood now has a name the list did not have before, and the
    band follows it; otherwise its price was removed, and so is the band.
    """
    old: list[str] = [price[CONF_NAME] for price in before]
    new: list[str] = [price[CONF_NAME] for price in after]

    def renamed(name: str) -> str | None:
        if name in new:
            return name
        index = old.index(name) if name in old else len(new)
        if index < len(new) and new[index] not in old:
            return new[index]
        return None

    kept = []
    for band in bands:
        name = renamed(band[CONF_BAND_PRICE])
        if name is not None:
            kept.append({**band, CONF_BAND_PRICE: name})
    return kept


def _hours_error(answers: Mapping[str, Any]) -> str | None:
    """Why a band's hours cannot be a band's, or ``None`` if they can."""
    try:
        Band(
            Days.EVERY_DAY,
            int(answers[CONF_BAND_START]),
            int(answers[CONF_BAND_END]),
            Decimal(0),
        )
    except ValueError:
        return "band_hours"
    return None


def _figure(value: object) -> str:
    """A typed price as the figure typed: 0.31, not its nearest binary float."""
    return str(Decimal(str(value)))


def _overlap(band: Band, other: Band) -> bool:
    """Whether two bands price some hour of some day both at once."""
    return bool(band.covers & other.covers) and bool(band.hours & other.hours)


def _uncovered(plan: Plan, labels: dict[str, str]) -> str:
    """The hours no band covers yet, a line for each set of days missing them."""
    lines = [
        f"{_days_label(gap.days, labels)}: {_hour_ranges(gap.hours)}"
        for gap in plan.gaps()
        if gap.covered_by == 0
    ]
    if not lines:
        return labels.get("plan_all_covered", "Every hour is covered.")
    template = labels.get("plan_uncovered", "Not priced yet:\n{hours}")
    return template.format(hours="\n".join(lines))


def _band_label(band: Band, price: str, labels: dict[str, str]) -> str:
    """A band as the review lists it: its days, hours and price."""
    days = (
        _label(_DAYS_LABELS[band.days], labels)
        if isinstance(band.days, Days)
        else _days_label(band.days, labels)
    )
    return f"{days} {band.start:02d}:00-{band.end:02d}:00: {price}"


def _days_label(days: Iterable[Day], labels: dict[str, str]) -> str:
    """Days in a word where they have one, "Weekends", else one by one."""
    chosen = frozenset(days)
    if chosen in _NAMED_DAYS:
        return _label(_NAMED_DAYS[chosen], labels)
    return ", ".join(_label(_DAY_LABELS[day], labels) for day in Day if day in chosen)


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
