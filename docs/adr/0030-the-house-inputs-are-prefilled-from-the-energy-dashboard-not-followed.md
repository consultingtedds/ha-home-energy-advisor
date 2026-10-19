# ADR-0030: The house inputs are prefilled from the Energy Dashboard, not followed

## Status

Accepted

## Context

Home Assistant's Energy Dashboard already holds most of what this integration
asks for on its house screen: the grid's import and export meters, every solar
source, the battery's charge and discharge meters, and the import price. Setup
prefills each of those from it, and the household confirms or changes them in
the same dropdowns. What it saves is our own copy.

Two things are read live and never copied: the export price (ADR-0026) and which
device sits inside which (HEA-168). Each has exactly one sensible source, and a
second copy could only drift.

Before 1.0 the question was asked whether the house inputs should work the same
way: follow the Energy Dashboard live, with the form asking only for what it
does not hold (HEA-222). A household had written that defining their batteries
twice was a burden, and following would hand several batteries and several grid
meters over in the shape Home Assistant already keeps them.

Two findings settled it.

**The households who re-entered things did so because of what we lacked.** The
batteries were entered twice because this integration took one battery, so two
had to be summed with template helpers first; that is HEA-220. Several grid
meters are HEA-221. The prefill itself was doing its job.

**The two configurations legitimately differ.** On the reference household,
every house input differs from its Energy Dashboard, and on purpose. The Energy
Dashboard there reads a template-filtered grid meter at two decimals, a daily
solar counter, and the inverter's own daily battery counters at 0.01 kWh. This
integration reads lifetime counters at full precision. The Energy Dashboard's
choices are fine for daily bars; for an engine that splits five-minute intervals
they are coarse steps and a reset every midnight, the conditions behind HEA-133
and HEA-139.

## Decision

**The house inputs stay this integration's own, prefilled from the Energy
Dashboard wherever it has an answer.**

1. **Prefill is the bridge.** Setup offers every meter the Energy Dashboard
   holds for a role, in its shape: every solar source, every battery (HEA-220,
   with its level and capacity where it has them), every grid meter (HEA-221).
   A grid source that only carries a standing charge is not a meter and is not
   offered. Reconfigure offers the same suggestions, so a battery added to the
   Energy Dashboard later is one confirmation away.
2. **Nothing a household chose is overridden.** What is saved is what they
   confirmed. An edit to the Energy Dashboard reaches this integration when the
   household opens Reconfigure, never by itself.
3. **Live reading stays for what has one source.** The export price and nesting
   are still read where they live (ADR-0026, HEA-168).

Rejected:

- **Follow the Energy Dashboard live, with overrides** (HEA-222's middle path).
  It would have moved the reference household onto worse meters unless it
  noticed and opted back out. An edit made for the Energy Dashboard's sake would
  have re-baselined our accounting without the household thinking of us. And
  every refusal on our form, a net counter for one (ADR-0010), would have had to
  become a Repair raised after the fact.
- **Follow only where the two already match.** It removes the first objection,
  but the rest remain. What it adds over a prefill is an edit arriving without a
  Reconfigure, which is rare, and if the two drift apart our figures keep
  running on a meter that still works.

## Consequences

- HEA-220 and HEA-221 carry the prefill work they need: lists of batteries and
  grid meters, read in the Energy Dashboard's shape.
- Reconfigure gains the Energy Dashboard's suggestions, and keeps what the
  household saved wherever they differ.
- A household that edits only the Energy Dashboard keeps its old meters here
  until it reconfigures. Those meters still work, so its figures stay right.
- Revisit if a household shows a real harm from the two drifting apart, or if
  Home Assistant itself starts treating the Energy Dashboard as the one
  register of meters that integrations are expected to follow.

## Update - 2026-10-19: the Energy Dashboard is where things are entered, and a change there is offered, not imposed

The decision above left one gap: a household that adds a battery or changes a
meter in the Energy Dashboard is not told this integration still has the old
one, and "why do I have to enter this when you already have it" is the
complaint that follows. So the Energy Dashboard becomes the **recommended**
place to enter the house's meters, and this integration takes changes from it
with the household's consent:

1. **Setup says where each answer came from** - taken from the Energy
   Dashboard - and where the Energy Dashboard lacks something it can hold, such
   as a battery's level and capacity, it says that is the place to add it.
2. **A change there is noticed.** When the Energy Dashboard's batteries or
   meters differ from what is saved here, a Repair lists the differences with
   two answers: **take them**, which updates the saved inputs as a Reconfigure
   would, or **keep mine**, which is remembered for exactly those differences so
   the household is not asked again until the Energy Dashboard changes once
   more.
3. Nothing is applied without that answer. The reasons above for not following
   live still hold: a household may keep better meters here on purpose, as the
   reference household does, and the form's refusals stay refusals.

Built with the battery work in HEA-220, and applied to grid meters by HEA-221.
