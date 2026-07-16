# ADR-0002: Cost attribution — full proportional source allocation

## Status

Accepted

## Context

The product's core promise is per-device financial accounting a household can
trust (`PRD.md`; ADR-0000). At any instant a device's energy may be served by
grid import, local solar, or battery discharge, and several measurable devices
run at once. The central question raised in ADR-0000 — *how should the cost of
imported electricity be allocated between devices?* — has to be answered before
any sensor can publish a number.

An earlier MVP plan answered it with a **binary solar gate**: price a device's
energy at the live import rate while the house was in deficit, and at zero while
in surplus. A critical review on 2026-07-11 (recorded in `PLAN.md`) showed the
gate was not merely approximate but *wrong* in a way that undermines trust, so
the model was revised before any engine code was written. Accuracy is the
product.

## Decision

### Model: full proportional source allocation

Time is divided into **5-minute intervals**. Within each interval the house's
consumption is the sum of its sources:

```
consumption = grid import + solar used + battery discharge
```

Each source carries a cost, and every kWh consumed — by a tracked device or by
the "Untracked" remainder — is priced at the interval's blended rate, i.e. each
source is allocated across consumers in proportion to their draw. Solar and
battery are optional: absent, the balance collapses to import-only and the
product still serves tariff-only households.

Per device (and the remainder): **Energy Used** = its metered draw;
**Actual Cost** = its share of the blended cost; **Cost Without Solar** = its
draw valued entirely at the import rate; the saving = Cost Without Solar −
Actual Cost. Entity naming is ADR-0003.

The model is built to hold two invariants, enforced by tests (see
`docs/CRITICAL_INSTRUCTIONS.md`): Σ device + remainder allocations equal the
interval's real cost exactly, and no allocation is negative. This is precisely
what the binary gate could not guarantee.

### Pricing per source

- **Grid import** — the live import price at the time of use.
- **Solar** — zero at the margin (but see *Export opportunity cost*, below).
- **Battery discharge** — the weighted-average stored cost from the battery
  ledger: charge is priced at source (grid charge at the import rate of the
  moment, solar charge at zero), discharge draws down at that blend. Flat-rate or
  free battery pricing would misprice the winter Predbat regime badly, where the
  battery is force-charged cheaply overnight and discharged at peak.

### Interval model: 5 minutes, with coarse deltas spread

Allocation needs synchronised cross-device intervals so that, within a bucket, a
device's draw lines up with the sources serving it. Five minutes balances
fidelity against sensor noise. Device energy deltas coarser than one interval
(the WF-RAC aircons report 0.25 kWh steps minutes-to-hours apart) are spread
uniformly across the intervals they span, in proportion to real elapsed time —
an acknowledged approximation, since we cannot know the true intra-delta profile.

### Strategy interface

Allocation sits behind a `CostAllocationStrategy` interface with the MVP
`ProportionalAllocationStrategy` as the sole implementation, so the fallback and
future variants below can be swapped without changing the sensor layer.

## Rejected alternatives

### Binary solar gate (the prior MVP model)

Rejected on two counts:

1. **It breaks the aggregate invariant.** When the house deficit is small
   relative to total tracked draw, every device in deficit is charged the full
   import rate, so the sum of device "actual costs" can exceed the house's real
   import cost by an order of magnitude. Costs that do not add up to the real
   bill destroy the trust the product exists to build.
2. **It misprices battery-covered energy** at live import rates, ignoring that
   the battery was often charged cheaply.

The July 2026 manual validation figure (all nine aircons, €7.63 "binary-gated")
is retained only as a historical reference in the golden-master fixtures; it is
**not** a target output and must not be asserted (HEA-19).

### Deficit-capped per-device model (the recorded fallback)

If a hard blocker makes full allocation infeasible (e.g. house-level source data
proves unavailable in practice), fall back to a per-device model where each
device's chargeable energy is its draw capped by the integral of the house
deficit. It restores the invariant (Σ ≤ real import cost) without needing the
full source balance. Held in reserve, not implemented.

## Consequences

- The engine is built as four composable pure-Python pieces — delta extraction
  (HEA-16), interval ledger (HEA-17), battery stored-cost ledger (HEA-35), and
  the proportional strategy (HEA-18) — each with the invariants under test.
- **Export opportunity cost is deferred.** Pricing solar at zero ignores that
  self-consumed solar forgoes export revenue, so the saving figure is knowingly
  *optimistic*. This bias is documented here, in the README, and surfaced to
  users; an export-aware strategy variant is tracked in HEA-38.
- The 5-minute spreading of coarse deltas is an approximation whose adequacy is a
  question for dogfooding (HEA-28), which reconciles Σ device + remainder cost
  against the real grid-import cost on the live instance.
- More work than the binary gate (interval ledger, battery ledger, cross-device
  allocation) — accepted deliberately: accuracy is the product.
- Revisit if: dogfooding shows the proportional model diverges materially from
  metered reality, a hard blocker forces the deficit-capped fallback, or the
  export-aware variant (HEA-38) supersedes the solar-at-zero pricing.
