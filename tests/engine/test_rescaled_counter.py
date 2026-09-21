"""A counter whose scale changes is not a cycle that restarted (HEA-157).

A firmware update rescaled two smart plugs by a factor of ten and reverted it
four days later. The unit label said `kWh` throughout, so nothing declarative
marked the change - only the numbers moved. Going down, that reads as a cycle
reset, and the reset rule credits the post-reset value as a fresh cycle's
energy: 119.34 kWh booked for a water heater that had run four hours.

The claim a reset makes is testable. "The counter restarted and climbed to this
value since the last reading" cannot be true of more energy than the whole house
was metered as consuming over the same span, and the house meter saw the same
span the device did.

The comparison is floored at one plausibility window, and that floor is the
whole design. A device's coarse step legitimately exceeds what the house was
metered in the twenty seconds it was reported over - that is the spreading
approximation ADR-0006 is built on, and it is why HEA-60's window is twelve
buckets rather than one. Over an hour the artefact cancels; a counter that has
been rescaled does not.

This guard stops one reading. HEA-60's `_judge` continues to catch a counter
that lies steadily, which it does well and this does not replace.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.energy_source import (
    DecisionReason,
)

# A 5-minute-aligned instant; readings are placed at whole-minute offsets from it.
BASE = datetime(2026, 9, 19, 18, 0, tzinfo=UTC)
PEAK = Decimal("0.30")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


HOUSE = "sensor.house_load"
GRID = "sensor.grid_import"
PLUG = "sensor.water_heater_total"
DEVICE = "water_heater"

# What the reference instance's plugs actually did: a counter at 1193.38 kWh
# reappearing at 119.34 after a firmware update, across a four-hour gap.
BEFORE_RESCALE = Decimal("1193.38")
AFTER_RESCALE = Decimal("119.34")


def a_metered_home() -> Accountant:
    """A home whose own consumption is metered - the residual decomposition."""
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        device_energy_entities={DEVICE: PLUG},
    )


class _Home:
    """A metered home whose counters can be advanced bucket by bucket.

    The house keeps metering whether or not the plug is reporting, which is the
    shape that matters here: the plugs that prompted this had a four-hour gap
    across the firmware update while the house meter carried on throughout. A
    fixture that let the house fall silent too would be judging the guard
    against a case it never has to handle.
    """

    def __init__(self, plug: Decimal) -> None:
        self.acc = a_metered_home()
        self.house = Decimal(0)
        self.plug = plug
        self.minute = 0
        self.acc.record_price(at(0), PEAK)
        self.acc.observe(GRID, at(0), Decimal(0))
        self.acc.observe(HOUSE, at(0), Decimal(0))
        self.acc.observe(PLUG, at(0), plug)

    def run(self, *, buckets: int, house_step: str, plug_reports: bool = True) -> None:
        """Advance both meters, or only the house where the plug has gone quiet."""
        for _ in range(buckets):
            self.minute += 5
            self.house += Decimal(house_step)
            self.acc.observe(GRID, at(self.minute), self.house)
            self.acc.observe(HOUSE, at(self.minute), self.house)
            if plug_reports:
                # A tenth of the house's step: an ordinary share for one
                # appliance, and well inside anything this guard should refuse.
                self.plug += Decimal(house_step) / 10
                self.acc.observe(PLUG, at(self.minute), self.plug)
            # Finalised at the reading's own time, so the watermark trails by
            # the lateness margin exactly as the live timer leaves it. Closing
            # the bucket a reading just landed in would send every one of them
            # down the late-correction path, which is a different mechanism
            # with different arithmetic (ADR-0014) and not what is under test.
            self.acc.finalize(at(self.minute))

    def plug_reports(self, value: Decimal) -> None:
        """One reading from the plug, in the bucket after the last one run."""
        self.minute += 5
        self.plug = value
        self.acc.observe(PLUG, at(self.minute), value)
        self.acc.finalize(at(self.minute))

    def close(self) -> None:
        """Push the watermark past the last reading, so its bucket settles.

        Totals only carry finalised buckets, so a figure read before this is a
        figure the engine has not published yet.

        The clock moves with the watermark. Leaving it behind would put the next
        reading *before* the watermark, which is the late-correction path - a
        different mechanism with different arithmetic, and one a test meaning to
        exercise the live path would take without ever saying so.
        """
        self.minute += 30
        self.acc.finalize(at(self.minute))

    @property
    def booked(self) -> Decimal:
        """What the device has been credited with, once everything has settled."""
        self.close()
        return self.acc.totals().devices[DEVICE].energy_kwh


def a_settled_home(plug: Decimal, house_step: str = "0.15") -> _Home:
    """A home with a full plausibility window behind it.

    The window has to be *full* before anything is judged, so every test here
    needs a settled hour first - which is also the honest setup: a counter that
    rescales has been counting normally until it does.
    """
    # Enough buckets that twelve of them have finalised behind the watermark,
    # which is what `_PLAUSIBILITY_WINDOW` needs before anything is judged.
    home = _Home(plug)
    home.run(buckets=20, house_step=house_step)
    return home


def reasons(home: _Home) -> list[DecisionReason]:
    return [d.reason for d in home.acc.source_diagnostics()[PLUG].recent_decisions]


def a_rescaled_plug() -> _Home:
    """A settled home whose plug then rescales, four hours into a reporting gap."""
    home = a_settled_home(plug=BEFORE_RESCALE)
    # The plug goes quiet across the firmware update; the house meters on.
    home.run(buckets=48, house_step="0.15", plug_reports=False)
    home.plug_reports(AFTER_RESCALE)
    return home


def test_a_rescaled_counter_books_none_of_its_new_value() -> None:
    # Given - a plug whose counter stands where the reference instance's did
    # before its firmware was updated
    home = a_settled_home(plug=BEFORE_RESCALE)
    home.run(buckets=48, house_step="0.15", plug_reports=False)
    before = home.booked

    # When - the update rescales the counter by ten, which reads as a cycle
    # reset and credits the whole new value
    home.plug_reports(AFTER_RESCALE)

    # Then - nothing is booked. No household draws 119 kWh through one water
    # heater in four hours, and the house meter beside it says they did not
    assert home.booked == before


def test_a_rescaled_counter_resumes_counting_once_the_window_has_rolled() -> None:
    # Given - the same rescale, refused. The refused reading is still *claimed*,
    # so HEA-60 sees a device that asked for more than the house had and
    # condemns it - which is deliberate, because that is what raises the Repair
    # naming the device. The cost is that the plug stays condemned until the
    # claim ages out of the plausibility window
    home = a_rescaled_plug()
    assert DEVICE in home.acc.implausible_devices()

    # When - an hour of honest counting passes, ageing the claim out
    home.run(buckets=14, house_step="0.15", plug_reports=False)
    before = home.booked

    # Then - the device is believed again, and a step in the new scale is booked
    # normally. Refusing the discontinuity must not strand the device for good:
    # the counter is telling the truth again, and the vendor reverted this one
    # four days later
    assert DEVICE not in home.acc.implausible_devices()
    home.plug_reports(home.plug + Decimal("0.20"))
    assert home.booked > before


def test_the_refusal_is_told_apart_from_a_device_that_lies_steadily() -> None:
    # Given / When - a counter rescaled once
    home = a_rescaled_plug()

    # Then - its own reason, not HEA-60's. One reading that claimed more than
    # the house could deliver, and a device that has over-claimed for a whole
    # hour, have different remedies - so the diagnostics download must not give
    # them the same name (HEA-24).
    assert DecisionReason.BEYOND_THE_HOUSE in reasons(home)
    assert DecisionReason.IMPLAUSIBLE not in reasons(home)


def test_an_ordinary_coarse_step_is_not_refused() -> None:
    # Given - the case this guard must not break. A coarse counter holds still
    # and then jumps a whole step, reported over seconds: measured against the
    # house in those seconds it always looks impossible, which is why the
    # comparison is floored at a full window (ADR-0006, HEA-60)
    home = a_settled_home(plug=Decimal(4))
    before = home.booked

    # When - the aircon crosses a 0.25 kWh step, well over what the house
    # metered in the bucket it landed in
    home.plug_reports(home.plug + Decimal("0.25"))

    # Then - booked in full
    assert home.booked == before + Decimal("0.25")


def test_a_genuine_cycle_reset_still_credits_its_partial_cycle() -> None:
    # Given - the behaviour ADR-0002 and HEA-50 were built around: an aircon
    # whose counter restarts when its compressor cycle ends
    home = a_settled_home(plug=Decimal("2.75"))
    before = home.booked

    # When - the cycle ends and the counter restarts, already at 0.10 kWh
    home.plug_reports(Decimal("0.10"))

    # Then - the fresh cycle's energy is credited. A reset that a house could
    # have delivered is still a reset, and refusing every one of them would
    # silently drop the energy of every cycle-resetting device in the home.
    # Quantised because spreading a step across intervals divides, and the last
    # digit of a 28-digit Decimal is not a household's concern
    grew = (home.booked - before).quantize(Decimal("0.000000001"))
    assert grew == Decimal("0.100000000")
    assert DecisionReason.BEYOND_THE_HOUSE not in reasons(home)


def test_a_device_quiet_for_hours_is_judged_over_the_hours_it_was_quiet() -> None:
    # Given - the false positive worth designing against: an EV charger on a
    # coarse counter, quiet while the house draws heavily, then honest about all
    # of it at once. Judged against a *rate* taken from an idle hour it would be
    # refused; judged against the house over its own span it is not
    home = a_settled_home(plug=Decimal(10), house_step="0.05")
    home.run(buckets=24, house_step="2.0", plug_reports=False)
    before = home.booked

    # When - it reports 20 kWh at once, against a house that metered 48 over
    # the two hours it was charging
    home.plug_reports(home.plug + Decimal(20))

    # Then - believed. The house meter saw the same span the device did, and it
    # agrees there was that much energy to have.
    #
    # What the figure then *becomes* is the late-correction path's business, not
    # this guard's: the delta lands in buckets that have already finalised, so
    # only what each can still fund is published now and the rest waits (HEA-85,
    # ADR-0014). Asserting the full 20 here would tie this test to arithmetic it
    # is not about, and it has its own tests. What matters is that the reading
    # was not thrown away
    assert DecisionReason.BEYOND_THE_HOUSE not in reasons(home)
    assert home.booked > before


def test_nothing_is_judged_before_the_window_has_filled() -> None:
    # Given - a fresh accountant, which has no hour of house readings to judge
    # anything against
    home = _Home(plug=BEFORE_RESCALE)
    home.run(buckets=1, house_step="0.15")

    # When - a rescale arrives before there is any evidence
    home.plug_reports(AFTER_RESCALE)

    # Then - not refused here. A fresh start condemns nothing on one interval's
    # evidence, exactly as HEA-60's own window refuses to; what catches this one
    # is the power guard, and past that, the hour that follows
    assert DecisionReason.BEYOND_THE_HOUSE not in reasons(home)


def test_a_silent_house_meter_is_no_evidence_against_a_device() -> None:
    # Given - a settled hour in which the house meter reported nothing at all.
    # A silent house meter is its own fault, reported elsewhere (HEA-24)
    home = a_settled_home(plug=Decimal(4), house_step="0")

    # When - the device reports a step
    home.plug_reports(Decimal("4.25"))

    # Then - believed rather than refused. Judging a device against a meter
    # that is not reporting would condemn every device in the house for a
    # failure none of them caused
    assert DecisionReason.BEYOND_THE_HOUSE not in reasons(home)
