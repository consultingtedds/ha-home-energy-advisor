# ADR-0041: An import price can charge only on the first kWh of a period

## Status

Accepted

HEA-264 (GitHub discussion 58). Adds to ADR-0036's prices and mirrors ADR-0039's
export allowances; leaves ADR-0036 to ADR-0040 standing.

## Context

Some plans make import free, or cheap, for a few hours, but only up to a limit.
Checked on 2026-11-09, at the maintainer's request, against Australia, the UK and
Spain, so that the shape fits more than one market:

- **Australia, per day.** GloBird's FOUR4FREE is free from 11:00 to 15:00, on the
  first 50 kWh a day (30 kWh on one comparison site). The Solar Sharer Offer every
  retailer must offer is three free hours a day, capped at 24 kWh; one retailer
  averages that cap over the billing period. Beyond the cap, the ordinary rate.
- **UK, per week.** One comparison site reports OVO's free weekend hours, Saturday
  and Sunday 11:00 to 14:00, capped at 30 kWh a week.
- **Spain, no limit.** Endesa's Tempo Happy makes two chosen hours free every day,
  or one chosen day a week, with no limit found.
- **Event-based sessions.** Octopus's Free Electricity Sessions and EDF's or
  British Gas's reward schemes are announced or earned, not scheduled.

A free window with no limit is already a band priced at 0, on any days
(ADR-0038). What could not be entered was the limit.

## Decision

**A named price can carry an import allowance: how many kWh its import price
charges on each day, week or month, and which of the plan's other prices its
hours are charged beyond it.**

1. **Per day, week or month.** Per day for the Australian caps; per week for a
   weekend cap; per month for a cap averaged over a bill, the nearest of the
   three. A day and a month start at local midnight, and a week on Monday, as
   in Australia, the UK and most of Europe.

2. **Another named price beyond it.** Above the limit an hour costs what it
   otherwise would, which is one of the plan's prices already. Naming it rather
   than typing its figure keeps the two the same when the plan's prices are
   renewed. A name the list no longer has is refused, not guessed at.

3. **The price's, across its bands.** As an export allowance does, an import
   allowance belongs to the named price, so it counts across every band charging
   it however its hours are split into bands. One price within it and one beyond,
   so the total does not depend on the order the intervals are priced in.

4. **A plan's own prices only.** A plan importing at a market price (ADR-0037)
   charges every interval at the market, so has no allowance.

### Rejected

- **Per day only, like the export allowance.** A weekly cap entered as its daily
  share misprices a weekend window: 30 kWh a week is not 4.3 kWh on each of two
  days.
- **A figure beyond the allowance.** One more figure to keep in step with the
  price it copies, at every renewal.
- **Event-based free sessions.** Not a schedule, so not part of a plan;
  revisit if a household asks to record the sessions it had.

## Consequences

- Capped free hours can be entered as they are published, in each market
  checked.
- A cap averaged over a billing period is priced per calendar month.
- Revisit if an offer's week starts on another day, or charges more than one
  price beyond its limit.
