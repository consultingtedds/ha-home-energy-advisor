# ADR-0006: Late-arrival correction policy — retention ring, derived Untracked, total semantics

## Status

Accepted

## Context

ADR-0002/0005 fix the accounting model: each 5-minute interval is priced and
allocated across devices plus an Untracked remainder. Intervals are finalised on
a lateness margin (~20 min = 15-min lateness + one 5-min bucket) so late-arriving
readings can still land before the interval is closed.

What happened *after* the margin was never decided in an ADR — only asserted in a
docstring: energy for an already-finalised interval was dropped, "the amounts are
tiny". That is true for finely-updating meters and **false for exactly the
devices this product was built around.** The cycle-resetting aircons (the founding use
case) and cloud-polled Tuya devices report cumulative energy in coarse 0.25 kWh
steps every 15-90+ minutes. A device's delta therefore spans well past the
watermark, and every portion older than it was discarded — an estimated **30-50 %
of such a device's energy**, silently reattributed to the Untracked remainder.
The aggregate invariant (Σ costs = real bill) still held, which is precisely why
nothing looked broken (HEA-48; `docs/notes/REVIEW_2026_07_26.md` §1).

This ADR owns the late-arrival policy explicitly.

## Decision

**1. Retained-context reallocation ring.** Finalising a bucket no longer seals
it. Each finalised bucket retains the scalars a later correction needs — its
fixed consumption, blended unit price, import price, and running total device
draw — in a bounded ring (default **24 h**, configurable; a few KB per bucket, so
under 1 MB/day). A device portion that arrives for a *retained* bucket corrects
it; a portion for a bucket already evicted from the ring is dropped **with a
`DROPPED_LATE` decision-log entry** — never silently, so diagnostics can prove
it.

**2. Corrections never reduce a tracked device.** A finalised bucket's real cost
and consumption are fixed, so the correction is a closed form, not a re-run: the
late device is credited its full energy at the bucket's blended price, its cost
gain **capped at the headroom the Untracked remainder still holds**; any overdraw
beyond that grows the whole-home total instead. Value moves only from Untracked to
the late device — no other device's already-published figure is ever revised
downward.

**3. Untracked is derived, not accumulated.** Because every label shares each
bucket's blended price, `Untracked ≡ whole-home total − Σ device totals` holds
identically. The engine tracks the whole home plus each device and subtracts, so
the split reconciles exactly however corrections have moved value. A **monotonic
whole-home total falls out for free** and is exposed as its own device with the
four lifetime figures (the maintainer's call: expose it now, running totals only — see
Consequences).

**4. Untracked moves to `state_class: total`.** A correction legitimately pulls
the remainder down. Its Energy Used, Actual Cost and Cost Without Solar therefore
become `total` (Cost Savings already is); left `total_increasing`, HA long-term
statistics would read every correction as a meter reset and corrupt the history.
Existing Untracked cycle (utility_meter) helpers are reconciled in place to
`net_consumption` as part of this change. The whole-home total stays
`total_increasing` — it only ever grows.

**5. `state_reported` subscription.** The coordinator also tracks state *reports*
(unchanged re-writes), not only state *changes*, feeding each source's
`last_reported`. Polled integrations that re-report an unchanged counter every
poll thereby advance the source's last-seen time, so when the counter finally
steps the delta spans only the poll interval. Ring depth then matters only for
push-only sources that emit nothing between rare steps — which the 24 h ring
covers. Trade-off: with short spans a 0.25 kWh step concentrates into its final
bucket rather than spreading over the true accrual window; the retained ring
makes this tolerable rather than load-bearing.

## Consequences

- Energy is conserved to Decimal-context rounding (~1e-27 kWh, zero at any
  observable precision); the exact aggregate invariant (Σ devices + Untracked ≡
  whole-home) holds by construction via the derivation.
- The whole-home aggregate adds one HA device and four sensors, but **no cycle
  meters**: its period totals are the sum of the device and Untracked cycle
  meters and duplicate the Energy Dashboard, so it carries lifetime running
  totals only. Entity multiplication overall is tracked separately (HEA-40).
- Late portions for **house-level** sources (grid/solar/battery) past the
  watermark are still dropped silently: those meters report frequently, so their
  deltas rarely cross the watermark. Revisit if evidence shows otherwise.
- A restart still discards in-flight (unfinalised) buckets — flush-on-unload is
  out of scope here (HEA-53).
- Reconciliation validation (HEA-28) must run *after* this lands; before it, a
  validation week would have measured the undercount.
- Revisit if: push-only devices routinely step less often than the 24 h ring, or
  the reconciliation week shows residual bias.

Supersedes the docstring-only drop policy. Relates to ADR-0002 (allocation),
ADR-0005 (decomposition), and ADR-0003 (Untracked entity contract).

## Update — flush-on-unload delivered (2026-07-28, HEA-53)

The Consequences above noted that a restart still discards in-flight
(unfinalised) buckets and deferred the fix to HEA-53. That is now done. On unload
— a restart, or **any** options/config change, since the update listener reloads
the entry — the coordinator flushes: it finalises past the lateness margin
(`finalize(now + lateness + BUCKET)`) and publishes once **before** the sensor
platform is torn down, so each `RestoreSensor` banks the freshly finalised totals
into its restore baseline. Up to ~20 min × all devices of accounting that used to
die on every reload now survives it.

**Trade-off (accepted).** Flushing seals the partial *current* bucket early, so a
device portion that would have arrived for it *after* the reload can no longer
correct it — and the rebuilt runtime's retention ring (decision 1) starts empty,
holding no pre-reload buckets. In exchange no whole bucket is lost. With the
`state_reported` subscription (decision 5) keeping delta spans at the poll
interval, the uncorrectable tail of a flushed partial bucket is small; a reload is
also far rarer than the coarse-step cadence the ring exists for. Net: flushing
banks far more than the early seal forfeits. Only ever *increases* device energy,
so `total_increasing` Energy Used stays monotonic across the reload.

## Update — decision 5's trade-off was not tolerable (2026-08-10, HEA-74)

Decision 5 added the `state_reported` subscription so an unchanged re-report
advances a source's last-seen time, and recorded the consequence as a trade-off:

> with short spans a 0.25 kWh step concentrates into its final bucket rather than
> spreading over the true accrual window; the retained ring makes this tolerable
> rather than load-bearing.

Measured against the reference instance, it was not tolerable. Concentrating a
whole step into one 5-minute bucket meant a single coarse device routinely
claimed more than the entire house was metered as consuming in that interval —
overnight, when house demand is lowest, one step was 1.5-3× the whole house.
Published whole-home energy ran **+44 % above the metered house load across a
night and +29.5 % across a weekday**, and the resulting mispricing put tracked
devices at a quarter to a sixth of the import tariff (HEA-74).

The ring did not soften this, because the concentration never reached the ring:
with sources re-reporting every ~60 s the delta spans a minute and lands far
inside the watermark, on the live path. The decision-log evidence carries no
`DROPPED_LATE` entries at all for those devices.

**Amendment.** A delta now spans from the counter's last **movement**, not its
last reading. Decision 5's subscription stands — it is still what keeps a
recovering counter from claiming a multi-day span — but it no longer determines
where the energy is attributed. Only the *quiet* run between movements is capped
(`MAX_QUIET_SPAN`, 2 h); a genuine reporting gap is never trimmed, so a source
that fell silent for three days still spreads across those three days.

Decision 2's headroom cap is amended by ADR-0014: a late device now buys, at the
import rate, whatever the Untracked remainder cannot fund, instead of receiving
it free.

The cap is a bound on the opposite error — a device switched off for hours is
indistinguishable, from the counter alone, from one trickling along.

## Update — the cap is measured, and run-signal weighting is rejected (HEA-75)

The amendment above called two hours interim, and expected a per-device run
signal to replace it. Both halves have now been tested against the devices' own
on/off signals, captured over five days for all fourteen devices.

**The cap is right.** Devices were running for 92-98 % of every counter-movement
gap up to two hours, then 53 %, 29 % and 4 % beyond it — the boundary between
"working slowly" and "switched off" falls exactly at the chosen value.
Independently, the energy a capped uniform spread misplaces against a
run-weighted one is minimised at the same point (6.9 % of fleet energy, against
10.4 % at one hour and 34 % at thirty minutes).

**Weighting by the run signal is not worth its cost.** It moves whole-home actual
cost by ~1 % in summer and 0.3 % when the same week is replayed against a January
solar profile. The large per-device percentages it shifts (up to 47 %) fall
entirely on devices whose cost is pennies, because a near-zero denominator
inflates them; in absolute terms the movement is about €0.02/day in either
season. A 30-90 minute spread is simply short next to a 2-4 hour tariff band, so
displacement rarely crosses a price boundary at all. HEA-75 is closed on this
evidence rather than left open as a standing intention.
