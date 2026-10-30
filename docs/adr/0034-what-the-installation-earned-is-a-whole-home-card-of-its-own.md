# ADR-0034: What the installation earned is a whole-home card of its own

## Status

Accepted

Revises ADR-0029's 2026-10-23 update, which recorded export earnings as never to
be built. That reasoning stands for devices; this decision builds the figure at
the one level it belongs to.

## Context

Export earnings were decided against on 2026-10-23 (HEA-97) because they are
money received for energy no device used, so they are no device's cost. That is
still true. What it missed is a question the figures already half answer: the
cards say what each device saved by running on the household's own generation
and battery, but nothing says **what the installation as a whole has been
worth** - the panels and battery together, including what the exports earned.
That figure is also what a payback estimate needs (HEA-242).

Most of it is already in the engine, exactly:

- **Cost Savings** is, per slice, generation used at the import price, plus
  battery energy used at the import price less what that energy cost to store.
- **Battery Savings** is precisely the second of those terms, kept alongside it
  slice by slice, late corrections included.
- **Battery Losses** is published as a device. A loss enters the whole home's
  Paid and its Would have paid alike, at what the lost energy cost to store, so
  it never moves Cost Savings.

What is not in the engine is the money the exports earned. The Energy Dashboard
already records it, whenever a grid source has an export price: its own
compensation statistic, or a cost statistic the household provides. That is the
same export price this integration reads (ADR-0026).

## Decision

**A new card, "What your installation earned", shows the whole home's return on
its generation and battery over the selected period, in three parts.**

1. **Generation saved** = the whole home's Cost Savings less its Battery
   Savings.
2. **Battery saved** = the whole home's Battery Savings less Battery Losses'
   Paid. It can be negative: a battery that loses more than it saves has cost
   money, and the card says so rather than flattering it.
3. **Exports earned** = the Energy Dashboard's compensation statistic for each
   grid source with an export price, summed. Found as the Energy Dashboard
   finds it, not by guessing a sensor's name.

The total is the sum of the three. Every part is read from long-term statistics
that already exist, so the engine does not change and no new sensor is needed.

The decisions behind it (maintainer, 2026-10-30):

- **Measured against the current tariff.** Every figure here prices energy at
  the import price the household is on. A tariff only worth having because of
  the installation (dynamic or wholesale pricing with a battery) makes the true
  comparison a different set of prices; an optional "without the installation"
  tariff was suggested (discussion 48) and is left to HEA-242, where it matters
  most. *Rejected for now:* building it here, because it is a new setting and a
  second price for every slice, on top of a figure this card can show from what
  is already recorded.
- **Exports earned is the Energy Dashboard's, not ours.** *Rejected:* computing
  exported energy at the export rate in the engine as a new sensor. It would
  repeat a statistic Home Assistant already keeps, from the same price, and
  could only ever agree with it or be wrong. Exports are whole-home, so nothing
  per device is lost.
- **Losses count against the battery.** Against no installation at all, energy
  lost in the battery would never have been bought (grid charge) or had (stored
  generation). *Rejected:* leaving losses out, which would show a lossy battery
  charged from the grid as better than it is - the one way this figure could
  flatter the installation. Battery Losses' Could have earned stays out: with no
  installation there would be no generation to export.
- **A card of its own, not rows on the totals card.** Every other card can be
  filtered by device, area or label. These figures are whole-home and cannot be,
  so on a card of their own they can say so plainly. *Rejected:* rows on the
  totals card, which would be the only part of a filtered card that ignored the
  filter.

**How it fits ADR-0029.** ADR-0029 makes every card lead with what was paid,
because the cards answer what each device's use cost. This card answers a
different question, about the installation, so it does not lead with Paid. It
keeps that ADR's other rule: none of its figures is ever merged into Paid, and
each has a name of its own.

## Consequences

- The card appears only where there is something to show: a home with
  generation or a battery, by the rule that already keeps zero-only sensors away
  (HEA-175). A part that does not apply - battery saved with no battery,
  exports earned with no export price - is left out rather than shown as zero.
- It follows the dashboard's period picker like every card, and ignores device,
  area and label filters, saying it covers the whole home.
- Generation means any self-generation, not only solar; the card's wording says
  so.
- Its figures depend on the Energy Dashboard's export statistic existing. A
  household with no export meter or price there gets no exports part, and this
  integration had no exports to count for them either.
- Payback (HEA-242) builds on this card: the installation's cost, how much of it
  has been recovered, and when the rest is projected to be.
- Revisit if a household needs the return under a different tariff (HEA-242's
  open question), or if Home Assistant stops recording compensation for an
  export price.
