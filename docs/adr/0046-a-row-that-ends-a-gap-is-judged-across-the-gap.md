# ADR-0046: A row that ends a gap is judged across the gap

## Status

Accepted

HEA-303. Amends ADR-0043 decision 2 (a long gap left out of every plan) and
ADR-0045 decisions 1, 4 and 5 (what is impossible, what probably happened, what
is suggested), and adds a way to leave a Repair as it is. Leaves the rest of both
standing.

## Context

1.6.0's first check on the reference home raised three impossible-hour Repairs,
and none of them was what ADR-0045 describes: a glitch in an hour. All three
were the first row after Home Assistant stopped receiving a meter's data while
the system was being commissioned in 2024 and early 2025.

- **2025-02-28, +117.69 kWh.** The meter's statistics stopped for 75 hours. When
  they resumed, the meter's counter had moved on by 117.69 kWh, and Home
  Assistant recorded all of it in the first hour back: about 1.6 kWh an hour
  across the gap, a possible rate. Suggesting a typical hour would delete it from
  the household's totals.
- **2024-10-11, −106.96 kWh, and 2024-11-16, −121.18 kWh.** The statistic's running
  total restarted from zero, once when the inverter's integration was set up
  again and once after a 24-day outage, so the hour reads as a fall the size of
  everything before it. On 16 Nov the meter's own reading had moved on by 101.45
  kWh of export across the gap, which the household knows did not happen: a
  meter's reading across a gap cannot be trusted either.

Three faults follow.

1. **A row is judged per hour, ignoring how long since the meter's last row.** A
   row that ends a gap carries the whole gap's change.
2. **The comparison leaves out the gap but not the row that ends it** (ADR-0043).
   That row's change covers the gap, so days of energy are priced in one hour.
   The 100 kWh ceiling caught the reference home's case by accident; a smaller
   gap is still mispriced.
3. **The Repair tells the household to choose Ignore,** and Home Assistant offers
   no Ignore on a Repair with a fix flow, so a household that wants to leave an
   hour as recorded cannot dismiss it.

## Decision

**A row that ends a gap is judged across the gap, it is left out of the
comparison with the gap, and a statistics restart is suggested as nothing
recorded. Every impossible-hour Repair can be left as it is.**

1. **The rate is measured across the gap.** A row's change is impossible only if
   it is beyond the ceiling's rate over the time since that meter's previous
   row: more than 100 kWh an hour over that span, either way. A row after a
   75-hour gap is impossible only above 7,500 kWh. A change within the rate is
   energy recorded late, not a fault, and raises no Repair.

2. **The row that ends a long gap is left out with it** (amending ADR-0043
   decision 2). A gap longer than two hours is left out of every plan, and so is
   the row that follows it, since its change is the gap's. A gap of two hours or
   less is still bridged, its energy kept in the next row. A gap the compared
   period starts with is the exception: what is read begins at the period's
   start, so whether its first row ends a gap or is the meter's first ever is
   not known, and that row stays in. Its change is still held to the ceiling.

3. **A statistics restart is named as one, and suggested as 0.** A fall to a
   running total of zero is the statistic restarting, not energy going
   backwards. The Repair says so, and that the energy across it is not known
   from the statistics. It suggests 0 for the hour: what was recorded, and no
   more. The meter's reading across a gap is never suggested, because it can be
   wrong.

4. **Every Repair offers to leave the hour as it is.** Its first step is a
   choice: correct the hour, or leave it as it is. Leaving it ignores the Repair
   through Home Assistant's issue registry, as Ignore does for a Repair without a
   fix flow, and the household can find it again under Show ignored repairs.

### Rejected

- **Spreading a gap's change across the gap.** It would invent a shape for hours
  nobody recorded.
- **Suggesting the meter's reading across a gap.** It is what the meter claims,
  and the reference home's showed export that did not happen.
- **Raising a Repair for energy recorded late.** The total is right; only its
  hour is unknown, and nothing a household could enter would be better.

## Consequences

- A household commissioning a system, or one whose integration dropped for a
  while, is not told its late energy is a fault.
- The comparison never prices a gap's energy as one hour, whatever its size.
- A household can dismiss any impossible-hour Repair without changing anything.
