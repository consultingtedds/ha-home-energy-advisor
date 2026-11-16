# ADR-0043: An hour the comparison has no data for is left out for every plan

## Status

Proposed

HEA-299 (GitHub discussion 58). Replaces decision 3 of ADR-0037 ("a gap carries
the last price") and its 2026-11-11 update (one common start), and the part of
ADR-0036 point 4 that counts a daily charge "for every day of the period it
covers". Leaves the rest of ADR-0036 and ADR-0037 standing.

## Context

The plan comparison prices every plan against the grid meters' recorded
statistics (ADR-0036), and a market-priced plan against its price entity's
statistics too (ADR-0037). Either can have holes, and the comparison treats the
two kinds differently, and neither well.

**A missing price is carried, without limit.** ADR-0037 prices an interval with
no price statistic at the last price before it, looking up to a day before the
period for one. That was meant for a restart or a late publish. On 12 November a
household's GloBird price sensors stopped recording statistics, most likely
after a unit was edited. The comparison carried one price from the 11th across
the whole day, and showed GloBird earning nothing for 44 kWh of export, beside a
plan that earned $2.33 for the same export. The only sign was a note that 24
hours were "priced at the last market price". On the 13th there was nothing
within the day to carry, so GloBird could not be compared at all, and the card
did not say which sensor was at fault.

**Missing energy is charged a daily charge.** An hour none of the grid meters
recorded is already left out of the energy. But daily charges are counted for
every day of the period, so those hours are charged as if nothing was used. The
reference home's recorder has weeks like that in 2024 and 2025. Every plan is
charged alike, so the ranking barely moves, but no total over such a period
matches what was paid.

**Only a gap at the start is shared.** HEA-294 made every plan start from when
all of them can be priced, so a plan with a short history does not read cheapest
by being charged for fewer days. A gap later in the period has no such rule: one
plan carries a guess across it while the others are priced from real data.

ADR-0037 rejected leaving a gap unpriced because the plan with the gap would read
cheaper than it was. That objection holds for one plan, not for every plan
leaving out the same hours.

## Decision

**An hour the comparison has no data for, price or energy, is left out for every
plan, its daily charges with it, and the card says which hours and why. Gaps of
up to two hours are bridged rather than left out.**

1. **Two hours are bridged.** A price missing for up to two hours is carried
   from the last price before it, inside the period or across its start, as
   ADR-0037 carried it. That covers a restart, a late publish, or a missed
   statistics hour. The same two hours hold for the grid meters: a gap that
   short is a restart, and the meters' counters carry its energy into the hour
   after it, so its daily charges stay. Measured in time, so five-minute
   intervals bridge the same two hours as hourly ones.

2. **Beyond two hours, left out for every plan.** A gap longer than two hours,
   in any market price a plan follows or in the grid meters' statistics, is
   left out of every plan: its energy, its export, and its share of the daily
   charges. Every plan is still compared over the same hours, so the ranking
   stays fair and every plan keeps its figures. HEA-294's common start becomes
   the case where the left-out hours come first.

3. **Daily charges for the hours compared.** A plan's daily charges are its
   daily charge for each local day of the period, less each left-out hour's
   share of its day. A day of 23 or 25 hours, when the clocks change, is shared
   across its own hours.

4. **A recorded zero is data.** An hour the meters recorded as zero, such as
   no import on a sunny day, is priced as zero use with its daily charge. Only
   an hour with no statistics row at all is missing, as a zero price is a real
   price and only an unavailable one is missing (HEA-251).

5. **The card says what was left out, and why.** It lists the left-out days, or
   the hours where only part of a day was left out. It names each price sensor
   that had no statistics, or the grid meters, and says to check that sensor's
   statistics (Developer Tools > Statistics), not its state. The state can look
   right while the statistics have stopped, as GloBird's did.

6. **A plan with no price at all is still listed alone.** A plan whose price
   entity has no statistics anywhere in the period would otherwise leave out
   every hour of every plan. It stays listed without figures, naming its
   sensor, and does not shorten the others (unchanged from ADR-0037's update).

### Rejected

- **Carrying without limit** (ADR-0037 as it stands). It prices a stopped
  sensor's last reading as though it were the market, which is what showed
  GloBird earning nothing for a day of export.
- **Leaving the plan with the gap out of the comparison.** One missing day
  would blank a plan for a whole year, and the household would see no figures
  for the plan it is weighing.
- **Pricing each plan over what it can be priced for.** Keeps every figure, but
  compares unlike spans: the plan with the most gaps reads cheapest, which is
  what HEA-294 removed for the start.
- **Keeping the daily charges for missing energy, with a note.** The least
  change, but the totals still match no bill, and the note is easy to miss.
- **Leaving out only whole missing days.** Simpler to show, but a gap of six
  hours would still be charged as zero use.
- **A longer bridge, such as six hours.** More forgiving of an overnight
  outage, but it can carry one overnight price into a morning of export, the
  GloBird failure on a smaller scale. The maintainer chose two hours.

## Consequences

- Nothing changes for a household whose statistics have no gap longer than two
  hours, which is the common case. Its totals are the same as today's.
- A comparison over a period with a gap no longer matches a bill for the whole
  period, and says so. It matches what the plans would have charged for the
  hours it compares.
- A sensor that stopped months ago shortens every plan's comparison to the
  hours it has prices for. The card names it, so the household can fix the
  sensor or remove the plan. The same is already true of a short history at the
  start (HEA-294).
- The rules acting on a period's totals see only the hours compared: the
  monthly export cap (ADR-0040) and the allowances (ADR-0039, ADR-0041). A month
  with left-out days caps export at the energy cost of the days compared.
- The energy recorded after a long gap stays in the hour the recorder put it.
  Where the meters' counters kept counting while the recorder was down, that
  hour carries the gap's energy too, at that hour's price. That is what the
  statistics say, and spreading it across hours the comparison has no record
  of would be inventing data.
- The figures that follow the same intervals follow the same rule: the plan
  without the installation (HEA-293), and each plan's kWh per price (HEA-300).
- The response replaces `compared_from` and `carried_hours` with the left-out
  stretches and the sensor behind each, and the card's strings change with it.
- Built after 1.5.0 is released, so that release stays the code its last beta
  ran.
- Revisit if: price feeds start publishing less often than every two hours, or
  the recorder starts filling its own gaps.
