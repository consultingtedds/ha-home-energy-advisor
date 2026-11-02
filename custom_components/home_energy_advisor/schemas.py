"""The schema library Home Assistant validates flows and services with.

Home Assistant is moving from voluptuous to probatio, its successor with the
same interface: 2026.9 ships it, and from 2026.10 the flow and service APIs
validate with it. The oldest release this integration supports uses only
voluptuous (ADR-0023). Every schema here is built through this one name, so each
release is handed the library it validates with (HEA-256).

Chosen by Home Assistant's version, never by what happens to be importable: an
older Home Assistant can have probatio installed beside it, by another
integration or an upgrade that was rolled back, and a probatio schema handed to a
voluptuous flow is refused outright.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import MAJOR_VERSION, MINOR_VERSION

if TYPE_CHECKING or (MAJOR_VERSION, MINOR_VERSION) >= (2026, 10):
    import probatio as vol
else:
    import voluptuous as vol

__all__ = ["vol"]
