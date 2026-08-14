# ADR-0017: Reuse before build, in that order

## Status

Accepted

Amends ADR-0008 decision 4, and the reasoning — though not the conclusions — of
ADR-0012 and ADR-0013.

## Context

The project's operating principle, as agreed with the maintainer, is a
**preference order**: start with what Home Assistant ships; if that will not do
the job, look at what the community has already built; write our own only when
neither will. Writing something that already exists is work we then have to
maintain forever.

`PLAN.md` records it correctly — *"Custom card only if evidence demands it"* —
and the charter's Open Source First principle says to avoid **unnecessary**
dependencies, not to avoid dependencies.

**ADR-0008 decision 4 hardened that into something stricter than was agreed.** It
decided that HEA ships its own Lovelace card "rather than requiring a HACS
install", and justified it by showing that *core* cards cannot express the
flagship view. Existing community cards were never assessed. They were excluded
by a premise stated in passing and never argued: that the flagship view must not
require a separate install.

That premise then travelled as settled law:

- ADR-0012 rejected a HACS period picker — *"ADR-0008 requires the flagship view
  to work without a separate install"*.
- ADR-0013 rejected ApexCharts and Plotly — *"Still rejected, by ADR-0008: the
  flagship view must not require a separate install"*.

In both, the option is dismissed by citation rather than by evaluation.
ApexCharts did also get a real capability check (no categorical x-axis, verified
in HEA-25); Plotly got none.

The irony is that ADR-0013 diagnosed exactly this failure mode, in its own
opening, about a different option:

> *"This option is excluded" was quietly promoted into "therefore mine is the
> only one left", without checking the middle.*

It corrected the error for Home Assistant's bundled chart component — reaching
the right answer, `ha-chart-base` — and left the same error standing one line
below for community cards.

**Re-examined, the conclusions hold.** No community card accepts an arbitrary
date range × device filter over our own statistics, so the card suite is
justified on evidence. And the HACS period picker would not have removed
ADR-0012's dependency on frontend internals: it is also a picker that creates the
same shared energy collection, so a card would still have to read that collection
off `hass.connection`. That coupling comes from *wanting to share a period with
Home Assistant's own energy cards*, which is ADR-0012 decision 1, not from
refusing an install.

So nothing shipped needs undoing. What needs fixing is the rule, because it will
be cited again — on the Sankey view PLAN sketches, on HEA-86's chart band, and on
whatever comes after.

## Decision

**1. The order is: Home Assistant core, then an existing community component,
then our own.**

Applies to everything, not only Lovelace cards: integrations, add-ons, frontend
components, Python dependencies. Each step is taken only when the one before it
is *measured* to fall short — the same evidence standard the charter already
demands.

**2. "Requires a separate install" is a cost to weigh, never a disqualifier.**

It is a real cost: a household has to find the thing, install it, and keep it
updated, and a flagship view that silently depends on a second install is a poor
first run. Weigh it. Do not let it end the comparison before it starts.

**3. Rejecting an existing component requires a reason of its own.**

Naming a rule is not a reason. A rejection must say which of these applies, with
evidence:

- **Capability** — it cannot do the job (ApexCharts' missing categorical axis is
  the model: verified, then recorded).
- **Maintenance** — abandoned, or a dependency we would end up owning anyway.
- **Fit** — it forces a shape that breaks something we have decided elsewhere.

"ADR-000n excludes it" is a pointer to a reason, not a reason. If the cited ADR
did not evaluate the option either, the chain has no evidence at the bottom.

**4. Decisions already shipped are not reopened by this.**

ADR-0008's card, ADR-0012's picker adapter and ADR-0013's use of `ha-chart-base`
all stand, re-examined above. This governs the next decision, not the last one.

## Rejected alternatives

- **Amend ADR-0008 decision 4 in place and stop there.** Smallest change, and it
  keeps the fix where the rule originated. Rejected because the principle is
  cross-cutting — it governs add-ons and libraries too — and burying it in an ADR
  about the statistics substrate is how it got lost the first time.
- **Leave it and rely on the maintainer catching it.** That is what happened
  here, three ADRs late, and only because the rule was quoted back to him in a
  form he recognised as wrong. Relying on that again is not a plan.
- **Ban writing our own without explicit sign-off.** Rejected as the same error
  inverted: a rule standing in for a judgement. The evidence requirement in
  decision 3 does the work without the ceremony.

## Consequences

A rejection is now falsifiable. "We looked at X and it cannot do Y" can be
checked and overturned when X gains Y; "the rules forbid X" cannot.

Some evaluations will cost real time — reading a card's source to find out
whether it can do the job is slower than citing a rule. That is the intended
trade: the alternative is maintaining a reimplementation forever.

Expect this to be cited when the Sankey view is designed. Community Sankey cards
exist and are the obvious first thing to test against the requirement, ahead of
extending our own suite.

The card suite HEA already ships is not evidence that building is the default. It
is evidence that this particular view had no existing answer — a conclusion that
was reached, in the end, on capability.
