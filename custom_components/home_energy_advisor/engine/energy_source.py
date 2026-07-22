"""Turns a device's cumulative energy counter into discrete, time-spanned deltas.

Home Assistant's ``total_increasing`` counters come in two flavours on real
hardware: lifetime counters that climb for years (Zigbee plugs) and counters
that reset constantly (the WF-RAC aircons restart every compressor cycle, Tuya's
daily counters roll over at midnight). Both are handled by one rule, validated
against real instance data in ``docs/notes/AIRCON_COST_EXPLORATION.md``.

Deltas carry the span they accumulated over, not just a magnitude. A sensor that
was unavailable for three days reports one large jump on recovery; attributing
that energy to the instant it was reported would price it all at whatever tariff
happened to be active then. The interval ledger spreads it across the span
instead.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

_WH_PER_KWH = Decimal(1000)

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

    A ``value`` of ``None`` means the source had no reading — Home Assistant's
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
    duplicate timestamp, or a counter that simply did not move).
    """

    COUNTED = "counted"
    RESET = "reset"
    FIRST_READING = "first_reading"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    NO_MOVEMENT = "no_movement"


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
class _Observation:
    """A reading known to carry a value — the only kind worth remembering."""

    at: datetime
    value: Decimal


class CumulativeEnergySource:
    """Extracts energy deltas from a ``total_increasing`` counter.

    A falling counter is a reset, not negative consumption: the new value is
    taken as a fresh cycle's energy. Gaps are always attributed — a counter that
    climbs while its sensor is unavailable really did consume that energy, so it
    is reported spanning the gap rather than discarded.
    """

    def __init__(self, unit: EnergyUnit = EnergyUnit.KWH) -> None:
        self._unit = unit
        self._last: _Observation | None = None
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
        if previous is None:
            self._last = current
            self._log(current.at, DecisionReason.FIRST_READING, None)
            return None
        if current.at <= previous.at:
            self._log(current.at, DecisionReason.STALE, None)
            return None

        self._last = current
        is_reset = current.value < previous.value
        kwh = self._to_kwh(self._counted(previous, current))
        if kwh == 0:
            self._log(current.at, DecisionReason.NO_MOVEMENT, None)
            return None
        reason = DecisionReason.RESET if is_reset else DecisionReason.COUNTED
        self._log(current.at, reason, kwh)
        return EnergyDelta(kwh=kwh, start=previous.at, end=current.at)

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

    def _counted(self, previous: _Observation, current: _Observation) -> Decimal:
        if current.value < previous.value:
            return current.value
        return current.value - previous.value

    def _to_kwh(self, value: Decimal) -> Decimal:
        if self._unit is EnergyUnit.WH:
            return value / _WH_PER_KWH
        return value
