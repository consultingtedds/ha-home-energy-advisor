# Critical Instructions — Home Energy Advisor

Scan this before every session. Push details to the linked documents — this
file is the checklist, not the guide. Adapted from the retirement platform's
`ai-shared-config/CRITICAL_INSTRUCTIONS.md` for a Python / Home Assistant
custom integration.

---

## AI Workflow

### Before writing any code
1. Read `CLAUDE.md`, this file, `docs/PLAN.md`, and any ADRs touching the task
2. If any requirement or approach is ambiguous, ask clarifying questions one at a time before writing code — do not assume
3. Think before coding. State your assumptions. If a request is impossible, explain why and propose alternatives. If a simpler approach exists, propose it. If a more complex approach is required, explain why.
4. Do not just agree that recommendations or answers are great or right. Reason them through; if you disagree, give your reasoning. Healthy debate is expected — the maintainer chooses the course.

### Before responding
1. Review every changed file against the 🚫 NEVER and ✓ ALWAYS checklists below
2. List every violation found
3. Fix every violation
4. Only then present the solution

### Workflow for writing new code
1. Confirm the Linear ticket (HEA-nn) the work belongs to
2. Write the tests first (TDD) — engine behaviour before integration wiring
3. Write the code to make the tests pass
4. Run ruff, mypy, pytest with coverage
5. Run the local SonarQube gate before committing

---

## 🚫 NEVER

### Architecture

| Never | Use instead |
| --- | --- |
| `homeassistant.*` imports inside `engine/` | Engine is pure Python; the integration layer adapts HA state to engine inputs |
| Reimplementing native helper functionality (cycle resets, W→kWh integration) | Auto-create native `utility_meter` / Integral helpers — ADR-0004 |
| Static/module-level mutable state for shared behaviour | Small injected objects; composition over inheritance |
| Reflection, `importlib` tricks, `eval` | Explicit, type-safe wiring |
| Logic inlined in orchestrating functions (conditionals, nested loops) | Linear sequence of named helpers; max one level of loop nesting |

### Home Assistant

| Never | Use instead |
| --- | --- |
| Blocking I/O in the event loop (`time.sleep`, sync HTTP, file I/O in callbacks) | async APIs; `hass.async_add_executor_job` for blocking libraries |
| I/O or heavy computation in entity properties | Compute in the update path; properties return stored values |
| `device_id` where `entity_id` works | `entity_id` |
| Editing `.storage`, or YAML instructions for UI-managed config | Config flow / options flow / HA APIs |
| Auto-onboarding devices that merely match `device_class` | Explicit user selection (false friends: cycling FTP watts, phone battery power) |
| Entities without `unique_id` or `translation_key` | Both, always |
| Hardcoded user-facing strings (flow text, entity names, Repairs) | `strings.json` + `translations/en.json`, `es.json` |
| `suggested_area` on `DeviceInfo`, or assigning an area to HEA's own devices | Nothing — read the *source* device's area and expose it as data (ADR-0009 / HEA-58). `suggested_area` is removed in HA **2026.9**, and an area changes entity ids |

### Money and accounting

| Never | Use instead |
| --- | --- |
| Binary-float accumulation of money or energy totals | `Decimal` for accumulators; round only at presentation |
| Costs that break the invariant | Σ device + remainder allocations must equal bucket totals — test-enforced |
| Phantom deltas after `unavailable`/`unknown` spans or source-sensor recovery | Treat unavailable spans as no-data; reset-rule per ADR-0004 |

### Tests

| Never | Use instead |
| --- | --- |
| `try/except` in test bodies | `pytest.raises` |
| `@pytest.mark.skip` / weakened assertions to silence a failure | Leave it red; fix the underlying issue |
| Modifying production code to make a test pass | Fixtures, fakes, or a genuine design fix |
| `foo` / `bar` / `test123` data | Realistic data: Guest Bedroom Aircon, €0.234/kWh, 0.25 kWh steps |
| Naked float equality | `Decimal` comparisons or `pytest.approx` with explicit tolerance |
| Invoking `pytest` from Windows-side automation (git hooks, pre-commit, scripts) | Route it through a Unix shell (WSL). HA imports `fcntl`, so pytest dies at *collection* on native Windows — even for tests with no HA imports |

### Privacy — this is a public repo

Everything here is MIT-licensed and world-readable, including git history. Assume
anything committed is permanent and indexed.

Never reference a real home. Development and dogfooding run against a lived-in
instance, so any capture, table or example taken from it is real data until it is
deliberately made otherwise — treat it that way by default.

| Never | Use instead |
| --- | --- |
| Committing real captured instance data | Keep the capture local and `.gitignore` it; make the test `skipif` the fixture is absent. Anything CI must prove needs a **synthetic** fixture |
| Whole-house consumption at sub-hourly resolution, anywhere | Nothing — it is an occupancy trace (when the house is empty, when people wake). This is the single most sensitive artefact the project touches |
| Household members' names, room-by-room inventories, appliance lists that narrow the property type | Generic labels, or omit entirely. "Living Room Aircon" is fine; a garden appliance implies a private water supply |
| Hostnames, IPs, timezones, lifetime counter readings | "the reference instance". A live hostname is an address for someone's home |
| Assuming a rename is enough | **Minimise first, anonymise second.** Ask what the project actually needs. A 9-row table relabelled still discloses that the house has 9 rooms |

### Process

| Never | Use instead |
| --- | --- |
| Code without a Linear ticket | Create/pick the HEA-nn ticket first |
| Secrets in code or git | Environment variables; nothing secret belongs in this repo at all |
| Writing multiple files in one operation | One file at a time — each change must trigger the IDE diff window |
| Authoring project files through shell heredocs (`cat >> file`) | The editor, always. A shell write opens no diff, so the maintainer cannot see or challenge it as it happens. Bash is for *running* things, never for authoring |

---

## ✓ ALWAYS

### Before writing any file
- Confirm with the maintainer first — skip only if a plan covering those files was already approved this session

### Architecture
- Engine (`engine/`) pure Python, fully typed, no HA dependency
- Integration layer thin: adapts HA events/state to engine calls, publishes results to entities
- Full type hints everywhere; `mypy --strict` clean; `from __future__ import annotations`
- Orchestrating functions read as a linear sequence of named helper calls
- Helpers named for what they return, not how they work

### Home Assistant
- Config flow for all setup; options flow for changes; pre-fill from Energy Dashboard preferences where possible
- `RestoreEntity` for accumulating sensors; correct `device_class`/`state_class` so long-term statistics work
- Diagnostics expose enough to explain any cost figure (transparency is a PRD constraint)
- Repairs issues for broken source entities, never silent failure
- Consult the HA best-practices skill/docs before dashboards, automations, helper choices

### Tests
- Write tests **before** implementation — TDD, no exceptions
- `# Given`, `# When`, `# Then` comments in every test (combine `# When / Then` for a single fluent expression)
- Full patterns: `docs/TESTING_STANDARDS.md`

### i18n
- All user-facing strings in `strings.json` + `translations/` (en, es) from day one

### Privacy
- Before committing any example, table or fixture, ask: *does this describe a real
  home, and does the project actually need it?* Omit before renaming
- Real captures live only in `.gitignore`d fixture directories; their tests skip
  when absent, and a synthetic equivalent covers whatever CI must prove

---

## ⚠ CHECK — before every commit

- [ ] `ruff check .` and `ruff format --check .` — clean
- [ ] `mypy custom_components tests` — clean, strict
- [ ] `pytest --cov --cov-fail-under=90` — green
- [ ] `./scripts/sonar-check.sh scan` — all measures 0
- [ ] `./scripts/sonar-check.sh qualitygate` — `"status":"OK"` near the top of the JSON. Never pipe through `tail`/`head`; `"caycStatus"` at the bottom is unrelated.
- [ ] Commit message: `type(HEA-nn): description` (commitlint enforces locally + in CI)

SonarQube is a **local** gate (the maintainer's server at `http://localhost:9000`); the GitHub CI
pipeline must stay green without it, because external contributors cannot run it. If
SonarQube is unavailable, run the other three gates, note the skip in the commit
message, and run sonar as a follow-up before the next push.

### Commit types
| Type | Version effect |
| --- | --- |
| `feat:` | minor bump |
| `fix:` | patch bump |
| `chore:`, `docs:`, `refactor:`, `test:`, `ci:` | no bump |

Use `fix`/`chore`/`test`/`docs` for in-progress commits; `feat` **only on the final
commit** that delivers the user-visible capability. Work directly on `main`.

---

## Quick references

| If you need... | Read |
| --- | --- |
| Delivery plan, decisions, epic map | `docs/PLAN.md` |
| Accounting model rationale | `docs/adr/0002-*.md`; late-arrival correction policy in `docs/adr/0006-*.md` |
| Device/sensor behaviour patterns on the reference instance | `docs/notes/DEVICE_SENSOR_SURVEY.md` |
| Original validation data + published tables | `docs/notes/AIRCON_COST_EXPLORATION.md`, `tests/fixtures/exploration_2026_07/` (local-only capture — see `.gitignore`) |
| Entity naming, and why it is effectively permanent | `docs/adr/0003-*.md`, superseded on one name by `docs/adr/0009-*.md` |
| Why period figures come from statistics, not helpers | `docs/adr/0008-*.md` |
| Test patterns | `docs/TESTING_STANDARDS.md` |
| Docstring/ADR/README/diagram rules | `docs/DOCUMENTATION_STANDARDS.md` |
| A ruff upgrade failing on rules nobody chose | `pyproject.toml`, the comment above `select = ["ALL"]` |
| Why two files pin the same version, and what breaks if they drift | `tests/test_dependency_pins.py` |
| Product intent | `docs/VISION.md`, `docs/PRODUCT_CHARTER.md`, `docs/PRD.md`, `docs/adr/0000-*.md` |
