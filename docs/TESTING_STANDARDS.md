# Testing Standards - Home Energy Advisor

Adapted from the retirement platform's `TESTING_STANDARDS.md` for Python /
pytest / Home Assistant. `docs/CRITICAL_INSTRUCTIONS.md` has the
non-negotiable one-liners; this file has the patterns.

---

## Test-Driven Development - Non-Negotiable

**Write tests before writing implementation code.** Always.

- Tests define expected behaviour; implementation satisfies the tests
- Minimum **90% line coverage** enforced in CI (`--cov-fail-under=90`)
- Realistic domain data in all tests - device names, prices, and step sizes
  from the real instance (see the fixtures README), never `foo`/`test123`
- Tests are documentation: they should read like specifications

### Given / When / Then

Every test uses `# Given` / `# When` / `# Then` comments with a short
description of the precondition/action/outcome unless completely obvious.
Combine `# When / Then` only for a single fluent expression (e.g.
`pytest.raises` context).

```python
def test_cumulative_source_cycle_reset_treats_the_new_value_as_a_fresh_cycle() -> None:
    # Given - the cycle-resetting counter is mid-cycle at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When - the compressor cycle ends and the counter restarts, already at 0.25
    delta = source.observe(reading(at="02:19", value="0.25"))

    # Then - the post-reset value is the energy, not a negative difference
    assert delta == EnergyDelta(
        kwh=Decimal("0.25"), start=moment("02:14"), end=moment("02:19")
    )
```

Note the delta carries its **span**, not just a magnitude. A counter that climbed
while its sensor was unavailable reports one jump on recovery; pricing that at the
instant it was reported would charge it all at whatever tariff happened to be
active then. Assertions therefore pin `start` and `end`, not only `kwh`.

### Failing tests are work in progress - never work around them

A failing test is a signal, not a nuisance. Do not modify a test to make it
pass unless the test itself is wrong. No `@pytest.mark.skip`, no weakened
assertions, no `try/except` swallowing. If the feature isn't built yet, the
test stays red as the standing reminder.

### Do not change production code to make tests pass

Missing collaborator? Build a fake or use a fixture. Only change production
code when a test reveals a genuine design flaw.

---

## What to assert

Coverage says which lines ran. These three rules are about the assertions that
made them run, and each is here because a green suite missed something that
then cost live debugging time.

### Assert the obligation, not the mechanism

A test that describes your implementation can only confirm you wrote what you
wrote. Assert the job the value has to do.

```python
# BAD - restates the implementation, and passes for any build of the same release
assert "0.0.1" in url

# GOOD - states why the url exists: it must differ when the content differs
assert fingerprint(changed) != fingerprint(before)
```

The first shipped. The url carried only the release, every build between two
releases reused it, and it is served with a 31-day cache, so a redeploy was
invisible to any browser that had already loaded the cards.

**Where a value's purpose is a relation between two states, the test has to
instantiate both states.** One output inspected for a substring cannot express
"differs when it should". This covers cache keys, `unique_id`, idempotency
guards, migration versions, restore baselines, and anything else whose whole
point is same-or-different.

It pairs with the rule that a fixture must be able to disagree: `"0.0.1"` was a
string also written into the manifest, so the test and the code were reading
from the same belief.

### Enumerate the host contract

When implementing against a Home Assistant interface, read the **type
definition**, not the guide, and record a decision for every member: implement
it, or omit it deliberately and say why.

The developer docs for dashboard strategies describe one member, `generate`. The
interface has six, plus `getCreateSuggestions` alongside. Implementing only the
documented one shipped a dashboard that opened an empty title/icon/url form, and
very nearly shipped a layout that never regenerated. Two defects, one omission,
and no test of our own code could have found either: the code was absent, not
wrong.

### What CI cannot reach gets a check in the procedure

Some failures live outside the test boundary - a deploy that copies without
deleting, a share holding files the repository no longer has. Those get a step
in the deploy procedure rather than a test.

**Make it assert a number.** "Check the cards work" passes in the broken state;
the cards worked perfectly while the instance served a bundle from two releases
earlier. "One request of about 51 KB" does not.

---

## Test types

| Type | Scope | Tools | Speed |
|---|---|---|---|
| Engine unit | `engine/` - pure Python, no HA | pytest | milliseconds; the default suite |
| Golden master | Engine against captured real-world fixtures | pytest + `tests/fixtures/` | fast |
| Integration-layer | Config flow, entity lifecycle, listeners, helper auto-creation | pytest + `pytest-homeassistant-custom-component` | slower; still no real HA instance |
| Dogfood | Real instance (the maintainer's, not in CI) | Epic 6 protocol | manual, per release |

No Docker, no Testcontainers - `pytest-homeassistant-custom-component`
provides a full in-process `hass` fixture.

**Config-flow tests are written before the flow is implemented** - the same
TDD loop applied at the UI boundary: define each step's schema, happy path,
and error paths as failing tests first.

### Test naming

```
test_<unit>_<context>_<expected_outcome>
```

e.g. `test_allocator_deficit_smaller_than_tracked_draw_caps_total_at_import_cost`.

---

## Assert the value, not that something happened

**If the expected value can be worked out, assert it.** An assertion earns its
place only if a materially wrong implementation would fail it.

```python
# No - every wrong answer but zero passes
assert hass.states.get("sensor.untracked_energy_devices_actual_cost") is not None
assert saved(allocation) > 0
assert any(entry.reason is DecisionReason.DROPPED_LATE for entry in decisions)

# Yes - 1 kWh imported at 30 c, of which the aircon drew 0.6
assert _published(hass, UNTRACKED_COST) == Decimal("0.1200")
assert saved(allocation) == 2 * PEAK
```

Work the figure out **from the scenario, by hand, before running the test**. A
value copied out of a failing run is not a prediction, and a test written that
way passes whatever the code does.

### What is still specific

- **Equality and identity**, including absence: `assert hass.states.get(...) is
  None` for an entity that must not exist is an exact claim, and so is
  `assert entries == []`.
- **A guard before a real assertion.** `assert state is not None` so that mypy
  will allow `state.state`, or so a helper can return a non-optional, is type
  narrowing rather than a test. The assertion is the line after it.
- **A precondition in `# Given`.** `assert before > 0` before a rebase stops the
  test proving nothing on a household that had accrued nothing. The same line in
  `# Then` is a weak outcome - the section decides which it is.
- **A relationship, where the relationship is the claim.** `floor <= actual <=
  ceiling` says the band brackets the figure; `after >= before` says a published
  total never falls. No single value expresses either.
- **A boolean that is itself the outcome**: `assert await
  hass.config_entries.async_setup(entry_id)`.

### When a figure genuinely cannot be pinned

Say so in the test, and say where it *is* pinned. A power-only device's energy
depends on Home Assistant's own integration helper, so the coordinator test
asserts the seam and names `test_integral_helper` as the place the arithmetic is
proven. That is the exemption; an unexplained `> 0` is not.

---

## Engine test rules

- Money and energy assertions compare `Decimal`s exactly; if float enters at
  a boundary, convert once and assert with explicit tolerance (`pytest.approx`)
- **Invariant tests are first-class**: Σ device + remainder allocations equals
  bucket totals for every strategy, on every scenario, including
  property-style randomised scenarios if useful
- Time is always passed in, never read from the clock - engine functions take
  timestamps as arguments, which makes DST cases (Europe/Madrid transitions)
  plain test inputs
- Unavailable/unknown spans, cycle resets, midnight-spanning resets, and
  out-of-order events all have named test cases (see HEA-16/17 for the list)

## Golden-master rules

- Fixtures in `tests/fixtures/exploration_2026_07/` are captured real data -
  never edit them; provenance is documented in their README
- Energy (107.75 kWh) and naive-cost (€19.30) expectations are fixed;
  allocated-cost expectations are computed once under the agreed model, then
  pinned
- The binary-gate €7.63 figure is historical reference only - do not assert it

## Integration-layer test rules

- Use the `hass` fixture from `pytest-homeassistant-custom-component`; drive
  time with `async_fire_time_changed`, states with `hass.states.async_set`
- Every config-flow step: one test per outcome (success, each validation
  error, abort)
- Entity tests assert `unique_id`, `device_class`, `state_class`,
  `translation_key`, and restore-on-restart behaviour - these are what make
  long-term statistics and i18n work, so they are contract, not detail
- Repairs and diagnostics have tests (a broken source entity must raise a
  Repair, not log-and-continue)

---

## CI

`pytest --cov --cov-fail-under=90` runs on every push/PR alongside ruff, mypy,
hassfest, and HACS validation. The suite must stay runnable by any external
contributor with `pip install -r requirements_test.txt` - no local
infrastructure dependencies (SonarQube is a local pre-commit gate only, see
`CRITICAL_INSTRUCTIONS.md`).

CI tests against the pinned minimum supported HA version and the latest
release (`pytest-homeassistant-custom-component` tracks HA monthly releases -
the matrix catches breakage on either edge).
