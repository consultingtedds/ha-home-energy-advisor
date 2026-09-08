"""The accountant snapshot's file on disk, and when it is refused."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.home_energy_advisor.accountant_store import (
    MAX_SNAPSHOT_AGE,
    STORAGE_VERSION,
    AccountantStore,
    SnapshotStatus,
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
    assert loaded.state == _STATE
    assert loaded.status is SnapshotStatus.RESTORED
    assert _stored(hass_storage, "entry-1")["version"] == STORAGE_VERSION


async def test_a_snapshot_older_than_the_age_limit_is_refused_and_says_so(
    hass: HomeAssistant,
) -> None:
    # Given - a snapshot written before a long outage
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)

    # When - Home Assistant comes back after longer than the limit
    loaded = await store.async_load(now=NOW + MAX_SNAPSHOT_AGE + timedelta(minutes=1))

    # Then - it is refused. Open buckets a day old would attribute fresh energy
    # to intervals long gone, and a battery ledger from before the outage
    # describes charge the household has since cycled unobserved.
    assert loaded.state is None

    # ...and the reason is reported, not swallowed. This is the case where the
    # figures visibly change behaviour - the battery ledger empties and discharge
    # goes back to costing nothing - so a household that cannot see why is left
    # with an unexplained cost figure.
    assert loaded.status is SnapshotStatus.STALE
    assert loaded.age == MAX_SNAPSHOT_AGE + timedelta(minutes=1)


async def test_a_snapshot_at_exactly_the_age_limit_is_still_used(
    hass: HomeAssistant,
) -> None:
    # Given - a snapshot written exactly the limit ago
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)

    # When / Then - the boundary is inclusive, so the rule has one unambiguous
    # reading rather than a second's worth of undefined behaviour
    loaded = await store.async_load(now=NOW + MAX_SNAPSHOT_AGE)
    assert loaded.state == _STATE
    assert loaded.status is SnapshotStatus.RESTORED


async def test_no_snapshot_at_all_loads_as_a_cold_start(hass: HomeAssistant) -> None:
    # Given - a household that has never run a version that writes snapshots
    store = AccountantStore(hass, "never-run")

    # When
    loaded = await store.async_load(now=NOW)

    # Then - absence is the upgrade path every existing install takes exactly
    # once, so it is reported as its own status rather than as a fault
    assert loaded.state is None
    assert loaded.status is SnapshotStatus.ABSENT
    assert loaded.age is None


async def test_a_snapshot_missing_its_timestamp_is_refused(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored file whose age cannot be established
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)
    _stored(hass_storage, "entry-1")["data"].pop("written_at")

    # When / Then - refused rather than assumed fresh. Guessing would restore a
    # snapshot of unknown age, which is the one case the age limit exists to stop
    loaded = await store.async_load(now=NOW)
    assert loaded.state is None
    assert loaded.status is SnapshotStatus.UNREADABLE


async def test_a_snapshot_with_an_unparseable_timestamp_is_refused(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    # Given - a stored file whose timestamp is not a date
    store = AccountantStore(hass, "entry-1")
    await store.async_save(_STATE, now=NOW)
    _stored(hass_storage, "entry-1")["data"]["written_at"] = "the day before"

    # When / Then - refused, for the same reason a missing one is: an age that
    # cannot be read cannot be checked against the limit
    loaded = await store.async_load(now=NOW)
    assert loaded.state is None
    assert loaded.status is SnapshotStatus.UNREADABLE


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
    loaded = await store.async_load(now=NOW)
    assert loaded.state is None
    assert loaded.status is SnapshotStatus.UNREADABLE


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
