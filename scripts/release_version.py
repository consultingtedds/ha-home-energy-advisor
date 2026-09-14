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

    python scripts/release_version.py 0.4.2    # prints 0.5.0, or nothing

Printing nothing is a real answer, and the common one: a week of documentation
and dependency work earns no release.
"""

from __future__ import annotations

import re
import subprocess
import sys
from enum import IntEnum

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
    """Print the next version, or nothing at all."""
    current = sys.argv[1] if len(sys.argv) > 1 else "0.0.0"
    version = next_version(current, commits_since(latest_tag()))
    if version is None:
        return 0
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
