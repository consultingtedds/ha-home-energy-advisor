# ADR-0040: A plan can cap export at each month's energy cost

## Status

Accepted

HEA-258. Adds to ADR-0036's export prices and ADR-0039's allowances; leaves the
rest of ADR-0036 to ADR-0039 standing.

## Context

The comparison credited every kWh exported at the plan's export price. Many
plans pay less than that: what export earns in a billing period cannot exceed
that period's energy cost, and anything beyond it is lost. Spain's simplified
compensation is one such scheme, and the reference home is on it. Some plans
carry the excess forward instead, as a "virtual battery" or a credit that rolls
over.

In a month with high export and low import, a solar home's spring, the cap
binds, and the comparison credited export the household would never receive. It
flattered exactly the plans with a high export price. On the reference home
August is within the cap, but April to June are not.

## Decision

**A plan says whether its export is paid in full, capped at each month's energy
cost, or capped with the excess carried to the next month.**

1. **Calendar months, in local time.** The comparison prices whatever range the
   picker shows, which need not be a billing period. Each calendar month in it is
   capped on its own, part-months included. No billing day per plan.

2. **The energy term only.** A month's cap is what its import cost under the
   plan, before tax, as the comparison prices it. Daily charges are payable
   however much is exported. A month whose energy cost is below nothing, a
   market paying the household to import, has nothing for export to offset.

3. **Carried forward simply.** On a carrying plan, what a month's cap does not
   pay joins the next month's export credit, within the shown range. What is
   still carried when the range ends is reported, not credited. No expiry, and
   no fees.

4. **After allowances.** A month's export credit is what ADR-0039's allowances
   and the plan's prices earned, then capped.

5. **New plans capped, old ones not.** A new plan defaults to capped each month,
   the way most plans that pay for export pay. A plan entered before the cap
   existed is read as paid in full, and its form holds that when it is edited or
   copied, so no household's figures change on upgrade.

6. **Said on the card.** A plan's total uses what was credited. Where the cap
   bit, the card says how much export was not paid, or how much was carried and
   is unused.

### Rejected

- **Capping the whole shown range at once.** Wrong for any range longer than a
  bill: a sunny May would offset a dark January.
- **A billing day per plan.** More accurate for a bill that runs mid-month, but a
  field on every plan for a refinement no household has asked for.
- **Offsetting the daily charges too.** Some retailers' credits do, but the
  schemes this was checked against do not.

## Consequences

- A plan with a generous export price is compared as it would really pay.
- A range that starts or ends mid-month caps a part-month against its own part
  of the energy, where a bill would cap the whole month.
- Revisit if a household's bill runs mid-month, or a plan's credit expires or
  offsets the daily charges.
