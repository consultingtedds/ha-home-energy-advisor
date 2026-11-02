"""Reading the household's tariff plans out of a config entry (ADR-0036).

A plan entry holds what the household typed: its details and a list of bands.
This turns them into the engine's `Plan`, with the two things only the
integration knows about - whether it is the plan the household is on, and which
calendar its holidays come from.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_NAME

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
    SUBENTRY_TYPE_PLAN,
)
from .engine.plan_pricing import Band, Days, Plan

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry


@dataclass(frozen=True)
class TariffPlan:
    """A plan as the household entered it."""

    plan: Plan
    current: bool
    holidays: str | None


def plans_of(entry: ConfigEntry) -> dict[str, TariffPlan]:
    """Every plan the household has entered, keyed by its subentry id."""
    return {
        subentry_id: tariff_plan_from(subentry.title, subentry.data)
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_PLAN
    }


def tariff_plan_from(name: str, data: Mapping[str, Any]) -> TariffPlan:
    """A plan from what its entry holds."""
    return TariffPlan(
        plan=Plan(
            name=data.get(CONF_NAME) or name,
            bands=tuple(band_from(band) for band in data.get(CONF_BANDS, ())),
            daily_charge=_decimal(data.get(CONF_PLAN_DAILY_CHARGE)),
            export_price=_decimal(data.get(CONF_PLAN_EXPORT_PRICE)),
        ),
        current=bool(data.get(CONF_PLAN_CURRENT)),
        holidays=data.get(CONF_PLAN_HOLIDAYS) or None,
    )


def band_from(data: Mapping[str, Any]) -> Band:
    """A band from the answers to one band form.

    Raises ``ValueError`` for hours that are not whole hours of one day.
    """
    export = data.get(CONF_BAND_EXPORT_PRICE)
    return Band(
        days=Days(data[CONF_BAND_DAYS]),
        start=int(data[CONF_BAND_START]),
        end=int(data[CONF_BAND_END]),
        import_price=_decimal(data[CONF_BAND_IMPORT_PRICE]),
        export_price=None if export is None else _decimal(export),
    )


def _decimal(value: object) -> Decimal:
    """A typed price as the figure typed: 0.31, not its nearest binary float."""
    return Decimal(0) if value is None else Decimal(str(value))
