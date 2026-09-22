"""Drift guards between `strings.json` and every translation beside it.

Three languages now hold the same keys, and nothing in the toolchain relates
them. The failure mode is specific and quiet:

* **A key added to `strings.json` and not to a translation is invisible where
  it was added.** Home Assistant falls back to the English source, and the
  cards fall back to their own English `DEFAULTS` (ADR-0018) - so an English
  instance shows the new string correctly while a Spanish or Russian one shows
  English, and no test of the card's own behaviour can tell the difference.
* **A placeholder translated along with the prose stops substituting.** `{name}`
  rendered into another language is no longer the marker Home Assistant fills,
  so the household reads the literal braces where the device name should be.
  This is the easiest thing to get wrong in a file nobody on the project reads.

Both are asserted against `strings.json`, which is the source Home Assistant
ships to a household whose language we do not carry, so it is the one file the
others owe parity to.

The parser tests below are not ceremony, for the reason `test_dependency_pins`
gives: a flattener that quietly stopped descending would make every parity check
pass vacuously (HEA-163).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

import pytest

REPO_ROOT: Final = Path(__file__).parent.parent
COMPONENT: Final = REPO_ROOT / "custom_components" / "home_energy_advisor"
TRANSLATIONS: Final = COMPONENT / "translations"


def string_keys(document: dict[str, Any], prefix: str = "") -> set[str]:
    """Every leaf key in a strings document, as a dotted path."""
    found: set[str] = set()
    for key, value in document.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            found |= string_keys(value, path)
        else:
            found.add(path)
    return found


def string_at(document: dict[str, Any], path: str) -> str:
    """The string a dotted path leads to."""
    value: Any = document
    for part in path.split("."):
        value = value[part]
    return str(value)


def placeholders(text: str) -> set[str]:
    """The `{name}` markers Home Assistant will substitute into a string."""
    return set(re.findall(r"\{(\w+)\}", text))


def translation_files() -> list[Path]:
    """Every translation shipped beside `strings.json`."""
    return sorted(TRANSLATIONS.glob("*.json"))


def load(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def test_string_keys_descends_into_every_level() -> None:
    # Given - a strings document nested the way Home Assistant nests one
    document = {"issues": {"source_removed": {"title": "A", "description": "B"}}}

    # When - its keys are flattened
    keys = string_keys(document)

    # Then
    assert keys == {
        "issues.source_removed.title",
        "issues.source_removed.description",
    }


def test_string_keys_is_empty_for_a_document_with_nothing_in_it() -> None:
    # Given / When / Then - an empty result must fail a parity check, not satisfy
    # it by having nothing to disagree about
    assert string_keys({}) == set()


def test_placeholders_reads_every_marker_in_a_string() -> None:
    # Given - a Repair description naming both the device and its entity
    text = "{name} is tracked by `{entity_id}`, which has never reported."

    # When / Then
    assert placeholders(text) == {"name", "entity_id"}


def test_placeholders_is_empty_when_a_string_carries_none() -> None:
    # Given - prose with no substitution in it at all
    text = "Home Energy Advisor is already configured."

    # When / Then - absent is not the same as matching whatever the source has
    assert placeholders(text) == set()


def test_placeholders_ignores_markdown_bold_which_is_not_a_marker() -> None:
    # Given - a description using the bold Home Assistant renders in a Repair
    text = "**This cannot be undone.** Your devices are untouched."

    # When / Then - reading emphasis as a placeholder would report drift that is
    # not there, and a check that cries wolf gets turned off
    assert placeholders(text) == set()


def test_a_translation_missing_a_key_reads_as_drift() -> None:
    # Given - a string added to the source and not to one of the translations,
    # which is invisible on an English instance
    source = {"issues": {"rescaled_source": {"title": "A", "description": "B"}}}
    translation = {"issues": {"rescaled_source": {"title": "A"}}}

    # When / Then - the same expression the repo-wide check asserts
    assert string_keys(source) - string_keys(translation) == {
        "issues.rescaled_source.description"
    }


def test_a_translated_placeholder_reads_as_drift() -> None:
    # Given - a translator who carried the marker into their own language along
    # with the prose around it. Home Assistant substitutes `{name}` and nothing
    # else, so the household reads the braces
    source = "{name} is reporting more energy than the whole house"
    translation = "{nombre} está consumiendo más que toda la casa"

    # When / Then - the same expression the repo-wide check asserts
    assert placeholders(source) != placeholders(translation)


def test_there_is_a_translation_for_every_language_the_project_claims() -> None:
    # Given - the languages `CRITICAL_INSTRUCTIONS.md` and `PLAN.md` state the
    # project ships from day one
    shipped = {path.stem for path in translation_files()}

    # Then - a language named in the rules and absent from the tree is a promise
    # to a household that nothing keeps
    assert shipped == {"en", "es", "ru"}


@pytest.mark.parametrize("path", translation_files(), ids=lambda path: path.stem)
def test_a_translation_carries_every_key_the_source_does(path: Path) -> None:
    # Given - the source Home Assistant falls back to, and one translation
    source = load(COMPONENT / "strings.json")
    translation = load(path)

    # Then - a missing key shows English on that install and shows nothing wrong
    # anywhere else, so it cannot be found by reading a card's own tests
    assert string_keys(source) - string_keys(translation) == set()


@pytest.mark.parametrize("path", translation_files(), ids=lambda path: path.stem)
def test_a_translation_invents_no_key_of_its_own(path: Path) -> None:
    # Given - the same pair
    source = load(COMPONENT / "strings.json")
    translation = load(path)

    # Then - a key only a translation has is one nothing reads: either a typo in
    # the path, or a string the source dropped and this file kept
    assert string_keys(translation) - string_keys(source) == set()


@pytest.mark.parametrize("path", translation_files(), ids=lambda path: path.stem)
def test_a_translation_substitutes_exactly_what_the_source_does(path: Path) -> None:
    # Given - the same pair, over every key they share
    source = load(COMPONENT / "strings.json")
    translation = load(path)
    shared = string_keys(source) & string_keys(translation)

    # Then - a marker translated, dropped or invented renders as literal braces
    # in front of a household, in the one language nobody here proofreads
    drifted = {
        key
        for key in shared
        if placeholders(string_at(source, key))
        != placeholders(string_at(translation, key))
    }
    assert drifted == set()
