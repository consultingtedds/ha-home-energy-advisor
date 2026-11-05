# ADR-0039: An export price can pay only on the first kWh of a day

## Status

Accepted

HEA-265 (GitHub discussion 58). Adds to ADR-0036's export prices; leaves the
rest of ADR-0036, ADR-0037 and ADR-0038 standing.

## Context

Some feed-in offers pay a higher price only on the first kWh exported each day
(checked 2026-11-05 against the retailer's published offers):

- **Across the whole day.** GloBird's 11c Solar (Queensland, Energex) pays its
  higher rate on the first 8 kWh exported each day, then 4c/kWh.
- **Within a window.** GloBird's ZEROHERO pays 10c/kWh on the first 15 kWh a day
  exported between 18:00 and 21:00.

The comparison credited every kWh at one price, so it overstated what such a
plan pays a household that exports more than the allowance.

The Energy Manager tariff files attached to discussion 58 carry
`other_export_N_kwh` and `other_free_kwh`, but with the same values in every
file, including where that export or free window is switched off. They read as
Energy Manager's battery control defaults rather than an offer's terms, and
FOUR4FREE's published terms state no export allowance. They are not read as
allowances.

## Decision

**An export price can carry an allowance: the kWh a day it pays on. The plan's
own export price can carry one, with a price for the rest. A named price's
export price can carry one too, and what it does not pay falls to the plan's
export price.**

1. **Per day, from local midnight.** Every published allowance found is per day.
   Each starts again at midnight, local time, as the bands are.

2. **The plan's, with a price after it.** The 11c Solar shape is the plan's
   export price for the first 8 kWh, and its price after the allowance for the
   rest.

3. **A named price's, within its hours.** The ZEROHERO shape is a named price
   whose export price pays 0.10 on the first 15 kWh, charged by the bands from
   18:00 to 21:00. The allowance belongs to the price, so it counts across every
   band charging it, however the window is split into bands. Beyond it, export
   earns the plan's export price.

4. **One count for the plan's price.** Everything credited at the plan's export
   price counts against the plan's allowance, whether exported outside every
   band's export price or beyond a named price's allowance. Each allowance has
   one price within it and one beyond, so the total does not depend on the order
   intervals are priced in, and 5-minute intervals price as hours do.

5. **A market feed-in has no allowance.** A plan exporting at a market price
   (ADR-0037) credits every kWh at that price.

### Rejected

- **The plan's allowance only.** Two fields, but the ZEROHERO shape would credit
  its premium on every kWh in its window.
- **A named price's allowance only.** A whole-day allowance would need every
  price in the plan to carry the same export price, and each would count its own
  allowance, so it would overpay.
- **Reading Energy Manager's `_kwh` fields as allowances.** Their values match
  across files whatever the offer, so they would invent allowances.

## Consequences

- Both published shapes can be entered, and a plan with no allowance prices as
  before.
- An allowance per billing period, if an offer publishes one, cannot be entered.
- The compensation cap (HEA-258), when it comes, applies after allowances.
- Revisit if an offer counts its allowance over a period other than a day, or
  pays more than two prices for export in the same hours.
