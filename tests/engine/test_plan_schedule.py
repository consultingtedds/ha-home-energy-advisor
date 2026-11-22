"""What a typed plan charges at a moment, by the clock alone.

Its import price is its band's at that local moment, on its days and holidays;
its export price is the band's own where it has one, otherwise the plan's. A plan
at a market price has none of its own here: the market's is its price. Only a
plan priced by the clock alone can be read this way: one with an allowance
charges by how much has been used.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.home_energy_advisor.engine.plan_pricing import (
    AllowancePeriod,
    Band,
    Day,
    Days,
    Plan,
)
from custom_components.home_energy_advisor.engine.plan_schedule import (
    export_price_at,
    follows_the_clock,
    import_price_at,
)

MADRID = ZoneInfo("Europe/Madrid")

# Dear from 08:00 to 22:00 on weekdays, paying more for export then; cheap
# overnight and all weekend; a price of its own on public holidays.
TIME_OF_USE = Plan(
    name="Three periods",
    bands=(
        Band(Days.WEEKDAYS, 8, 22, Decimal("0.245"), Decimal("0.08")),
        Band(Days.WEEKDAYS, 22, 8, Decimal("0.098")),
        Band(frozenset({Day.SATURDAY, Day.SUNDAY}), 0, 24, Decimal("0.098")),
        Band(frozenset({Day.HOLIDAY}), 0, 24, Decimal("0.05")),
    ),
    daily_charge=Decimal("1.47"),
    export_price=Decimal("0.04"),
)
MARKET = Plan(
    name="Market tracker",
    bands=(),
    daily_charge=Decimal("0.25"),
    export_price=Decimal("0.04"),
    import_per_interval=True,
)

# Thursday 19 November 2026.
THURSDAY = date(2026, 11, 19)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=MADRID)


# What it charges


def test_the_import_price_is_the_band_s_at_that_moment() -> None:
    # Given / When / Then - a weekday's peak, and the same day after 22:00
    assert import_price_at(TIME_OF_USE, _at(THURSDAY, 10), ()) == Decimal("0.245")
    assert import_price_at(TIME_OF_USE, _at(THURSDAY, 21, 59), ()) == Decimal("0.245")
    assert import_price_at(TIME_OF_USE, _at(THURSDAY, 22), ()) == Decimal("0.098")
    # Saturday is cheap all day
    assert import_price_at(TIME_OF_USE, _at(date(2026, 11, 21), 10), ()) == Decimal(
        "0.098"
    )


def test_a_holiday_is_priced_as_one_where_the_plan_prices_holidays() -> None:
    # Given - a Thursday that is a public holiday
    holidays = {THURSDAY}

    # When / Then - the holiday's own price, not the weekday's peak
    assert import_price_at(TIME_OF_USE, _at(THURSDAY, 10), holidays) == Decimal("0.05")


def test_the_export_price_is_the_band_s_own_or_else_the_plan_s() -> None:
    # Given / When / Then - the peak pays its own; overnight pays the plan's
    assert export_price_at(TIME_OF_USE, _at(THURSDAY, 10), ()) == Decimal("0.08")
    assert export_price_at(TIME_OF_USE, _at(THURSDAY, 23), ()) == Decimal("0.04")


def test_a_market_plan_has_no_import_price_of_its_own() -> None:
    # Given / When / Then - the market's is its price; its export is still the
    # plan's
    assert import_price_at(MARKET, _at(THURSDAY, 10), ()) is None
    assert export_price_at(MARKET, _at(THURSDAY, 10), ()) == Decimal("0.04")


def test_the_hour_is_the_local_one_across_a_change_of_clocks() -> None:
    # Given - the Monday after Madrid's clocks went back on 25 October 2026
    monday = date(2026, 10, 26)

    # When / Then - the band edge falls at 08:00 local time
    assert import_price_at(TIME_OF_USE, _at(monday, 7, 59), ()) == Decimal("0.098")
    assert import_price_at(TIME_OF_USE, _at(monday, 8), ()) == Decimal("0.245")


# Which plans can be read this way


def test_a_plan_priced_by_the_clock_alone_can_be_read_at_a_moment() -> None:
    # Given / When / Then
    assert follows_the_clock(TIME_OF_USE) is True
    assert follows_the_clock(MARKET) is True


def test_a_plan_with_an_allowance_cannot_be_read_at_a_moment() -> None:
    # Given - free hours on the first 24 kWh a day, and a plan paying its export
    # price on the first 8 kWh exported a day
    free_hours = Plan(
        name="Free hours",
        bands=(
            Band(
                Days.EVERY_DAY,
                0,
                24,
                Decimal(0),
                import_allowance=Decimal(24),
                import_allowance_period=AllowancePeriod.DAY,
                import_price_after=Decimal("0.2"),
            ),
        ),
    )
    export_allowance = Plan(
        name="11c Solar",
        bands=(Band(Days.EVERY_DAY, 0, 24, Decimal("0.3")),),
        export_price=Decimal("0.11"),
        export_allowance=Decimal(8),
        export_price_after=Decimal("0.04"),
    )

    # When / Then
    assert follows_the_clock(free_hours) is False
    assert follows_the_clock(export_allowance) is False
