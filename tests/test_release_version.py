"""Deciding the next version from the commits since the last release (HEA-31).

HACS installs from tagged releases and reads the version out of `manifest.json`
inside the tag, so the version is not decoration - it is what a household's
update check compares against. Getting it wrong either offers an update that is
not one, or hides one that is.

The commits already carry the answer. Conventional Commits are required and
enforced by commitlint, so what changed is stated in every subject line and the
version follows from it rather than from anybody remembering to bump a file.

These tests are the rules. The parser cases are not ceremony: the failure that
would matter most here is a matcher that quietly stops matching, which would
turn every release into "nothing to release" and go unnoticed for weeks.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from scripts.release_version import RELEASE_RULES, Bump, bump_for, next_version

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("feat: add per-device self-sufficiency", Bump.MINOR),
        ("fix: stop the remainder going negative", Bump.PATCH),
        ("perf: prune the price list on every tick", Bump.PATCH),
        ("docs: explain why Sonar is not required", Bump.NONE),
        ("chore(deps): bump ruff", Bump.NONE),
        ("refactor: extract the interval ledger", Bump.NONE),
        ("test: cover the coarse-step path", Bump.NONE),
        ("ci: pin the checkout action", Bump.NONE),
        ("style: reflow a docstring", Bump.NONE),
        ("build: bundle the cards", Bump.NONE),
        ("revert: undo the clamp", Bump.NONE),
    ],
)
def test_the_commit_type_decides_the_bump(subject: str, expected: Bump) -> None:
    # Given / When / Then - only a user-visible change earns a release. The rest
    # is work on the project rather than the product, and releasing for it would
    # teach a household to ignore the update notification
    assert bump_for(subject) is expected


def test_a_scope_does_not_change_the_type() -> None:
    # Given - the maintainer's commits carry the ticket id as the scope, which is
    # why the history looks the way it does
    # When / Then - `fix(HEA-59):` is a fix like any other
    assert bump_for("fix(HEA-59): round published values") is Bump.PATCH
    assert bump_for("feat(HEA-94): ship a dashboard") is Bump.MINOR


def test_an_exclamation_mark_marks_a_breaking_change() -> None:
    # Given / When / Then - the Conventional Commits marker, with and without a
    # scope in front of it
    assert bump_for("feat!: rename every cost sensor") is Bump.BREAKING
    assert bump_for("fix(HEA-61)!: rename Cost Without Solar") is Bump.BREAKING


def test_a_subject_that_is_not_conventional_asks_for_nothing() -> None:
    # Given / When / Then - commitlint keeps these out of `main`, but a merge or
    # a bot could still produce one. Guessing at it would be worse than ignoring
    # it: a version is not the place to be imaginative
    assert bump_for("Merge branch 'main' into feature") is Bump.NONE
    assert bump_for("") is Bump.NONE
    assert bump_for("feat no colon so not a conventional subject") is Bump.NONE


def test_a_breaking_change_footer_is_honoured() -> None:
    # Given - the other half of the spec: a type with no `!`, and the breaking
    # change declared in the footer below
    message = (
        "fix: move the generation storage key\n\n"
        "BREAKING CHANGE: solar_entity is now generation_entity."
    )

    # When / Then - the footer outranks the type, or a rename ships as a patch
    assert bump_for(message) is Bump.BREAKING


def test_the_words_in_prose_are_not_a_footer() -> None:
    # Given - a commit that merely discusses one, which this project's commit
    # messages do at length
    message = "docs: explain what a BREAKING CHANGE would mean for statistics"

    # When / Then - the footer is a line of its own. Matching the words anywhere
    # would make any mention of the subject cut a major release
    assert bump_for(message) is Bump.NONE


def test_the_largest_bump_in_the_set_wins() -> None:
    # Given - a release's worth of work as it actually arrives: several small
    # commits building towards one capability
    commits = [
        "test: cover the new card",
        "fix: correct the axis label",
        "feat: add the self-sufficiency card",
        "docs: describe it in the README",
    ]

    # When / Then - one feat among them makes the whole release a minor one
    assert next_version("0.4.2", commits) == "0.5.0"


def test_a_patch_release_leaves_the_minor_alone() -> None:
    # Given / When / Then
    assert next_version("0.4.2", ["fix: stop the remainder going negative"]) == "0.4.3"


def test_a_minor_release_resets_the_patch() -> None:
    # Given / When / Then
    assert next_version("0.4.2", ["feat: add a card"]) == "0.5.0"


def test_nothing_releasable_produces_no_version() -> None:
    # Given - a run of documentation and dependency work, which is most weeks
    commits = ["docs: update the plan", "chore(deps): bump ruff", "ci: pin an action"]

    # When / Then - None rather than the current version, so the workflow can
    # tell "nothing to release" from "release the same version again". The second
    # would fail on an existing tag, loudly and for entirely the wrong reason
    assert next_version("0.4.2", commits) is None


def test_no_commits_at_all_produces_no_version() -> None:
    # Given / When / Then
    assert next_version("0.4.2", []) is None


def test_the_first_release_comes_off_the_placeholder_version() -> None:
    # Given - `manifest.json` has carried 0.0.1 since the repository was created,
    # and nothing has ever been tagged
    # When / Then - the first release of a working integration is 0.1.0, not
    # 0.0.2: it is a capability, not a fix to something already shipped
    assert next_version("0.0.1", ["feat: the whole integration"]) == "0.1.0"


def test_a_breaking_change_before_one_point_zero_bumps_the_minor() -> None:
    # Given - a pre-1.0 integration, where 0.x already means "anything here may
    # change"
    # When / Then - 1.0.0 is a statement about stability that a maintainer makes
    # deliberately, not one a commit subject makes for them. Reaching it by
    # accident would promise a household something nobody decided to promise
    assert next_version("0.5.1", ["feat!: rename every cost sensor"]) == "0.6.0"


def test_a_breaking_change_after_one_point_zero_bumps_the_major() -> None:
    # Given / When / Then - once 1.0.0 is out the promise exists, and breaking it
    # is exactly what a major release says
    assert next_version("1.4.2", ["feat!: rename every cost sensor"]) == "2.0.0"
    assert next_version("1.4.2", ["feat: add a card"]) == "1.5.0"


def documented_commit_types(contributing: str) -> set[str]:
    """The commit types `CONTRIBUTING.md` tells a contributor it accepts."""
    match = re.search(r"Accepted types are\s+(.+?)\.\s", contributing, flags=re.DOTALL)
    return set(re.findall(r"`([a-z]+)`", match.group(1))) if match else set()


def test_documented_commit_types_reads_the_list_it_is_given() -> None:
    # Given - the sentence as CONTRIBUTING.md writes it, wrapped mid-list
    text = "Accepted types are `build`, `chore`,\n`feat`, `fix`. Then a break.\n"

    # When / Then - the wrap must not lose half the list, which is the way this
    # parser would fail while still looking like it worked
    assert documented_commit_types(text) == {"build", "chore", "feat", "fix"}


def test_documented_commit_types_is_empty_when_the_sentence_is_gone() -> None:
    # Given / When / Then - a parser that quietly stops matching would make the
    # drift check below pass vacuously, so absence has to be visible
    assert documented_commit_types("No such sentence here.") == set()


def test_every_documented_commit_type_has_a_release_rule() -> None:
    # Given - the types a contributor is told to use, and the types the release
    # has an opinion about
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    documented = documented_commit_types(contributing)

    # Then - a type nobody classified would silently release nothing, and the
    # first anyone knew of it would be a capability that shipped without a
    # version. Adding one to the guide now fails here until it is decided.
    assert documented, "CONTRIBUTING.md no longer lists the accepted commit types"
    assert documented == RELEASE_RULES
