# ADR-0012: Reuse Home Assistant's energy period selection, don't rebuild it

## Status

Accepted

Shapes the build of HEA-50 (the shipped Lovelace card) and absorbs the open
question in HEA-39 (how to present negative Cost Savings). Does not change any
decision in ADR-0008, which established *why* a shipped card is needed; this
decides *what it is built on*.

## Context

ADR-0008 concluded that a `utility_meter` cannot answer an arbitrary date range,
that long-term statistics can, and that HEA therefore ships its own Lovelace
card. HEA-50 then specified that card as needing a date-range picker with
presets, a device filter, and per-device cost figures over the chosen range.

Specifying a date-range picker is easy. Building a good one — presets, arbitrary
ranges, previous/next stepping, comparison against a prior period, timezone and
DST correctness, translation into every language Home Assistant supports — is
weeks of work, and it is work someone has already done.

**Home Assistant's Energy Dashboard already ships exactly this control.**
Inspected on 2026.8: preset ranges (today, yesterday, this week/month/quarter/
year, last 7/30/365 days, last 12 months), a calendar for an arbitrary start and
end, previous/next stepping, a "now" reset, and a menu offering *Compare data*
and *Download data*. The arbitrary-range case is precisely the question HEA-50
exists to answer.

It is also, from a user's point of view, **the** energy period control in Home
Assistant. A household that has used the Energy Dashboard already knows it. A
second, subtly different picker on a second energy-ish dashboard is a worse
experience even if it is built perfectly.

The governing principle, stated by the maintainer: *if it exists already, use it
rather than rewrite it* — and ideally, when Home Assistant improves it, that
improvement arrives with no work on our side.

## Decision

**1. Period selection is Home Assistant's, not ours.**

`energy-date-selection` is a core Lovelace card usable on any dashboard, not only
the Energy panel. Energy cards coordinate through a shared *energy collection*
identified by a `collection_key`. HEA's cards subscribe to that same collection
rather than owning a date range of their own.

The user places Home Assistant's own picker on the dashboard; our cards follow
it. Improvements to the picker arrive for free, and the two dashboards behave
identically because they are the same component.

**2. The layout follows the Energy Dashboard's structure.**

Wide charts in a primary column, a narrow rail of summary figures beside them, a
totals table beneath. Not imitation for its own sake: the arrangement is
familiar, it has been iterated on by people who do this full time, and
divergence should be something we choose deliberately rather than drift into.

**3. Negative values follow Home Assistant's existing convention.**

The Energy Dashboard already renders negative quantities — exported energy,
battery charge — as bars *below the axis* within the same stacked series. Cost
Savings goes negative under battery arbitrage loss (ADR-0003, HEA-39), and it
uses that same treatment. This settles HEA-39's open question: the mechanism is
not a `binary_sensor`, an attribute or a Repair, but the presentation convention
users already read elsewhere in the product they are already using.

**4. We do not attempt to reuse Home Assistant's energy *graph* cards.**

`energy-usage-graph` and its siblings are bound to Home Assistant's energy
preferences — the grid, solar and battery statistics configured in the Energy
Dashboard. They cannot be pointed at per-device cost data. This is the same wall
ADR-0008 hit. **We reuse the chrome, not the data cards.**

**5. The dependency on frontend internals is isolated to one module.**

Reading the energy collection (`getEnergyDataCollection` and friends) uses
Home Assistant frontend internals, which carry no stability guarantee. The
approach is proven — community cards extend `hui-energy-date-selection-card`
today — but a frontend refactor can break it.

That risk is accepted and contained: every touch of a frontend internal lives
behind a single adapter module. A breaking change upstream is then a one-file
fix, not a hunt through every card.

### Rejected alternatives

- **Build our own period picker.** Rejected: weeks of work to reach parity,
  permanently divergent from the control users already know, and every future
  Home Assistant improvement would have to be re-implemented by hand.
- **Depend on a HACS picker** (e.g. `energy-period-selector-plus`). Rejected:
  ADR-0008 requires the flagship view to work without a separate install, and it
  trades one unstable dependency for another that is also unmaintained-by-us.

  > **Reason corrected by ADR-0017**, conclusion unchanged. Citing ADR-0008's
  > install rule was not a reason — see ADR-0017 decision 3. The real one, found
  > by re-examining it: a HACS picker **would not remove the coupling at all.**
  > It is also a picker that creates the same shared energy collection, so a card
  > must still read that collection off `hass.connection` to follow it. The
  > dependency on frontend internals comes from decision 1 — sharing a period
  > with Home Assistant's own energy cards — not from refusing an install.
- **Wait for a public frontend extension API.** Rejected: none is announced, and
  the feature is the product's central promise. Waiting indefinitely for a
  guarantee is not a plan.
- **Only use the picker's *output* (a start and end date) and manage our own
  state.** Rejected: it drops the shared collection, so our cards and any
  Home Assistant energy card on the same dashboard would drift out of sync — the
  familiarity argument is lost precisely when both are on screen together.

## Consequences

The date-range capability HEA-50 was scoped to build no longer needs building.
That removes the largest and fiddliest piece of the card and lets the work start
on what is actually unique to HEA — the counterfactual, the per-device
allocation, and the ranked comparison.

The dashboard gains a hard dependency on Home Assistant's energy frontend
internals, isolated per decision 5. If that surface changes, the symptom is our
cards no longer following the picker, and the fix is one module.

HEA-39 needs no separate mechanism decision and no new entity; it becomes a
rendering rule inside the card.

A user must place Home Assistant's picker card on the dashboard for our cards to
follow it. The shipped example dashboard therefore includes it, and a card left
without a collection must degrade to a sensible default range rather than
render empty.

This decision would be worth revisiting if Home Assistant published a supported
extension API for energy collections — at which point decision 5's adapter is
the single place that changes — or if the internals proved unstable enough that
the maintenance outweighed the parity gained.
