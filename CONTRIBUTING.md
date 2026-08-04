# Contributing

Contributions are welcome. This guide covers the things that are easy to trip
over, most of which are consequences of what the project is: a financial
accounting engine, where being wrong quietly is worse than failing loudly.

## Reporting a bug

Use [GitHub Issues](https://github.com/consultingtedds/ha-home-energy-advisor/issues).
That is the right place, and the only place you need.

For anything involving wrong figures, please attach the **diagnostics download**
(Settings → Devices & Services → Home Energy Advisor → ⋮ → Download diagnostics).
It carries the per-source decision log — why each reading was counted, gated or
refused — which is usually enough to explain a figure without access to your
instance. Entity ids and device names are redacted.

## What are those `HEA-nn` references?

Issue ids from the maintainer's private tracker. They appear in commit messages,
ADRs and code comments as provenance markers — "this line exists because of that
piece of work".

**You do not need access to them.** Everything a contributor needs is in the
repository:

- `docs/adr/` — the decisions and, more usefully, the reasoning and the
  alternatives that were rejected. Start here for *why* the code is shaped as it
  is.
- `docs/PLAN.md` — the delivery plan and the decision log.
- Commit messages — deliberately written to explain reasoning, not just changes.

If you find yourself needing a ticket to understand something, that is a
documentation bug worth raising.

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

Use `feat` only for a commit that completes a user-visible capability — the
intermediate commits building towards it are `fix`, `refactor`, `test` or
`chore`. Versioning keys off this.

**The scope is optional for you.** The maintainer's commits carry the ticket id
as the scope (`fix(HEA-59): …`), which is why the history looks like that; since
you have no ticket number, a scope-less commit is correct and CI will not fail
you for it. If a scope is useful — `chore(deps): …`, `docs(ci): …` — use one.

## Development

The test suite **requires a Unix-like OS** — Linux, macOS, or WSL on Windows.
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

### The gates

CI runs ruff, mypy (strict), pytest with a 90% coverage floor, hassfest and HACS
validation. All must pass.

There is also a **SonarQube** gate, which runs only on the maintainer's local
server and is **deliberately not required in CI** — an external contributor
cannot run it, and being unable to run a required check is a bad contributor
experience. Do not worry about it.

### Some tests skip, and that is expected

Golden-master tests replay real recorder history captured from a live household.
That capture is **not in the repository** and never will be: whole-house
consumption at five-minute resolution is an occupancy trace, and this repo is
public. Those modules `skipif` the fixture is absent, so the suite is green
without it.

Where CI needs to prove something the capture would have shown, there is a
**synthetic** fixture that reproduces the behaviour instead — see
`tests/engine/test_bad_source_replay.py`, which regenerates a real upstream
counter bug from its arithmetic rather than shipping the readings.

If you contribute a fixture, the same rule applies: no real household data.

## House style

Worth knowing before your first PR — the full set is in
`docs/CRITICAL_INSTRUCTIONS.md` and `docs/TESTING_STANDARDS.md`.

- **Tests first.** TDD, and the tests carry `# Given` / `# When` / `# Then`
  comments.
- **The engine (`custom_components/home_energy_advisor/engine/`) is pure Python**
  with zero `homeassistant.*` imports. It is the accounting model, and it stays
  independently testable.
- **`Decimal` for money and energy**, never binary floats. Round only where a
  value becomes a Home Assistant state.
- **Realistic test data** — `Guest Bedroom Aircon`, `€0.234/kWh`, `0.25 kWh`
  steps. Not `foo` and `bar`.
- **Never weaken a test to make it pass.** A red test is information. If it is
  wrong, fix the test deliberately and say why in the commit.

## Design discussion

Disagreement is welcome and useful — several of the load-bearing decisions here
came from someone pushing back. If you think an ADR is wrong, say so in an issue
with your reasoning; ADRs are append-only, so a decision is revised by a new one
that supersedes it, not by editing history.
