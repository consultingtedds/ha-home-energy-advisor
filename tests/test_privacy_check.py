"""The privacy guard has to fail on the shapes that got through before.

Every string here is invented. Proving a guard by feeding it the maintainer's
real terms would put them in the repo to prove they must not be in the repo, so
the fixtures *drift* synthetic content through the same expressions instead:
rooms this household does not have, a name nobody here is called, a host that
resolves nowhere.

The four incidents this encodes (HEA-63, HEA-74, HEA-76, HEA-105) were each
caught by a human reading a diff. That is why this file exists.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

#: Writes one throwaway file and runs the checker over it.
ScanText = Callable[..., list[str]]

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "privacy_check", REPO / "scripts" / "privacy_check.py"
)
assert _spec is not None
assert _spec.loader is not None
privacy_check: Any = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(privacy_check)


@pytest.fixture
def scan_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScanText:
    """Run the checker over one throwaway file, as if it were tracked."""

    def run(content: str, terms: list[str] | None = None) -> list[str]:
        target = tmp_path / "sample.py"
        target.write_text(content, encoding="utf-8")
        monkeypatch.setattr(privacy_check, "REPO", tmp_path)
        found: list[str] = privacy_check.scan(["sample.py"], terms or [])
        return found

    return run


def test_it_catches_a_room_word_inside_an_identifier(scan_text: ScanText) -> None:
    # Given - the HEA-76 shape: a fixture named for where it sits rather than
    # for how its meter behaves. The room here is one this household lacks
    findings = scan_text('KEY = "conservatory_heater"\n')

    # Then
    assert len(findings) == 1
    assert "room name in an identifier" in findings[0]


def test_it_catches_a_room_word_inside_a_display_name(scan_text: ScanText) -> None:
    # Given - the same leak in its human-readable half, which is how one room
    # name reached 122 occurrences of the history
    findings = scan_text('NAME = "Annexe Aircon"\n')

    # Then
    assert len(findings) == 1
    assert "room name in a display name" in findings[0]


def test_it_catches_a_live_hostname(scan_text: ScanText) -> None:
    # Given - an address for somebody's home, which is what the HEA-63 sweep
    # found in six files
    findings = scan_text('HOST = "homeassistant.nowhere-at-all.net"\n')

    # Then
    assert len(findings) == 1
    assert "hostname" in findings[0]


def test_it_catches_a_household_name_from_the_local_list(scan_text: ScanText) -> None:
    # Given - the HEA-105 shape: a bug report quoted into a code comment,
    # carrying whoever's device the reporter happened to be looking at. Only
    # the local list can catch this, which is why that half exists at all
    findings = scan_text("# Marlowe's plug was blue on one chart\n", terms=["Marlowe"])

    # Then
    assert len(findings) == 1
    assert "household term: Marlowe" in findings[0]


def test_it_catches_a_local_term_whatever_the_casing(scan_text: ScanText) -> None:
    # Given - a name reaches the repo lower-cased inside a slug as often as it
    # does capitalised in prose
    findings = scan_text("KEY = 'quokka_lamp'\n", terms=["Quokka"])

    # Then
    assert len(findings) == 1
    assert "household term: Quokka" in findings[0]


def test_it_allows_the_projects_own_fixture_vocabulary(scan_text: ScanText) -> None:
    # Given - names describing how a meter behaves, which is the standard
    # HEA-76 established and what every fixture here should look like
    findings = scan_text(
        'KEYS = ["slow_poll_aircon", "coarse_step_aircon", '
        '"cloud_polled_pump", "lifetime_counter_plug"]\n'
    )

    # Then
    assert findings == []


def test_it_allows_prose_that_mentions_a_room_generically(scan_text: ScanText) -> None:
    # Given - describing the product, not a house. A check that shouts at
    # ordinary prose is a check somebody turns off
    findings = scan_text("# A device in a bedroom draws no more than one elsewhere.\n")

    # Then
    assert findings == []


def test_it_never_flags_a_possessive_on_shape_alone(scan_text: ScanText) -> None:
    # Given - pinning a decision rather than a behaviour. Flagging every
    # capitalised possessive was tried and withdrawn: it fires on "Untracked's
    # share", "Predbat's schedule" and "Monday's spending" alike, and a check
    # that shouts at ordinary prose gets switched off within a day, costing
    # more than it ever caught. A name has no shape - it is caught against the
    # local list or not at all
    prose = (
        "# Home Assistant's chart component is lazy-loaded, and the\n"
        "# Untracked's share follows Monday's spending.\n"
    )

    # Then
    assert scan_text(prose) == []


def test_it_allows_a_documented_host_and_a_dotted_filename(
    scan_text: ScanText,
) -> None:
    # Given - an allowed host, and a filename that is dotted without being an
    # address. Treating `hea-format.js` as a hostname would make the check
    # useless within a day
    findings = scan_text(
        '// see https://www.home-assistant.io and import "./hea-format.js"\n'
    )

    # Then
    assert findings == []


def test_the_room_lists_survived_a_history_rewrite() -> None:
    # Given - the guard's own room words are the one place in this repo where
    # those words are *supposed* to appear, which makes them collateral in any
    # `filter-repo --replace-text` sweep. HEA-107's rewrite mapped them onto
    # the fixture vocabulary and left a checker that would flag
    # `slow_poll_aircon` and miss a real room; nothing here noticed, because
    # the words these tests happen to use were not in that sweep.
    #
    # Assembled from fragments so a literal replacement cannot rewrite the
    # assertion to agree with a corrupted list.
    expected = ("living" + "_room", "games" + "_room", "pool" + "_house")

    # Then
    for word in expected:
        assert word in privacy_check.ROOM_SNAKE
        assert word.replace("_", " ").title() in privacy_check.ROOM_TITLE


def test_the_repository_itself_is_clean() -> None:
    # Given - the guard pointed at the tree it guards. This is the assertion
    # that would have failed before the HEA-105 sweep, and the one that fails
    # first if anything drifts back
    findings = privacy_check.scan(privacy_check.tracked_files(), [])

    # Then
    assert findings == [], "\n".join(findings)
