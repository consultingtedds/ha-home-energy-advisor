# ADR-0048: A typed plan feeds the household's price sensors from the day it is switched to

## Status

Accepted

HEA-307. Builds on ADR-0042 (the current plan is priced at the prices Paid is
priced at): this integration can now provide those prices. Leaves ADR-0042
standing for a household whose prices come from elsewhere.

## Context

Under ADR-0042 the prices have one home, the household's own price sensors, and
the current plan follows their recorded history. But the household builds those
sensors by hand and keeps them in step with its plan: a template per band, a
daily charge built as a grid source of its own, all rewritten on the day it
changes plan, while a typed copy of the same plan sits beside them in this
integration.

The daily charge is the hardest. The Energy Dashboard has none, so households
enter it as a pretend grid source whose meter ticks and whose price makes the
right euros. Working on the reference home's (HEA-308) met every trap: a meter
rising 1 a day adds 1 kWh a day to the grid totals; an Integration helper over a
price "per day" gives a unit of "EUR/dayd"; a meter reset by an automation at
midnight also reset on every restart, because the automation compared a UTC date
with a local one.

And a typed daily charge, or a fixed price, keeps no history: changing it changes
every period compared (ADR-0042, option 1).

## Decision

**A typed plan can feed one set of price sensors this integration provides,
from the start of a day the household chooses. The sensors follow its bands by
themselves, and their recorded statistics keep every past price across every
switch.**

1. **One set of sensors, following the plan the household is on.** Not a set per
   plan. A switch changes which typed plan feeds them:
   - **Import price** (per kWh, recorded as a mean): the price of the band in
     force, changing at every band boundary, on the plan's days, and on holidays
     from the plan's calendar. A plan at a market price follows its market sensor
     with the plan's adjustments.
   - **Export price** (per kWh, recorded as a mean): the export price of the price
     in force, the plan's own, or its market's.
   - **Daily charge cost** (money, a running total): the plan's daily charge
     accumulated as it is charged. The rate in force is shown on it.
   - **Daily charge meter** (energy, a running total): 0.001 kWh a day, never
     resetting, so the Energy Dashboard can carry the daily charge as a grid
     source of its own while adding next to nothing to the grid totals.

2. **History splits exactly at a switch.** Every value changes at 00:00 local on
   the day of the switch, and not a moment before or after. Every hour before it
   is recorded at the old plan's prices and daily charge, every hour from it at
   the new plan's, so a period across the switch is charged each plan for its own
   days, as the bills were. Tested: a switch at midnight leaves the day before
   costing exactly the old daily charge and the day of the switch exactly the new
   one, and the import price's recorded means either side of midnight at each
   plan's band. Checked live on the reference home at its first switch.

3. **The household points its prices at them once.** Its grid meters' price and
   the Energy Dashboard's import and export prices take the price sensors, and the
   Energy Dashboard gains one grid source: the meter, with the cost as its cost
   statistic. The current plan then follows them as ADR-0042 says, its daily
   charge following that source's recorded cost. This integration says what to
   point where; it never edits the Energy Dashboard itself, which stays the
   household's (ADR-0030).

4. **Carrying the history in.** Opting in would otherwise leave every period
   before it without prices, since the current plan reads the new sensors'
   history. So when it opts in, the household chooses the sensors and the
   standing-charge source it used before, and their recorded history is written
   behind the new ones: each hour's mean price for the price sensors, each hour's
   cost for the daily charge, joined to the live rows without a step. The steps
   are rehearsed first on the reference home's own data (HEA-308), on helpers
   nothing uses.

5. **A switch takes effect from the start of a day the household chooses**,
   today or later, never backdated: what was charged before is recorded, and is
   not rewritten. A switch waiting for its day shows on the plan and can be
   cancelled. Each switch is kept, so the plans the household has been on can be
   told.

6. **Plans the household has been on are badged, and nothing is hidden.** "Your
   plan since 24 Nov", "Your plan until 23 Nov": the old plan stays a comparison
   row, answering what staying would have cost.

7. **A plan can be archived** from its own form: left out of the table and the
   `compare_plans` action, the card saying in one line how many are not shown,
   and brought back by clearing it. The plan feeding the sensors cannot be
   archived.

8. **A plan with an allowance cannot be switched to yet.** Its price depends on
   how much has been used, not on the clock, which these sensors cannot follow;
   the switch says so. The comparison still prices it exactly. Following usage
   live is HEA-309.

### Rejected

- **A set of sensors per plan.** A switch would mean repointing the Energy
  Dashboard, and history would be split across plans. Revisit if a real need
  appears, with that history cost.
- **Switching immediately only.** A switch due overnight would wait for someone to
  press it, and the hours before would be priced at the old plan.
- **Backdating a switch.** It would rewrite statistics already recorded and
  already shown.
- **Editing the Energy Dashboard on the household's behalf.** It is the
  household's, and a wrong guess would price its real meters wrongly.
- **A daily charge sensor in money per day only**, leaving the meter and the cost
  to each household: every household would meet HEA-308's traps.
- **Archiving from the card.** A card cannot open the plan's settings robustly
  (HEA-295).

## Consequences

- A household that switches through this integration keeps one set of sensors for
  good, and changing plan is one choice made ahead of time.
- A typed daily charge fed through the sensors is recorded as it is charged, so
  ADR-0042's gap (option 1) closes for every plan switched to.
- Four entities are added, created only when the household opts in.
- The reference home moves once, from its old standing charge and price sensors
  straight to these, carrying the history. The helpers built for HEA-308 are a
  rehearsal only, and are deleted afterwards.
