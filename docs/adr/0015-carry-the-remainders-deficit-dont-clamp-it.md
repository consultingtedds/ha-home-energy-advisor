# ADR-0015: Carry the remainder's deficit, don't clamp it per bucket

## Status

Accepted

Refines ADR-0006's late-arrival policy and narrows ADR-0014 to the case it was
really needed for. Leaves ADR-0002's proportional allocation and ADR-0005's
decomposition untouched: this is about *when* the remainder is allowed to be
negative, not about how a bucket's cost is split.

## Context

The Untracked remainder is derived by subtraction, and the subtraction was
floored:

```python
remainder = max(consumption, total_draw) - total_draw
```

Published whole-home energy for a bucket is therefore `max(C, D)`, so over any
period:

```
Σ W = Σ C + Σ max(0, D_t − C_t)
```

That second term is a rectifier. Feed it a zero-mean signal and it returns a
strictly positive number, every time, which nothing downstream ever cancels.

And the signal *is* zero-mean. A house meter and a device counter are not two
views of the same clock. On the reference instance over 72 hours the house meter
wrote **18,728** readings while individual device counters wrote between **3 and
87** - a sampling ratio of up to 6000:1. Cycle-resetting counters hold still for
30-90 minutes and then reveal a whole step; a cloud-polled counter reports when
its vendor's API feels like it. None of them are wrong, and all of them are late
by different amounts. They agree eventually and never instantaneously.

Because tracked devices are ~68 % of that house, the remainder has only ~32 % of
headroom before the subtraction crosses zero - and a single 0.25 kWh step
against a 0.19 kWh bucket clears that easily. The estimate crosses zero
constantly, and every crossing was rectified.

Measured by replaying the shipped engine over a 72-hour raw capture: **+1.9 %**
over the full window, **+3.2 %** over the 20 hours since the HEA-74 fix. The
figure scales with the *variance* of the misalignment rather than with energy,
which is why a quiet night came in at +2 % and a busy afternoon at +8 %: same
scale of consumption, very different concurrency.

**There are two clamps, not one.** `_correct` re-applies the identical rule for
every late portion:

```python
grew = max(retained.consumption, retained.draw + kwh) - max(
    retained.consumption, retained.draw
)
```

and that is the *dominant* path - of 113.8 kWh of device energy in the capture,
only 62.5 kWh arrived through live allocation. A fix confined to `_energies`
would have left most of the bias in place.

ADR-0014 already addressed the *cost* consequence of overdraw, and correctly:
energy the meters have not yet reported can only have come off the grid, so it
is charged at import. But pricing the excess correctly does not stop the excess
being published as energy the house never used. Cost was right and the
arithmetic still did not add up.

## Decision

**1. The remainder carries a signed balance instead of clamping per bucket.**

Each bucket adds `consumption − total_draw` to a running balance and publishes
`max(0, balance)`, retaining any deficit. A later bucket's surplus repays the
debt before anything is published. The bias stops accumulating once per bucket
and becomes bounded by the largest excursion.

**2. Published allocations stay non-negative.**

Only the internal balance is signed. The invariant in `allocation.py` and
`CRITICAL_INSTRUCTIONS.md` - no allocation is negative - is preserved exactly,
which is why this needs no change to what the sensors may publish.

**3. The debt expires after `MAX_QUIET_SPAN`, and that is a derivation.**

A coarse step is spread over at most `MAX_QUIET_SPAN`, so a deficit it creates
takes at most `MAX_QUIET_SPAN` to be repaid. The expiry is not a second tuning
knob; it is the same constant, and a household that changes one changes both.
Measured against the capture, the knee is exactly there: a 2-hour expiry leaves
+0.10 % over 72 hours and **+0.00 %** over the post-deploy window, where 1 hour
leaves +0.65 % and 30 minutes +1.04 %.

**4. Both paths share one balance.**

Live allocation and late correction are the same rectifier applied at two
moments, so the balance must survive finalisation rather than living inside
`_energies`.

**5. The balance carries cost as well as energy, and the overdraw's charge is
suspended until it settles.**

*Amended by HEA-85. This decision originally charged the overdraw at the import
rate immediately and refunded the difference on repayment. The money was right
and the timing was not - see below.*

A deficit repaid at a later bucket's blended price would break `Σ allocations =
real costs`, so the debt remembers what it was recorded at.

*Where* it lands is not a detail. An overdrawing device would be charged the
import rate, because energy the meters have not yet reported can only have come
off the grid (ADR-0014). When the meters catch up they may say otherwise - that
the energy was partly generated, and free. The correction belongs to the devices
that incurred the debt, in proportion to their draw in the bucket that incurred
it, never to the remainder: that would leave a device paying grid price for
energy that turned out to be solar, push the credit into a remainder that never
used the sun, and drive the remainder's published cost negative (−€0.03 on a
bucket pair costing €0.09), breaking decision 2 for a figure that means nothing.
Correct attribution of generation to the device that consumed it is the
product's central claim.

**What HEA-85 changes is when the household is told.** Charging at import and
refunding later publishes a figure we expect to withdraw, and a withdrawal can
only land in the bucket that discovered it: the sensors are cumulative running
totals and Home Assistant derives each bucket's `change` from their value at the
boundaries. On the reference instance two adjacent hours of near identical draw
published **+€0.105 and −€0.118** - the household was told they had been *paid*
to run their appliances. The totals reconciled at every level; nobody would
believe them.

So the overdraw's energy is published, because the period must reconcile, and
its money is not. The charge falls due once, when the debt settles: at the
repaying interval's own blend, or at the import rate if it expires unpaid
(decision 6), because then nothing better was ever learned. Actual cost and its
counterfactual are withheld and released together, which leaves Cost Savings
untouched while a charge waits and preserves ADR-0014's invariance (HEA-77).

Measured over the same 72-hour capture: **3 negative whole-home hours and 10
negative device-hours become 0**, with the period total unchanged to the cent
(€6.2741), published energy unchanged (166.609 kWh) and nothing forgiven. The
cost is that up to **1.47 %** of the running bill is unpublished at any moment,
median **67 minutes** before it arrives - a figure that converges upward, never
one that is taken back.

Revising a device's total after the fact is not a new behaviour: `_correct`
already does it whenever late energy lands in a retained bucket (ADR-0006). What
is new is that the revision only ever *adds*.

**6. Expired debt is published, not swallowed.**

Timing noise clears within the window; a calibration mismatch between the house
meter and the device counters never clears, so whatever survives the expiry *is*
that mismatch, in kWh. It is surfaced as an unreconciled-energy figure rather
than absorbed, with a Repair only at an egregious threshold (ADR-0016 covers the
disclosure).

The *energy* is written off - the meters never accounted for it, so it can never
be reconciled - but the *money* is not. Under decision 5 as amended it has been
waiting unpublished, and expiry is the moment nothing better will be learned, so
it falls due at the import rate ADR-0014 always intended. Its counterfactual
matches it exactly, so an expired debt contributes no saving: the household was
spared nothing.

Expiry is therefore driven by time, not by activity. Each closing bucket checks
it - that keeps the ordering right while buckets are being settled - and
`finalize` sweeps once more, because a household whose meters have gone quiet
closes no buckets at all and a suspended charge must still arrive.

## Rejected alternatives

- **Publish a signed remainder.** The sensor could carry it - Untracked is
  `total` since HEA-48, and late corrections already push individual buckets
  negative. Rejected because it breaks the non-negativity invariant for no gain
  the carry does not already deliver, and a cumulative figure that visibly dips
  reads as a fault.
- **Longer accounting buckets.** Measured to remove ~76 % of the bias at 30
  minutes and ~97 % at 60. Rejected: it attacks the variance rather than the
  rectifier, and it coarsens the source mix - the grid/generation/battery split
  is the product's central claim (ADR-0002), and an hourly bucket cannot see a
  cloud passing.
- **Deskewing each source by its measured latency.** Rejected as the
  house-specific fix: it needs per-device lags that are stable and measurable,
  and it degrades silently when they drift. The carry needs to know only that
  latencies are finite.
- **Leaving it to ADR-0014.** Pricing the overdraw at import fixes what the
  excess *costs*, not that it is published as energy. Rejected: the household
  can still add the device figures up and get more than their meter.

## Consequences

Published whole-home energy reconciles to metered consumption over the window.
On the capture it is not approximately equal - it is **exactly** equal, 166.609
kWh against 166.609 kWh.

ADR-0014's overdraw rule stops being the routine path and becomes the fallback
for a debt that cannot be repaid. It is not superseded: an unpayable overdraw is
still energy that can only have come off the grid, and is still priced there.

The Untracked remainder will publish zero in roughly one bucket in five while a
debt clears, then catch up. That is visible in a 5-minute chart and invisible in
any period a user actually reads.

A household whose meters genuinely disagree is no longer flattered. The carry
absorbs timing and refuses to absorb calibration, so a persistent over-read now
shows up as growing unreconciled energy instead of quietly inflating the home
total. On the reference instance that figure is zero over 72 hours at every
expiry tested, including "never" - the meters do reconcile, they simply never do
so within a single bucket.

The replay reproduces live behaviour to about 2 percentage points (+3.2 % against
a live +5.35 %), starting cold with no retention ring and no prior counter state.
The recovery is therefore better evidenced than the absolute bias, and the true
bias is likely a little higher than the replayed figure rather than lower.

## Amendment, 2026-09-16: the same rectifier, one layer up

A separate finding, from the first bug report by a household outside the
reference home (HEA-133, GitHub #19). The decision above stands unchanged; this
extends it to the other clamp in the engine.

### What was found

The decomposition that turns house meters into served sources (ADR-0005) had two
clamps of its own, applied per bucket:

```python
grid_charge = min(charge, imp)
generation = max(Decimal(0), gen - generation_charge - exp)
```

The household in question meters an inverter that publishes whole kilowatt-hours
and reports each figure independently. So a bucket routinely holds export with no
generation beside it, or a battery charge before the import that supplied it. Both
clamps then discard the leftover, and both can only discard in the direction that
*raises* what the house is said to have used. It is the rectifier of the decision
above, on a different subtraction: they reported 14.972 kWh used against their
inverter's own 8.0.

The charge clamp is worse than a bias, because it counts one kilowatt-hour twice.
A charge arriving before its import is booked as generation filling the battery
for free; the import that follows is then booked as energy the house burned; and
the same energy is charged for a third time when the battery discharges it.

Reproduced in `tests/engine/test_coarse_house_counters.py` without any of their
data: 2 kWh generated and exported one bucket later published 1 kWh of phantom
consumption, and half an hour of an ordinary generating day published 4.5 kWh
against meters recording 4.

### Decision

Carry both leftovers, as this ADR already carries the remainder's deficit.
`HouseBalance` holds two: export awaiting the generation it came from, and a
charge awaiting the supply that filled it. Each is taken off the next bucket that
can settle it, and each expires on `max_quiet_span`, the same span a suspended
charge does and for the same reason - beyond it, the household's meters disagree
rather than merely lag.

### What this does and does not fix

The charge case is settled exactly: the import that arrives later is spent on the
charge before anything is booked as consumption, so no kilowatt-hour is counted
twice.

Generation is settled **over a period, not within a bucket**. Energy credited
before its export tick has already been published, and a published figure is
never retracted (HEA-85), so the correction lands on the generation that follows
instead. A house generating through the day converges; one whose last tick before
a reading is generation stands a fraction of one tick high until the next tick
arrives.

What is outstanding is therefore a figure in its own right, and
`balance_diagnostics` publishes both carries in the diagnostics download. A
household whose total runs above their meter can now be told which of the two it
is: energy still waiting for its counterpart, or a genuine disagreement between
their meters.

### Why the reference household never saw it

It has a house consumption meter, so the balance takes the branch that reads
consumption directly and never runs the generation subtraction. The defect needs
a house without one - which is the configuration the README calls optional, and
the first outside household had. Dogfooding one house cannot find a defect that
lives in the branch that house does not take.
