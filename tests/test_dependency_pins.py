"""Drift guards for tool versions that are pinned in more than one file.

Two pins are recorded twice, and nothing in the toolchain relates the copies,
so they drift silently:

* ``pytest-homeassistant-custom-component`` is pinned in
  ``requirements_test.txt`` and again in the CI test matrix - and the test job
  installs the matrix value *over* the requirements one. Bumping the
  requirements file alone is therefore undone in the only job that runs the
  suite, which then passes against a Home Assistant nobody declared.
* ``ruff`` is pinned in ``requirements_test.txt`` and again as the
  ``ruff-pre-commit`` rev. Bumping one alone leaves the local hook formatting
  code the way CI then refuses to accept.

Dependabot ignores the first pair (a phacc bump is a supported-floor decision,
not a chore) and bumps the second. A ruff PR therefore arrives red until its
pre-commit rev is updated on the same branch - that is the intended signal,
not a fault. See HEA-71.

The parser tests below are not ceremony. The failure that would matter most
here is a silent one: a matcher that quietly stops matching would make every
drift check pass vacuously. Each parser is therefore pinned on what it returns
when the version it looks for is absent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import yaml

REPO_ROOT: Final = Path(__file__).parent.parent
PHACC: Final = "pytest-homeassistant-custom-component"
RUFF_PRE_COMMIT_REPO: Final = "https://github.com/astral-sh/ruff-pre-commit"


def requirement_pin(requirements: str, package: str) -> str | None:
    """Return the version ``package`` is pinned to, or None if it is absent."""
    match = re.search(
        rf"^{re.escape(package)}==(\S+)\s*$", requirements, flags=re.MULTILINE
    )
    return match.group(1) if match else None


def ci_matrix_phacc_pins(workflow: str) -> list[str]:
    """Return the phacc pin from every entry of the CI test matrix."""
    document: dict[str, Any] = yaml.safe_load(workflow)
    include = document["jobs"]["test"]["strategy"]["matrix"]["include"]
    return [str(entry["phacc"]) for entry in include if "phacc" in entry]


def pre_commit_rev(config: str, repo: str) -> str | None:
    """Return the rev ``repo`` is pinned to, or None if it is not configured."""
    document: dict[str, Any] = yaml.safe_load(config)
    for entry in document["repos"]:
        if entry["repo"] == repo:
            return str(entry["rev"])
    return None


def test_requirement_pin_reads_the_version_for_the_named_package() -> None:
    # Given - a requirements file pinning ruff alongside the other tools
    requirements = f"{PHACC}==0.13.346\n\nruff==0.15.21\nmypy==2.2.0\n"

    # When - the ruff pin is read
    pin = requirement_pin(requirements, "ruff")

    # Then
    assert pin == "0.15.21"


def test_requirement_pin_is_none_when_the_package_is_absent() -> None:
    # Given - a requirements file with no ruff pin at all
    requirements = "mypy==2.2.0\n"

    # When / Then - a missing pin must be visible, not silently treated as a match
    assert requirement_pin(requirements, "ruff") is None


def test_requirement_pin_ignores_a_package_whose_name_merely_starts_the_same() -> None:
    # Given - a requirements file pinning ruff-lsp but not ruff itself
    requirements = "ruff-lsp==0.0.62\n"

    # When / Then - matching the wrong line would compare two unrelated versions
    assert requirement_pin(requirements, "ruff") is None


def test_ci_matrix_phacc_pins_reads_the_pin_from_every_matrix_entry() -> None:
    # Given - a test job whose matrix covers a supported floor and the latest
    workflow = """
jobs:
  test:
    strategy:
      matrix:
        include:
          - ha-version: "2026.6.1"
            phacc: "0.13.300"
          - ha-version: "2026.7.2"
            phacc: "0.13.346"
"""

    # When - the matrix pins are read
    pins = ci_matrix_phacc_pins(workflow)

    # Then
    assert pins == ["0.13.300", "0.13.346"]


def test_ci_matrix_phacc_pins_is_empty_when_no_entry_pins_phacc() -> None:
    # Given - a matrix that varies something other than the phacc version
    workflow = """
jobs:
  test:
    strategy:
      matrix:
        include:
          - python-version: "3.14"
"""

    # When / Then - an empty result must fail the drift check, not satisfy it
    assert ci_matrix_phacc_pins(workflow) == []


def test_pre_commit_rev_reads_the_rev_pinned_for_the_named_repo() -> None:
    # Given - a hook config pinning ruff-pre-commit among other repos
    config = f"""
repos:
  - repo: {RUFF_PRE_COMMIT_REPO}
    rev: v0.15.21
    hooks:
      - id: ruff-check
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-yaml
"""

    # When - the ruff rev is read
    rev = pre_commit_rev(config, RUFF_PRE_COMMIT_REPO)

    # Then
    assert rev == "v0.15.21"


def test_pre_commit_rev_is_none_when_the_repo_is_not_configured() -> None:
    # Given - a hook config with no ruff hook at all
    config = """
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-yaml
"""

    # When / Then - a missing repo must be visible, not silently treated as a match
    assert pre_commit_rev(config, RUFF_PRE_COMMIT_REPO) is None


def test_a_matrix_that_never_learned_the_requirements_pin_reads_as_drift() -> None:
    # Given - requirements bumped to a phacc the CI matrix was never updated to
    requirements = f"{PHACC}==0.13.400\n"
    workflow = """
jobs:
  test:
    strategy:
      matrix:
        include:
          - ha-version: "2026.7.2"
            phacc: "0.13.346"
"""

    # When / Then - the same expression the repo-wide check asserts, on the
    # half-applied bump it exists to catch
    assert requirement_pin(requirements, PHACC) not in ci_matrix_phacc_pins(workflow)


def test_a_pre_commit_rev_left_behind_by_a_ruff_bump_reads_as_drift() -> None:
    # Given - requirements bumped to a ruff the commit hook still lags behind
    requirements = "ruff==0.16.0\n"
    config = f"""
repos:
  - repo: {RUFF_PRE_COMMIT_REPO}
    rev: v0.15.21
    hooks:
      - id: ruff-check
"""

    # When / Then - the shape every Dependabot ruff PR arrives in
    assert pre_commit_rev(config, RUFF_PRE_COMMIT_REPO) != (
        f"v{requirement_pin(requirements, 'ruff')}"
    )


def test_phacc_pin_in_requirements_is_one_the_ci_matrix_actually_tests() -> None:
    # Given - the pin contributors install, and the pins CI runs the suite against
    requirements = (REPO_ROOT / "requirements_test.txt").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    pinned = requirement_pin(requirements, PHACC)
    matrix_pins = ci_matrix_phacc_pins(workflow)

    # Then - the test job force-installs a matrix pin over the requirements one,
    # so a version absent from the matrix is a version nothing ever tests. The
    # matrix may hold more entries than this; it must hold at least this one.
    assert pinned is not None
    assert pinned in matrix_pins


def test_ruff_pin_in_requirements_matches_the_pre_commit_hook_rev() -> None:
    # Given - the ruff CI runs and the ruff the local commit hook runs
    requirements = (REPO_ROOT / "requirements_test.txt").read_text(encoding="utf-8")
    config = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    pinned = requirement_pin(requirements, "ruff")
    rev = pre_commit_rev(config, RUFF_PRE_COMMIT_REPO)

    # Then - two ruff versions means the hook reformats what CI rejects. The rev
    # carries a leading "v" that the requirements pin does not.
    assert pinned is not None
    assert rev == f"v{pinned}"
