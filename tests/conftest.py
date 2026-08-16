"""Shared pytest fixtures for the Home Energy Advisor test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Let Home Assistant discover and load this custom integration in tests.

    ``recorder_db_url`` is requested first purely for ordering. It refuses to be
    created once ``hass`` exists, and this fixture is autouse - so without it
    here, ``hass`` would always be set up first and no test could ever ask for a
    real recorder (HEA-69 needs one to prove the history probe works).
    """
