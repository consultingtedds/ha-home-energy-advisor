# ADR-0036: A tariff plan is a typed schedule, priced against recorded grid statistics

## Status

Accepted

The first part of HEA-255 (GitHub discussion 58). Takes the integration from
reporting what was paid into advising on what else could have been paid. Leaves
the standing-charge decision for devices (PLAN.md, HEA-97) standing: the daily
charge here belongs to a plan comparison only.

## Context

Would have paid prices the household's energy at its **own** import price, so it
says what the installation saved at today's prices, not whether another plan
would be cheaper. A household told its tariff is going up (the reference home,
November 2026) wants to know which offer to move to, and the offers it can choose
from are published as schedules: a price for each time band, weekdays and
weekends, sometimes an export price, and a daily charge.

Home Assistant already records what such a comparison needs. The grid's import
and export meters are long-term statistics, kept hourly and indefinitely; the
reference home holds thirteen months of them. Every hour of a schedule has a
price, so every recorded hour can be priced at any plan.

Two questions sit under "what would plan B have cost?":

1. What would the household's **real** imports and exports have cost on plan B?
2. What would the house have cost on the plan it would be on **without** its
   installation - all consumption from the grid, nothing exported?

The first decides whether to switch. The second is a fairer baseline for Saved.

## Decision

**A plan is a typed schedule, entered in the integration, and priced against
Home Assistant's recorded hourly grid statistics. The first comparison re-prices
the household's real flows.**

1. **Real flows first.** Each plan prices the grid import and export the meters
   actually recorded, hour by hour: import at the band's import price, export at
   its export price. Nothing is modelled, so the figure is exact. Its one
   assumption is said beside it: the household is taken to have run its battery
   the same way, where a different plan might have led an optimiser elsewhere.
   The no-installation baseline (question 2) comes later, on the same plans.

2. **A plan is a schedule, not an entity.**
   - It is a name, a daily charge, a flat export price, an optional holiday
     calendar, and its time bands.
   - A band is which days it applies to (weekdays; weekends and holidays; every
     day), the hours it covers, an import price, and optionally its own export
     price, which otherwise is the plan's.
   - Every hour of every kind of day falls in exactly one band. A plan that
     leaves an hour uncovered, or covers one twice, is refused when it is
     entered, never priced as zero.
   - Bands are in the household's local time, as offers are published. An hour
     that daylight saving repeats is priced twice, once for each recorded hour;
     an hour it skips has no record and costs nothing.

3. **Priced against recorded statistics, on request.** The comparison reads the
   hourly change of every grid import and export meter entered in the
   integration, summed across registers, for whatever period is asked, past
   months included. This re-prices statistics Home Assistant already holds. It
   reconstructs no figure of this integration's own, which is what the cancelled
   backfill (HEA-7) would have had to do.

4. **A daily charge, in the comparison only.** Plans differ heavily in their
   daily charges, and an energy-only comparison can rank the dearer plan first.
   So a plan carries one, counted for every day of the period it covers, and it
   appears in the comparison and nowhere else: no device's figure, no Paid. A
   contracted-power term is entered as its daily cost.

5. **The current plan is a plan too.** Every plan, the one the household is on
   included, is priced the same way from the same statistics, and the comparison
   is with that one, never with Paid - which leaves daily charges out and is
   computed differently.

6. **Holidays follow a calendar.** Many time-of-use plans price public holidays
   as weekends. A plan may name a calendar entity, and a date carrying an all-day
   event in it is priced as a weekend day. Only a calendar can answer for dates
   already past, which the comparison needs; a workday sensor knows only today.

7. **Prices are compared as entered.** With or without tax, consistently. Taxes
   charged as a share of the bill scale every plan alike and do not change which
   is cheapest, so the comparison says this rather than modelling any country's
   taxes.

8. **Shown as a card.** A card on the integration's dashboard, following its
   period picker, lists each plan's energy cost, export credit, daily charges and
   total, and its difference from the current plan, cheapest marked. Paid stays
   the headline of every other card (ADR-0029).

### Rejected

- **Plans as price entities**, as the Energy Dashboard takes a price. They cover
  dynamic tariffs, but a plan added today could only be priced from today, so the
  comparison would say nothing for weeks, and each offer would need a template
  sensor written for it. Kept as a possible later option for spot-price plans.
- **A sensor per plan** carrying its running cost. Counts only forward from when
  it exists, adds entities per plan, and answers no past month.
- **Energy only, without daily charges.** Simpler, and wrong exactly where the
  choice is hard: cheap energy with a high daily charge against the reverse.
- **Comparing each plan with Paid.** Paid leaves daily charges out and is priced
  interval by interval from the engine's allocation, so a difference from it
  would mix two methods. Pricing the current plan alike keeps the comparison
  like for like.
- **The no-installation baseline first.** A smaller change, and it fixes what
  Saved means, but it does not answer whether to switch.
- **Per-device plan figures.** A device's share of a plan's cost would need the
  engine's allocation re-run at every plan's prices. The switching question is a
  whole-home one, so the first version is whole-home.

## Consequences

- A household can enter any number of plans and see, for any period it has
  recorded statistics for, what each would have cost against the plan it is on.
- The comparison is as hourly as the statistics. A band boundary inside an hour
  cannot be represented, so a band's hours are whole hours; published offers use
  whole hours.
- A household without a holiday calendar has holidays priced as weekdays, and the
  plan form says how to add one.
- Its accuracy rests on the grid meters' statistics. A meter that missed hours,
  or was replaced, misstates every plan alike, so the ranking is more robust than
  the totals.
- Follow-ups: the no-installation baseline for Saved; plans priced from a
  spot-price entity; payback (HEA-242) measured against the baseline.
- Revisit if: offers start to price in sub-hour bands, or households need
  per-device plan figures.
