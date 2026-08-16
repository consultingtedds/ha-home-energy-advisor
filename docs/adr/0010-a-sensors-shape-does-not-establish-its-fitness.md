# ADR-0010: A sensor's shape does not establish its fitness

## Status

Accepted

Generalises a pattern already applied piecemeal in ADR-0004 (the EnergySource
taxonomy) and ADR-0006 (treating unavailable spans as no-data). It supersedes
nothing; it names a principle the codebase had been rediscovering one incident at
a time.

## Context

Home Assistant describes a sensor structurally: `device_class`, `state_class`,
unit. The integration leaned on that description to decide what it could account
for - a `total_increasing` kWh sensor is an energy counter, a `measurement` W
sensor is a power reading, and anything else is rejected.

That is necessary and it works. It is also, repeatedly, not sufficient. Four
separate defects in four weeks were all the same shape:

| | The sensor was… | and it was… |
|---|---|---|
| **HEA-54** | a well-formed counter | a net or forecast figure the engine would mis-account |
| **HEA-60** | a well-formed `total_increasing` kWh counter | **lying** - `total += consumption` each poll, inflating one device ~97× and, because allocation is proportional, silently under-reporting every other device for days |
| **HEA-64** | a well-formed `total_increasing` kWh counter | **dead** - `unknown` since the instance was first surveyed, no recorded history in seven days. Discovery offered it *in preference to* the working power sensor beside it, so the device could only be added in a way that could never accumulate |
| **HEA-66** | 90 well-formed counters | **derived from inputs already consumed** - period aggregates of the household's own grid and battery meters. Selecting one would book house-level energy a second time, as a device |

Every one passed every structural check available. Each was found by dogfooding
rather than by a test, because a test asserts what we thought to ask.

The common failure is not a missing rule. It is a category error: treating *how a
sensor is described* as evidence of *what it means and whether it works*. Home
Assistant's schema tells us how to read a number. It cannot tell us whether the
number is true, whether it is arriving, or whether we are already counting it
somewhere else.

This matters more here than in most integrations because of what the product
claims. The PRD's promise is that the per-device figures can be trusted, and
ADR-0002's proportional allocation means every source feeds every device's
number: one bad input does not produce one bad figure, it produces a whole bad
ledger. Being confidently wrong is the specific failure this product cannot
afford.

## Decision

**A sensor's structure gates whether we *can* read it. Fitness - is it true, is
it arriving, is it already counted - is a separate question, asked separately, at
three distinct points.**

### 1. Suggestion time (discovery) - semantics, not just shape

Discovery answers "which of your appliances could you track?". A candidate must
therefore be plausibly *a device*, not merely a readable number. Structural
eligibility is the entry condition, not the answer. At minimum, exclude what is
provably not a device: sensors derived (transitively) from inputs the integration
already consumes, and sensors belonging to a device already supplying a tracked
or house-level source (HEA-66).

Prefer a source that is *working* over one that merely type-checks (HEA-64).

This never becomes auto-onboarding. ADR-0004's rule stands: the user always
chooses. Filtering changes what is *offered*, not who decides - and offering a
choice that is provably wrong to make is its own kind of failure.

### 2. Add time (config flow) - lenient, because the user is explicit

An explicit manual pick is a statement of intent and is trusted further than a
suggestion: a present-but-wrong `state_class` is rejected, an absent one is
allowed (ADR-0004, HEA-54). Unchanged by this ADR, and deliberately asymmetric
with discovery - strict about what we *propose*, lenient about what the user
*insists on*.

### 3. Ingest time (engine) - plausibility, continuously

Configuration-time checks cannot catch a source that breaks later, and HEA-60's
counter was correct when configured. The engine therefore validates readings
against physical reality as they arrive, using facts it holds rather than
thresholds someone has to tune. The implemented instance: no device can consume
more than the whole house over a full window.

A refusal is never silent. It is logged as a `DecisionReason` on the source's own
diagnostics log and surfaced as a Repair naming the device, because a figure
frozen at a stale value is precisely the quiet wrongness this is meant to
prevent.

### Rejected alternatives

- **Tighter structural rules.** Rejected: no `device_class`/`state_class`
  combination distinguishes a counter that is true from one that is lying, dead
  or double-counted. All four defects satisfied every rule we could express in
  those terms. More schema would have caught none of them.
- **Trust the user, validate nothing.** Rejected: the user cannot see it either.
  HEA-60 ran for days against figures that looked entirely reasonable, and the
  daily total matched the counter delta exactly - the accounting was flawless and
  the answer was wrong by 97×.
- **Validate everything at configuration time.** Rejected: a source that works
  today can break tomorrow, and a device that is legitimately off looks identical
  to one that is broken. Seasonal silence is normal (HEA-24), so a
  configuration-time liveness gate would reject working setups every winter.
- **Hide anything suspect from discovery.** Rejected: it conflicts with
  never-auto-onboard and hides real devices with unusual sensors. The rule is
  narrower - exclude only what is *provably* not a device; sort the merely
  suspicious last, and let the user see it.

## Consequences

- **Fitness checks are a first-class concern**, not incident response. When
  adding a source, ask what makes it *unfit* and where that is best detected -
  and prefer facts the system already holds (the house total, a helper's declared
  source) over configurable thresholds, which are a maintenance burden and a
  support question.
- **Every refusal must be explainable.** The `DecisionReason` log and the
  diagnostics download are load-bearing, not debug aids: they are how a user or
  maintainer finds out *why* a figure is missing. New gating reasons belong there.
- **Discovery gets more logic**, and with it the risk of hiding a genuine device.
  Its tests must include the awkward case - a legitimate appliance whose source is
  itself a helper, e.g. a Riemann integral over a plug's power sensor - so
  filtering never becomes a blunt "exclude all derived sensors".
- Immediate follow-up: HEA-64 and HEA-66.
- **Revisit if** Home Assistant gains a first-class way to express sensor
  provenance or health (something like "this is derived from that", or a
  standardised liveness signal). Several filters here reconstruct by inference
  what the platform could state outright, and would be better delegated than
  maintained.
