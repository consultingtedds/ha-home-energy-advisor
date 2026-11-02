"""The schema library Home Assistant validates flows and services with.

Home Assistant is moving from voluptuous to probatio, its successor with the
same interface: 2026.9 ships it, and from 2026.10 the flow and service APIs are
typed against it. The oldest release this integration supports ships only
voluptuous (ADR-0023). Every schema here is built through this one name, so each
release is handed the library it expects (HEA-256).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import probatio as vol
else:
    try:
        import probatio as vol
    except ImportError:  # Home Assistant before 2026.9
        import voluptuous as vol

__all__ = ["vol"]
