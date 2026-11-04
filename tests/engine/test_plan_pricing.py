"""What a tariff plan would have charged for the grid flows actually recorded.

A plan is a typed schedule: time bands with an import price, an optional export
price of their own, and a daily charge (ADR-0036). It is priced against the
household's recorded hourly import and export, so the figure re-prices what
really happened rather than modelling anything. Bands are in local time, as
offers are published. A band applies to any days of the week, and to public
holidays as a day of their own; a plan with no band for holidays prices each as
the day of the week it falls on (HEA-268, ADR-0038).

Every hour of every day falls in exactly one band, and a plan that leaves one
uncovered or covers one twice is refused rather than priced.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_energy_advisor.engine.plan_pricing import (
    Band,
    Day,
    Days,
    IntervalOfEnergy,
    Plan,
    PlanCost,
    PlanGap,
    days_covered,
    price_plan,
)

LOCAL = ZoneInfo("Europe/Madrid")

# A flat plan: one price all day, every day.
FLAT = Plan(
    name="Flat rate",
    bands=(Band(Days.EVERY_DAY, 0, 24, Decimal("0.234")),),
    daily_charge=Decimal("0.45"),
    export_price=Decimal("0.05"),
)

# A three-band time-of-use plan, as such offers are published: dear in the
# morning and evening on weekdays, middling around them, cheap overnight and
# all weekend.
PEAK = Decimal("0.31")
SHOULDER = Decimal("0.18")
OFF_PEAK = Decimal("0.09")
TIME_OF_USE = Plan(
    name="Three bands",
    bands=(
        Band(Days.WEEKDAYS, 0, 8, OFF_PEAK),
        Band(Days.WEEKDAYS, 8, 10, SHOULDER),
        Band(Days.WEEKDAYS, 10, 14, PEAK),
        Band(Days.WEEKDAYS, 14, 18, SHOULDER),
        Band(Days.WEEKDAYS, 18, 22, PEAK),
        Band(Days.WEEKDAYS, 22, 24, SHOULDER),
        Band(Days.REST_DAYS, 0, 24, OFF_PEAK),
    ),
    daily_charge=Decimal("0.30"),
    export_price=Decimal("0.04"),
)

# Wednesday 2026-11-04 to Saturday 2026-11-07.
WEDNESDAY = date(2026, 11, 4)
THURSDAY = date(2026, 11, 5)
FRIDAY = date(2026, 11, 6)
SATURDAY = date(2026, 11, 7)

MONDAY_TO_FRIDAY = (Day.MONDAY, Day.TUESDAY, Day.WEDNESDAY, Day.THURSDAY, Day.FRIDAY)
WEEKEND = (Day.SATURDAY, Day.SUNDAY)


def hour(day: date, at: int, imported: str, exported: str = "0") -> IntervalOfEnergy:
    """One recorded hour of grid flow, starting at `at` o'clock local time."""
    return IntervalOfEnergy(
        start=datetime(day.year, day.month, day.day, at, tzinfo=LOCAL),
        imported_kwh=Decimal(imported),
        exported_kwh=Decimal(exported),
    )


# Pricing


def test_a_flat_plan_charges_its_price_credits_export_and_adds_the_daily_charge() -> (
    None
):
    # Given - two hours of a day: 1.2 kWh in, then 0.5 in and 2.0 out
    hours = [hour(WEDNESDAY, 9, "1.2"), hour(WEDNESDAY, 13, "0.5", "2.0")]

    # When - over one whole day
    cost = price_plan(FLAT, hours, days=Decimal(1), holidays=frozenset())

    # Then
    assert cost == PlanCost(
        energy=Decimal("0.3978"),  # 1.7 kWh at 0.234
        export_credit=Decimal("0.100"),  # 2.0 kWh at 0.05
        daily_charges=Decimal("0.45"),
    )
    assert cost.total == Decimal("0.7478")


def test_each_hour_is_priced_at_the_band_its_local_hour_falls_in() -> None:
    # Given - 1 kWh at 07:00 (off-peak), 09:00 (shoulder), 12:00 (peak) and
    # 23:00 (shoulder) on a weekday
    hours = [hour(WEDNESDAY, at, "1") for at in (7, 9, 12, 23)]

    # When
    cost = price_plan(TIME_OF_USE, hours, days=Decimal(0), holidays=frozenset())

    # Then
    assert cost.energy == OFF_PEAK + SHOULDER + PEAK + SHOULDER


def test_a_weekend_hour_is_priced_at_the_rest_day_band() -> None:
    # Given - the weekday peak hour, on a Saturday
    hours = [hour(SATURDAY, 12, "1")]

    # When
    cost = price_plan(TIME_OF_USE, hours, days=Decimal(0), holidays=frozenset())

    # Then
    assert cost.energy == OFF_PEAK


def test_a_holiday_is_priced_as_a_rest_day() -> None:
    # Given - the weekday peak hour, on a Wednesday that is a public holiday
    hours = [hour(WEDNESDAY, 12, "1")]

    # When
    cost = price_plan(
        TIME_OF_USE, hours, days=Decimal(0), holidays=frozenset({WEDNESDAY})
    )

    # Then
    assert cost.energy == OFF_PEAK


def test_a_band_can_apply_to_days_of_its_own_choosing() -> None:
    # Given - a weekend that starts at 22:00 on Friday: peak until then, Monday
    # to Thursday evenings included, and off-peak from then until Monday
    friday_night = Plan(
        name="Friday night weekend",
        bands=(
            Band(frozenset(MONDAY_TO_FRIDAY), 0, 22, PEAK),
            Band(frozenset(MONDAY_TO_FRIDAY[:4]), 22, 24, PEAK),
            Band(frozenset({Day.FRIDAY}), 22, 24, OFF_PEAK),
            Band(frozenset(WEEKEND), 0, 24, OFF_PEAK),
        ),
    )
    hours = [
        hour(THURSDAY, 23, "1"),
        hour(FRIDAY, 21, "1"),
        hour(FRIDAY, 23, "1"),
        hour(SATURDAY, 12, "1"),
    ]

    # When
    cost = price_plan(friday_night, hours, days=Decimal(0), holidays=frozenset())

    # Then - Friday is peak until 22:00 and off-peak after, Thursday is not
    assert friday_night.gaps() == ()
    assert cost.energy == PEAK + PEAK + OFF_PEAK + OFF_PEAK


def test_a_holiday_band_gives_holidays_prices_of_their_own() -> None:
    # Given - weekdays at peak, weekends at shoulder, and holidays off-peak
    three_kinds = Plan(
        name="Three kinds of day",
        bands=(
            Band(Days.WEEKDAYS, 0, 24, PEAK),
            Band(frozenset(WEEKEND), 0, 24, SHOULDER),
            Band(frozenset({Day.HOLIDAY}), 0, 24, OFF_PEAK),
        ),
    )
    hours = [hour(WEDNESDAY, 12, "1"), hour(SATURDAY, 12, "1")]

    # When - the Wednesday is a public holiday
    cost = price_plan(
        three_kinds, hours, days=Decimal(0), holidays=frozenset({WEDNESDAY})
    )

    # Then - neither a weekday's price nor a weekend's
    assert three_kinds.gaps() == ()
    assert cost.energy == OFF_PEAK + SHOULDER


def test_without_a_holiday_band_a_holiday_is_priced_as_its_day_of_the_week() -> None:
    # Given - bands chosen day by day, none of them for holidays
    by_day = Plan(
        name="By day",
        bands=(
            Band(frozenset(MONDAY_TO_FRIDAY), 0, 24, PEAK),
            Band(frozenset(WEEKEND), 0, 24, OFF_PEAK),
        ),
    )

    # When - the Wednesday is a public holiday
    cost = price_plan(
        by_day,
        [hour(WEDNESDAY, 12, "1")],
        days=Decimal(0),
        holidays=frozenset({WEDNESDAY}),
    )

    # Then - priced as the Wednesday it is, and nothing is missing
    assert by_day.gaps() == ()
    assert cost.energy == PEAK


def test_a_band_can_run_across_midnight() -> None:
    # Given - a plan whose cheap band runs from 22:00 to 08:00
    overnight = Plan(
        name="Overnight",
        bands=(
            Band(Days.EVERY_DAY, 22, 8, OFF_PEAK),
            Band(Days.EVERY_DAY, 8, 22, PEAK),
        ),
    )
    hours = [hour(WEDNESDAY, at, "1") for at in (23, 3, 8)]

    # When
    cost = price_plan(overnight, hours, days=Decimal(0), holidays=frozenset())

    # Then - 23:00 and 03:00 are in the overnight band, 08:00 is not
    assert cost.energy == OFF_PEAK + OFF_PEAK + PEAK


def test_a_band_with_its_own_export_price_credits_at_it() -> None:
    # Given - export pays 0.12 around midday and the plan's 0.04 otherwise
    paying = Plan(
        name="Midday export",
        bands=(
            Band(Days.EVERY_DAY, 0, 11, OFF_PEAK),
            Band(Days.EVERY_DAY, 11, 15, OFF_PEAK, export_price=Decimal("0.12")),
            Band(Days.EVERY_DAY, 15, 24, OFF_PEAK),
        ),
        export_price=Decimal("0.04"),
    )
    hours = [hour(WEDNESDAY, 12, "0", "2.0"), hour(WEDNESDAY, 16, "0", "1.0")]

    # When
    cost = price_plan(paying, hours, days=Decimal(0), holidays=frozenset())

    # Then
    assert cost.export_credit == Decimal("0.28")  # 2.0 at 0.12, 1.0 at 0.04


def test_a_negative_import_price_lowers_the_cost() -> None:
    # Given - wholesale-linked plans pay households to import at times
    negative = Plan(
        name="Spot",
        bands=(Band(Days.EVERY_DAY, 0, 24, Decimal("-0.02")),),
    )

    # When
    cost = price_plan(
        negative, [hour(WEDNESDAY, 14, "3")], days=Decimal(0), holidays=frozenset()
    )

    # Then
    assert cost.energy == Decimal("-0.06")


def test_the_hour_daylight_saving_repeats_is_priced_once_for_each_record() -> None:
    # Given - 25 October 2026, when 02:00 to 03:00 local happens twice; the
    # recorder holds an hour for each, an hour of UTC apart
    utc = ZoneInfo("UTC")
    first = datetime(2026, 10, 25, 0, 0, tzinfo=utc).astimezone(LOCAL)
    second = datetime(2026, 10, 25, 1, 0, tzinfo=utc).astimezone(LOCAL)
    assert (first.hour, second.hour) == (2, 2)
    hours = [
        IntervalOfEnergy(first, Decimal(1), Decimal(0)),
        IntervalOfEnergy(second, Decimal(1), Decimal(0)),
    ]

    # When - a Sunday, so the rest-day band
    cost = price_plan(TIME_OF_USE, hours, days=Decimal(0), holidays=frozenset())

    # Then
    assert cost.energy == OFF_PEAK * 2


# Daily charges


def test_a_whole_day_is_one_day_of_charges() -> None:
    # Given / When
    start = datetime(2026, 11, 4, tzinfo=LOCAL)

    # Then
    assert days_covered(start, start + timedelta(days=1)) == Decimal(1)


def test_part_of_a_day_is_that_share_of_its_charge() -> None:
    # Given - midnight to 06:00, a quarter of the day
    start = datetime(2026, 11, 4, tzinfo=LOCAL)

    # When / Then
    assert days_covered(start, start + timedelta(hours=6)) == Decimal("0.25")


def test_the_short_and_long_days_of_daylight_saving_are_each_one_day() -> None:
    # Given - the 23-hour day in March and the 25-hour day in October
    spring = datetime(2026, 3, 29, tzinfo=LOCAL)
    autumn = datetime(2026, 10, 25, tzinfo=LOCAL)

    # When / Then - a day is a day, however long the clock made it
    assert days_covered(spring, datetime(2026, 3, 30, tzinfo=LOCAL)) == Decimal(1)
    assert days_covered(autumn, datetime(2026, 10, 26, tzinfo=LOCAL)) == Decimal(1)


def test_a_week_is_seven_days_of_charges() -> None:
    # Given / When
    start = datetime(2026, 11, 2, tzinfo=LOCAL)
    days = days_covered(start, start + timedelta(days=7))

    # Then
    assert days == Decimal(7)
    cost = price_plan(FLAT, [], days=days, holidays=frozenset())
    assert cost.daily_charges == Decimal("3.15")


# A plan is a schedule that covers every hour once


def test_a_plan_covering_every_hour_once_has_no_gaps() -> None:
    # Given / When / Then
    assert FLAT.gaps() == ()
    assert TIME_OF_USE.gaps() == ()


def test_an_hour_no_band_covers_is_a_gap() -> None:
    # Given - weekdays stop at 22:00, and nothing covers rest days at all
    incomplete = Plan(
        name="Incomplete",
        bands=(Band(Days.WEEKDAYS, 0, 22, PEAK),),
    )

    # When
    gaps = incomplete.gaps()

    # Then - the days sharing the same hours left out, and that none covers them;
    # no band prices holidays, so a holiday is one of the days of the week
    assert gaps == (
        PlanGap(MONDAY_TO_FRIDAY, (22, 23), covered_by=0),
        PlanGap(WEEKEND, tuple(range(24)), covered_by=0),
    )


def test_an_hour_two_bands_cover_is_a_gap_too() -> None:
    # Given - an every-day band and a rest-day band overlapping all weekend
    overlapping = Plan(
        name="Overlapping",
        bands=(
            Band(Days.EVERY_DAY, 0, 24, PEAK),
            Band(Days.REST_DAYS, 10, 12, OFF_PEAK),
        ),
    )

    # When / Then - which price applies would be a guess
    assert overlapping.gaps() == (
        PlanGap((*WEEKEND, Day.HOLIDAY), (10, 11), covered_by=2),
    )


def test_a_holiday_band_must_price_the_whole_of_a_holiday() -> None:
    # Given - holidays have a band of their own, but only until midday
    half_holiday = Plan(
        name="Half a holiday",
        bands=(
            Band(Days.WEEKDAYS, 0, 24, PEAK),
            Band(frozenset(WEEKEND), 0, 24, OFF_PEAK),
            Band(frozenset({Day.HOLIDAY}), 0, 12, OFF_PEAK),
        ),
    )

    # When / Then - a holiday afternoon would otherwise be a guess
    assert half_holiday.gaps() == (
        PlanGap((Day.HOLIDAY,), tuple(range(12, 24)), covered_by=0),
    )


def test_a_band_applies_to_at_least_one_day() -> None:
    # When / Then
    with pytest.raises(ValueError, match="day"):
        Band(frozenset(), 0, 24, PEAK)


def test_a_plan_with_a_gap_is_not_priced() -> None:
    # Given
    incomplete = Plan(name="Incomplete", bands=(Band(Days.WEEKDAYS, 0, 22, PEAK),))

    # When / Then - never as zero
    with pytest.raises(ValueError, match="does not cover every hour"):
        price_plan(
            incomplete,
            [hour(WEDNESDAY, 23, "1")],
            days=Decimal(0),
            holidays=frozenset(),
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 8), (0, 25), (8, 8)],
)
def test_a_band_must_cover_whole_hours_of_one_day(start: int, end: int) -> None:
    # When / Then - hours run 0 to 24, and a band covers at least one
    with pytest.raises(ValueError, match="hours"):
        Band(Days.EVERY_DAY, start, end, PEAK)


# Prices from an entity, interval by interval (HEA-260, ADR-0037)

# A wholesale plan: no bands, its import at whatever the market charged in each
# interval, its export at a flat feed-in price.
WHOLESALE = Plan(
    name="Wholesale",
    bands=(),
    daily_charge=Decimal("1.10"),
    export_price=Decimal("0.05"),
    import_per_interval=True,
)


def interval(  # noqa: PLR0913 - one recorded interval field by field
    day: date,
    at: int,
    minute: int,
    imported: str,
    exported: str = "0",
    *,
    import_price: str | None = None,
    export_price: str | None = None,
) -> IntervalOfEnergy:
    """Five recorded minutes of grid flow, at the prices the market set for them."""
    return IntervalOfEnergy(
        start=datetime(day.year, day.month, day.day, at, minute, tzinfo=LOCAL),
        imported_kwh=Decimal(imported),
        exported_kwh=Decimal(exported),
        import_price=None if import_price is None else Decimal(import_price),
        export_price=None if export_price is None else Decimal(export_price),
    )


def test_a_plan_importing_at_the_market_charges_each_interval_its_own_price() -> None:
    # Given - the same hour, cheap for five minutes and below nothing for the
    # next five, as a wholesale price can be
    intervals = [
        interval(WEDNESDAY, 12, 0, "0.4", import_price="0.12"),
        interval(WEDNESDAY, 12, 5, "1.5", import_price="-0.02"),
    ]

    # When
    cost = price_plan(WHOLESALE, intervals, days=Decimal(1), holidays=frozenset())

    # Then - each at its own price, not the hour's average
    assert cost == PlanCost(
        energy=Decimal("0.018"),  # 0.4 at 0.12, less 1.5 at 0.02
        export_credit=Decimal(0),
        daily_charges=Decimal("1.10"),
    )


def test_a_plan_exporting_at_the_market_credits_each_interval_its_own_price() -> None:
    # Given - a time-of-use plan whose feed-in follows the market instead of its
    # flat price, at the weekday peak
    plan = Plan(
        name="Banded, market feed-in",
        bands=TIME_OF_USE.bands,
        export_price=Decimal("0.04"),
        export_per_interval=True,
    )
    intervals = [interval(WEDNESDAY, 18, 30, "0", "2.0", export_price="0.21")]

    # When
    cost = price_plan(plan, intervals, days=Decimal(0), holidays=frozenset())

    # Then - the band still prices import, the market prices export
    assert cost.export_credit == Decimal("0.420")


def test_a_plan_importing_at_the_market_needs_no_bands() -> None:
    # When / Then - no hour is left unpriced, since every interval has a price
    assert WHOLESALE.gaps() == ()


def test_an_interval_without_a_price_of_its_own_is_not_guessed_at() -> None:
    # Given - an interval the comparison found no price for
    intervals = [interval(WEDNESDAY, 12, 0, "0.4")]

    # When / Then
    with pytest.raises(ValueError, match="price"):
        price_plan(WHOLESALE, intervals, days=Decimal(0), holidays=frozenset())


def test_a_five_minute_interval_is_priced_at_the_band_its_start_falls_in() -> None:
    # Given - five minutes before the weekday peak, and the first five of it
    intervals = [
        interval(WEDNESDAY, 9, 55, "1"),
        interval(WEDNESDAY, 10, 0, "1"),
    ]

    # When
    cost = price_plan(TIME_OF_USE, intervals, days=Decimal(0), holidays=frozenset())

    # Then
    assert cost.energy == SHOULDER + PEAK
