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
87** — a sampling ratio of up to 6000:1. Cycle-resetting counters hold still for
30–90 minutes and then reveal a whole step; a cloud-polled counter reports when
its vendor's API feels like it. None of them are wrong, and all of them are late
by different amounts. They agree eventually and never instantaneously.

Because tracked devices are ~68 % of that house, the remainder has only ~32 % of
headroom before the subtraction crosses zero — and a single 0.25 kWh step
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

and that is the *dominant* path — of 113.8 kWh of device energy in the capture,
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
`CRITICAL_INSTRUCTIONS.md` — no allocation is negative — is preserved exactly,
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

**5. The balance carries cost as well as energy, and repayment refunds the
devices that overdrew.**

A deficit repaid at a later bucket's blended price would break `Σ allocations =
real costs`, so the debt remembers what it was charged and gives that back.

*Where* it gives it back is not a detail. An overdrawing device is charged the
import rate, because energy the meters have not yet reported can only have come
off the grid (ADR-0014). When the meters catch up they may say otherwise — that
the energy was partly generated, and free. The device therefore overpaid, and
the refund is returned to the devices that incurred the debt, in proportion to
their draw in the bucket that incurred it.

Letting the remainder absorb it instead reconciles the same total and is wrong
in the way that matters: it leaves the device paying grid price for energy that
turned out to be solar, and pushes the credit into a remainder that never used
the sun. Worked through, it also drives the remainder's published cost negative
(−€0.03 on a bucket pair costing €0.09), breaking decision 2 for a figure that
means nothing. Correct attribution of generation to the device that consumed it
is the product's central claim; reconciling the total at its expense would be
arithmetic honesty covering for attribution dishonesty.

Revising a device's total after the fact is not a new behaviour: `_correct`
already does it whenever late energy lands in a retained bucket (ADR-0006).

**6. Expired debt is published, not swallowed.**

Timing noise clears within the window; a calibration mismatch between the house
meter and the device counters never clears, so whatever survives the expiry *is*
that mismatch, in kWh. It is surfaced as an unreconciled-energy figure rather
than absorbed, with a Repair only at an egregious threshold (ADR-0016 covers the
disclosure).

## Rejected alternatives

- **Publish a signed remainder.** The sensor could carry it — Untracked is
  `total` since HEA-48, and late corrections already push individual buckets
  negative. Rejected because it breaks the non-negativity invariant for no gain
  the carry does not already deliver, and a cumulative figure that visibly dips
  reads as a fault.
- **Longer accounting buckets.** Measured to remove ~76 % of the bias at 30
  minutes and ~97 % at 60. Rejected: it attacks the variance rather than the
  rectifier, and it coarsens the source mix — the grid/generation/battery split
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
On the capture it is not approximately equal — it is **exactly** equal, 166.609
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
expiry tested, including "never" — the meters do reconcile, they simply never do
so within a single bucket.

The replay reproduces live behaviour to about 2 percentage points (+3.2 % against
a live +5.35 %), starting cold with no retention ring and no prior counter state.
The recovery is therefore better evidenced than the absolute bias, and the true
bias is likely a little higher than the replayed figure rather than lower.
