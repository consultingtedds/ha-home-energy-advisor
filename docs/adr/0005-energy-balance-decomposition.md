# ADR-0005: Energy-balance decomposition and the adaptive source model

## Status

Accepted

## Context

ADR-0002 fixed the cost model: per 5-minute interval,
`consumption = grid import + solar used + battery discharge`, each source priced
and allocated across devices. It did **not** specify how those source energies
are derived from the raw Home Assistant sensors — and that derivation turns out
to be load-bearing for the aggregate invariant.

Raw meters measure gross flows, not house-served energy. The grid-import meter
includes energy used to **charge the battery**. Feeding raw grid import in as the
"import" source double-counts: that grid-charged energy is counted once as
import, and again as battery discharge when it later serves the house. The sum of
device costs then exceeds the real grid bill — the exact invariant violation that
sank the binary gate (ADR-0002).

So the runtime must decompose raw meter deltas into what actually served the
house:

- **battery → house** = battery discharge
- **grid → house** = grid import − grid-charge
- **solar → house** = the remainder

`grid-charge` comes from the charge split — the min-import heuristic: a
household's battery charge is attributed to grid up to what was imported that
interval, the rest to solar (Predbat-independent, validated in HEA-28). The
remainder, solar → house, needs one more anchor, and households differ in which
sensor can supply it.

## Decision

Decompose **adaptively**, from whichever sensors a household has configured. The
decomposition lives in one place in the runtime coordinator (HEA-21); the engine
downstream (HEA-17/18) is unchanged — it still receives per-bucket source
energies that sum to consumption.

- **Residual model** — when a measured house-consumption (load) sensor is
  configured: `consumption = house_consumption`;
  `solar→house = house_consumption − grid→house − battery→house`. Fewest sensors,
  and solar-used is exact from a measured total.
- **Full-balance model** — otherwise, from generation + export:
  `solar→house = solar_generation − solar-charge − grid_export`;
  `consumption = grid→house + solar→house + battery→house`. This matches what
  Home Assistant Energy Dashboard users already have configured (import, export,
  generation, battery), at the cost of compounding more meters (more noise).
- **Import-only** — no solar or battery: `consumption = grid import`.

Adaptive was chosen over a single model because a direct house-load sensor is
cleaner but not universal, while export + generation are Energy Dashboard
staples but noisier. Supporting both serves the target users — the integration
pre-fills from the Energy Dashboard — without forcing a sensor a household may
not have. The full-balance model is the broader default (Paul's steer: usefulness
to other users first); the residual model is preferred automatically when a
house-load sensor is present.

Config implications, reworked into HEA-20: **grid-export is added**; the
house-level source inputs are optional, and the coordinator selects the model
from what is present.

## Consequences

- HEA-21 (coordinator) owns the decomposition; HEA-20 config gains grid-export
  and the "provide the set your setup has" model, with the required/optional
  logic relaxed accordingly.
- `solar→house` as a residual can go slightly negative under measurement noise or
  a wrong charge split; it is clamped at zero and the over-draw handling / the
  Untracked remainder absorbs the discrepancy (ADR-0002, HEA-18), flagged via
  Repairs (HEA-24).
- If a solar/battery household configures neither a house-load sensor nor
  (solar + export), the decomposition cannot be done and accuracy degrades to
  import-only; this is surfaced through diagnostics/Repairs (HEA-24), not hidden.
- The charge-split heuristic and the decomposition are the main accuracy risks;
  both are validated against Predbat's own accounting in dogfooding (HEA-28).
- Revisit if: dogfooding shows the full-balance meter noise is material, or a
  reliable direct solar-self-consumption sensor becomes commonly available (it
  would sidestep the decomposition entirely).

Relates to and elaborates ADR-0002.
