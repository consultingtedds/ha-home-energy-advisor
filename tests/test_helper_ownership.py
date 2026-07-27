"""Provenance records for auto-created helpers (HEA-52).

Pins the created-vs-adopted rules that decide whether HEA may delete a native
helper on cleanup — the difference between tidying up after itself and destroying
a helper the user made themselves.
"""

from __future__ import annotations

from custom_components.home_energy_advisor.helper_ownership import (
    helper_entry_id,
    helper_was_created,
    owned_helper,
    resolve_provenance,
)


def test_a_created_record_round_trips() -> None:
    record = owned_helper("abc123", created=True)
    assert helper_entry_id(record) == "abc123"
    assert helper_was_created(record) is True


def test_an_adopted_record_is_never_treated_as_created() -> None:
    record = owned_helper("def456", created=False)
    assert helper_entry_id(record) == "def456"
    assert helper_was_created(record) is False


def test_a_legacy_bare_id_is_read_as_created() -> None:
    # Records written before HEA-52 are bare id strings; treat them as created so
    # existing HEA-made helpers still get cleaned up.
    assert helper_entry_id("legacy-id") == "legacy-id"
    assert helper_was_created("legacy-id") is True


def test_a_freshly_created_helper_is_recorded_created() -> None:
    # Nothing pre-existed over the source, so HEA made it.
    record = resolve_provenance(None, "new-id", pre_existing=None)
    assert record == owned_helper("new-id", created=True)


def test_a_freshly_adopted_helper_is_recorded_adopted() -> None:
    # A helper already existed over the source and HEA is seeing it for the first
    # time (no prior record) — it is the user's, so adopted.
    record = resolve_provenance(None, "users-id", pre_existing="users-id")
    assert record == owned_helper("users-id", created=False)


def test_provenance_is_sticky_across_a_reload() -> None:
    # On reload HEA's own created helper still exists, so source-match finds it —
    # but the prior record pins it as created, not re-read as adopted.
    prior = owned_helper("mine", created=True)
    record = resolve_provenance(prior, "mine", pre_existing="mine")
    assert record == owned_helper("mine", created=True)

    # And an adopted helper stays adopted across reloads.
    prior_adopted = owned_helper("theirs", created=False)
    record = resolve_provenance(prior_adopted, "theirs", pre_existing="theirs")
    assert record == owned_helper("theirs", created=False)


def test_a_legacy_record_becomes_created_on_first_reconcile() -> None:
    # A pre-HEA-52 bare-id record for a still-tracked helper migrates to a created
    # provenance record (the common case: HEA made it).
    record = resolve_provenance("legacy-id", "legacy-id", pre_existing="legacy-id")
    assert record == owned_helper("legacy-id", created=True)
