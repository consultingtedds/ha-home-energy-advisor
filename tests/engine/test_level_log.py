"""What the battery's level read, kept for the diagnostics download (HEA-212).

The battery's loss is measured against its level, and on GitHub 34 every round
of the investigation needed the household to export the level's history by hand,
because nothing the download carried could say what it had read. The level is
read once a minute and is unchanged almost every time, so the log keeps a reading
only when what was read, or what was made of it, changes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.level_log import (
    LevelLog,
    LevelReason,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def test_a_reading_is_kept_only_when_it_changes() -> None:
    # Given - a level read every minute that holds at 50% for three minutes, goes
    # unavailable twice, then comes back
    log = LevelLog()
    log.record(at(0), "50", Decimal("2.5"), LevelReason.USED)
    log.record(at(1), "50", Decimal("2.5"), LevelReason.USED)
    log.record(at(2), "50", Decimal("2.5"), LevelReason.USED)
    log.record(at(3), "unavailable", None, LevelReason.UNAVAILABLE)
    log.record(at(4), "unavailable", None, LevelReason.UNAVAILABLE)
    log.record(at(5), "51", Decimal("2.55"), LevelReason.USED)

    # When / Then - one entry for each thing that happened, dated when it began
    assert log.diagnostics() == [
        {
            "at": "2026-07-08T22:00:00+00:00",
            "state": "50",
            "kwh": "2.5",
            "reason": "used",
        },
        {
            "at": "2026-07-08T22:03:00+00:00",
            "state": "unavailable",
            "kwh": None,
            "reason": "unavailable",
        },
        {
            "at": "2026-07-08T22:05:00+00:00",
            "state": "51",
            "kwh": "2.55",
            "reason": "used",
        },
    ]


def test_a_reading_that_is_not_a_percentage_says_so() -> None:
    # Given / When - a level reading 150, which is not a percentage read badly
    # but no percentage at all, so it is refused rather than clamped
    log = LevelLog()
    log.record(at(0), "150", None, LevelReason.NOT_A_PERCENTAGE)

    # Then - kept, with what was read and why nothing was made of it
    assert log.diagnostics() == [
        {
            "at": "2026-07-08T22:00:00+00:00",
            "state": "150",
            "kwh": None,
            "reason": "not_a_percentage",
        }
    ]


def test_the_log_keeps_the_most_recent_readings() -> None:
    # Given - a small log, and more changes than it holds
    log = LevelLog(size=3)
    for minute, percent in enumerate(("40", "41", "42", "43", "44")):
        log.record(at(minute), percent, Decimal(percent) / 20, LevelReason.USED)

    # When / Then - the newest three, oldest first
    assert [entry["state"] for entry in log.diagnostics()] == ["42", "43", "44"]
