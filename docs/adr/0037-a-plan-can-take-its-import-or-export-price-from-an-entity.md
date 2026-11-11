# ADR-0037: A plan can take its import or export price from an entity

## Status

Accepted

HEA-260 (GitHub discussion 58). Takes up the follow-up ADR-0036 named, plans
priced from a spot-price entity, which ADR-0036 rejected as the *only* shape of a
plan and kept for dynamic tariffs. Leaves ADR-0036 standing for every banded
plan.

## Context

Wholesale retailers publish an import and a feed-in price that change every five
minutes (Amber, Localvolts and Flow Power in eastern Australia), and each has a
Home Assistant integration whose price sensors the recorder already keeps. A
household comparing such a plan with a banded one has no schedule to type: the
price is the entity's history. ADR-0036's objection was that a plan priced from
an entity could only be priced from when it was added. That holds for an entity
created for the comparison, but not for these, whose statistics go back as far
as the integration has been installed.

The sensors measured (2026-11-04): Amber's price sensors in Home Assistant core
and Localvolts' are `state_class: measurement` in `$/kWh`, so long-term
statistics keep their hourly mean indefinitely, and short-term statistics keep a
5-minute mean for the recorder's purge window (ten days by default).

Pricing a 5-minute price against hourly energy is exact only where use is flat
across the hour. A battery charged in the cheapest five minutes of an hour is
exactly the use a wholesale plan rewards, and an hourly mean misses it.

## Decision

**A plan's import price, and separately its export price, can come from an
entity. Such a price is read from the recorder's statistics: at 5-minute
resolution where the recorder still keeps 5-minute statistics, at the hourly
mean before that.**

1. **Import and export each.** A plan's import is either its named prices and
   bands (ADR-0036, HEA-262) or an entity; its export is either the plan's and
   its prices' export prices, or an entity. A wholesale plan takes both from
   entities; a time-of-use plan with a wholesale-linked feed-in takes only its
   export. A plan whose import comes from an entity has no bands, so its export
   is the plan's flat price or an entity. The daily charge is always typed: the
   feeds leave it out.

2. **5-minute where kept, hourly before.** The comparison prices every plan
   against one sequence of intervals: the grid meters' 5-minute changes from the
   first whole hour the recorder still holds them for, and their hourly changes
   before that. An entity-priced interval is charged at that interval's mean
   price. A banded plan prices the same either way, so it shares the sequence.
   A period's figure for an entity-priced plan therefore moves once its 5-minute
   statistics are purged and it is repriced at hourly means. The card says from
   when 5-minute prices applied, so the change is visible rather than silent.

3. **A gap carries the last price.** An interval with no price statistic (the
   integration was unavailable, the recorder has a hole) is priced at the last
   price before it, as the accounting treats an unavailable price entity
   (HEA-251), and the card says how many hours were carried. Before an entity's
   first price there is nothing to carry: the plan is priced from that first
   price, its daily charges from then too, and the card says from when.

4. **Units as the Energy Dashboard reads them.** A price entity's unit is read as
   the Energy Dashboard reads it: the part after the `/` names the energy it is
   per, converted to kWh (`/Wh`, `/MWh`), and the part before it is not checked
   against the household's currency. An entity in cents reads as a hundred times
   its price there as it would in the Energy Dashboard, so the plan form says the
   price must be in the household's currency.

5. **Dormant until complete.** Built on main as refactors, with the plan form
   offering the entities only in the commit that completes the capability, so a
   fix release can be cut from main at any point (HEA-260).

### Rejected

- **Hourly means only.** One resolution, a figure that never moves, and the
  simplest code, but it misses the within-hour timing a wholesale plan is chosen
  for. The maintainer chose 5-minute where kept.
- **Weighting each hour's mean price by when the household drew power in it.**
  Closer for recent days, but needs the same 5-minute energy, so it ages out the
  same way for more complexity than pricing the 5-minute intervals directly.
- **Leaving a gap unpriced.** Never guesses, but a plan with gaps reads cheaper
  than it was, and the comparison would favour exactly the plans whose feeds drop
  out.
- **Refusing a period with any gap.** One short outage would hide a whole month.
- **Bands for import beside an entity for import.** No offer prices some hours
  from the market and others from a schedule; it would make every hour's price
  depend on two inputs.

## Consequences

- A household on, or weighing, a wholesale plan sees it priced against the same
  real flows as every banded plan, for any period the price entity's statistics
  reach.
- Recent periods are priced more exactly than old ones, and a recent period's
  figure for an entity-priced plan can change by a little once it ages past the
  purge window. Banded plans never change.
- The comparison reads 5-minute statistics only when a plan takes a price from an
  entity, so a household with banded plans only pays nothing for it.
- Follow-ups under HEA-260: demand charges (HEA-263), free-import windows
  (HEA-264), tiered export (HEA-265), the compensation cap (HEA-258), and starting
  a plan from an Energy Manager tariff file (HEA-266).
- Revisit if: retailers publish prices finer than 5 minutes, or the recorder's
  short-term statistics change resolution.

## Update - 2026-11-11: every plan is compared from when all of them can be priced

Decision 3 priced an entity plan from its first price, and only that plan. Over a
long period that compared plans over different days: one household's year
charged a banded plan about 315 days of daily charges, an entity plan whose
history began in April about 218, and one whose history began two days earlier
about 2, with energy over the same unequal spans. The cheapest plan was then the
one with the least history, which is the opposite of the comparison's purpose
(HEA-294, discussion 58).

Now the comparison finds one start for every plan: the latest of the grid
meters' first recorded hour in the period and each entity plan's first price.
Every plan's energy and daily charges are priced from that hour to the period's
end, and the card says from when once, naming the plan whose prices set it, or
the grid meters. A plan with no price at all in the period stays listed without
a total and does not shorten the others.

Rejected: each plan over its own days with the dates shown in its row, which
leaves the totals not comparable and "cheapest" wrong; and dropping a plan whose
prices do not reach back to the period's start, which hides a plan the
household entered to compare. The maintainer chose one common span.
