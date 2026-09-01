#!/usr/bin/env python3
"""Refuse to commit anything that describes the maintainer's actual home.

This repo is public and its history is permanent. The disclosure has recurred
four times (HEA-63, HEA-74, HEA-76, HEA-105) and each time a human caught it, so
the rules in ``docs/CRITICAL_INSTRUCTIONS.md`` are necessary but have proven not
to be sufficient. This is the mechanical backstop.

**The list of banned words cannot live in this file.** A denylist naming a
household's rooms, devices and family *is* the room-by-room inventory the rules
exist to keep out - committing it would be the disclosure, dressed as its own
cure. So the check has two halves:

1. **Structural patterns, here and public.** They describe the *shape* of a
   leak - a room word inside an identifier, a possessive proper noun, a live
   hostname - and name nobody. These are what CI runs, and they would have
   caught every incident so far.
2. **Exact terms, local and never committed.** ``.privacy-terms`` is
   git-ignored; one term per line. Pre-commit reads it when present, so the
   maintainer's own machine checks for the real words while CI checks only for
   the shapes. Neither half discloses anything on its own.

Run over specific paths, or with no arguments over every tracked file.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Local, git-ignored, one term per line; ``#`` comments and blanks skipped.
TERMS_FILE = REPO / ".privacy-terms"

#: Never scanned: local notes, the lock files nobody reads, and this checker -
#: which necessarily contains the patterns it looks for.
SKIP = {
    "CLAUDE.local.md",
    ".privacy-terms",
    "scripts/privacy_check.py",
    "tests/test_privacy_check.py",
    "package-lock.json",
    "uv.lock",
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip"}

#: Rooms only a *home* has. A device or fixture named for one of these is naming
#: somebody's floor plan, which is the failure mode of HEA-74 and HEA-76 both.
#:
#: Matched only where a room word is *attached to something* - `spare_room_fan`,
#: "Utility Room Heater" - never bare. Prose may say "a device in a bedroom"
#: without describing anybody's house, and a check that shouts at ordinary prose
#: is a check somebody turns off.
#:
#: **Exclude this file from any future `git filter-repo --replace-text` run.**
#: The HEA-107 rewrite mapped real room words onto the fixture vocabulary across
#: every blob, and these two lists are the one place in the repo where those
#: words are supposed to appear - so the sweep quietly rewrote the guard into
#: one that would flag `slow_poll_aircon` and miss the thing it was built for.
#: The existing tests did not notice, because the words they happened to use
#: were not in the sweep - so `test_the_room_lists_survived_a_history_rewrite`
#: now asserts these entries directly, from fragments a replacement cannot see.
ROOM_SNAKE = (
    "bedroom|bathroom|ensuite|living_room|dining_room|games_room|utility_room|"
    "box_room|spare_room|playroom|conservatory|pool_house|driveway|patio|"
    "cellar|attic|hallway|porch|annexe"
)
ROOM_TITLE = (
    "Bedroom|Bathroom|Ensuite|Living Room|Dining Room|Games Room|Utility Room|"
    "Box Room|Spare Room|Playroom|Conservatory|Pool House|Driveway|Patio|"
    "Cellar|Attic|Hallway|Porch|Annexe"
)

#: Ends a hostname. Deliberately not "any dotted token": `hea-format.js` and
#: `package.json` are dotted and are not addresses.
TLDS = "net|com|org|io|local|lan|home|internal|uk|es|dev|xyz|tv"

#: Proper nouns that legitimately take a possessive in prose. Anything else
#: capitalised and possessive is assumed to be a person until proven otherwise.
KNOWN_POSSESSIVES = {
    "Anthropic",
    "Assistant",
    "Chrome",
    "ECharts",
    "GitHub",
    "HA",
    "Home",
    "Lovelace",
    "MIT",
    "Okabe",
    "Python",
    "Sonar",
    "Windows",
}

#: Hosts the project genuinely refers to. A hostname outside this set is assumed
#: to be somebody's house until it is added here deliberately.
KNOWN_HOSTS = {
    "astral.sh",
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "claude.ai",
    "code.jquery.com",
    "developers.home-assistant.io",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "github.com",
    "home-assistant.io",
    "linear.app",
    "pre-commit.com",
    "python.org",
    "schema.org",
    "sonarsource.com",
    "www.conventionalcommits.org",
    "www.home-assistant.io",
}

NAME_ADVICE = (
    "Name a fixture for how its meter behaves, never for where it sits: "
    "slow_poll_aircon, coarse_step_aircon, cloud_polled_pump."
)

CHECKS = (
    (
        "room name in an identifier",
        re.compile(rf"\b([a-z0-9]+_(?:{ROOM_SNAKE})|(?:{ROOM_SNAKE})_[a-z0-9]+)\b"),
        NAME_ADVICE,
    ),
    (
        "room name in a display name",
        re.compile(rf"\b([A-Z][a-z]+ (?:{ROOM_TITLE})|(?:{ROOM_TITLE}) [A-Z][a-z]+)\b"),
        NAME_ADVICE,
    ),
    # No check for household members' *names*, deliberately. A name has no
    # shape: "Untracked's share", "Predbat's schedule", "Monday's spending" and
    # a child's name are the same string to a regex, and a check that fires on
    # ordinary prose is a check somebody switches off within a day - which would
    # cost more than it ever caught. A name is detectable only against a list of
    # names, and that list cannot be public. It lives in `.privacy-terms`, which
    # is precisely why the local half of this check exists.
    (
        "hostname",
        re.compile(rf"\b([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:{TLDS}))\b"),
        (
            "A live hostname is an address for someone's home. "
            "Call it the reference instance instead."
        ),
    ),
)


def tracked_files() -> list[str]:
    """Every file git knows about, which is exactly what would be published."""
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def local_terms() -> list[str]:
    """The maintainer's own words, when the ignored file is present."""
    if not TERMS_FILE.is_file():
        return []
    lines = TERMS_FILE.read_text(encoding="utf-8").splitlines()
    return [t.strip() for t in lines if t.strip() and not t.startswith("#")]


def _skip(path: str) -> bool:
    return path in SKIP or Path(path).suffix.lower() in SKIP_SUFFIXES


def _allowed(check: str, hit: str) -> bool:
    """Whether a structural match is one of the cases we mean to permit."""
    if check == "possessive proper noun":
        return hit in KNOWN_POSSESSIVES
    if check == "hostname":
        return hit.lower() in KNOWN_HOSTS
    return False


def _findings_in_line(
    path: str, number: int, line: str, lowered: list[tuple[str, str]]
) -> list[str]:
    """Both halves of the check against one line: exact terms, then shapes."""
    findings = [
        f"{path}:{number}: household term: {term}"
        for term, needle in lowered
        if needle in line.lower()
    ]
    for name, pattern, advice in CHECKS:
        for match in pattern.finditer(line):
            hit = match.group(1) if pattern.groups else match.group(0)
            if not _allowed(name, hit):
                findings.append(f"{path}:{number}: {name}: {hit}\n    {advice}")
    return findings


def _readable(path: str) -> str | None:
    """A tracked file's text, or ``None`` where there is nothing to read."""
    if _skip(path):
        return None
    file = REPO / path
    if not file.is_file():
        return None
    try:
        raw = file.read_bytes()
    except OSError:
        return None
    # Decoded leniently rather than skipped on a bad byte. A file this cannot
    # read is a file this cannot check, and silently passing one is how a
    # disclosure would get through the gate that exists to stop it - so a
    # stray byte costs one mangled character, not a whole unexamined file.
    return raw.decode("utf-8", errors="ignore")


def scan(paths: list[str], terms: list[str]) -> list[str]:
    """Every finding, as a printable line."""
    lowered = [(t, t.lower()) for t in terms]
    findings: list[str] = []
    for path in paths:
        text = _readable(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            findings.extend(_findings_in_line(path, number, line, lowered))
    return findings


def main(argv: list[str]) -> int:
    """Check the named paths, or every tracked file when given none."""
    paths = argv[1:] or tracked_files()
    terms = local_terms()
    findings = scan(paths, terms)

    if not findings:
        return 0

    print("Privacy check failed - this repo is public and its history permanent.")
    print("See the Privacy sections of docs/CRITICAL_INSTRUCTIONS.md.\n")
    for finding in findings:
        print(f"  {finding}")
    print(f"\n{len(findings)} finding(s).")
    if not terms:
        print(
            "\nNote: .privacy-terms is absent, so only the structural patterns "
            "ran. On the maintainer's machine that file adds the exact-word check."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
