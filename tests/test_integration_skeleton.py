from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

INTEGRATION_ROOT = (
    Path(__file__).parent.parent / "custom_components" / "home_energy_advisor"
)


def _manifest() -> dict[str, Any]:
    contents: dict[str, Any] = json.loads(
        (INTEGRATION_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    return contents


def test_integration_package_imports_without_a_home_assistant_instance() -> None:
    # Given / When — the package is imported the way Home Assistant loads it
    module = importlib.import_module("custom_components.home_energy_advisor")

    # Then — it loads standalone; nothing at import time reaches for a running hass
    assert module.__name__ == "custom_components.home_energy_advisor"


def test_manifest_domain_matches_the_package_directory() -> None:
    # Given — the manifest shipped inside the integration package
    manifest = _manifest()

    # When / Then — Home Assistant resolves an integration by directory name, so a
    # domain that disagrees with it silently fails to load
    assert manifest["domain"] == INTEGRATION_ROOT.name


def test_manifest_declares_config_flow_only_when_the_flow_module_exists() -> None:
    # Given — the manifest, which does not yet opt into a config flow
    manifest = _manifest()

    # When — we compare the declaration against the files actually shipped
    declares_config_flow = manifest.get("config_flow", False)
    ships_config_flow = (INTEGRATION_ROOT / "config_flow.py").exists()

    # Then — the two move together: `config_flow: true` without a config_flow.py
    # makes Home Assistant fail to set up the entry at runtime
    assert declares_config_flow == ships_config_flow
