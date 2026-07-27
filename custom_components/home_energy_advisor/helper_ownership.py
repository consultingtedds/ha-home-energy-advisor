"""Provenance for the native helpers HEA auto-creates (HEA-52).

Every Integral / utility_meter helper HEA tracks is one of two kinds:

* **created** — HEA made it, so HEA may delete it on device removal or uninstall.
* **adopted** — a helper the user already had over the same source, which HEA
  merely reuses. Deleting it would destroy the user's own config, so HEA must
  never remove it.

The owned maps persisted on the config entry therefore store a small provenance
record per helper — ``{"id": entry_id, "created": bool}`` — instead of a bare id.
Records written before HEA-52 are plain id strings; those predate any adoption
(the reuse-by-source-match that could grab a user's helper is what HEA-52 fixes),
so a legacy record is read as *created* — existing HEA-made helpers still get
cleaned up, and provenance is tracked correctly for every helper from here on.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# One tracked helper on the entry's owned map: a provenance record, or (from
# entries written before HEA-52) a bare config-entry-id string.
type OwnedHelper = dict[str, Any]


def owned_helper(entry_id: str, *, created: bool) -> OwnedHelper:
    """A provenance record for one tracked helper."""
    return {"id": entry_id, "created": created}


def helper_entry_id(record: object) -> str:
    """The helper's config entry id, tolerating the legacy bare-string form."""
    if isinstance(record, Mapping):
        return str(record["id"])
    return str(record)


def helper_was_created(record: object) -> bool:
    """Whether HEA created this helper (and so may delete it).

    Legacy bare-string records predate provenance and are treated as created.
    """
    if isinstance(record, Mapping):
        return bool(record["created"])
    return True


def resolve_provenance(
    prior: object | None, entry_id: str, *, pre_existing: str | None
) -> OwnedHelper:
    """Provenance for a helper HEA just ensured over a source.

    Sticky across reloads: if the entry already tracked this exact helper, its
    recorded provenance is kept (HEA's own helper still exists on reload, so it
    must not be re-read as adopted). Otherwise the helper is *created* only if
    nothing already existed over the source — a pre-existing helper is adopted.
    """
    if prior is not None and helper_entry_id(prior) == entry_id:
        created = helper_was_created(prior)
    else:
        created = pre_existing is None
    return owned_helper(entry_id, created=created)
