"""Repairs issue registry for Home Energy Advisor (HEA-24).

The single home for the integration's issue keys and the thin wrappers that raise
and clear them, so every caller uses the same translation keys and severity — the
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

# Translation keys — each has a matching block under ``issues`` in strings.json.
ISSUE_SOURCE_REMOVED = "source_removed"
ISSUE_SOURCE_UNAVAILABLE = "source_unavailable"
ISSUE_PRICE_UNAVAILABLE = "price_unavailable"
ISSUE_HELPER_RECREATED = "helper_recreated"
ISSUE_CYCLE_HELPER_RECREATED = "cycle_helper_recreated"
ISSUE_NEGATIVE_REMAINDER = "negative_remainder"


def source_removed_issue_id(entity_id: str) -> str:
    """Stable issue id for a configured entity that has left the registry."""
    return f"{ISSUE_SOURCE_REMOVED}_{entity_id}"


def source_unavailable_issue_id(entity_id: str) -> str:
    """Stable issue id for a critical input unavailable past the grace period."""
    return f"{ISSUE_SOURCE_UNAVAILABLE}_{entity_id}"


def helper_recreated_issue_id(subentry_id: str) -> str:
    """Stable issue id for a device whose deleted Integral helper was re-created."""
    return f"{ISSUE_HELPER_RECREATED}_{subentry_id}"


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
