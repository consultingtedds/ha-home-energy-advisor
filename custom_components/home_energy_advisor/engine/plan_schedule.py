"""What a typed plan charges at a moment, by the clock alone.

Its import price is its band's on that local day and hour, a public holiday
priced as one where the plan prices holidays. Its export price is the band's own
where it has one, the plan's otherwise. A plan at a market price has no import
price here: the market's is its price.

Only a plan priced by the clock alone can be read this way: one with an allowance
charges by how much has been used, which no single moment says.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import date, datetime
    from decimal import Decimal

    from .plan_pricing import Plan


def import_price_at(
    plan: Plan, moment: datetime, holidays: Collection[date]
) -> Decimal | None:
    """What the plan charges per kWh imported at `moment`, local time.

    None for a plan at a market price: the market's is the price.
    """
    if plan.import_per_interval:
        return None
    day = plan.day_of(moment.date(), holidays)
    return plan.band_at(day, moment.hour).import_price


def export_price_at(
    plan: Plan, moment: datetime, holidays: Collection[date]
) -> Decimal | None:
    """What the plan pays per kWh exported at `moment`, local time.

    None for a plan exporting at a market price.
    """
    if plan.export_per_interval:
        return None
    if not plan.bands:
        return plan.export_price
    band = plan.band_at(plan.day_of(moment.date(), holidays), moment.hour)
    return band.export_price if band.export_price is not None else plan.export_price


def follows_the_clock(plan: Plan) -> bool:
    """Whether the plan's prices depend on the time alone, not on what was used."""
    if plan.export_allowance is not None:
        return False
    return not any(
        band.import_allowance is not None or band.export_allowance is not None
        for band in plan.bands
    )
