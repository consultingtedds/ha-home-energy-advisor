"""Decide the next version from the commits since the last release (HEA-31).

HACS installs an integration from its **tagged releases**, and reads the version
out of `manifest.json` inside the tag. So the version is not decoration: it is
what a household's update check compares against. A wrong one either offers an
update that is not one, or hides one that is.

The commits already carry the answer. Conventional Commits are required here and
enforced by commitlint, so what changed is stated in every subject line. Deriving
the version from them means it can never drift from what actually shipped, which
bumping a file by hand cannot promise.

Used by `.github/workflows/release.yml`:

    python scripts/release_version.py 0.4.2       # prints 0.5.0, or nothing
    python scripts/release_version.py --notes     # prints what went into it
    python scripts/release_version.py --stamp 0.5.0   # dates the paragraph

Printing nothing is a real answer, and the common one: a week of documentation
and dependency work earns no release.

The notes come from the same parse for the same reason the version does: what a
household reads in the update notification and the version their instance
compares against then cannot disagree about what shipped (HEA-177).

What that parse cannot do is explain a change. A release sometimes has to say
something no commit subject had room for - a figure that will now read
differently, a setting worth checking - so `docs/UPGRADING.md` carries a
paragraph under a pending heading, and the release puts its own number on it
(HEA-181). The heading is not written in advance because the version is not a
thing anybody should have to predict: a paragraph keyed to a guess is one that
vanishes the day the guess is wrong.
"""

from __future__ import annotations

import re
import subprocess
import sys
from enum import IntEnum
from pathlib import Path

#: Where a release's hand-written paragraph lives, resolved from this file so it
#: does not depend on the directory the workflow happens to run in.
UPGRADING = Path(__file__).resolve().parent.parent / "docs" / "UPGRADING.md"

#: The heading a paragraph waits under until a release gives it a number.
PENDING_HEADING = "## Unreleased"

#: Types that change something a household can observe.
_MINOR_TYPES = frozenset({"feat"})
_PATCH_TYPES = frozenset({"fix", "perf"})

#: Types that deliberately release nothing: work on the project rather than on
#: the product. Releasing for these would teach a household to ignore the update
#: notification, which is the one thing an update notification cannot survive.
#:
#: Listed rather than left as the default, so that adding a commit type to
#: `CONTRIBUTING.md` without deciding whether it ships is a test failure instead
#: of a silent "no". `tests/test_release_version.py` holds the two together.
_NO_RELEASE_TYPES = frozenset(
    {"build", "chore", "ci", "docs", "refactor", "revert", "style", "test"}
)

#: Every type this project accepts, which `CONTRIBUTING.md` states for humans.
RELEASE_RULES = _MINOR_TYPES | _PATCH_TYPES | _NO_RELEASE_TYPES

#: A Conventional Commits subject: type, optional scope, optional `!`, colon.
#: Anchored, because a body line that happens to start with "fix:" is prose.
_SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?: .+")

#: The footer form of a breaking change, which is a line of its own. Matching
#: the words anywhere would make any commit that merely *discusses* one cut a
#: major release - and this project's commit messages discuss things at length.
_BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)

#: Another footer, or a git trailer: a word, a colon, a space. A footer's prose
#: ends where one of these begins, because `Refs: HEA-61` is metadata and reads
#: as nonsense in front of a household.
_FOOTER_TOKEN = re.compile(r"^(?:[A-Za-z][A-Za-z-]*: |BREAKING[ -]CHANGE:)")


class Bump(IntEnum):
    """How much of the version one change moves.

    Ordered, so a release's bump is `max()` over its commits: one feature among
    twenty fixes still makes the release a minor one.
    """

    NONE = 0
    PATCH = 1
    MINOR = 2
    BREAKING = 3


def bump_for(message: str) -> Bump:
    """What one commit message asks for.

    Takes the whole message, not just the subject, because a breaking change may
    be declared either way the spec allows: a `!` after the type, or a
    `BREAKING CHANGE:` footer.
    """
    if _BREAKING_FOOTER.search(message):
        return Bump.BREAKING
    match = _SUBJECT.match(message.splitlines()[0] if message else "")
    if match is None:
        return Bump.NONE
    if match.group("breaking"):
        return Bump.BREAKING
    kind = match.group("type")
    if kind in _MINOR_TYPES:
        return Bump.MINOR
    if kind in _PATCH_TYPES:
        return Bump.PATCH
    return Bump.NONE


def next_version(current: str, messages: list[str]) -> str | None:
    """The version these commits produce, or None if none of them earns one.

    `None` rather than the current version, so a caller can tell "nothing to
    release" from "release the same version again". The second would fail on an
    existing tag, loudly and for entirely the wrong reason.

    **A breaking change before 1.0.0 bumps the minor, not the major.** Settled
    2026-09-14, not a default: 0.x already means "anything here may change", and
    1.0.0 is a statement about stability a maintainer makes deliberately - not
    one a commit subject makes on their behalf. Reaching it by accident would
    promise a household something nobody decided to promise.

    Once 1.0.0 is cut the promise exists, and this switches to bumping the major
    on its own. Nothing here needs changing for that; cutting it is the
    decision, and it is the only one left in this rule.
    """
    bump = max((bump_for(message) for message in messages), default=Bump.NONE)
    if bump is Bump.NONE:
        return None

    major, minor, patch = (int(part) for part in current.split("."))
    if bump is Bump.BREAKING:
        return f"{major}.{minor + 1}.0" if major == 0 else f"{major + 1}.0.0"
    if bump is Bump.MINOR:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


#: What each releasable type is called in front of a household. `perf` sits under
#: the same heading as `fix` because the difference is ours, not theirs: both are
#: "it behaves better than it did" and neither is new.
_HEADINGS: tuple[tuple[str, frozenset[str]], ...] = (
    ("New", frozenset(_MINOR_TYPES)),
    ("Fixed", frozenset(_PATCH_TYPES)),
)


def pending_note(upgrading: str) -> str:
    """The paragraph waiting for the next release, or `""` if none is.

    Takes the whole of `docs/UPGRADING.md` and returns only what sits under the
    pending heading, stopping at the release below it. Most releases need no
    paragraph, so the empty string is the ordinary answer rather than an error -
    and a heading left behind with nothing under it counts as none, or stamping
    it would file an empty entry under a version.
    """
    lines = upgrading.splitlines()
    index = _pending_index(lines)
    if index is None:
        return ""
    body: list[str] = []
    for line in lines[index + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body).strip()


def stamp_pending_note(upgrading: str, version: str) -> str:
    """The file with the pending heading replaced by the version carrying it.

    This is what keeps `docs/UPGRADING.md` an archive rather than a scratch file
    somebody has to remember to clear, and it is why the heading is not written
    with a version in the first place: the number arrives from the commits at
    release time, so nothing can be written against a version never cut.

    Returned unchanged when nothing is pending, so the usual release neither
    rewrites the file nor invents a heading for a version nobody described.
    """
    if not pending_note(upgrading):
        return upgrading
    return re.sub(
        rf"^{re.escape(PENDING_HEADING)}[ \t]*$",
        f"## {version}",
        upgrading,
        count=1,
        flags=re.MULTILINE,
    )


def _pending_index(lines: list[str]) -> int | None:
    """Which line is the pending heading, tolerating trailing whitespace."""
    for index, line in enumerate(lines):
        if line.rstrip() == PENDING_HEADING:
            return index
    return None


def release_notes(messages: list[str], note: str = "") -> str:
    """What these commits changed, as the update dialog will render it.

    Home Assistant shows an integration's release notes inside the update
    notification, and HACS already offers ours. Until this existed the body held
    only a compare link, because `--generate-notes` builds its list from merged
    pull requests and this project has none (HEA-177).

    Derived from the same parse as the version, so the two can never disagree
    about what a release contains. Anything that earned no release is left out
    entirely: a household told about a test fixture learns that the list is not
    worth reading, and an update notification does not survive that.

    Breaking changes lead, and are quoted from the `BREAKING CHANGE:` footer
    where there is one. That footer exists precisely because a subject line has
    no room to say what somebody has to go and change.

    `note` is the hand-written paragraph from `docs/UPGRADING.md`, printed under
    its own heading above the list. It sits below a breaking change and above
    everything else: "go and change this" outranks "you should know this", and
    both outrank news.

    The empty string where nothing qualifies, rather than a heading with no list
    under it.
    """
    sections = [_breaking_section(messages), _paragraph("Upgrading", note)]
    sections += [
        _section(heading, _subjects_of(messages, types)) for heading, types in _HEADINGS
    ]
    return "\n\n".join(section for section in sections if section)


def _breaking_section(messages: list[str]) -> str:
    breaking = [
        _breaking_line(message)
        for message in messages
        if bump_for(message) is Bump.BREAKING
    ]
    return _section("Breaking changes", breaking)


def _breaking_line(message: str) -> str:
    """What a breaking commit says, preferring its footer to its subject."""
    if match := _BREAKING_FOOTER.search(message):
        return _sentence(_footer_paragraph(message[match.end() :]))
    return _subject_of(message) or _sentence(message.splitlines()[0])


def _footer_paragraph(text: str) -> str:
    """One footer's prose, rewrapped onto a single line.

    commitlint wraps a footer at 100 characters, so anything worth saying there
    arrives as several lines. Reading only the first printed half a sentence and
    dropped the half that said what to go and do about it.

    The paragraph ends at a blank line or at the next footer, neither of which is
    part of what it says.
    """
    collected: list[str] = []
    for line in text.strip().splitlines():
        if not line.strip() or (collected and _FOOTER_TOKEN.match(line)):
            break
        collected.append(line.strip())
    return " ".join(collected)


def _subjects_of(messages: list[str], types: frozenset[str]) -> list[str]:
    """Every subject of the given types, breaking ones excluded.

    A breaking change is reported once, under its own heading, however its type
    would otherwise classify it.
    """
    return [
        subject
        for message in messages
        if bump_for(message) is not Bump.BREAKING
        and (match := _SUBJECT.match(message.splitlines()[0] if message else ""))
        and match.group("type") in types
        and (subject := _subject_of(message))
    ]


def _subject_of(message: str) -> str:
    """A commit's subject with its type and ticket scope taken off.

    The scope here is a ticket id, which means nothing to a household and reads
    as noise beside sentences that are otherwise plain English.
    """
    first = message.splitlines()[0] if message else ""
    _, _, text = first.partition(": ")
    return _sentence(text)


def _sentence(text: str) -> str:
    """The text as a sentence, without mangling whatever it starts with.

    Conventional Commits subjects start lower case, and a list of them reads
    badly. Capitalising blindly reads worse: the first word is often an
    identifier, and `solar_entity is now generation_entity` becomes a name that
    never existed. So only a plainly alphabetic, all-lower-case first word is
    touched - anything carrying an underscore, a digit, a dot or a capital of
    its own is left exactly as the author wrote it.
    """
    first = text.split(" ", 1)[0]
    if not first.isalpha() or not first.islower():
        return text
    return text[:1].upper() + text[1:]


def _section(heading: str, lines: list[str]) -> str:
    if not lines:
        return ""
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {heading}\n\n{body}"


def _paragraph(heading: str, text: str) -> str:
    """A section of prose rather than a list, or nothing where there is none."""
    return f"### {heading}\n\n{text.strip()}" if text.strip() else ""


def commits_since(tag: str | None) -> list[str]:
    """Every commit message since `tag`, or the whole history if there is none.

    Separated by a record character rather than by newlines, because these
    messages are multi-line by house style and splitting on newlines would read
    every paragraph as its own commit.
    """
    span = f"{tag}..HEAD" if tag else "HEAD"
    # The argv is fixed and there is no shell. The one interpolated value is a
    # tag name git itself produced, filtered by `latest_tag`'s own `--match`, so
    # there is no path by which a caller supplies it.
    result = subprocess.run(  # noqa: S603
        ["git", "log", span, "--format=%B%x1e"],
        capture_output=True,
        text=True,
        check=True,
    )
    parts = result.stdout.split("\x1e")
    return [message.strip() for message in parts if message.strip()]


def latest_tag() -> str | None:
    """The most recent version tag, or None before the first release."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--match=v[0-9]*"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def main() -> int:
    """Print the next version, or with `--notes` what went into it.

    Both read the same commits. `--notes` has to run *before* the release is
    tagged, or the tag it measures from is the one being cut and there is
    nothing between them.

    `--stamp <version>` is the other half: it puts that version's number on the
    paragraph the notes just printed, so the file becomes an archive and the next
    release does not print it again. It runs after the notes and before the
    release commit, which carries the rewritten file.
    """
    match sys.argv[1:]:
        case ["--stamp", version]:
            return _stamp(version)
        case ["--stamp", *_]:
            print("--stamp needs the version to date the paragraph with.")
            return 1
        case ["--notes", *_]:
            print(release_notes(commits_since(latest_tag()), _pending_paragraph()))
            return 0
        case [current, *_]:
            pass
        case _:
            current = "0.0.0"

    next_ = next_version(current, commits_since(latest_tag()))
    if next_ is None:
        return 0
    print(next_)
    return 0


def _pending_paragraph() -> str:
    """The paragraph waiting in `docs/UPGRADING.md`.

    Read without a fallback. A missing file is a release that would print no
    paragraph and say nothing about it, which is the silence this mechanism
    exists to remove.
    """
    return pending_note(UPGRADING.read_text(encoding="utf-8"))


def _stamp(version: str) -> int:
    """Put this version's number on the pending paragraph, if there is one."""
    before = UPGRADING.read_text(encoding="utf-8")
    after = stamp_pending_note(before, version)
    if after == before:
        print(f"No paragraph was waiting, so {version} carries none.")
        return 0
    UPGRADING.write_text(after, encoding="utf-8")
    print(f"{UPGRADING.name}: the pending paragraph is now {version}'s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
