# ADR-0042: The current plan is priced at what the household pays

## Status

Proposed

HEA-267 (GitHub discussion 58). Replaces point 5 of ADR-0036 ("the current plan
is a plan too", priced from its own schedule like every other). Leaves ADR-0026,
ADR-0030, ADR-0032 and ADR-0037 standing.

## Context

The plan comparison (ADR-0036) prices every plan from its typed schedule, the
one marked current included, and compares each plan with that one. Paid is
priced differently: from the price each grid meter carries (ADR-0032), the
household's own copy prefilled from the Energy Dashboard (ADR-0030), and from
the Energy Dashboard's export price, read live (ADR-0026). So the household
keeps its prices twice, once for Paid and once for the current plan, and
nothing says when the two disagree.

The first design for HEA-267 (2026-11-04) closed the gap the other way round:
the current plan would price Paid. Every install would have migrated to a plan
kind holding its grid meters' prices, and a time-of-use household could have
made a banded plan current and dropped its price sensor.

That benefit does not survive contact with how households use Home Assistant.
A household that sees costs in the Energy Dashboard already keeps a live price
for it, banded or not: the Energy Dashboard needs one to show any cost at all.
The reference home prices its grid with a time-of-use price sensor, and even
enters its standing charge as a second grid source priced by a sensor of its
own. Under the first design, Paid would have been priced from a plan's bands
while the Energy Dashboard priced from that sensor. The first time the two
differed, Paid would have disagreed with Home Assistant's own cost, without a
word. A plan switch is exactly that moment: the household updates the sensor
the Energy Dashboard uses, and the plan's bands too, and if one lags the figures
split.

The integration ties in with the Energy Dashboard as closely as it can
(ADR-0017, ADR-0030), so the prices should have one home, and it is the one the
household already keeps.

## Decision

**The current plan is priced at the prices Paid is priced at. The household
types only the billing rules that no price sensor can hold.**

1. **Paid's prices, exactly.** The current plan's import is each grid meter's
   recorded change priced at that meter's own price, entity or fixed, as Paid
   prices it, meter by meter, as the Energy Dashboard prices each grid source.
   Its export is priced at the Energy Dashboard's export price. An entity price
   is read from its recorded statistics, as an entity-priced plan's already is
   (ADR-0037). Paid and the current plan cannot disagree, and they agree with
   the Energy Dashboard as closely as the prefill already makes them.

2. **Billing rules typed, price rules not.** The current plan carries a typed
   daily charge and the monthly export cap (ADR-0040). Both act on a bill's
   totals, which no price sensor holds, and without the cap the current plan
   would credit every kWh exported while the capped plans beside it did not, and
   read cheaper than it is. Allowances (ADR-0039, ADR-0041) change the price per
   kWh, so they belong to the price itself: where a household's plan has one,
   its price sensor expresses it, as the Energy Dashboard already needs it to.
   These rules price the comparison only. Paid is unchanged (ADR-0036, point 4).

3. **Created, then asked.** Every household has a current plan, created by the
   integration rather than entered. A fixable Repair asks for its daily charge
   and cap in a form of its own. Until it is answered, the current plan's energy
   figures are shown, but no plan's difference from it is: a plan without daily
   charges compared with plans that have them would rank wrongly, so the
   difference is held, and the card says why ("publish late, never retract").

4. **A typed current plan becomes an ordinary one.** On upgrade, a household
   that had marked a typed plan as current keeps it as an ordinary plan, and its
   daily charge and cap are carried over to the new current plan. The same
   Repair tells the household that the typed plan now duplicates the current
   one, and that the household can delete it. Until then the gap between the two
   rows shows where the typed prices and the household's own prices disagree.

5. **A plan switch needs nothing of its own.** The current plan follows the
   prices' recorded statistics, so across a switch it shows what was actually
   charged on each side of it. A plan typed in advance of a switch is an
   ordinary plan beside it, as every other is.

### Rejected

- **The current plan prices the accounting** (the first design, 2026-11-04).
  It keeps two copies of the household's prices, one for Home Assistant and one
  for this integration, and lets Paid drift from the Energy Dashboard's cost.
  The time-of-use household it was for already keeps a price sensor.
- **Either kind of plan can be current.** No upgrade change at all, but it keeps
  the two copies this decision exists to remove.
- **Converting a typed current plan in place.** One row instead of two, but its
  typed prices are lost, and with them the one chance to see whether they
  disagreed with the sensor.
- **A missing daily charge priced at zero, with a note.** Every column shows,
  but until the household notices, every other plan reads dearer than it is.
- **Asking during setup only.** Every existing household would see a current
  plan without daily charges, and nothing would tell them.
- **Typing allowances on the current plan.** An allowance on a followed price
  means the sensor's price up to a limit and a typed price beyond it: a second
  price to keep in step with the first, which is the drift this decision avoids.

## Consequences

- The comparison's baseline and Paid agree by construction, and a household
  changes its prices in one place, the one Home Assistant expects.
- The comparison can no longer show a current plan the household believes it is
  on but does not pay. That gap is better found against a bill (HEA-298) than
  hidden in a typed plan.
- A config entry migration: create the current plan, carry the marked plan's
  daily charge and cap over, unmark it, and raise the Repair. It is tested from
  a real snapshot of an entry that has a marked plan and one that has none.
- The plan form's "This is the plan I am on" goes, with its help text, which
  says the plan does not change how costs are worked out.
- Built after 1.5.0 is released, so that release stays the code its last beta
  ran.
- Revisit if the Energy Dashboard gains a daily charge or a cap of its own: the
  current plan would follow it as it follows the prices.
