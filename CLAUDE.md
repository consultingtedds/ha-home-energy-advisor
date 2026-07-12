# Home Energy Advisor — Session Entry Point

A Home Assistant custom integration providing per-device financial accounting:
Energy Used, Actual Cost, Cost Without Solar, Solar Saving.

## Read before any work

1. `docs/CRITICAL_INSTRUCTIONS.md` — non-negotiable checklist; scan every session
2. `docs/PLAN.md` — delivery plan, decisions made, epic/ticket map
3. `docs/adr/` — accepted decisions (append-only; never edit an accepted ADR)
4. Topic-specific: `docs/TESTING_STANDARDS.md` (writing tests),
   `docs/DOCUMENTATION_STANDARDS.md` (writing docs),
   `docs/notes/DEVICE_SENSOR_SURVEY.md` (device/sensor behaviour patterns)

## Project shape

- `custom_components/home_energy_advisor/` — the integration (thin HA adapter layer)
- `custom_components/home_energy_advisor/engine/` — accounting engine: **pure
  Python, zero `homeassistant.*` imports**, fully unit-testable
- `tests/` — pytest; `tests/fixtures/exploration_2026_07/` holds golden-master
  data captured from the real instance (provenance in its README)
- `docs/` — plan, ADRs, standards, notes

## Core architecture (detail in docs/PLAN.md and ADR-0002/0004)

Full proportional source allocation per 5-minute interval: house consumption =
grid import (live price) + solar (0, export cost deferred) + battery discharge
(weighted-average stored cost), allocated across tracked devices + an
"Untracked" remainder by share of draw. Invariant: Σ allocations = real costs.
Cycles (daily/monthly…) and power→energy conversion use **auto-created native
helpers** (utility_meter, Integral), never reimplemented maths.

## Workflow

- Plan → Linear ticket → TDD → code. Never code without a ticket.
- Linear: team **HEA**, project "MVP — Device Cost Accounting".
- Ask clarifying questions one at a time before writing code — do not assume.
  Debate design honestly; Paul decides.
- Confirm with Paul before writing files unless an approved plan covers them.
- Commits: Conventional Commits `type(HEA-nn): description`, direct to `main`,
  no feature branches. `feat` only on the final commit of a capability.

## Commands

```bash
pytest                          # unit tests (fast, no HA instance needed)
pytest --cov --cov-fail-under=90
ruff check . && ruff format --check .
mypy custom_components tests
./scripts/sonar-check.sh scan        # local SonarQube gate (see CRITICAL_INSTRUCTIONS)
./scripts/sonar-check.sh qualitygate # "status" must be "OK" — read full output, never tail/head
```
