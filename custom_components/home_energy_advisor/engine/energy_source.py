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


class EnergyUnit(Enum):
    """The unit a device's counter reports in, normalised to kWh on the way in."""

    KWH = "kWh"
    WH = "Wh"


@dataclass(frozen=True)
class Reading:
    """One observation of a counter.

    A ``value`` of ``None`` means the source had no reading - Home Assistant's
    ``unavailable`` and ``unknown`` states, mapped by the integration layer so
    that the engine never learns Home Assistant's vocabulary.
    """

    at: datetime
    value: Decimal | None


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
    ``HELD_AFTER_DROP`` is a reading waiting on the next one: the counter fell
    past the floor, and whether it restarted or blinked is not knowable until
    something follows it (HEA-139).
    """

    COUNTED = "counted"
    RESET = "reset"
    IMPLAUSIBLE_STEP = "implausible_step"
    HELD_AFTER_DROP = "held_after_drop"
    FIRST_READING = "first_reading"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    NO_MOVEMENT = "no_movement"
    DROPPED_LATE = "dropped_late"
    ZERO_PRICED = "zero_priced"
    IMPLAUSIBLE = "implausible"


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
class SourceSnapshot:
    """A source's diagnostics state: its unit, last reading, and decision log."""

    unit: EnergyUnit
    last_value: Decimal | None
    last_at: datetime | None
    recent_decisions: tuple[Decision, ...]


@dataclass(frozen=True)
class _Drop:
    """A fall past the floor, and what it was credited with when it arrived."""

    before: _Observation
    credited: Decimal


@dataclass(frozen=True)
class _Observation:
    """A reading known to carry a value - the only kind worth remembering."""

    at: datetime
    value: Decimal


class CumulativeEnergySource:
    """Extracts energy deltas from a ``total_increasing`` counter.

    A falling counter is a reset, not negative consumption: the new value is
    taken as a fresh cycle's energy. Gaps are always attributed - a counter that
    climbs while its sensor is unavailable really did consume that energy, so it
    is reported spanning the gap rather than discarded.
    """

    def __init__(
        self,
        unit: EnergyUnit = EnergyUnit.KWH,
        *,
        max_quiet_span: timedelta = MAX_QUIET_SPAN,
    ) -> None:
        self._unit = unit
        self._last: _Observation | None = None
        # Where the counter stood before it fell past the floor, and what the
        # fall was credited with, until the next reading says whether it
        # restarted or merely blinked (HEA-139).
        self._before_drop: _Drop | None = None
        self._moved_at: datetime | None = None
        self._max_quiet_span = max_quiet_span
        self._decisions: deque[Decision] = deque(maxlen=_DECISION_LOG_SIZE)

    def observe(self, reading: Reading) -> EnergyDelta | None:
        """Records a reading and returns the energy it revealed, if any.

        Returns ``None`` when the reading yields no energy to account for: the
        first reading of a counter (its history is unknowable), an unavailable
        source, a reading that is stale or contemporaneous with the last one, or
        a counter that simply has not moved. Every reading leaves one entry in
        the decision log (HEA-24), whether or not it produced energy.

        Raises:
            ValueError: if the counter reports a negative value, which a
                ``total_increasing`` energy counter cannot legitimately do.
        """
        current = self._observation(reading)
        if current is None:
            self._log(reading.at, DecisionReason.UNAVAILABLE, None)
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
        kwh = self._to_kwh(self._revealed(previous, current, held))
        accrued_from = self._accrual_start(self._anchor(previous, current, held))
        if current.value != previous.value:
            self._moved_at = current.at
        if kwh == 0:
            self._log(current.at, DecisionReason.NO_MOVEMENT, None)
            return None
        if not self._credible(kwh, previous.at, current.at):
            # The counter's position is already ``current``, so the replacement
            # becomes the baseline and everything after it is counted normally.
            self._log(current.at, DecisionReason.IMPLAUSIBLE_STEP, kwh)
            return None
        reason = DecisionReason.RESET if is_reset else DecisionReason.COUNTED
        self._log(current.at, reason, kwh)
        return EnergyDelta(kwh=kwh, start=accrued_from, end=current.at)

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
        self._last = _Observation(at=current.at, value=previous.value)
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

        Distinct from :meth:`snapshot`, which builds the diagnostics view.
        """
        return {
            "unit": self._unit.value,
            "last": None
            if self._last is None
            else {"at": self._last.at.isoformat(), "value": str(self._last.value)},
            "moved_at": None if self._moved_at is None else self._moved_at.isoformat(),
        }

    def restore(self, data: Mapping[str, Any]) -> None:
        """Reinstates state captured by :meth:`persisted_state`."""
        last = data["last"]
        self._last = (
            None
            if last is None
            else _Observation(
                at=datetime.fromisoformat(last["at"]), value=Decimal(last["value"])
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
            unit=self._unit,
            last_value=self._last.value if self._last else None,
            last_at=self._last.at if self._last else None,
            recent_decisions=self.recent_decisions(),
        )

    def _log(self, at: datetime, reason: DecisionReason, kwh: Decimal | None) -> None:
        self._decisions.append(Decision(at=at, reason=reason, kwh=kwh))

    def _observation(self, reading: Reading) -> _Observation | None:
        if reading.value is None:
            return None
        if reading.value < 0:
            msg = f"energy counter reported a negative value: {reading.value}"
            raise ValueError(msg)
        return _Observation(at=reading.at, value=reading.value)

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

    def _to_kwh(self, value: Decimal) -> Decimal:
        if self._unit is EnergyUnit.WH:
            return value / _WH_PER_KWH
        return value
