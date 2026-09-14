# Contributing

Contributions are welcome. This guide covers the things that are easy to trip
over, most of which are consequences of what the project is: a financial
accounting engine, where being wrong quietly is worse than failing loudly.

## Reporting a bug

Use [GitHub Issues](https://github.com/consultingtedds/ha-home-energy-advisor/issues).
That is the right place, and the only place you need.

For anything involving wrong figures, please attach the **diagnostics download**
(Settings → Devices & Services → Home Energy Advisor → ⋮ → Download diagnostics).
It carries the per-source decision log - why each reading was counted, gated or
refused - which is usually enough to explain a figure without access to your
instance. Entity ids and device names are redacted.

## What are those `HEA-nn` references?

Issue ids from the maintainer's private tracker. They appear in commit messages,
ADRs and code comments as provenance markers - "this line exists because of that
piece of work".

**You do not need access to them.** Everything a contributor needs is in the
repository:

- `docs/adr/` - the decisions and, more usefully, the reasoning and the
  alternatives that were rejected. Start here for *why* the code is shaped as it
  is.
- `docs/PLAN.md` - the delivery plan and the decision log.
- Commit messages - deliberately written to explain reasoning, not just changes.

If you find yourself needing a ticket to understand something, that is a
documentation bug worth raising.

## How the code is laid out

```
custom_components/home_energy_advisor/          the integration - a thin adapter
custom_components/home_energy_advisor/engine/   the accounting engine
frontend/                                       the Lovelace cards, plain ES modules
tests/                                          pytest
demo/                                           a throwaway Home Assistant in a container
docs/                                           plan, ADRs, standards, notes
```

**The split between the first two is the load-bearing one.** The engine is pure
Python with zero `homeassistant.*` imports - it is the financial model, and it
stays independently testable. Everything that knows about Home Assistant lives
above it and adapts state into engine inputs.

What the engine does, in a paragraph: house consumption over each five-minute
interval is decomposed into grid import (priced live), generation (priced at
zero, with the export cost deferred) and battery discharge (priced at the
weighted average cost of what went in). That is allocated across the tracked
devices and an "Untracked" remainder by each one's share of the draw, so the
allocations always sum to the real cost. Period totals and any power-to-energy
conversion use Home Assistant's own `utility_meter` and Integral helpers,
created automatically - the arithmetic is never reimplemented here.

`docs/adr/0002` and `docs/adr/0004` carry that properly, with the alternatives
that were rejected.

## Where the reasoning lives

- `docs/CRITICAL_INSTRUCTIONS.md` - the project's own rules, as two checklists of
  what is never done and what is always done. Terse by design.
- `docs/PLAN.md` - the delivery plan, the decision log, and the epic map.
- `docs/adr/` - accepted decisions, append-only. Start here for *why*.
- `docs/TESTING_STANDARDS.md` and `docs/DOCUMENTATION_STANDARDS.md` - how tests
  and docs are written here, and why they look as they do.
- `docs/notes/DEVICE_SENSOR_SURVEY.md` - how real energy and power sensors
  actually behave, which is where several of the stranger rules come from.

## Commit messages

**[Conventional Commits](https://www.conventionalcommits.org/) are required**, and
enforced by `commitlint` locally and in CI. Every commit needs a type and a
subject:

```
feat: add per-device self-sufficiency percentages
fix: stop the remainder going negative on a coarse device
docs: explain why Sonar is not a required check
```

Accepted types are `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`,
`refactor`, `revert`, `style`, `test`. Append `!` for a breaking change
(`feat!: …`). The type must be lower-case and the subject must not be empty or
sentence-cased.

Use `feat` only for a commit that completes a user-visible capability - the
intermediate commits building towards it are `fix`, `refactor`, `test` or
`chore`. Versioning keys off this.

### Your commit type chooses the version

Releases are cut automatically, and the version comes from the commits since the
last one rather than from anybody editing a file:

| Commit | Release |
| --- | --- |
| `feat:` | minor - `0.4.2` becomes `0.5.0` |
| `fix:`, `perf:` | patch - `0.4.2` becomes `0.4.3` |
| anything else | none |
| `feat!:`, or a `BREAKING CHANGE:` footer | minor while the version is still `0.x`, major after `1.0.0` |

So a week of documentation and dependency work releases nothing, which is the
intended outcome: an update notification a household learns to ignore is worse
than no notification.

A breaking change staying inside `0.x` is deliberate. `0.x` already means
anything here may change, and `1.0.0` is a promise about stability that a
maintainer makes on purpose - not one a commit subject makes on their behalf.

The rules are `scripts/release_version.py`, and `tests/test_release_version.py`
holds them against the table above: adding a type here without deciding whether
it ships fails the suite.

**The scope is optional for you.** The maintainer's commits carry the ticket id
as the scope (`fix(HEA-59): …`), which is why the history looks like that; since
you have no ticket number, a scope-less commit is correct and CI will not fail
you for it. If a scope is useful - `chore(deps): …`, `docs(ci): …` - use one.

## Development

The test suite **requires a Unix-like OS** - Linux, macOS, or WSL on Windows.
Home Assistant imports `fcntl`, and `pytest-homeassistant-custom-component`
registers as a pytest plugin, so on native Windows `pytest` fails during
*collection*, even for tests that never import Home Assistant. This is a platform
limit, not a configuration problem.

Python ≥3.14.2 (Home Assistant's floor).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt

pytest                                  # fast; no Home Assistant instance needed
pytest --cov --cov-fail-under=90
ruff check . && ruff format --check .
mypy custom_components tests
```

### The Lovelace cards

The cards are plain ES modules under `frontend/`, tested with vitest. What the
integration serves is a single bundle built from them:

```bash
npm ci
npm test                                # vitest
npm run build                           # frontend/ -> custom_components/.../frontend/
```

**The bundle is committed.** HACS ships `custom_components/` and nothing builds
on a household's machine, so the built file has to be in the repository. If you
change anything under `frontend/`, run `npm run build` and commit the result
alongside it - CI rebuilds and fails on a diff, because a stale bundle would
serve card code that no longer matches the sources under review.

### Trying a change against a real Home Assistant

`demo/` stands up a throwaway Home Assistant in a container, with an invented
household in it: rooms, devices, a week of fabricated figures, and the
integration set up against them. It needs Docker and nothing else.

```bash
node demo/run-e2e.mjs      # build a house, assert against it, repeat in Spanish
node demo/reset.mjs        # throw the house away, leave a container ready
node demo/setup.mjs        # onboard, build the rooms, fill in the Energy Dashboard
node demo/screenshots.mjs  # drive the setup flow, seed a week, photograph it all
node demo/cold-load.mjs 10 # load the dashboard cold N times, and count what renders
```

**`run-e2e.mjs` is the one to reach for before a frontend change.** It takes
about ten minutes and is deliberately not one of the gates - too slow, needs
Docker, and Home Assistant ships monthly and will break it periodically.

It earns that anyway. The unit tests mount a card against a double, which cannot
disagree with the code it was written beside; this runs the real cards in a real
Home Assistant and reads the figures a household would see. Its first Spanish
run found that every card reported an empty house on a Spanish install, which
501 green tests had never been able to see.

`docs/notes/DEMO_INSTANCE.md` covers it properly.

### The gates

CI runs ruff, mypy (strict), pytest with a 90% coverage floor, vitest, the
bundle-is-current check, hassfest and HACS validation. All must pass.

There is also a **SonarQube** gate, which runs only on the maintainer's local
server and is **deliberately not required in CI** - an external contributor
cannot run it, and being unable to run a required check is a bad contributor
experience. Do not worry about it.

### Some tests skip, and that is expected

Golden-master tests replay real recorder history captured from a live household.
That capture is **not in the repository** and never will be: whole-house
consumption at five-minute resolution is an occupancy trace, and this repo is
public. Those modules `skipif` the fixture is absent, so the suite is green
without it.

Where CI needs to prove something the capture would have shown, there is a
**synthetic** fixture that reproduces the behaviour instead - see
`tests/engine/test_bad_source_replay.py`, which regenerates a real upstream
counter bug from its arithmetic rather than shipping the readings.

If you contribute a fixture, the same rule applies: no real household data.

## House style

Worth knowing before your first PR - the full set is in
`docs/CRITICAL_INSTRUCTIONS.md` and `docs/TESTING_STANDARDS.md`.

- **Tests first.** TDD, and the tests carry `# Given` / `# When` / `# Then`
  comments.
- **The engine (`custom_components/home_energy_advisor/engine/`) is pure Python**
  with zero `homeassistant.*` imports. It is the accounting model, and it stays
  independently testable.
- **`Decimal` for money and energy**, never binary floats. Round only where a
  value becomes a Home Assistant state.
- **Realistic test data** - `Coarse Step Aircon`, `€0.234/kWh`, `0.25 kWh`
  steps. Not `foo` and `bar`.
- **Never weaken a test to make it pass.** A red test is information. If it is
  wrong, fix the test deliberately and say why in the commit.

## Design discussion

Disagreement is welcome and useful - several of the load-bearing decisions here
came from someone pushing back. If you think an ADR is wrong, say so in an issue
with your reasoning; ADRs are append-only, so a decision is revised by a new one
that supersedes it, not by editing history.
