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
from scripts.release_version import (
    PENDING_HEADING,
    RELEASE_RULES,
    UPGRADING,
    Bump,
    bump_for,
    next_version,
    pending_note,
    release_notes,
    stamp_pending_note,
)

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


def test_the_notes_group_what_a_household_can_see(with_notes: list[str]) -> None:
    # Given / When - a release's worth of work
    notes = release_notes(with_notes)

    # Then - the two kinds are named the way a household thinks of them, and in
    # the order they will want them
    assert notes.index("### New") < notes.index("### Fixed")
    assert "- Add the self-sufficiency card" in notes
    assert "- Correct the axis label" in notes


def test_the_notes_leave_out_what_earned_no_release(with_notes: list[str]) -> None:
    # Given / When - the same set, which contains documentation and test work
    notes = release_notes(with_notes)

    # Then - none of it appears. A household told about a test fixture learns
    # that this list is not worth reading, which is the one thing an update
    # notification cannot survive. The filter is the same one that decided
    # there was a release at all.
    assert "cover the new card" not in notes
    assert "README" not in notes


def test_a_breaking_change_is_the_first_thing_in_the_notes() -> None:
    # Given - a release carrying one, among ordinary work
    commits = [
        "fix: correct the axis label",
        "feat!: rename every cost sensor",
        "feat: add a card",
    ]

    # When
    notes = release_notes(commits)

    # Then - it leads. This is what the dialog is for: everything else in it is
    # news, and this is the part that will cost somebody their history if they
    # install without reading it
    assert notes.startswith("### Breaking changes")
    assert notes.index("Rename every cost sensor") < notes.index("### New")


def test_a_breaking_change_footer_is_what_gets_read_out() -> None:
    # Given - the explanation lives in the footer, which is the half of the
    # spec that exists precisely because a subject line has no room for it
    commits = [
        (
            "fix: move the generation storage key\n\n"
            "BREAKING CHANGE: solar_entity is now generation_entity."
        )
    ]

    # When / Then - the footer is quoted rather than the subject, or a household
    # reads "move the generation storage key" and learns nothing about what it
    # has to go and change
    notes = release_notes(commits)
    assert "solar_entity is now generation_entity." in notes


def test_the_notes_drop_the_ticket_scope() -> None:
    # Given / When - the maintainer's own commit format, where the scope is a
    # ticket id
    notes = release_notes(["fix(HEA-175): stop giving a grid-only home figures"])

    # Then - HEA-175 means nothing to a household and reads as noise beside
    # sentences that are otherwise plain English
    assert "- Stop giving a grid-only home figures" in notes
    assert "HEA-175" not in notes


def test_a_section_with_nothing_in_it_is_not_printed() -> None:
    # Given / When - a patch release, which is most of them
    notes = release_notes(["fix: stop the remainder going negative"])

    # Then - no empty "New" heading above it
    assert "### New" not in notes
    assert notes.startswith("### Fixed")


def test_nothing_releasable_produces_no_notes() -> None:
    # Given / When / Then - the empty string, so a caller can tell there is
    # nothing to say from being handed a heading with no list under it
    assert release_notes(["docs: update the plan", "chore(deps): bump ruff"]) == ""


def test_the_paragraph_waiting_for_the_next_release_is_read_out(
    upgrading: str,
) -> None:
    """What no commit subject could have held (HEA-181).

    0.5.0 published the battery's round-trip losses, so whole-home energy began
    reading slightly above a house-consumption meter. Correct, intended, and
    indistinguishable from a defect to anybody comparing the two. The subject
    that carried it said what we did, which is the wrong half.
    """
    # Given / When - the notes file with a paragraph under the pending heading
    note = pending_note(upgrading)

    # Then - exactly that paragraph, with the heading and the archive below it
    # left out
    assert note == (
        "Battery Losses is back, and it is now measured. It is worked out from\n"
        "what your house's own meters cannot account for, less whatever the\n"
        "battery actually gained."
    )


def test_an_archive_with_nothing_pending_offers_no_paragraph() -> None:
    # Given - the file between releases, which is how it reads most of the time
    archive = "# Upgrading\n\n## 0.5.2\n\nSaving any setting reloaded it.\n"

    # When / Then - the empty string, so a release that needs no paragraph gets
    # no heading rather than an empty one. Most releases need no paragraph
    assert pending_note(archive) == ""


def test_a_pending_heading_with_nothing_under_it_is_not_a_paragraph() -> None:
    # Given - the heading left behind, or typed in advance and not yet written
    waiting = "# Upgrading\n\n## Unreleased\n\n## 0.5.2\n\nSaving a setting.\n"

    # When / Then - still nothing. An empty heading must not become an empty
    # archive entry when the release stamps it
    assert pending_note(waiting) == ""


def test_the_pending_paragraph_is_stamped_with_the_version_that_carries_it(
    upgrading: str,
) -> None:
    # Given / When - the release the paragraph was written for turns out to be
    # 0.6.0, which only the commits can decide
    stamped = stamp_pending_note(upgrading, "0.6.0")

    # Then - the heading carries the number, and the paragraph underneath it is
    # untouched. Nothing was keyed to a guess, so nothing could be orphaned by
    # the version coming out different
    assert "## 0.6.0\n\nBattery Losses is back" in stamped
    assert PENDING_HEADING not in stamped

    # ...and the releases already in the file are left exactly as they were
    assert stamped.endswith(
        "## 0.5.2\n"
        "\n"
        "Saving any setting reloaded the integration, and on the way back up it\n"
        "counted everything since its last save a second time.\n"
    )


def test_stamping_a_file_with_nothing_pending_leaves_it_alone() -> None:
    # Given - the usual case: a release whose commits need no paragraph
    archive = "# Upgrading\n\n## 0.5.2\n\nSaving any setting reloaded it.\n"

    # When / Then - unchanged, rather than a heading invented for a version
    # nobody wrote anything about
    assert stamp_pending_note(archive, "0.6.0") == archive


def test_the_notes_put_the_paragraph_above_the_list(with_notes: list[str]) -> None:
    # Given - a release carrying both: work the commits describe, and a sentence
    # they could not
    note = "Your total may sit slightly above your house consumption meter."

    # When
    notes = release_notes(with_notes, note)

    # Then - the paragraph leads, under a heading of its own. It is the part
    # somebody has to read before installing; the list is news
    assert notes.startswith(f"### Upgrading\n\n{note}")
    assert notes.index("### Upgrading") < notes.index("### New")


def test_a_breaking_change_still_outranks_the_paragraph() -> None:
    # Given - both, which is the one ordering that is not obvious
    commits = ["feat!: rename every cost sensor"]

    # When
    notes = release_notes(commits, "Your total may sit slightly above your meter.")

    # Then - breaking leads. "You must go and change something" outranks
    # "you should know this", and that heading is the one a household must never
    # learn to skim
    assert notes.startswith("### Breaking changes")
    assert notes.index("### Breaking changes") < notes.index("### Upgrading")


def test_no_paragraph_means_no_upgrading_heading(with_notes: list[str]) -> None:
    # Given / When - the common release, where the subjects say it all
    notes = release_notes(with_notes)

    # Then - no empty heading above the list, and the list is unchanged from
    # what the commits alone produce
    assert "### Upgrading" not in notes
    assert notes.startswith("### New\n\n- Add the self-sufficiency card")


def test_a_breaking_change_footer_that_wrapped_is_read_whole() -> None:
    """A footer is wrapped at 100 characters, and was read as far as the wrap.

    `commitlint`'s `config-conventional` enforces `footer-max-line-length`, so a
    footer saying anything substantial arrives as several lines. Reading only the
    first printed half a sentence and dropped the half that said what to do.
    """
    # Given - the footer as commitlint requires it to be written
    commits = [
        (
            "feat: price stored energy from the ledger\n"
            "\n"
            "BREAKING CHANGE: battery_entity is now battery_level_entity, and a\n"
            "configuration naming the old key is ignored until you reconfigure the\n"
            "integration.\n"
        )
    ]

    # When
    notes = release_notes(commits)

    # Then - the whole sentence, rewrapped onto one line, including the half
    # that says what somebody has to go and do. The key keeps its own case, or
    # the notes would name a setting that never existed
    assert notes.startswith(
        "### Breaking changes\n"
        "\n"
        "- battery_entity is now battery_level_entity, and a configuration "
        "naming the old key is ignored until you reconfigure the integration."
    )


def test_a_footer_stops_where_the_next_one_starts() -> None:
    # Given - a message with a footer after the breaking one, which is the shape
    # a trailer produces
    commits = [
        (
            "fix: move the generation storage key\n"
            "\n"
            "BREAKING CHANGE: solar_entity is now generation_entity.\n"
            "Refs: HEA-61\n"
        )
    ]

    # When / Then - the trailer is not prose and does not belong in front of a
    # household
    notes = release_notes(commits)
    assert "- solar_entity is now generation_entity." in notes
    assert "HEA-61" not in notes


def test_the_notes_file_is_where_the_script_reads_it() -> None:
    # Given / When / Then - moving it would produce releases with no paragraph
    # and no complaint, which is the silence this ticket exists to remove
    assert UPGRADING.is_file()
    assert UPGRADING.read_text(encoding="utf-8").startswith("# Upgrading\n")


def test_the_notes_file_keeps_its_guidance_above_the_sections() -> None:
    """Prose below the last section is printed to a household (HEA-190).

    A pending section ends where the next one begins, so with nothing below it
    the extractor reads to the end of the file. The first paragraph written under
    `## Unreleased` took this file's own closing sentence about the releases page
    with it, into the release body.

    The layout is the fix - guidance above, version sections below, nothing after
    them - and this is what holds the layout.
    """
    # Given - the shipped file, and the guidance that is really in it
    text = UPGRADING.read_text(encoding="utf-8")
    assert "releases page" in text, "the sentence this is guarding has been reworded"

    # Then - the last section in the file holds none of it. That is the invariant
    # whether or not a release has already stamped the pending heading away,
    # because the last section is the one with nothing after it to stop at
    assert "releases page" not in text[text.rindex("## ") :]

    # ...and what a release would print is the paragraph alone. The releases-page
    # pointer is the sentence that actually leaked into a release body, so it is
    # the one named here rather than a general claim about prose
    assert "releases page" not in pending_note(text)


def test_the_guide_names_the_heading_the_script_looks_for() -> None:
    # Given - the heading a contributor is told to write
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    # Then - it is the one the script actually finds. Renaming either on its own
    # leaves a paragraph that is never printed, and nothing else would say so
    assert PENDING_HEADING in contributing
    assert str(UPGRADING.relative_to(REPO_ROOT)).replace("\\", "/") in contributing


def test_the_workflow_stamps_the_paragraph_into_the_release_commit() -> None:
    """The ordering that keeps the file an archive rather than a scratch pad.

    The notes are built from the pending heading, so the stamp has to happen
    after they are written and before the release commit - otherwise the
    paragraph either misses the notes or stays pending, and the next release
    prints it a second time.
    """
    # Given - the workflow as it will run, with the prose stripped out
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    steps = "\n".join(
        line for line in workflow.splitlines() if not line.lstrip().startswith("#")
    )

    # Then - built, then stamped, then committed, and the file is staged by name
    assert steps.index("Write the release notes") < steps.index("--stamp")
    assert steps.index("--stamp") < steps.index("Commit, tag and push")
    assert "docs/UPGRADING.md" in steps.split("Commit, tag and push")[1]


def test_the_workflow_writes_the_notes_before_it_tags() -> None:
    """The one ordering nothing else can catch (HEA-177).

    The notes are the commits since the previous release. Computed after the tag
    is pushed, `git describe` returns the release being cut and there is nothing
    between them - so the body would be empty, the release would succeed, and
    the first anyone knew of it would be a household seeing a blank changelog.
    """
    # Given - the release workflow as it will run, with the prose stripped out.
    # The comments explain why `--generate-notes` was abandoned, so reading them
    # as configuration would fail this for saying so.
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    steps = "\n".join(
        line for line in workflow.splitlines() if not line.lstrip().startswith("#")
    )

    # Then - the notes are built first, and the generator that cannot see this
    # project's history is not used at all
    assert "--generate-notes" not in steps
    assert "--notes-file notes.md" in steps
    assert steps.index("Write the release notes") < steps.index("Commit, tag and push")


@pytest.fixture
def with_notes() -> list[str]:
    """A release's worth of commits, as this project's history actually reads."""
    return [
        "test: cover the new card",
        "fix: correct the axis label",
        "feat: add the self-sufficiency card",
        "docs: describe it in the README",
    ]


@pytest.fixture
def upgrading() -> str:
    """The notes file with a paragraph waiting, and one release behind it.

    The pending text is 0.6.0's own and the archived one is 0.5.2's, both as they
    were written. Neither could have been a commit subject, and both were pasted
    into the release body by hand after the workflow had created it.
    """
    return (
        "# Upgrading\n"
        "\n"
        "What a release has to tell a household that no commit subject could.\n"
        "\n"
        "## Unreleased\n"
        "\n"
        "Battery Losses is back, and it is now measured. It is worked out from\n"
        "what your house's own meters cannot account for, less whatever the\n"
        "battery actually gained.\n"
        "\n"
        "## 0.5.2\n"
        "\n"
        "Saving any setting reloaded the integration, and on the way back up it\n"
        "counted everything since its last save a second time.\n"
    )


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
