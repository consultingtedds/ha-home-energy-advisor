"""Persists the accounting runtime so it survives a restart.

The engine produces and consumes plain JSON-safe state
(``Accountant.snapshot`` / ``Accountant.restore``); this module owns where that
state lives and how old it may be before it is refused.

A snapshot is a cache, not a source of truth. Every failure path returns
``None`` and the engine starts cold, because failing setup over an unreadable
cache would cost a household more than the accounting the cache carries.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

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


class AccountantStore:
    """Reads and writes one config entry's accounting snapshot."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.accountant"
        )

    async def async_load(self, *, now: datetime) -> dict[str, Any] | None:
        """The stored engine state, or ``None`` when there is nothing to trust.

        One return value covers never written, written by a version that shaped
        it differently, too old, and damaged: the caller answers all of them the
        same way.
        """
        try:
            stored = await self._store.async_load()
        except HomeAssistantError, ValueError, KeyError:
            return None
        if not isinstance(stored, dict):
            return None

        written_at = stored.get("written_at")
        state = stored.get("state")
        if not isinstance(written_at, str) or not isinstance(state, dict):
            return None
        try:
            written = datetime.fromisoformat(written_at)
        except ValueError:
            return None
        if now - written > MAX_SNAPSHOT_AGE:
            return None
        return state

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
