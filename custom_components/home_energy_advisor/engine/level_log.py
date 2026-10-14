"""What the battery's level read, for the diagnostics download (HEA-212).

The battery's loss is measured against its level, and on GitHub 34 every round of
the investigation needed the household to export the level's history by hand,
because nothing the download carried could say what it had read.

The level is read once a minute and is unchanged almost every time, so a reading
is kept only when what was read, or what was made of it, changes. A battery that
cycles every day moves about a hundred and fifty times, so the default size
holds roughly two days - enough to cover a report sent the day after something
was noticed.

Not persisted: it is a diagnostics ring, like the meters' decision logs, and a
restart starting it afresh loses nothing any figure depends on.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal

_LOG_SIZE = 300


class LevelReason(Enum):
    """What was made of a reading."""

    USED = "used"
    UNAVAILABLE = "unavailable"
    # Outside 0-100, or not a number: refused rather than clamped, because a
    # reading that is not a percentage is not a percentage read badly.
    NOT_A_PERCENTAGE = "not_a_percentage"


@dataclass(frozen=True)
class _Reading:
    at: datetime
    state: str | None
    kwh: Decimal | None
    reason: LevelReason


class LevelLog:
    """The battery level's recent readings, kept where they change."""

    def __init__(self, size: int = _LOG_SIZE) -> None:
        self._readings: deque[_Reading] = deque(maxlen=size)

    def record(
        self,
        at: datetime,
        state: str | None,
        kwh: Decimal | None,
        reason: LevelReason,
    ) -> None:
        """Keep a reading, unless it says what the last one already did."""
        last = self._readings[-1] if self._readings else None
        if last is not None and (last.state, last.reason) == (state, reason):
            return
        self._readings.append(_Reading(at=at, state=state, kwh=kwh, reason=reason))

    def diagnostics(self) -> list[dict[str, str | None]]:
        """The readings as JSON-safe primitives, oldest first."""
        return [
            {
                "at": reading.at.isoformat(),
                "state": reading.state,
                "kwh": None if reading.kwh is None else str(reading.kwh),
                "reason": reading.reason.value,
            }
            for reading in self._readings
        ]
