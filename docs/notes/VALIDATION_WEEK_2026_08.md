# One-Week Parallel Validation — Methodology (HEA-28)

> **Written 2026-08-04, before the run starts and before any result is seen.**
> That ordering is the point: an acceptance threshold chosen after looking at the
> numbers is not a threshold, it is a description. Provenance for the run itself
> — instance, window, build — is filled in under "Run record" once the deploy and
> reset land.
>
> Instance: the reference instance (HA 2026.7.4) — a real, lived-in home, not a
> test box. Solar inverter with a scheduled battery, 14 tracked devices plus the
> Untracked remainder.

## What this validates

`PLAN.md` Epic 6.2: re-run the manual, history-based calculation over the same
week the integration ran live, and compare per device per day. The manual method
is the one in `AIRCON_COST_EXPLORATION.md`, which hand-computed the same concepts
from recorder history before any of this was built.

Under the full-allocation model (ADR-0002) the comparison is necessary but not
sufficient, so three reconciliation checks run alongside it.

## Preconditions

The week does not start until all of these hold. Each exists because a known
defect would otherwise contaminate the run.

| Precondition | Why |
|---|---|
| The build carrying HEA-57/59/51/61 is installed | The reset action does not exist on the old build |
| `reset_totals` has been run **once**, after install | Clears the phantom energy from the bad source (HEA-60) and the new-accumulator baseline skew in one pass |
| Every HEA total reads zero immediately after the reset | Proves the rebase actually took, rather than leaving a restored baseline underneath |
| The cloud-polled plug is pointed at its honest `consumption` counter | Its `total_energy` sibling is bugged upstream — `total += consumption` on every poll — and inflated that device ~97× |
| No change to the cycle-meter set during the week | ADR-0008 froze this; changing it mid-run invalidates the period figures |
| **The build also carries HEA-67** | Added 2026-08-05. It is the last change that alters accounting behaviour: until it is installed, a house-meter outage collapses consumption to grid + battery *and* lets the plausibility guard condemn healthy devices, whose energy is then refused outright. Either would corrupt exactly what this run measures |

Development continues during the week. Changes are safe to land mid-run only if
they touch neither `engine/` nor the sensor set: renaming a sensor or adding a
metered concept breaks the statistics series the comparison is drawn from, and
an accounting change makes the week's data two datasets rather than one. On the
day the run started, nothing remaining in the backlog required either.

Because the reset zeroes everything, this run can reconcile on **absolute**
values, not just window deltas — which is what makes a one-week comparison
meaningful at all.

## Acceptance threshold

Fixed in advance:

> A device-day passes when the integration's Actual Cost is within **±5 %** or
> **±€0.05**, whichever is *larger*, of the manually computed figure.

The larger-of rule exists so a device costing €0.02 for the day is not failed by
a rounding-scale difference, while a device costing €3 is not passed by a €0.15
error. Both bounds are needed; either alone is wrong at one end of the range.

**The run passes** when ≥95 % of device-days fall inside the threshold *and*
every reconciliation check below holds on every day. A single reconciliation
failure fails the run regardless of the per-device agreement, because those
checks test the invariant the product's honesty rests on.

Failures become child issues of HEA-28, not silent adjustments to the threshold.

## Reconciliation checks

**1. The aggregate invariant.** Over the period:

```
Σ (device Actual Cost) + Untracked Actual Cost
  == real grid import cost + battery-ledger discharge cost
```

This is the invariant that motivated rejecting the binary-gate model
(`PLAN.md` revision note). It is test-enforced per bucket in the engine; this
checks it survives a week of real data, restarts and late corrections.

**2. The remainder is never negative.** Untracked energy and cost stay ≥ 0 on
every day. The engine clamps the remainder at zero rather than letting it go
negative (ADR-0002), so a *clamped* day is not visible in the figure itself —
check `consecutive_overdrawn_buckets` and the negative-remainder Repair instead
of only the published value.

**3. The battery ledger against Predbat.** Compare HEA's stored-cost ledger with
Predbat's own cost accounting for the same window. Two documented optimistic
biases are expected and are *not* failures, but must be quantified rather than
waved through:

- the ledger starts empty, so pre-existing charge discharges at zero cost until
  it washes out;
- round-trip losses are not inflated into the discharge price.

## New in this build — validate explicitly

These ship for the first time in the deploy that starts the week, so the run is
also their first real exercise.

- **By-source split (HEA-51).** For every device and every day,
  `energy_from_grid + energy_from_generation + energy_from_battery ==
  energy_used`. A shortfall is legitimate only for intervals where no
  house-level source reported at all; any other gap is a defect. Also sanity-check
  that the whole-home by-source figures track the Energy Dashboard's own
  grid/solar/battery split for the same window.
- **Rounding (HEA-59).** No published state carries more than 6 dp (energy) or
  4 dp (money), and no `total_increasing` figure steps backwards across a restart.
- **Rename (HEA-61).** No `cost_without_solar` entity is still being written to.
  46 of them existed on the old build; they should be orphaned, not updating.

## Method

0. Confirm the preconditions above, including that every source is reporting —
   a source that has never reported since the restart is the one thing that will
   quietly produce a zero device-day (HEA-69 raises a Repair for it, but only
   once its silence outlasts the grace period).
1. Record the starting instant and confirm every HEA total is zero.
2. Let it run seven full days. Do not reload, reconfigure, or add devices —
   a reload seals in-flight buckets (ADR-0006) and a device change reshapes the
   allocation.
3. Pull per-device, per-day figures from **long-term statistics** (`change`
   between day boundaries), which ADR-0008 makes the substrate for exactly this
   question — not from the cycle meters, whose fixed periods cannot be re-cut.
4. Recompute the same days manually from recorder history per
   `AIRCON_COST_EXPLORATION.md`.
5. Tabulate device × day, mark each cell against the threshold, and run the three
   reconciliation checks per day.
6. Record results below; raise a child issue per failure.

## Known limitation, stated up front

**A summer week cannot validate the winter battery regime.** In August the
battery mostly cycles free surplus generation; the regime that stresses the
stored-cost model is Predbat force-charging from the grid at ~€0.093 overnight
and discharging at peak, which is a winter pattern. Passing this run therefore
does **not** mean the model is proven — a post-winter accuracy review is a
required follow-up before that claim is made (`PLAN.md` → Risks, Epic 6.3).

## Run record

- **Reset run at:** 2026-08-04, on the build carrying HEA-57/59/51/61/58.
- **Build / commit:** `57fd40b`, installed 2026-08-05. This is the last change
  that alters accounting behaviour (HEA-67); the preconditions table says why the
  run waited for it.
- **Ledger continuity across two restarts confirmed.** The reset totals survived
  both the discovery deploy and the HEA-67 deploy: accumulation continued
  smoothly across each restart rather than restarting from zero, so the figures
  date from the 2026-08-04 reset and no second reset was needed. Checked at each
  restart, and again at the start of the window, that
  **Σ devices + Untracked ≡ whole home** exactly — residual `0.000000`.
- **Window:** the seven whole local days beginning at the first midnight after
  the 2026-08-05 install. The manual side is recomputed retrospectively from
  recorder history, so the window is cut at analysis time; a part-day at either
  end makes those device-day comparisons meaningless, so both are excluded.
- **Result:** _to be completed._

Figures are recorded here as reconciliations and percentages, never as absolute
meter readings — a counter total is one of the things the repo's privacy rules
keep out of a public repository, and the invariant is what this run is actually
testing.

### What this run cannot tell us

Recorded at the start, so it is not discovered as a convenient caveat afterwards.
Live figures on the day showed `energy_from_grid: 0` with essentially all energy
from generation. August exercises the solar-surplus regime almost exclusively, so
a pass here validates proportional allocation and the generation path and says
nothing about the stored-cost ledger under winter force-charging. See "Known
limitation" above — the post-winter review is a condition of the accuracy claim,
not an optional follow-up.
