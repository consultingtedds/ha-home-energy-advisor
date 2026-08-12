# ADR-0016: Publish the cost bounds reporting latency permits

## Status

Accepted

Follows ADR-0015, which removes the reconciliation error the product *could*
fix. This one is about the error it cannot: what a device's cost is knowable to
at all, given how rarely its counter reports.

## Context

A cycle-resetting counter holds still for 30–90 minutes and then reveals a whole
step. The engine spreads that step across the span it accrued over and prices
each 5-minute slice at that slice's own rate (ADR-0002, and the quiet-run cap in
HEA-74). This is the best available answer, and it is still an estimate: the
energy really happened *somewhere* inside the span, and nothing in the data says
where.

So the cost has a floor and a ceiling. If every kWh landed in the cheapest
5-minute slice of its span, the device cost one figure; in the dearest, another.

**This ADR first quoted the wrong measurement, and the corrected one is much
wider.** The original bounded each delta by the range of *import prices* over its
span. That is the uncertainty in **Cost at Grid Price**, which is priced at
import — a well-behaved ±6.0 % on the reference instance. Actual cost is priced
at the *blend* of grid, generation and battery serving each bucket, so its span
may hold a bucket served by the sun and a bucket served entirely by the meter.
Re-measured against the per-bucket blends the engine actually charges, over the
same 72-hour capture:

| | |
|---|---|
| spread span | median 32 min, 90th pct 81 min, max 135 min |
| tracked devices, as charged | €4.0022 |
| cheapest their spans allow | €3.6090 |
| dearest their spans allow | €4.7241 |
| **width of the band** | **+27.9 %** of actual cost |

The width is not a household constant, and the spread is far larger than the
import-price figure suggested: **+8.1 % to +1252 %** per device. The extremes are
not noise. A device that ran only in the middle of the day costs almost nothing
because it ran on generation, while a two-hour span containing one grid-served
bucket permits a cost a hundred times higher — and nothing in the data says which
happened. Even the well-behaved devices sit at 20–33 %, not 6 %.

The honest summary for this house is that per-device actual cost is knowable to
roughly ±15 %, not ±3 %.

Critically, **it cannot be derived from reporting cadence**. One device with an
8-minute median span carries a wider band than another with a 29-minute span,
because the band depends on how volatile the price was during the hours that
device actually ran. Any downstream approximation from "how often does this
sensor report" would misrank devices, and a confidence figure that misranks is
worse than none.

The same effect was measured from the other side in HEA-75, where weighting a
spread by the device's run signal moved whole-home cost by ~1 %. Both results
say the same thing: the aggregate is sound, and the per-device attribution
carries a real band.

This is a disclosure problem, not an accounting one. The PRD requires
transparency about the model's limits as a product constraint, not as marketing
softening, and an honest bound is worth more than a paragraph of hedging.

## Decision

**1. The bounds are published as costs, not as percentages.**

A floor and a ceiling in currency. Costs sum over a period and percentages do
not, so bounds ride the existing long-term-statistics substrate (ADR-0008)
unchanged, and a card computes the band for any picked range as
`(ceiling − floor) / actual`. No new period machinery.

**2. Whole-home bounds always; per-device bounds opt-in.**

Two extra sensors are cheap and make every install honest by default. Twenty-
eight more are a real recorder cost that a household should choose, so per-device
bounds sit behind an option, following the precedent `opt_in_cycles` already
sets for the cycle meters.

**3. They are diagnostic entities.**

`entity_category: diagnostic` keeps them off the headline device page while
leaving them recorded and chartable. The bound is context for a figure, not a
figure the household is meant to read first.

**4. The band is a bound, and is labelled as one.**

Summing each delta's worst case assumes every device's energy landed in its own
most expensive 5-minute slice at once. That is a genuine outer limit, not a
confidence interval, and it must not be presented as "the error is 28 %". The
typical error is a fraction of the width and partly cancels across devices.

**5. It is shown as a range in money, never as a percentage.**

`(ceiling − floor) / actual` explodes as actual approaches zero — the +1252 %
above is a device that cost less than a cent. That is the same defect that
sank run-signal weighting in HEA-75: a near-zero denominator turning a small
absolute uncertainty into a meaningless percentage. Currency has no such
failure mode, so a device reads `€0.01 (€0.00 – €0.10)`, which says "we cannot
tell whether this ran on the sun" without arithmetic theatre.

This is also why the bounds are published as costs rather than as a width:
a range can be rendered directly, and a percentage can still be derived by
anyone who wants one for a figure large enough to carry it.

**6. Unreconciled energy is published alongside it.**

ADR-0015's expired debt measures how far a household's meters disagree.
Presented together, the two answer the whole question: how far apart are my
meters, and how precisely can this energy be priced.

## Rejected alternatives

- **A single band percentage per device.** Cannot be aggregated over a period by
  the statistics substrate, and loses the asymmetry — the priced figure does not
  sit at the midpoint of its own band.
- **Bounds as attributes on the existing cost sensors.** No statistics, so the
  band could not be shown for a picked period, which is the only place it is
  useful. Attributes are also recorded per state change, so it is not even
  cheap.
- **Deriving the band in the card from reporting cadence.** Measured to misrank
  devices, as above. Rejected on accuracy, not on cost.
- **A household-level figure only.** Cheapest, and it would tell a ±2.2 % device
  and a ±14.5 % device the same thing. The variation *is* the information.
- **Saying nothing and documenting the limitation in prose.** Rejected: a
  per-household measured number is worth more than a general disclaimer, and the
  disclaimer would have to be written anyway.

## Consequences

The product states what it does not know, per device and per period, from
measurement rather than assertion. That is a stronger claim than accuracy alone,
and it is the difference between a figure a user trusts and one they check.

A household with fast-reporting metering sees narrow bands and learns their
figures are solid. One with slow cloud-polled counters sees wide ones and learns
where to spend money on better metering — which is actionable in a way "results
may vary" is not.

Bounds must be maintained on the same paths as cost itself, including the late-
correction path, or they will silently stop tracking the figure they qualify.

The README's limitations section can cite a measured band instead of describing
the mechanism in the abstract.

For a household on true half-hourly or spot pricing the band widens, because the
same spread straddles more price changes. That is a real limitation for those
users and the figure will say so on their own instance without anyone having to
predict it.
