"""Turns a device's cumulative energy counter into discrete, time-spanned deltas.

Home Assistant's ``total_increasing`` counters come in two flavours on real
hardware: lifetime counters that climb for years, and counters that reset
constantly - per-cycle counters that restart whenever the appliance's cycle
ends, device-side daily counters that roll over at midnight. Both are handled by
one rule, validated against real instance data in
``docs/notes/AIRCON_COST_EXPLORATION.md``.

Deltas carry the span they accumulated over, not just a magnitude. A sensor that
was unavailable for three days reports one large jump on recovery; attributing
that energy to the instant it was reported would price it all at whatever tariff
happened to be active then. The interval ledger spreads it across the span
instead.

That span runs from the counter's last **movement**, not its last reading. Coarse
counters are re-reported unchanged every poll and then jump a whole step; the
step accrued across the quiet run between movements, so anchoring it to the
previous reading concentrates an hour of energy into one 5-minute bucket. There
it can exceed everything the house was metered as consuming, which is what
priced tracked devices far below the grid rate (HEA-74). Only the quiet run is
capped, at ``MAX_QUIET_SPAN``; a genuine reporting gap is never trimmed.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

_WH_PER_KWH = Decimal(1000)

# How far back into a *quiet* run - one where the source kept reporting an
# unchanged counter - a delta may reach for the energy it finally reveals.
#
# Coarse counters hold still for 30-90 minutes and then jump a whole step. That
# step accrued across the quiet run, so anchoring it to the previous *reading*
# books an hour of energy into one 5-minute bucket, where it can exceed
# everything the house was served and collapse the price the allocation model
# pays for it (HEA-74).
#
# The cap exists only to bound the opposite error: a device switched off for
# hours reports the same unchanged counter as one trickling along, and the
# counter alone cannot tell them apart.
#
# Two hours, and measured rather than chosen (HEA-75). Across 684 counter
# movements from fourteen devices over five days, checked against each device's
# own on/off signal: devices were running for 92-98 % of every gap up to two
# hours, and 53 %, then 29 %, then 4 % beyond it. The cliff is the boundary
# between "working slowly" and "switched off", and it falls exactly here.
# Independently, the energy a capped spread misplaces against a run-signal
# weighting is minimised at the same value - 6.9 % of fleet energy, against
# 10.4 % at one hour and 34 % at thirty minutes.
#
# Weighting by the run signal itself was measured and rejected: it moves
# whole-home cost by ~1 % in summer and 0.3 % under a January solar profile,
# because a 30-90 minute spread is short next to a 2-4 hour tariff band. The
# large per-device percentages it shifts are all on devices costing pennies.
MAX_QUIET_SPAN = timedelta(hours=2)

# How far a counter may fall and still be the same counter. Home Assistant's own
# statistics use this figure: a `total_increasing` sensor counts as reset only
# below 90 % of what it read before, and a smaller dip is ignored
# (`components/sensor/recorder.py`). Without it, a sensor jittering downward in
# its last decimal has its whole value booked as energy on every jitter - which
# took one household's home total to 1,912 kWh in an hour (HEA-139, GitHub #22).
_SAME_COUNTER_FLOOR = Decimal("0.9")

# The most power a reading may imply and still be believed. A domestic supply is
# fused at about 24 kW single-phase and around 69 kW on the largest three-phase
# connection, so nothing an ordinary household can do reaches this - while the
# readings that brought it here imply 240 kW and 640 MW (HEA-137, GitHub #19 and
# #22). Above it, a counter has been replaced or rescaled: its value is somebody
# else's number, not energy this house used.
CREDIBLE_POWER_KW = Decimal(100)

# The shortest span a reading is judged over. Two readings a moment apart would
# otherwise make one step of a coarse counter imply a fortune - a 0.01 kWh step a
# tenth of a second on is 360 kW - and reporting jitter is not a fault.
_MIN_JUDGED_SPAN = timedelta(minutes=1)

# How many recent gating decisions each source retains for the diagnostics
# download (HEA-24). Bounded so a long-running source never grows without limit;
# 20 is enough to explain a device's most recent behaviour in a support thread.
_DECISION_LOG_SIZE = 20

# The scale changes worth naming. A vendor that moves a counter between watt
# hours and kilowatt hours shifts it by a thousand; one that fixes a decimal
# place shifts it by ten. Nothing here is special to ten, which is only the
# factor the reference instance happened to meet (HEA-159).
_SCALE_FACTORS = (Decimal(10), Decimal(100), Decimal(1000), Decimal(10000))

# How far from a clean power of ten a ratio may sit and still be called one.
# The reference instance's two heaters gave 10.0002 and 9.9672 - the second is
# 0.33 % out, because a counter keeps moving across the discontinuity. Two per
# cent covers that with room to spare while leaving a ratio like 54x, which is a
# counter that was *replaced* rather than rescaled, comfortably outside.
_SCALE_TOLERANCE = Decimal("0.02")


class EnergyUnit(Enum):
    """The unit a device's counter reports in, normalised to kWh on the way in.

    ``UNKNOWN`` is a unit in its own right here, and deliberately not ``None``:
    "the sensor did not say" is a state a reading is genuinely in - while a
    plug is reconnecting, or where an integration publishes a unit this engine
    does not count in - and it has to be as sayable as the other two. Modelling
    it as an absence is what let it be quietly read as kWh (GitHub #24).
    """

    KWH = "kWh"
    WH = "Wh"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Reading:
    """One observation of a counter.

    A ``value`` of ``None`` means the source had no reading - Home Assistant's
    ``unavailable`` and ``unknown`` states, mapped by the integration layer so
    that the engine never learns Home Assistant's vocabulary.

    ``unit`` travels with the reading rather than with the source, because it is
    a property of the number in hand. A sensor that has not reconnected yet
    publishes no unit, and one whose firmware is updated can start publishing a
    different one; a source told its unit once, at construction, is wrong in
    both cases and cannot find out (GitHub #24, HEA-149).
    """

    at: datetime
    value: Decimal | None
    unit: EnergyUnit


@dataclass(frozen=True)
class EnergyDelta:
    """Energy consumed between two readings, and the span it accumulated over."""

    kwh: Decimal
    start: datetime
    end: datetime


class DecisionReason(Enum):
    """Why a reading did or did not become accounted energy (HEA-24 diagnostics).

    One reason is logged per observed reading, so the diagnostics download can
    explain any figure: energy was counted, a reset was recognised, or the
    reading was gated out (no prior baseline, an unavailable source, a stale or
    duplicate timestamp, or a counter that simply did not move). ``DROPPED_LATE``
    is logged not per reading but per portion the accountant could not place: a
    delta reaching a bucket older than the retention ring (HEA-48). ``ZERO_PRICED``
    is likewise accountant-level: a bucket finalised before any import price was
    known, so its energy is costed at zero (logged once per cold-start, HEA-53).
    ``IMPLAUSIBLE`` is the third accountant-level reason: energy refused because
    the device claimed more than the whole house over a full window, which no
    real load can do (HEA-60). ``IMPLAUSIBLE_STEP`` is this class's own refusal:
    a reading implying more power than any household draws, which is a counter
    that has been replaced rather than energy anybody used (HEA-137).
    ``BEYOND_THE_HOUSE`` is its near neighbour and deliberately distinct: *one*
    delta claiming more energy than the house was metered as consuming over the
    span it covers, which is what a rescaled counter's reset credit looks like
    (HEA-157). A device over-claiming for an hour and a single reading that
    cannot be true have different remedies, so the log does not call them the
    same thing.

    The two unit reasons are what a household reading the diagnostics needs when
    a figure is missing rather than wrong. ``UNIT_UNKNOWN`` is a reading whose
    sensor published no unit, so there is no saying what its number means;
    ``UNIT_CHANGED`` is a counter that has started reporting in a different one,
    where the baseline and the new reading are no longer comparable (HEA-149).
    """

    COUNTED = "counted"
    RESET = "reset"
    IMPLAUSIBLE_STEP = "implausible_step"
    FIRST_READING = "first_reading"
    UNAVAILABLE = "unavailable"
    UNIT_UNKNOWN = "unit_unknown"
    UNIT_CHANGED = "unit_changed"
    STALE = "stale"
    NO_MOVEMENT = "no_movement"
    DROPPED_LATE = "dropped_late"
    ZERO_PRICED = "zero_priced"
    IMPLAUSIBLE = "implausible"
    BEYOND_THE_HOUSE = "beyond_the_house"


@dataclass(frozen=True)
class Decision:
    """What the engine did with one reading, for the diagnostics decision log.

    ``kwh`` carries the energy the reading revealed for ``COUNTED`` and ``RESET``;
    for every gated reason it is ``None``.
    """

    at: datetime
    reason: DecisionReason
    kwh: Decimal | None


@dataclass(frozen=True)
class ScaleChange:
    """A refused step whose size looks like the counter's scale moving.

    ``factor`` is the magnitude, always at least one, and ``shrank`` says which
    way the counter went. Both are needed and neither is enough: a counter that
    grew by ten is now over-reporting, one that shrank by ten may equally have
    just been *corrected* by the same vendor who broke it - which is exactly
    what happened on the reference instance four days apart. Nothing here says
    which scale is the true one, because nothing here can (HEA-159).
    """

    at: datetime
    factor: Decimal
    shrank: bool


@dataclass(frozen=True)
class SourceSnapshot:
    """A source's diagnostics state: its unit, last reading, and decision log.

    ``unit`` is the one its last reading carried, and ``UNKNOWN`` where no
    reading has carried a usable one yet - which is the difference between a
    source counting in kWh and a source nobody can count at all.
    """

    unit: EnergyUnit
    last_value: Decimal | None
    last_at: datetime | None
    recent_decisions: tuple[Decision, ...]
    # Set only while a refused step still looks like a rescale, and dropped as
    # soon as the counter reports something the house can account for.
    scale_change: ScaleChange | None = None


@dataclass(frozen=True)
class _Drop:
    """A fall past the floor, and what it was credited with when it arrived."""

    before: _Observation
    credited: Decimal


@dataclass(frozen=True)
class _Observation:
    """A reading known to carry a value and a unit - the only kind worth keeping.

    The unit is held with the value because the two only mean anything together:
    a baseline of 0.5 is half a kilowatt hour or half a watt hour depending on
    it, and the next reading can only be subtracted from it if both are counted
    in the same one.
    """

    at: datetime
    value: Decimal
    unit: EnergyUnit


class CumulativeEnergySource:
    """Extracts energy deltas from a ``total_increasing`` counter.

    A falling counter is a reset, not negative consumption: the new value is
    taken as a fresh cycle's energy. Gaps are always attributed - a counter that
    climbs while its sensor is unavailable really did consume that energy, so it
    is reported spanning the gap rather than discarded.
    """

    def __init__(
        self,
        *,
        max_quiet_span: timedelta = MAX_QUIET_SPAN,
    ) -> None:
        self._last: _Observation | None = None
        # Where the counter stood before it fell past the floor, and what the
        # fall was credited with, until the next reading says whether it
        # restarted or merely blinked (HEA-139).
        self._before_drop: _Drop | None = None
        self._moved_at: datetime | None = None
        self._max_quiet_span = max_quiet_span
        self._decisions: deque[Decision] = deque(maxlen=_DECISION_LOG_SIZE)
        # A refused step that looked like a rescale, and one the accountant has
        # not ruled on yet. Diagnostics only: nothing here changes a figure.
        self._scale_change: ScaleChange | None = None
        self._pending_scale: ScaleChange | None = None

    def observe(self, reading: Reading) -> EnergyDelta | None:
        """Records a reading and returns the energy it revealed, if any.

        Returns ``None`` when the reading yields no energy to account for: the
        first reading of a counter (its history is unknowable), an unavailable
        source, a reading whose unit is unknown or has changed, a reading that is
        stale or contemporaneous with the last one, or a counter that simply has
        not moved. Every reading leaves one entry in the decision log (HEA-24),
        whether or not it produced energy.

        Raises:
            ValueError: if the counter reports a negative value, which a
                ``total_increasing`` energy counter cannot legitimately do.
        """
        current = self._countable(reading)
        if current is None:
            return None
        previous = self._last
        if (
            previous is None
            or current.at <= previous.at
            or self._is_a_dip(previous, current)
        ):
            self._gate(previous, current)
            return None

        held = self._before_drop
        self._before_drop = None
        self._last = current
        is_reset = current.value < previous.value
        if is_reset:
            # Read as a restart now, because that is what it usually is and a
            # cycle meter's energy should not wait on its next poll. What it
            # stood at is kept, so that if the counter comes back above it the
            # reading turns out to have been a blink (HEA-139).
            self._before_drop = _Drop(before=previous, credited=current.value)
        kwh = self._to_kwh(self._revealed(previous, current, held), current.unit)
        accrued_from = self._accrual_start(self._anchor(previous, current, held))
        if current.value != previous.value:
            self._moved_at = current.at
        if kwh == 0:
            self._log(current.at, DecisionReason.NO_MOVEMENT, None)
            return None
        if not self._credible(kwh, previous.at, current.at):
            # The counter's position is already ``current``, so the replacement
            # becomes the baseline and everything after it is counted normally.
            self._note_scale_change(previous, current)
            self._log(current.at, DecisionReason.IMPLAUSIBLE_STEP, kwh)
            return None
        reason = DecisionReason.RESET if is_reset else DecisionReason.COUNTED
        # Held rather than recorded: the accountant has the last word on this
        # delta, and only if *it* refuses does the step become evidence of a
        # rescale. A step the house can account for is not one (HEA-159).
        self._pending_scale = _scale_change(previous, current)
        self._scale_change = None
        self._log(current.at, reason, kwh)
        return EnergyDelta(kwh=kwh, start=accrued_from, end=current.at)

    def _note_scale_change(self, previous: _Observation, current: _Observation) -> None:
        """Record a refused step whose size looks like the counter's scale moving."""
        self._scale_change = _scale_change(previous, current)
        self._pending_scale = None

    def _countable(self, reading: Reading) -> _Observation | None:
        """The reading as something to count from, or ``None`` with the reason logged.

        Three ways a reading is not that, all of them about whether its number
        means anything rather than about what it reveals:

        * the source had no reading at all - ``unavailable`` or ``unknown``;
        * its unit is unknown, so the number is of unknown size. Nothing is
          remembered from it either: taking it as the baseline would silently
          discard whatever the counter climbs before the unit turns up, the same
          reasoning that has an unavailable span spanned rather than skipped;
        * its unit differs from the baseline's, which is neither a reset nor a
          step. 0.5 kWh followed by 500 Wh is one quantity renamed, and their
          difference is not a quantity at all - so the new reading becomes the
          baseline in its own unit and counting resumes from there (HEA-149).
        """
        position = self._position(reading)
        if position is None:
            self._log(reading.at, DecisionReason.UNAVAILABLE, None)
            return None
        if reading.unit is EnergyUnit.UNKNOWN:
            self._log(reading.at, DecisionReason.UNIT_UNKNOWN, None)
            return None
        current = _Observation(at=reading.at, value=position, unit=reading.unit)
        if self._last is not None and self._last.unit is not current.unit:
            self._rebaseline(current)
            self._log(current.at, DecisionReason.UNIT_CHANGED, None)
            return None
        return current

    def _rebaseline(self, current: _Observation) -> None:
        """Start again from this reading, keeping none of the old position.

        A held drop goes with it: what the counter stood at before it fell is a
        figure in the unit it has stopped counting in.
        """
        self._last = current
        self._before_drop = None
        self._moved_at = current.at

    def _gate(self, previous: _Observation | None, current: _Observation) -> None:
        """Record a reading that reveals no energy, and why.

        Three of them: the first reading of a counter, whose history is
        unknowable; one no newer than the last; and a dip small enough to be the
        same counter wobbling, where the value it really reached is kept so the
        next genuine step is measured from there (HEA-139).
        """
        if previous is None:
            self._last = current
            self._moved_at = current.at
            self._log(current.at, DecisionReason.FIRST_READING, None)
            return
        if current.at <= previous.at:
            self._log(current.at, DecisionReason.STALE, None)
            return
        # The value it really reached, carried forward at the new reading's
        # time - and in the unit the reading that reached it was counted in.
        self._last = _Observation(
            at=current.at, value=previous.value, unit=previous.unit
        )
        self._log(current.at, DecisionReason.NO_MOVEMENT, None)

    def _anchor(
        self,
        previous: _Observation,
        current: _Observation,
        held: _Drop | None,
    ) -> _Observation:
        """Which reading the energy accrued from.

        Across a blink it is the one *before* the blink: that is when the energy
        started accumulating, and anchoring on the blink itself would crush it
        into the interval the counter happened to come back in.
        """
        if held is not None and current.value > held.before.value:
            return held.before
        return previous

    def _credible(self, kwh: Decimal, previous: datetime, current: datetime) -> bool:
        """Whether a reading could be energy rather than a replaced counter.

        Weighed as power over the span the reading covers, never as energy in a
        bucket: a meter that reports once a day delivers a day's energy in one
        step, and it is telling the truth. The span is the real gap between
        readings, so a source quiet for three days is judged over three days.
        """
        span = max(current - previous, _MIN_JUDGED_SPAN)
        hours = Decimal(span.total_seconds()) / Decimal(3600)
        return kwh / hours <= CREDIBLE_POWER_KW

    def persisted_state(self) -> dict[str, Any]:
        """The counter's position, so a restart resumes rather than rebaselines.

        ``_moved_at`` travels with the reading because it anchors how far back a
        step may be spread; without it a quiet run collapses into one bucket.

        The decision log is excluded: it is the diagnostics ring, and restoring
        it would present readings this run never saw.

        The unit is the baseline's own, and has to come back with it: a position
        restored without one would be subtracted from whatever the next reading
        happens to be counted in (HEA-149).

        Distinct from :meth:`snapshot`, which builds the diagnostics view.
        """
        return {
            "unit": None if self._last is None else self._last.unit.value,
            "last": None
            if self._last is None
            else {"at": self._last.at.isoformat(), "value": str(self._last.value)},
            "moved_at": None if self._moved_at is None else self._moved_at.isoformat(),
        }

    def restore(self, data: Mapping[str, Any]) -> None:
        """Reinstates state captured by :meth:`persisted_state`.

        A snapshot written before the unit travelled with the reading carries the
        unit the source was constructed with, which is the one its baseline was
        taken in - so it restores the same way. One with no unit at all has no
        usable baseline either, and starts again.
        """
        last = data["last"]
        unit = data.get("unit")
        self._last = (
            None
            if last is None or unit is None
            else _Observation(
                at=datetime.fromisoformat(last["at"]),
                value=Decimal(last["value"]),
                unit=EnergyUnit(unit),
            )
        )
        moved_at = data["moved_at"]
        self._moved_at = None if moved_at is None else datetime.fromisoformat(moved_at)

    def _accrual_start(self, previous: _Observation) -> datetime:
        """When the energy a stepping counter reveals began accumulating.

        A counter that moves on every reading accrues between readings, so the
        answer is simply the previous one. A counter that held still while its
        source kept reporting accrued across that whole quiet run, and anchoring
        it to the last reading crushes it into a single bucket (HEA-74).

        Only the quiet run is capped. The span from the last *reading* to now is
        never trimmed: a source that fell silent for three days really did meter
        those three days, and that energy has to be spread over them.
        """
        if self._moved_at is None:
            return previous.at
        return max(self._moved_at, previous.at - self._max_quiet_span)

    def note_dropped_late(self, at: datetime, kwh: Decimal) -> None:
        """Record that a portion of energy fell past the accountant's ring (HEA-48).

        The accountant, not the source, decides a portion is unplaceable - it lands
        in a bucket already evicted from the retention ring - but the drop is logged
        here so it rides the same per-source decision log the diagnostics read.
        """
        self._log(at, DecisionReason.DROPPED_LATE, kwh)

    def note_implausible(self, at: datetime, kwh: Decimal) -> None:
        """Record energy refused because this source cannot be telling the truth.

        The accountant, not the source, makes the judgement - it needs the whole
        house to compare against - but it is logged here so the diagnostics
        download can explain a device whose figures have stopped moving (HEA-60).
        """
        self._log(at, DecisionReason.IMPLAUSIBLE, kwh)

    def _promote_pending_scale(self) -> None:
        """Take up the step the accountant has just refused, if it looked like one."""
        self._scale_change = self._pending_scale
        self._pending_scale = None

    def note_beyond_the_house(self, at: datetime, kwh: Decimal) -> None:
        """Record one delta refused for claiming more than the house was served.

        Also the accountant's judgement, and for the same reason - only it holds
        the house meter. Distinct from :meth:`note_implausible` because it says
        something narrower: not that this source has been lying, but that this
        *one* reading cannot be true. It is what a counter looks like the moment
        its scale changes, and it is followed by ordinary readings rather than by
        more of the same (HEA-157).
        """
        self._promote_pending_scale()
        self._log(at, DecisionReason.BEYOND_THE_HOUSE, kwh)

    def note_zero_priced(self, at: datetime) -> None:
        """Record that a bucket finalised before any import price was known (HEA-53).

        Costing it at zero is deliberate - the price for that instant is genuinely
        unknowable in real time - but logging it here, on the price-bearing import
        source, lets the diagnostics download explain the zero-cost early bucket.
        """
        self._log(at, DecisionReason.ZERO_PRICED, None)

    def recent_decisions(self) -> tuple[Decision, ...]:
        """The bounded log of what the engine did with recent readings."""
        return tuple(self._decisions)

    def snapshot(self) -> SourceSnapshot:
        """The source's current diagnostics state (HEA-24)."""
        return SourceSnapshot(
            scale_change=self._scale_change,
            unit=self._last.unit if self._last else EnergyUnit.UNKNOWN,
            last_value=self._last.value if self._last else None,
            last_at=self._last.at if self._last else None,
            recent_decisions=self.recent_decisions(),
        )

    def _log(self, at: datetime, reason: DecisionReason, kwh: Decimal | None) -> None:
        self._decisions.append(Decision(at=at, reason=reason, kwh=kwh))

    def _position(self, reading: Reading) -> Decimal | None:
        """Where the counter stands, or ``None`` where the source had nothing.

        Validated before the unit is considered, so a counter reporting a
        negative value is refused whether or not its unit can be read.
        """
        if reading.value is None:
            return None
        if reading.value < 0:
            msg = f"energy counter reported a negative value: {reading.value}"
            raise ValueError(msg)
        return reading.value

    def _is_a_dip(self, previous: _Observation, current: _Observation) -> bool:
        """Whether a fall is small enough to be the same counter, wobbling."""
        return (
            previous.value > 0
            and previous.value * _SAME_COUNTER_FLOOR <= current.value < previous.value
        )

    def _revealed(
        self,
        previous: _Observation,
        current: _Observation,
        held: _Drop | None,
    ) -> Decimal:
        """The energy a reading reveals, settling any drop held before it.

        A counter that comes back *above* where it stood before a drop never
        restarted: something blinked, and the energy is the rise across the
        blink, less whatever the drop was already credited with. Read as a rise
        from the blink instead, it is the whole counter arriving at once, and is
        refused as implausible - so the household loses everything used across
        it (HEA-139).

        Clamped at zero. A blink to a *figure* is credited with that figure at
        the time, and a small return above the old value cannot take it back:
        published figures never go backwards (HEA-85).
        """
        if held is None or current.value <= held.before.value:
            return self._counted(previous, current)
        return max(Decimal(0), current.value - held.before.value - held.credited)

    def _counted(self, previous: _Observation, current: _Observation) -> Decimal:
        if current.value < previous.value:
            return current.value
        return current.value - previous.value

    def _to_kwh(self, value: Decimal, unit: EnergyUnit) -> Decimal:
        if unit is EnergyUnit.WH:
            return value / _WH_PER_KWH
        return value


def _scale_change(previous: _Observation, current: _Observation) -> ScaleChange | None:
    """Whether a step looks like the counter's scale moving, and by how much.

    The ratio between the two sides of a discontinuity *is* the factor, to three
    or four figures, because a counter barely moves across one. So this is a
    measurement rather than an inference - and a ratio nowhere near a power of
    ten is itself evidence: that counter was replaced, not rescaled, and saying
    "your scale changed by 54x" would be a guess wearing a measurement's clothes.

    ``None`` where either side is zero, which is a counter starting or restarting
    rather than changing what it counts in.
    """
    if previous.value <= 0 or current.value <= 0:
        return None
    larger = max(previous.value, current.value)
    smaller = min(previous.value, current.value)
    ratio = larger / smaller
    for factor in _SCALE_FACTORS:
        if abs(ratio - factor) <= factor * _SCALE_TOLERANCE:
            return ScaleChange(
                at=current.at, factor=factor, shrank=current.value < previous.value
            )
    return None
