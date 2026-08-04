# ADR-0009: Name the pricing rule, not the absent hardware

## Status

Accepted

Supersedes the **naming** of one concept in ADR-0003 — "Cost Without Solar"
becomes **"Cost at Grid Price"** (`cost_without_solar` → `cost_at_grid_price`).
Everything else in ADR-0003 stands: the `unique_id` scheme, the
`device_class`/`state_class` table, the Untracked remainder, and the reasoning
for Cost Savings being `total` (as amended by ADR-0007).

## Context

Three of the four per-device figures are named for what they are. The fourth was
named for a piece of hardware, and the name was wrong for most of the ways the
figure earns its number.

**What it computes** (`engine/allocation.py`): every kWh priced at the live grid
import rate at the moment it was used, whatever actually served it. The
counterfactual is *"nothing was self-supplied; it all came off the meter as you
used it."*

Three distinct problems with "Cost Without Solar":

1. **Battery arbitrage is not solar.** On the reference instance Predbat
   force-charges from the *grid* at ~€0.093 overnight and discharges at the
   evening peak. That saving is real, is captured by this figure, and has
   nothing to do with solar — nor is the energy self-produced. It is grid
   energy, time-shifted.
2. **Generation is not only solar.** Wind, micro-hydro, a generator, a shared
   supply — anything not coming off the metered import behaves identically in
   the model, because `SourceKind.GENERATION` is priced at zero at the margin.
   The engine never cared which technology produced it. Naming a source after
   one technology guarantees the name goes stale.
3. **ADR-0003 already made this argument and did not apply it.** Its rejected
   alternatives say "Solar Saving" was rejected because *"the figure captures
   savings from both local generation and cheap-battery arbitrage, not solar
   alone — 'Solar' would misdescribe it."* But
   `Savings ≡ Cost Without Solar − Actual Cost`, so the identical objection
   applies to the minuend. ADR-0003's own Context paragraph says "what it would
   have cost **without local generation**"; its decision table then says
   "Cost Without Solar". The prose and the table disagreed from the start.

The same misnomer ran deeper than the sensor: `SourceKind.SOLAR` and
`SourceRole.SOLAR` already meant "free non-grid supply of any kind", and the
config flow labelled the input "Solar generation energy".

### Why now, when ADR-0003 calls this a one-way door

ADR-0003 correctly states that changing entity identity after release orphans
long-term statistics. That cost is currently **zero**:

- no git tags and `manifest.json` still at `0.0.1`; not in the HACS default store;
- one known installation (the reference instance);
- decisively, the HEA-57 `reset_totals` action **clears HEA's own statistics** in
  the very same deploy. Renaming here discards history that is being deliberately
  discarded anyway.

The window is this deploy. After it, the same rename costs real validated
history or a migration.

## Decision

**1. Name the pricing rule, not the absent hardware.**

| Before | After |
|---|---|
| `cost_without_solar` / "Cost Without Solar" | `cost_at_grid_price` / "Cost at Grid Price" |
| `SourceKind.SOLAR` | `SourceKind.GENERATION` |
| `SourceRole.SOLAR` | `SourceRole.GENERATION` |
| `DeviceAllocation.solar_saving` | `DeviceAllocation.cost_savings` |
| `BatteryLedger.charge_from_solar` | `charge_from_generation` |
| "Solar generation energy" (config label) | "Local generation energy" |

"Cost at Grid Price" states the rule the code applies and is indifferent to which
sources a household has. It needs no revision when a fourth source kind appears.

**2. HEA-51's by-source sensor ships as `energy_from_generation`,** never
`energy_from_solar` — decided before it shipped, so it cost nothing. The trio is
`energy_from_grid` / `energy_from_generation` / `energy_from_battery`.

**3. `CONF_SOLAR_ENTITY` keeps its storage key `"solar_entity"`.** It is
persisted in live config entries; changing it needs a migration and buys nothing,
because ADR-0003 already makes *display* labels free to re-word. The constant name
is retained too, so the key and the symbol do not drift apart.

### Rejected alternatives

- **"Cost Without Solar and Battery"**: rejected — enumerating hardware is the
  original mistake in a longer form. It goes stale the moment a household has a
  wind turbine, and it cannot describe a source we have not thought of.
- **"Cost Without Self-Supply" / "Cost Without Self Production"**: rejected —
  both inherit the same *class* of error as "Solar", just less visibly. Energy
  discharged from a grid-charged battery was never self-supplied or
  self-produced; it was bought from the grid earlier and more cheaply. These
  names would misdescribe a large part of the winter Predbat saving.
- **"Grid-Only Cost"**: rejected — ambiguous against HEA-51's new
  `energy_from_grid`. It reads as "the cost of the grid-supplied portion only",
  which is a different and entirely plausible figure.
- **Renaming `CONF_SOLAR_ENTITY`'s storage key**: rejected — a config-entry
  migration for zero user-visible benefit.
- **Deferring until after HEA-28's validation week**: rejected — the free window
  is exactly this deploy, and shipping HEA-51 under a name already agreed to be
  wrong would mean renaming twice.

## Consequences

- `sensor.<device>_cost_without_solar` becomes
  `sensor.<device>_cost_at_grid_price` on every tracked device, the Untracked
  remainder and the whole-home aggregate. Its `unique_id` changes with the
  concept key, so Home Assistant creates a new entity; the old statistics are
  cleared by the HEA-57 reset in the same deploy.
- The cycle meters over the old sensor are reconciled away and re-created over
  the new one by `async_sync_cycle_meters`, because their ownership key is the
  source entity id.
- Any dashboard, automation or template referring to the old entity id must be
  updated. On the reference instance that is the uncommitted HEA-25 dashboard
  work (`docs/dashboard.md`, `docs/dashboard-template.yaml`).
- Spanish: "Coste sin solar" → "Coste a precio de red".
- **Revisit if** the export-aware allocation variant (HEA-38) changes what the
  counterfactual means — pricing generation at the export rate rather than zero
  would make "at grid price" describe only part of the comparison.
