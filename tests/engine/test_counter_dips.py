"""A counter that dips has not started again (HEA-139, GitHub #22).

A reset books the counter's whole value as energy used since it restarted, which
is right for a meter that has genuinely gone back to zero. Applied to *any*
fall, it is catastrophic: one household's sensor was jittering downward in the
eighth decimal place, and each jitter booked its entire 150 kWh.

Home Assistant's own statistics have the answer already - a `total_increasing`
sensor counts as reset only when it falls below 90% of what it read before, and
a smaller dip is ignored (`components/sensor/recorder.py`). This engine now
agrees with the platform it publishes to.

A fall past that threshold is still ambiguous at the moment it arrives: a
counter at zero may have restarted, or may be a sensor blinking. So the value
before it is held, and the next reading settles which it was - the pattern
ADR-0015 and HEA-85 already use for anything that cannot be known yet.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.energy_source import (
    CumulativeEnergySource,
    Reading,
)

BASE = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_meter(value: str = "104") -> CumulativeEnergySource:
    """A counter already reading, so the next reading is compared to something."""
    source = CumulativeEnergySource()
    source.observe(Reading(at=at(0), value=Decimal(value)))
    return source


def counted(source: CumulativeEnergySource, minutes: int, value: str) -> Decimal:
    """The energy one reading revealed, or zero where it revealed none."""
    delta = source.observe(Reading(at=at(minutes), value=Decimal(value)))
    return delta.kwh if delta is not None else Decimal(0)


def test_a_counter_jittering_in_its_last_decimal_books_nothing() -> None:
    # Given - the sensor from GitHub #22, whose value wobbles downward by a
    # rounding error between readings
    source = a_meter("150.341822988392")

    # When - two such readings arrive
    first = counted(source, 5, "150.341822973395")
    second = counted(source, 10, "150.341820647083")

    # Then - nothing is counted. Reading each dip as a restart booked the whole
    # 150 kWh, twenty times over, and their whole-home total reached 1,912 kWh
    # within an hour of a reset
    assert first == Decimal(0)
    assert second == Decimal(0)


def test_the_baseline_survives_a_dip_so_the_next_real_step_is_right() -> None:
    # Given - a counter that dipped slightly and then genuinely advanced
    source = a_meter("100")
    counted(source, 5, "99.999")

    # When - it reaches 100.5
    kwh = counted(source, 10, "100.5")

    # Then - half a kWh, measured from where the counter really was. Rebasing on
    # the dip would count 0.501, which is small here and is not small on a
    # counter that dips all day
    assert kwh == Decimal("0.5")


def test_a_counter_that_restarts_is_still_a_reset_straight_away() -> None:
    # Given - a cycle meter at 4 kWh that rolls over at midnight
    source = a_meter("4")

    # When - it restarts, reporting 0.4 kWh and then 0.6
    restart = counted(source, 5, "0.4")
    after = counted(source, 10, "0.6")

    # Then - the 0.4 is energy used since the restart, counted when it arrives.
    # Holding it back until the next reading would make a cycle meter that polls
    # every ninety minutes wait that long for energy it has already reported -
    # the founding case this engine was built for (ADR-0006)
    assert restart == Decimal("0.4")
    assert after == Decimal("0.2")


def test_a_sensor_blinking_to_zero_loses_nothing() -> None:
    # Given - a counter at 104 that blinks to zero, which is what a flaky
    # integration does between polls
    source = a_meter("104")
    blink = counted(source, 5, "0")

    # When - it comes back at 105, having really used 1 kWh
    after = counted(source, 10, "105")

    # Then - exactly that 1 kWh is counted. The blink itself counts nothing, and
    # the value before it is what the return is measured against: without that,
    # the return reads as 105 kWh out of nowhere and is refused (HEA-137),
    # losing the kilowatt-hour the household actually used
    assert blink == Decimal(0)
    assert after == Decimal(1)


def test_a_counter_that_stays_low_settles_as_a_genuine_reset() -> None:
    # Given - a counter at 104 that restarts for real
    source = a_meter("104")
    counted(source, 5, "0")

    # When - it climbs from zero rather than returning to where it was
    first = counted(source, 10, "0.3")
    second = counted(source, 15, "0.8")

    # Then - the energy since the restart is counted, and nothing is invented to
    # bridge the gap back to 104
    assert first == Decimal("0.3")
    assert second == Decimal("0.5")


def test_a_blink_to_a_figure_is_not_counted_twice_on_the_way_back() -> None:
    # Given - a counter at 104 that blinks to 0.3 rather than to zero, and is
    # credited with that 0.3 as though the cycle had restarted
    source = a_meter("104")
    assert counted(source, 5, "0.3") == Decimal("0.3")

    # When - it returns to 105, so the blink is what it was
    back = counted(source, 10, "105")

    # Then - the kilowatt-hour across the blink, less the 0.3 already credited.
    # Counting the whole 1 kWh again would pay for the same energy twice
    assert back == Decimal("0.7")
