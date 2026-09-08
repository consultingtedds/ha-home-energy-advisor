"""Persists the accounting runtime so it survives a restart.

The engine produces and consumes plain JSON-safe state
(``Accountant.snapshot`` / ``Accountant.restore``); this module owns where that
state lives and how old it may be before it is refused.

A snapshot is a cache, not a source of truth. Every failure path starts the
engine cold, because failing setup over an unreadable cache would cost a
household more than the accounting the cache carries. Each of those paths
reports *why*: refusing a snapshot changes what the next discharge costs, and
diagnostics have to be able to explain a cost figure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

# Matches the engine's retained ring. Past it the open buckets and retained
# context inside describe intervals the accounting can no longer reach, and the
# battery's state of charge has moved on unobserved, so an empty ledger that
# heals within a cycle beats a confidently wrong one.
MAX_SNAPSHOT_AGE = timedelta(hours=24)

# Home Assistant's Store keeps the earliest pending deadline and flushes on
# EVENT_HOMEASSISTANT_FINAL_WRITE, so this bounds what a crash loses while a
# clean shutdown always writes a current snapshot.
SAVE_DELAY = 300


class SnapshotStatus(StrEnum):
    """What became of the previous run's accounting on this startup."""

    RESTORED = "restored"
    # No file yet: a first install, or the first start on a version that writes
    # one. Expected, and the only status that is not worth a log line.
    ABSENT = "absent"
    STALE = "stale"
    # Present but not the shape this version reads - unstamped, undated, or
    # damaged.
    UNREADABLE = "unreadable"
    # Readable here, but the engine could not restore it.
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class SnapshotLoad:
    """The outcome of reading a snapshot, and how old it was."""

    state: dict[str, Any] | None
    status: SnapshotStatus
    age: timedelta | None = None


class AccountantStore:
    """Reads and writes one config entry's accounting snapshot."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        # Deliberately untyped contents: what comes back is whatever is on disk,
        # which a partial write or an older build may have shaped differently.
        # Declaring it as the mapping we expect would make the checks below look
        # redundant to a type checker and unguarded at runtime.
        self._store = Store[Any](
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.accountant"
        )

    async def async_load(self, *, now: datetime) -> SnapshotLoad:
        """The stored engine state, and why it was refused when it is missing.

        Every caller responds to a refusal the same way - start cold - but they
        are not the same event to a household reading diagnostics, so the reason
        travels with the answer rather than collapsing into ``None``.
        """
        try:
            stored = await self._store.async_load()
        except HomeAssistantError, ValueError, KeyError:
            return self._refused(SnapshotStatus.UNREADABLE)
        if stored is None:
            return SnapshotLoad(state=None, status=SnapshotStatus.ABSENT)

        written = self._written_at(stored)
        state = stored.get("state") if isinstance(stored, dict) else None
        if written is None or not isinstance(state, dict):
            return self._refused(SnapshotStatus.UNREADABLE)

        age = now - written
        if age > MAX_SNAPSHOT_AGE:
            return self._refused(SnapshotStatus.STALE, age)
        return SnapshotLoad(state=state, status=SnapshotStatus.RESTORED, age=age)

    @staticmethod
    def _written_at(stored: object) -> datetime | None:
        """When the snapshot was written, or ``None`` if that cannot be read.

        An age that cannot be established is the one case the limit exists to
        stop, so an unreadable stamp is refused rather than assumed fresh.
        """
        if not isinstance(stored, dict):
            return None
        written_at = stored.get("written_at")
        if not isinstance(written_at, str):
            return None
        try:
            return datetime.fromisoformat(written_at)
        except ValueError:
            return None

    @staticmethod
    def _refused(status: SnapshotStatus, age: timedelta | None = None) -> SnapshotLoad:
        """Records a refusal in the log on the way past."""
        if status is SnapshotStatus.STALE:
            _LOGGER.warning(
                "Accounting snapshot is %s old, past the %s limit, so accounting "
                "resumes from the sensors' restored totals. Energy metered while "
                "Home Assistant was down is not counted, and battery discharge is "
                "priced at zero until the stored-cost ledger refills",
                age,
                MAX_SNAPSHOT_AGE,
            )
        else:
            _LOGGER.warning(
                "Accounting snapshot could not be read, so accounting resumes "
                "from the sensors' restored totals"
            )
        return SnapshotLoad(state=None, status=status, age=age)

    async def async_save(self, state: dict[str, Any], *, now: datetime) -> None:
        """Writes a snapshot immediately, stamped so its age can be judged."""
        await self._store.async_save(self._envelope(state, now))

    def async_schedule_save(
        self,
        state_func: Callable[[], dict[str, Any]],
        *,
        now_func: Callable[[], datetime],
    ) -> None:
        """Queues a write, coalescing the calls the finalisation tick makes.

        The state is read when the write happens, so a queued save stores the
        newest accounting rather than whatever was current when it was asked for.
        """
        self._store.async_delay_save(
            lambda: self._envelope(state_func(), now_func()), SAVE_DELAY
        )

    async def async_remove(self) -> None:
        """Deletes the snapshot, so a reinstall does not inherit old totals."""
        await self._store.async_remove()

    @staticmethod
    def _envelope(state: dict[str, Any], now: datetime) -> dict[str, Any]:
        return {"written_at": now.isoformat(), "state": state}
