"""Repairs issue registry for Home Energy Advisor (HEA-24).

The single home for the integration's issue keys and the thin wrappers that raise
and clear them, so every caller uses the same translation keys and severity - the
coordinator (runtime health of sources, the price entity, and the Untracked
remainder) and the helper-sync modules (a native helper the user deleted, which
HEA re-created). Every issue is informational (``is_fixable=False``): the fix is
always an action in Home Assistant itself, never a flow this integration drives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Translation keys - each has a matching block under ``issues`` in strings.json.
ISSUE_SOURCE_REMOVED = "source_removed"
ISSUE_SOURCE_UNAVAILABLE = "source_unavailable"
ISSUE_SOURCE_NEVER_REPORTED = "source_never_reported"
ISSUE_PRICE_UNAVAILABLE = "price_unavailable"
ISSUE_HELPER_RECREATED = "helper_recreated"
ISSUE_CYCLE_HELPER_RECREATED = "cycle_helper_recreated"
# Replaces the old negative-remainder issue, which fired on over-drawn buckets.
# Those are now carried and repaid rather than clamped (ADR-0015), so they are
# ordinary coarse-counter timing rather than a fault; what is worth telling a
# household about is a disagreement that never reconciles (HEA-82).
ISSUE_UNRECONCILED_ENERGY = "unreconciled_energy"
ISSUE_IMPLAUSIBLE_SOURCE = "implausible_source"
ISSUE_IMPLAUSIBLE_STEP = "implausible_step"


def source_removed_issue_id(entity_id: str) -> str:
    """Stable issue id for a configured entity that has left the registry."""
    return f"{ISSUE_SOURCE_REMOVED}_{entity_id}"


def source_unavailable_issue_id(entity_id: str) -> str:
    """Stable issue id for a critical input unavailable past the grace period."""
    return f"{ISSUE_SOURCE_UNAVAILABLE}_{entity_id}"


def source_never_reported_issue_id(entity_id: str) -> str:
    """Stable issue id for a device source that has never produced a reading."""
    return f"{ISSUE_SOURCE_NEVER_REPORTED}_{entity_id}"


def helper_recreated_issue_id(subentry_id: str) -> str:
    """Stable issue id for a device whose deleted Integral helper was re-created."""
    return f"{ISSUE_HELPER_RECREATED}_{subentry_id}"


def implausible_source_issue_id(name: str) -> str:
    """Stable issue id for a device whose source claims more than the house."""
    return f"{ISSUE_IMPLAUSIBLE_SOURCE}_{name}"


def implausible_step_issue_id(entity_id: str) -> str:
    """Stable issue id for an input whose counter leapt and was not counted."""
    return f"{ISSUE_IMPLAUSIBLE_STEP}_{entity_id}"


def async_raised_subjects(hass: HomeAssistant, translation_key: str) -> set[str]:
    """Every subject this integration is currently accusing under one issue key.

    The subject is whatever the id builders above append - a device name, an
    entity id. An issue outlives the run that raised it, so a check that retracts
    only what it raised itself can never withdraw one left standing by an earlier
    run: the accusation becomes permanent, and a household who has since deleted
    the device or repointed the sensor has no way to answer it (HEA-146).

    Reading the registry back at startup gives a check the same view of its own
    outstanding accusations that it had before the restart, so the ordinary
    clearing path can reach them.
    """
    prefix = f"{translation_key}_"
    return {
        issue_id.removeprefix(prefix)
        for domain, issue_id in ir.async_get(hass).issues
        if domain == DOMAIN and issue_id.startswith(prefix)
    }


def async_raise(
    hass: HomeAssistant,
    issue_id: str,
    translation_key: str,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Raise (or refresh) an informational Repairs issue. Idempotent per id."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )


def async_clear(hass: HomeAssistant, issue_id: str) -> None:
    """Delete a previously raised issue; a no-op if it is not present."""
    ir.async_delete_issue(hass, DOMAIN, issue_id)
