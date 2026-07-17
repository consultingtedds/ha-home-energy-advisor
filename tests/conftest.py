"""Shared pytest fixtures for the Home Energy Advisor test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Let Home Assistant discover and load this custom integration in tests."""
