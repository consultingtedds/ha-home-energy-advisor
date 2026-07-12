# Testing Standards — Home Energy Advisor

Adapted from the retirement platform's `TESTING_STANDARDS.md` for Python /
pytest / Home Assistant. `docs/CRITICAL_INSTRUCTIONS.md` has the
non-negotiable one-liners; this file has the patterns.

---

## Test-Driven Development — Non-Negotiable

**Write tests before writing implementation code.** Always.

- Tests define expected behaviour; implementation satisfies the tests
- Minimum **90% line coverage** enforced in CI (`--cov-fail-under=90`)
- Realistic domain data in all tests — device names, prices, and step sizes
  from the real instance (see the fixtures README), never `foo`/`test123`
- Tests are documentation: they should read like specifications

### Given / When / Then

Every test uses `# Given` / `# When` / `# Then` comments with a short
description of the precondition/action/outcome unless completely obvious.
Combine `# When / Then` only for a single fluent expression (e.g.
`pytest.raises` context).

```python
def test_delta_calculator_cycle_reset_treats_new_value_as_fresh_cycle() -> None:
    # Given — counter mid-cycle at 2.75 kWh
    calculator = DeltaCalculator()
    calculator.observe(reading(at="02:14", kwh="2.75"))

    # When — the compressor cycle ends and the counter resets to 0 then climbs
    delta = calculator.observe(reading(at="02:19", kwh="0.0"))

    # Then — the reset itself yields no energy; the fresh value is the new baseline
    assert delta == Decimal("0")
```

### Failing tests are work in progress — never work around them

A failing test is a signal, not a nuisance. Do not modify a test to make it
pass unless the test itself is wrong. No `@pytest.mark.skip`, no weakened
assertions, no `try/except` swallowing. If the feature isn't built yet, the
test stays red as the standing reminder.

### Do not change production code to make tests pass

Missing collaborator? Build a fake or use a fixture. Only change production
code when a test reveals a genuine design flaw.

---

## Test types

| Type | Scope | Tools | Speed |
|---|---|---|---|
| Engine unit | `engine/` — pure Python, no HA | pytest | milliseconds; the default suite |
| Golden master | Engine against captured real-world fixtures | pytest + `tests/fixtures/` | fast |
| Integration-layer | Config flow, entity lifecycle, listeners, helper auto-creation | pytest + `pytest-homeassistant-custom-component` | slower; still no real HA instance |
| Dogfood | Real instance (homeassistant.tedds.net) | Epic 6 protocol | manual, per release |

No Docker, no Testcontainers — `pytest-homeassistant-custom-component`
provides a full in-process `hass` fixture.

**Config-flow tests are written before the flow is implemented** — the same
TDD loop applied at the UI boundary: define each step's schema, happy path,
and error paths as failing tests first.

### Test naming

```
test_<unit>_<context>_<expected_outcome>
```

e.g. `test_allocator_deficit_smaller_than_tracked_draw_caps_total_at_import_cost`.

---

## Engine test rules

- Money and energy assertions compare `Decimal`s exactly; if float enters at
  a boundary, convert once and assert with explicit tolerance (`pytest.approx`)
- **Invariant tests are first-class**: Σ device + remainder allocations equals
  bucket totals for every strategy, on every scenario, including
  property-style randomised scenarios if useful
- Time is always passed in, never read from the clock — engine functions take
  timestamps as arguments, which makes DST cases (Europe/Madrid transitions)
  plain test inputs
- Unavailable/unknown spans, cycle resets, midnight-spanning resets, and
  out-of-order events all have named test cases (see HEA-16/17 for the list)

## Golden-master rules

- Fixtures in `tests/fixtures/exploration_2026_07/` are captured real data —
  never edit them; provenance is documented in their README
- Energy (107.75 kWh) and naive-cost (€19.30) expectations are fixed;
  allocated-cost expectations are computed once under the agreed model, then
  pinned
- The binary-gate €7.63 figure is historical reference only — do not assert it

## Integration-layer test rules

- Use the `hass` fixture from `pytest-homeassistant-custom-component`; drive
  time with `async_fire_time_changed`, states with `hass.states.async_set`
- Every config-flow step: one test per outcome (success, each validation
  error, abort)
- Entity tests assert `unique_id`, `device_class`, `state_class`,
  `translation_key`, and restore-on-restart behaviour — these are what make
  long-term statistics and i18n work, so they are contract, not detail
- Repairs and diagnostics have tests (a broken source entity must raise a
  Repair, not log-and-continue)

---

## CI

`pytest --cov --cov-fail-under=90` runs on every push/PR alongside ruff, mypy,
hassfest, and HACS validation. The suite must stay runnable by any external
contributor with `pip install -r requirements_test.txt` — no local
infrastructure dependencies (SonarQube is a local pre-commit gate only, see
`CRITICAL_INSTRUCTIONS.md`).

CI tests against the pinned minimum supported HA version and the latest
release (`pytest-homeassistant-custom-component` tracks HA monthly releases —
the matrix catches breakage on either edge).
