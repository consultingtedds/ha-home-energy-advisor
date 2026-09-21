"""A counter that leaps has been replaced, not used (HEA-137, GitHub #22).

Swapping a source sensor leaves a counter reading something else entirely. A
counter that *falls* is already understood - that is a reset, and the new value
becomes the baseline. A counter that *leaps* was booked as energy that had just
been used, which is how one household's whole-home total reached 19,654 kWh
after they recreated their sensors, with 5,336 kWh counted in a single reading.

So a reading is weighed as power before it is believed. A domestic supply is
fused at about 24 kW single-phase, and around 69 kW on the largest three-phase
connection; ``CREDIBLE_POWER_KW`` sits well above both, and the readings that
brought this here imply 240 kW and 640 MW.

The span is the honest denominator: a meter quiet for a day and then honest
about a day's energy is believed, because a day of energy over a day is an
ordinary load. It is floored at a minute so that two readings a moment apart
cannot imply a fortune from a rounding step.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.energy_source import (
    CumulativeEnergySource,
    DecisionReason,
    EnergyUnit,
    Reading,
)

BASE = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)


def at(seconds: int) -> datetime:
    return BASE + timedelta(seconds=seconds)


def kwh(when: datetime, value: Decimal | str) -> Reading:
    """A reading of a plain kilowatt-hour counter, which these all are."""
    return Reading(at=when, value=Decimal(value), unit=EnergyUnit.KWH)


def a_meter() -> CumulativeEnergySource:
    """A counter already reading, so the next reading is weighed rather than first."""
    source = CumulativeEnergySource()
    source.observe(kwh(at(0), Decimal(100)))
    return source


def reasons(source: CumulativeEnergySource) -> list[str]:
    return [decision.reason.value for decision in source.snapshot().recent_decisions]


def test_a_counter_that_leaps_is_not_counted_as_energy() -> None:
    # Given - a house meter reading 100 kWh, and a household who has just
    # replaced the sensor behind it with one that counts from somewhere else
    source = a_meter()

    # When - the new sensor's first reading arrives thirty seconds later
    delta = source.observe(kwh(at(30), "5436.38"))

    # Then - nothing is counted. 5,336 kWh in thirty seconds is around 640 MW,
    # which is not a house; booking it puts energy in the lifetime totals that
    # only a rebase will ever remove
    assert delta is None
    assert reasons(source)[-1] == DecisionReason.IMPLAUSIBLE_STEP.value


def test_the_replaced_counter_becomes_the_new_baseline() -> None:
    # Given - a counter that has just leapt, and been refused
    source = a_meter()
    source.observe(kwh(at(30), "5436.38"))

    # When - the new sensor reports again, having genuinely used 0.2 kWh
    delta = source.observe(kwh(at(330), "5436.58"))

    # Then - that 0.2 is counted, from the new counter's position. Refusing the
    # step without adopting the value would refuse everything after it too
    assert delta is not None
    assert delta.kwh == Decimal("0.20")


def test_a_device_stepping_beyond_any_domestic_load_is_refused() -> None:
    # Given - the shape of GitHub #19: a socket's own counter stepping 4 kWh in
    # a minute, which is 240 kW
    source = a_meter()

    # When
    delta = source.observe(kwh(at(60), Decimal(104)))

    # Then - refused. The existing guard only condemns a device claiming more
    # than the *whole house* over a full hour, which this passes
    assert delta is None
    assert reasons(source)[-1] == DecisionReason.IMPLAUSIBLE_STEP.value


def test_a_quiet_meter_telling_the_truth_about_a_quiet_day_is_believed() -> None:
    # Given - a meter that reports once a day, as some cloud-polled ones do
    source = a_meter()

    # When - it reports a day's worth of an ordinary house: 60 kWh, which is
    # 2.5 kW averaged over the day it covers
    delta = source.observe(kwh(at(86400), Decimal(160)))

    # Then - counted in full. Judging the step against a bucket rather than
    # against the span it covers would refuse every coarse meter in the world
    assert delta is not None
    assert delta.kwh == Decimal(60)


def test_two_readings_a_moment_apart_do_not_imply_a_fortune() -> None:
    # Given - a counter whose integration reports twice in quick succession,
    # which polled sources do
    source = a_meter()

    # When - the second reading is a tenth of a second later, one step of a
    # 0.01 kWh counter on from the first
    moments_later = BASE + timedelta(milliseconds=100)
    delta = source.observe(kwh(moments_later, "100.01"))

    # Then - counted. Taken literally that step is 360 kW; the span is floored
    # at a minute precisely so that reporting jitter is not read as a fault
    assert delta is not None
    assert delta.kwh == Decimal("0.01")


def test_a_reset_to_an_implausible_value_is_refused_too() -> None:
    # Given - a counter replaced by one reading *lower*, which is seen as a
    # reset, and whose value is then booked as energy used since it
    source = a_meter()

    # When - the replacement reads 150 kWh, thirty seconds on
    delta = source.observe(kwh(at(30), Decimal(150)))

    # Then - refused as well. A reset books the new value as energy, so a
    # replaced sensor poisons the totals through this path just as readily
    assert delta is None
    assert reasons(source)[-1] == DecisionReason.IMPLAUSIBLE_STEP.value


def test_an_ordinary_reset_still_counts_what_followed_it() -> None:
    # Given - a cycle meter that resets to zero at midnight and climbs again,
    # which is the reset this engine was built around
    source = a_meter()

    # When - it restarts and reports 0.4 kWh five minutes later
    delta = source.observe(kwh(at(300), "0.4"))

    # Then - the 0.4 is counted. The guard must not turn every legitimate reset
    # into a refusal
    assert delta is not None
    assert delta.kwh == Decimal("0.4")
