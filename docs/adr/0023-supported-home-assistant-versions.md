# ADR-0023: Declare the oldest Home Assistant the suite actually runs against

## Status

Accepted

## Context

Home Assistant ships a minor release every month. HACS reads one optional key,
`homeassistant` in `hacs.json`, as the minimum version, and refuses to install
the integration for anyone below it. Nothing in HACS's own publishing
requirements says anything about versions, so the floor is entirely ours to
choose and entirely ours to get wrong.

It was wrong. The floor read `2026.7.0`, the suite tested `2026.7.2`, and the
reference instance ran `2026.9.1` - so the only version anybody actually used
was the one version nothing tested. That is how the deprecation in HEA-113
reached a live deploy while CI stayed green: on 2026.7.2 the call was not
deprecated, so there was nothing to report.

### What the platform actually guarantees

Two figures from Home Assistant's own documentation set the shape, and neither
is a matter of taste:

* **Supervisor treats Core older than 24 months as unsupported**, and users are
  told to *"update within 6 months (6 release cycles)"* because automatic YAML
  migrations only live that long. So a floor within about six months strands
  nobody Home Assistant itself considers current.
* **Deprecated functionality keeps working until a named release**, typically
  around two years out - 2027.8 for the one in HEA-113. Custom integrations get
  a warning for that whole window where core callers raise at once. Code written
  against an older floor therefore stays valid for a long time; what expires is
  the *warning-free* window, not the code.

### What the ecosystem does

Surveyed across well-known HACS integrations, the declared floor ranges from
three months behind (`ludeeus/integration_blueprint`, the scaffold most
integrations start from) to six years (HACS itself), with Frigate at six months
and several others past two years. There is no convention, only a habit: the
floor is raised when an integration needs a newer API, and otherwise left alone.

That habit is defensible - it is what the two guarantees above permit - but on
its own it produces exactly the failure this ADR exists to stop, because a floor
nobody tests is a claim rather than a fact.

## Decision

**The declared floor is the oldest Home Assistant release the test matrix
actually runs against. It is never a version we have not run.**

1. **CI tests the latest release**, so a deprecation is seen the month it lands
   rather than in a deploy log.
2. **CI also tests the floor**, as a second matrix entry with its own
   `pytest-homeassistant-custom-component` pin - that package hard-pins the Home
   Assistant it tests against, so the pin *is* how a version is chosen.
3. **`hacs.json` declares that floor**, and nothing else.
4. **The floor rises only when the integration needs something newer**, and the
   release notes say so. It is not raised to stay tidy: raising a floor strands
   installs, lowering one is free.
5. **Neither pin moves by bot.** `.github/dependabot.yml` ignores both, because
   this is a supported-floor decision rather than a chore, and
   `tests/test_dependency_pins.py` guards every copy of both.

**Before the first tagged release the floor is the latest release**, because
there is no install to strand and nothing to promise. That is the current state:
`2026.9.1`, one matrix entry, floor and ceiling the same version.

### The floor is measured, not chosen

Run against the suite, the integration passes completely on **2026.7.0** and
fails on **2026.6.4**, on two counts that are the product rather than the tests:
a power-only device's auto-created Integral helper produces no energy at all,
and a rebase leaves the cycle meters holding the crater that ADR-0022 removed.
So `2026.7.0` is the floor to declare when a release makes one meaningful, and
anything older is a version this integration does not support and must not
claim to.

The tests themselves must not narrow that. A device lookup written with
`async_get_device_by_identifier`, which exists only from 2026.9, would pin the
whole suite to 2026.9 and drag the declared floor up with it for no product
reason. Both test modules that resolve one of our devices scan the config
entry's own devices instead, which needs no API that moves.

### Rejected

* **Track the latest release forever.** Simple, always tested, and the right
  answer today - but after a tag it refuses to install for everyone who has not
  upgraded this month, including everybody Home Assistant's own six-month
  guidance considers current.
* **Declare a floor older than the matrix reaches**, as most of the ecosystem
  does. It costs nothing until it is wrong, and then it is wrong in a user's
  install rather than in CI. The whole point of a declared minimum is that
  somebody checked.
* **Follow a fixed distance - always six months back.** It would have declared
  2026.3.4 here, a release this integration genuinely does not work on. The
  distance is an input to choosing what to test, never a substitute for running
  it.

## Consequences

- One extra CI job once a range is supported, and one more place a Home
  Assistant bump can fail. That failure is the feature.
- `tests/test_dependency_pins.py` asserts the `home-assistant-frontend` pin
  against the *installed* Home Assistant's own manifest, which holds while one
  version is tested and needs revisiting when a second entry is added: the older
  job installs an older Home Assistant over the requirements file, and the two
  will not match. Carried on HEA-32 with the rest of the release work.
- A Home Assistant API newer than the floor cannot be used in shipped code
  without raising the floor, which is a decision with a cost rather than a
  convenience. HEA-113 took that trade deliberately, resolving a device through
  an entity instead.
- Revisit if HACS gains a supported-version policy of its own, if Home Assistant
  changes the 6-month or 24-month windows this rests on, or if the integration
  needs an API newer than the declared floor.
