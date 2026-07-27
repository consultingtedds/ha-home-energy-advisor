# ADR-0007: Monetary cost sensors are `state_class: total`; Cost Savings is not metered

## Status

Accepted

Supersedes the `state_class` column of ADR-0003 for `actual_cost` and
`cost_without_solar`, and restates ADR-0003's cycle-variant rule (the metered set
is unchanged; only its description needed reworking after the state_class move).
Extends ADR-0006, which already moved the Untracked remainder's costs to `total`.

## Context

ADR-0003 fixed the four per-device figures and their `state_class`: `energy_used`
(`total_increasing`), `actual_cost` and `cost_without_solar`
(`total_increasing`), and `cost_savings` (`total`). Two things have since made
that split wrong in practice:

1. **Home Assistant rejects `monetary` + `total_increasing`.** Current HA logs a
   validation warning that a `monetary` sensor's `state_class` must be `total` or
   `None`, never `total_increasing` — a currency total is not a strictly-rising
   meter (money can be refunded, corrected, netted). Every Actual Cost and Cost
   Without Solar sensor triggered this warning.
2. **ADR-0006 already moved the Untracked remainder's costs to `total`** so late
   corrections would not read as meter resets. That left device costs
   (`total_increasing`) and Untracked costs (`total`) inconsistent for the same
   `monetary` concept.

Separately, ADR-0003 decided Cost Savings gets **no** cycle `utility_meter`
helper (it can go negative under battery arbitrage, and period savings is exact
by subtraction). But the code metered **all four** concepts — the divergence
HEA-49 exists to close.

## Decision

**1. All monetary cost sensors use `state_class: total`.** `actual_cost` and
`cost_without_solar` move from `total_increasing` to `total`, joining
`cost_savings` (and Untracked's costs, per ADR-0006). `total` models a monotonic
accumulator perfectly well — it simply does not *assume* monotonicity — so the
actual/naive costs, which only grow, lose nothing, while Cost Savings' genuine
dips stay honest. One consistent rule: **energy is `total_increasing`, money is
`total`.** `energy_used` is unchanged (`energy` + `total_increasing` is valid and
correct). The only per-device/Untracked difference that remains is Energy Used
(`total_increasing` on a real device, `total` on Untracked — ADR-0006).

**2. Cost Savings gets no cycle meter; period savings is derived.** The code now
honours ADR-0003: `_device_cost_sensors` excludes `cost_savings`, so no
`cost_savings_daily/monthly/…` helper is created, and any that already exist are
reconciled away on the next setup. A period's saving is **Cost Without Solar
(cycle) − Actual Cost (cycle)** — needs no entity, stays exact, and cannot be
corrupted by a negative interval crossing a period boundary. The metered set is
therefore `energy_used`, `actual_cost`, `cost_without_solar` — the same three
ADR-0003 intended (it called them "the three `total_increasing` figures"; two are
now `total`, but the set is the same).

## Consequences

- The `monetary` + `total_increasing` HA warning is gone, and device / Untracked
  / whole-home costs are consistent.
- Cost-sensor cycle helpers drop from four concepts to three per group: a home
  with one device goes from 24 to 18 utility_meters (device + Untracked × 3
  concepts × 2 default cycles), easing the entity-count concern (HEA-40).
- `state_class` is a one-way door (ADR-0003): moving the costs to `total` is a
  permanent identity change. On an already-running instance HA will flag a
  one-time "statistics type changed" for the affected cost sensors — benign,
  cleared from Developer Tools → Statistics, exactly as for the ADR-0006 move.
- The dashboard (HEA-25) already derives period savings by subtraction, so no
  card depends on the removed `cost_savings` cycle sensors.
- Revisit if HA changes the valid `state_class` set for `monetary`, or if a
  future model makes an actual/naive cost genuinely non-monotonic (it would
  already be safe under `total`).
