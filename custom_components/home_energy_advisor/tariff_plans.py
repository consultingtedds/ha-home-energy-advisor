"""Reading the household's tariff plans out of a config entry (ADR-0036).

A plan entry holds what the household typed: its details, its prices, each named
as the offer names it, and a list of bands naming the price each charges
(HEA-262). This turns them into the engine's `Plan`, with the two things only the
integration knows about - whether it is the plan the household is on, and which
calendar its holidays come from.

A band entered before prices were named carries its figures itself, and is read
as it is. A band's days are either the name of the days an offer names, such as
weekdays, or the list of days it applies to (ADR-0038). A price's export price,
and the plan's, can pay only on the first kWh exported in a day (ADR-0039). A
plan at a market price can adjust it, from wholesale to what its supplier
charges (HEA-273). What its export earns a month can be capped at what the
month's energy cost (HEA-258); a plan saying nothing about it pays in full. A
price's import price can charge only up to an allowance, its hours charged
another of the plan's prices beyond it (HEA-264).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_NAME

from .const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_EXPORT_ALLOWANCE,
    CONF_BAND_EXPORT_PRICE,
    CONF_BAND_IMPORT_ALLOWANCE,
    CONF_BAND_IMPORT_ALLOWANCE_PERIOD,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_IMPORT_PRICE_AFTER,
    CONF_BAND_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_PLAN_CURRENT,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_ALLOWANCE,
    CONF_PLAN_EXPORT_CAP,
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
    SUBENTRY_TYPE_PLAN,
)
from .engine.plan_pricing import (
    AllowancePeriod,
    Band,
    Day,
    Days,
    ExportCap,
    MarketAdjustment,
    Plan,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.config_entries import ConfigEntry


@dataclass(frozen=True)
class TariffPlan:
    """A plan as the household entered it.

    `import_entity` and `export_entity` are the market prices it imports or
    exports at instead of its schedule, where it has them (ADR-0037).
    """

    plan: Plan
    current: bool
    holidays: str | None
    import_entity: str | None = None
    export_entity: str | None = None


def plans_of(entry: ConfigEntry) -> dict[str, TariffPlan]:
    """Every plan the household has entered, keyed by its subentry id."""
    return {
        subentry_id: tariff_plan_from(subentry.title, subentry.data)
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_PLAN
    }


def tariff_plan_from(name: str, data: Mapping[str, Any]) -> TariffPlan:
    """A plan from what its entry holds.

    A plan importing at a market price has no bands: whatever bands its entry
    still holds are not its prices.
    """
    prices = prices_by_name(data.get(CONF_PRICES, ()))
    import_entity = data.get(CONF_PLAN_IMPORT_PRICE_ENTITY) or None
    export_entity = data.get(CONF_PLAN_EXPORT_PRICE_ENTITY) or None
    bands = (
        ()
        if import_entity
        else tuple(band_from(band, prices) for band in data.get(CONF_BANDS, ()))
    )
    return TariffPlan(
        plan=Plan(
            name=data.get(CONF_NAME) or name,
            bands=bands,
            daily_charge=_decimal(data.get(CONF_PLAN_DAILY_CHARGE)),
            export_price=_decimal(data.get(CONF_PLAN_EXPORT_PRICE)),
            import_per_interval=import_entity is not None,
            export_per_interval=export_entity is not None,
            export_allowance=_optional_decimal(data.get(CONF_PLAN_EXPORT_ALLOWANCE)),
            export_price_after=_decimal(data.get(CONF_PLAN_EXPORT_PRICE_AFTER)),
            import_adjustment=_adjustment(
                data, CONF_PLAN_IMPORT_PRICE_ADD, CONF_PLAN_IMPORT_PRICE_MULTIPLY
            ),
            export_adjustment=_adjustment(
                data, CONF_PLAN_EXPORT_PRICE_ADD, CONF_PLAN_EXPORT_PRICE_MULTIPLY
            ),
            # A plan entered before export could be capped was paid in full.
            export_cap=ExportCap(data.get(CONF_PLAN_EXPORT_CAP, ExportCap.NONE)),
        ),
        current=bool(data.get(CONF_PLAN_CURRENT)),
        holidays=data.get(CONF_PLAN_HOLIDAYS) or None,
        import_entity=import_entity,
        export_entity=export_entity,
    )


def prices_by_name(
    prices: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """A plan's prices, keyed by the name its bands use."""
    return {price[CONF_NAME]: price for price in prices}


def band_from(data: Mapping[str, Any], prices: Mapping[str, Mapping[str, Any]]) -> Band:
    """A band from the answers to one band form, at the price it names.

    Raises ``ValueError`` for no days, or hours that are not whole hours of one
    day, and ``KeyError`` for a price the plan does not have, the one it names
    for beyond its import allowance included (HEA-264).
    """
    named = data.get(CONF_BAND_PRICE)
    figures = data if named is None else prices[named]
    export = figures.get(CONF_BAND_EXPORT_PRICE)
    days = data[CONF_BAND_DAYS]
    after = figures.get(CONF_BAND_IMPORT_PRICE_AFTER)
    return Band(
        days=Days(days)
        if isinstance(days, str)
        else frozenset(Day(day) for day in days),
        start=int(data[CONF_BAND_START]),
        end=int(data[CONF_BAND_END]),
        import_price=_decimal(figures[CONF_BAND_IMPORT_PRICE]),
        export_price=None if export is None else _decimal(export),
        export_allowance=_optional_decimal(figures.get(CONF_BAND_EXPORT_ALLOWANCE)),
        import_allowance=_optional_decimal(figures.get(CONF_BAND_IMPORT_ALLOWANCE)),
        import_allowance_period=AllowancePeriod(
            figures.get(CONF_BAND_IMPORT_ALLOWANCE_PERIOD, AllowancePeriod.DAY)
        ),
        import_price_after=Decimal(0)
        if after is None
        else _decimal(prices[after][CONF_BAND_IMPORT_PRICE]),
        name=named or "",
    )


def named_prices(
    data: Mapping[str, Any], numbered: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A plan's prices and its bands naming them.

    A plan whose bands carry their own figures gets a price for each distinct
    pair of figures, in the order its bands first use them, named from
    `numbered` ("Price {number}") for the household to rename.
    """
    if CONF_PRICES in data:
        return (
            [dict(price) for price in data[CONF_PRICES]],
            [dict(band) for band in data.get(CONF_BANDS, ())],
        )
    prices: list[dict[str, Any]] = []
    bands: list[dict[str, Any]] = []
    for band in data.get(CONF_BANDS, ()):
        figures = {
            key: band[key]
            for key in (CONF_BAND_IMPORT_PRICE, CONF_BAND_EXPORT_PRICE)
            if band.get(key) is not None
        }
        price = next((price for price in prices if _same_figures(price, figures)), None)
        if price is None:
            price = {CONF_NAME: numbered.format(number=len(prices) + 1), **figures}
            prices.append(price)
        bands.append(
            {
                CONF_BAND_DAYS: band[CONF_BAND_DAYS],
                CONF_BAND_START: band[CONF_BAND_START],
                CONF_BAND_END: band[CONF_BAND_END],
                CONF_BAND_PRICE: price[CONF_NAME],
            }
        )
    return prices, bands


def _adjustment(data: Mapping[str, Any], add: str, multiply: str) -> MarketAdjustment:
    """What a plan makes of its market price, nothing where it says nothing."""
    factor = data.get(multiply)
    return MarketAdjustment(
        add=_decimal(data.get(add)),
        multiply=Decimal(1) if factor is None else _decimal(factor),
    )


def _same_figures(price: Mapping[str, Any], figures: Mapping[str, Any]) -> bool:
    return all(
        _optional_decimal(price.get(key)) == _optional_decimal(figures.get(key))
        for key in (CONF_BAND_IMPORT_PRICE, CONF_BAND_EXPORT_PRICE)
    )


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else _decimal(value)


def _decimal(value: object) -> Decimal:
    """A typed price as the figure typed: 0.31, not its nearest binary float."""
    return Decimal(0) if value is None else Decimal(str(value))
