# ADR-0014: Price overdrawn energy at the marginal import rate

## Status

Accepted

## Context

ADR-0002 prices every kWh in a 5-minute bucket at that bucket's blended rate and
clamps the Untracked remainder at zero when tracked device draw exceeds the
consumption the house meters accounted for. What that clamp implied for *cost*
was never decided: the shipped code held the bucket's metered cost fixed and
divided it across the inflated energy.

HEA-74 found what that costs. Coarse counters — the ones this product was built
around — hold still for 30-90 minutes and then report a whole step. Anchoring
that step to the previous *reading* booked an hour of energy into a single
bucket, where overnight it routinely exceeded everything the house consumed in
that interval. HEA-74 fixes the anchoring; this ADR owns what happens in the
buckets where draw still exceeds consumption.

Measured on the reference instance before the fix:

| Window | Published whole-home energy vs metered |
|---|---|
| One night, 8 h | **+44 %** |
| One weekday, 24 h | **+29.5 %** |

Two paths reached that state by different wrong answers, which is itself the
argument that neither was decided:

- the **live** path diluted a fixed cost across inflated energy, so every label
  in the bucket was priced below what any kWh in it could have been bought for;
- the **late-arrival** path (ADR-0006 decision 2) capped a device's cost gain at
  the headroom the Untracked remainder still held, and booked everything beyond
  it at **exactly zero**.

Both err in the flattering direction: they understate cost and overstate the
saving, which is the product's headline claim. On the measured weekday the
claimed daily saving was €9.31 against a true €6.94 — overstated by 34 %.

## Decision

> **Amended by HEA-85 (see ADR-0015 decision 5).** The *rate* below still stands
> and is still what an unrepaid overdraw finally costs. What changed is **when**
> it is charged: the import rate is now applied at settlement rather than at the
> time, because a charge published immediately is one the repaying bucket usually
> takes most of back — and a withdrawal can only land in the bucket that
> discovered it, which published an hour reading −€0.118 on the reference
> instance. Read "is priced at" below as "will be priced at, once nothing better
> can be learned". The two paths still agree with each other; both now suspend.

**Energy beyond a bucket's metered consumption is priced at that bucket's import
rate, and the whole-home cost grows with it.** One rule, applied identically in
the live allocation and in the late-arrival correction, so the two paths can no
longer disagree.

The justification is physical rather than presentational: energy the house drew
that its meters have not yet reported can only have come off the grid. Metered
generation and battery discharge were already consumed and allocated within that
bucket; they cannot supply the same kWh twice.

A device's late energy therefore takes what the Untracked remainder can still
fund at the blended rate, and *buys* the rest at the import rate.

**Rejected — keep the metered cost fixed and dilute (the shipped behaviour).**
It preserves "Σ allocated cost == the metered bill" exactly, which is the more
elegant invariant. It was rejected because it buys that elegance with a figure
that is knowingly false: on a bucket served largely by generation the blended
rate approaches zero, so a device drawing hard at the peak tariff is published as
costing almost nothing. Measured across one weekday's peak bands, dilution
under-charged tracked devices by 2× to 4×, and by 60× on a single hourly-polled
counter. An invariant that holds only by mispricing the thing the user reads is
the wrong invariant to protect.

**Rejected — refuse the excess energy.** It keeps both the cost and the energy
invariants, and is what the plausibility guard already does for a source proven
to be lying (HEA-60). It was rejected because the energy here is real: the
device did draw it, and the meters are behind, not wrong. Refusing it would
reintroduce exactly the silent under-count ADR-0006 was written to end.

**Rejected — price the excess at the blended rate.** Cheaper to reason about and
enough to remove the zero-cost path. Rejected as arbitrary: the blend describes
what the bucket's *metered* supply cost, and the excess by definition was not
part of that supply.

## Consequences

- ~~Σ allocated cost now **exceeds** the metered bill by (overdraw × import
  price) in any bucket where draw exceeds consumption.~~ **Superseded by HEA-85**:
  an overdrawing bucket now allocates exactly its metered cost, and the excess is
  carried unpriced on the debt ledger. The consequence below described why
  exceeding it was acceptable; it is no longer exceeded at all, and the period
  invariant is unchanged. Read the rest of this bullet as the reasoning that
  justified the carry, not as current behaviour. This is a deliberate amendment
  to the ADR-0002 clamp: the aggregate invariant holds when the inputs agree, and
  when they disagree the engine errs toward overstating cost rather than
  flattering the user.
- Whole-home energy and whole-home cost now move together. Previously energy grew
  on overdraw while cost did not, which is what let a published €/kWh fall below
  anything the household could have paid.
- Overdraw becomes rare once HEA-74's anchoring lands — residual inflation
  measured at **+1.1 %** across a weekday and **+4.6 %** overnight, against
  +29.5 % and +44 % before — so this rule governs an exception rather than the
  common case. It is not a licence to leave overdraw unfixed.
- The negative-remainder Repair (HEA-36) becomes the user-visible signal that the
  inputs disagree, and had to change to serve that: it counted *consecutive*
  overdrawn buckets, which an intermittent coarse counter reset every time, so it
  stayed silent throughout the period this ADR describes. It now counts overdrawn
  buckets across a window.
- Revisit if the residual inflation stops being an exception — a household whose
  meters routinely lag its devices would be paying an import-rate premium on a
  systematic timing artefact rather than on real grid energy.

## The residual is the floor, and it does not reach Cost Savings (HEA-77)

Traced across five days and all fourteen devices of the reference instance:
published whole-home energy runs **1.07 %** above the metered house load —
2.816 kWh of accounted overdraw, 72 % of it arriving through the late-correction
path and 28 % through live allocation. It occurs in 31 buckets out of 1,498. No
single device causes it and no house meter reads zero; it is several devices'
spread estimates landing in the same five minutes.

**This is the approximation error of uniform spreading, not a fault to be fixed.**
The true accrual profile inside a coarse counter's quiet run is unknowable, so
the estimate spreads evenly, and an even estimate can exceed what the house
really drew in any one slice while reconciling exactly across the whole span.
Weighting by each device's own run signal reduces it only from 0.96 % to 0.70 %
(HEA-75), which is what establishes that the dominant term is ignorance of
timing rather than misplacement.

**Cost Savings is exactly invariant to it**, and that is a property of this
decision rather than a coincidence. The overdrawn energy is charged at the import
rate, and the counterfactual values the same energy at the import rate, so it
contributes precisely zero savings:

```
Σ savings = total_draw × import − (metered_cost + overdraw × import)
          = consumption × import − metered_cost
```

— the savings the bucket would have had with no overdraw at all. Measured across
three spreading strategies, the week's savings figure was identical to four
decimal places.

So the residual overstates `whole_home_energy_used` and both cost totals by
about 1 %, in the conservative direction, and leaves the figure the product is
actually about exact. Had the rejected dilution model been kept, this would not
hold: dilution leaves the counterfactual untouched while suppressing actual cost,
so every overdrawn kWh would have manufactured a saving.

Amends ADR-0002 (allocation and the remainder clamp) and ADR-0006 decision 2
(the late-arrival headroom cap). Relates to HEA-74; HEA-75 would reduce how often
this rule is reached at all.
