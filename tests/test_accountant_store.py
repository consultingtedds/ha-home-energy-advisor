"""The accountant snapshot's file on disk, and when it is refused (HEA-111)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.home_energy_advisor.accountant_store import (
    MAX_SNAPSHOT_AGE,
    STORAGE_VERSION,
    AccountantStore,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
_STATE = {"battery": {"stored_kwh": "4.5", "stored_cost": "0.4185"}}


def _stored(hass_storage: dict[str, Any], entry_id: str) -> dict[str, Any]:
    stored: dict[str, Any] = hass_storage[f"home_energy_advisor.{entry_id}.accountant"]
    return stored


async def test_a_saved_snapshot_is_read_back_unchanged(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a store for one config entry
    store = AccountantStore(hass, "entry-1")

    # When - a snapshot is written and read back within the age limit
    await store.async_save(_STATE, now=NOW)
    loaded = await store.async_load(now=NOW + timedelta(minutes=5))

    # Then - it survives the round trip exactly, so the engine restores what it
    # actually held rather than a lossy copy of it
    assert loaded == _STATE
    assert _stored(hass_storage, "entry-1")["version"] == STORAGE_VERSION


async def test_a_snapshot_older_than_the_age_limit_is_refused(
    hass: HomeAssistant,
) -> None:
    # Given - a snapshot written before a long outage
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)

    # When - Home Assistant comes back after longer than the limit
    loaded = await store.async_load(now=NOW + MAX_SNAPSHOT_AGE + timedelta(minutes=1))

    # Then - it is refused. Open buckets a day old would attribute fresh energy
    # to intervals long gone, and a battery ledger from before the outage
    # describes charge the household has since cycled without us watching.
    assert loaded is None


async def test_a_snapshot_at_exactly_the_age_limit_is_still_used(
    hass: HomeAssistant,
) -> None:
    # Given - a snapshot written exactly the limit ago
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)

    # When / Then - the boundary is inclusive, so the rule has one unambiguous
    # reading rather than a second's worth of undefined behaviour
    assert await store.async_load(now=NOW + MAX_SNAPSHOT_AGE) == _STATE


async def test_no_snapshot_at_all_loads_as_a_cold_start(hass: HomeAssistant) -> None:
    # Given - a household that has never run a version that writes snapshots
    store = AccountantStore(hass, "never-run")

    # When / Then - absence is not an error: it is the upgrade path, and every
    # existing install takes it exactly once
    assert await store.async_load(now=NOW) is None


async def test_a_snapshot_missing_its_timestamp_is_refused(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored file whose age cannot be established
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)
    _stored(hass_storage, "entry-1")["data"].pop("written_at")

    # When / Then - refused rather than assumed fresh. Guessing would restore a
    # snapshot of unknown age, which is the one case the age limit exists to stop
    assert await store.async_load(now=NOW) is None


async def test_a_snapshot_with_an_unparseable_timestamp_is_refused(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored file whose timestamp is not a date
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)
    _stored(hass_storage, "entry-1")["data"]["written_at"] = "the day before"

    # When / Then - refused, for the same reason a missing one is: an age that
    # cannot be read cannot be checked against the limit
    assert await store.async_load(now=NOW) is None


async def test_an_unreadable_snapshot_is_refused_rather_than_raised(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored file that is not the shape this version writes
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)
    hass_storage["home_energy_advisor.entry-1.accountant"]["data"] = "not a mapping"

    # When / Then - a corrupt snapshot degrades to a cold start. Setup failing on
    # it would take the whole integration down over a cache, and the household
    # would lose the accounting the snapshot exists to protect.
    assert await store.async_load(now=NOW) is None


async def test_removing_the_entry_removes_its_snapshot(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored snapshot for an entry being deleted
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)

    # When - the integration is removed
    await store.async_remove()

    # Then - nothing is left behind to be restored onto a later reinstall, which
    # would silently reinstate totals the household deleted the integration to be
    # rid of
    assert "home_energy_advisor.entry-1.accountant" not in hass_storage
