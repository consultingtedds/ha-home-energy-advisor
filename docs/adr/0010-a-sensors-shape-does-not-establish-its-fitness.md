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

## Update, 2026-09-21: the unit joins the shape, and ingest gains two checks

Four incidents from outside households, in one week. The decision above stands
unchanged; what follows fills in both of the gates it names, because each was
described by a single implemented instance and each now has more than one.

### Add time also asks what the sensor counts in

Section 2 said the config flow rejects a present-but-wrong `state_class` and
allows an absent one. It now applies the identical rule to the **unit**: a
present-but-uncountable unit is rejected, an absent one allowed (HEA-161).

The engine counts in kWh and Wh and converts between them from every reading, so
a mixture of the two is correct and is not flagged - two households lost time
believing a Wh sensor was their own mistake, and it was not
([issue 24](https://github.com/consultingtedds/ha-home-energy-advisor/issues/24),
[issue 27](https://github.com/consultingtedds/ha-home-energy-advisor/issues/27)).
Telling somebody their working setup is wrong would have them swap the entity,
which re-baselines the counter and loses accounting for nothing.

Anything the engine cannot convert - megawatt hours, joules - is a different
matter: it is refused at ingest, so the source would contribute nothing at all.
Refusing it while somebody is still choosing is the same asymmetry section 2
already draws, applied to a second property of the same pick.

**The absent case is the load-bearing half.** A cloud meter reconnecting
publishes no unit for several seconds, and treating that silence as a fact about
the sensor is exactly the defect HEA-149 was raised to fix - so the leniency here
is not politeness, it is correctness.

### Ingest time has three implemented instances, not one

Section 3 described the principle and then named one instance: no device can
consume more than the whole house over a full window. Two more now stand beside
it, and the three are deliberately at different scales.

| What is refused | Scale | Raised by |
| --- | --- | --- |
| A device's total above the whole house's | A full 12-bucket window | HEA-60 |
| One reading above what the house was metered over its own span | A single delta | HEA-157 |
| A reading whose unit is unknown, or has changed since the last one | A single reading | HEA-149 |

The middle one exists because the first cannot act in time. `_judge` needs a full
window of evidence before it will condemn anything - deliberately, so one
interval cannot condemn a coarse counter - and a single catastrophic delta lands
long before that verdict arrives. A vendor firmware update rescaled a plug's
counter by ten, which read as a cycle reset, and its whole new value was booked:
119 kWh to a water heater that had run four hours.

Two properties of that middle check are worth recording, because both are easy to
get wrong and neither is obvious from the code:

- **It is floored at one window.** Judged over its own span, every ordinary
  reading fails: a coarse counter's step exceeds what the house was metered in
  the twenty seconds it was reported over, which is the spreading approximation
  ADR-0006 is built on rather than a fault.
- **It measures the house over the delta's span, it does not extrapolate a
  rate.** An EV charger quiet while the house drew heavily, then honest about all
  of it at once, would be refused if it were judged against a rate taken from an
  idle hour. The house meter saw the same span the device did, so it is asked
  about that span.

### A refused reading is still claimed

This is the sharpest lesson of the four incidents and it qualifies the
"every refusal must be explainable" consequence above with a mechanism.

`_judge` is computed from what devices **claimed**, not from what was booked, and
it is what raises the Repair naming a faulty device. The first implementation of
HEA-157 refused a delta and dropped it - which silently removed the evidence, so
a counter that lied steadily became quietly uncounted instead of reported. The
project's own replay test caught it.

So a refusal at any of these gates must leave the claim behind it. The cost is
accepted openly: a rescaled device stays condemned until its claim ages out of
the window, about an hour, and its energy falls to Untracked in the meantime. The
house total stays right; what is lost is knowing which device spent it. That is
the correct trade, because the household is **told** - which is the whole of the
consequence this ADR already states.

## Update, 2026-09-22: the class is a permission, not a description

One exception to the `state_class` rule above, and it is worth recording because
the way it was found says more than the fix does.

**Home Assistant's Riemann sum helper declares `total`, unconditionally.**
`IntegrationSensor._attr_state_class` is set on the class, so no configuration
produces a `total_increasing` one. Sections 1 and 2 required exactly
`total_increasing` of an energy source, so every integral helper in Home
Assistant was refused - as a house-level input and as a device source alike.

That is the sensor a household builds to turn watts into energy, and it is **the
helper this integration creates for itself** on every power-only device
(ADR-0004). The coordinator reads its output directly, so the engine has been
accounting from a `total` Riemann sum since HEA-34 while the flow told households
the same sensor would be "misread". The rule was not protecting anything there;
it was refusing our own work.

The exception is drawn on the helper's **domain**, not on its class: an entity
published by an `integration`-domain config entry may declare `total`, and
nothing else may. A net meter is still refused, because no helper of that kind
publishes one. `discovery.py` already walked config entries to find what a helper
derives from, so the fact was to hand; what was missing was asking for it.

### The part worth keeping

The test that should have caught this **existed and was green**. This ADR's own
Consequences section demands it - *"a legitimate appliance whose source is itself
a helper, e.g. a Riemann integral over a plug's power sensor"* - and
`test_discovery_offers_an_integral_the_user_built_over_a_plug` asserted exactly
that. Its fixture gave the integral the class its `device_class` made eligible,
which Home Assistant never does. The fixture was written from the same belief as
the code, so it could only ever agree with it.

Changing that one fixture to say what Home Assistant says turned the test red
with no change to the production code at all. A fixture that cannot disagree with
the implementation is not evidence, and a structural check is only as good as the
structure the tests claim the platform has.

It reached a household before it reached us
([discussion 18](https://github.com/consultingtedds/ha-home-energy-advisor/discussions/18)),
who concluded the problem was his units, answered his own question wrongly, and
closed it - so the record said the rule worked (HEA-162).
