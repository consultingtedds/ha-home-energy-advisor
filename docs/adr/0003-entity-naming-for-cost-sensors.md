# ADR-0003: Entity naming for the per-device cost sensors

## Status

Accepted

## Context

The MVP exposes four figures per tracked device: the energy it used, what it
actually cost, what it would have cost without local generation, and the saving
between the two (`PRD.md` → Minimum Viable Product). The concepts were named but
left "intentionally undecided" in `docs/notes/IMPLEMENTATION_IDEAS.md`; the
accounting engine now computes them (HEA-16–HEA-18), so they must become concrete
Home Assistant sensor entities.

Entity identity has to be fixed **before** Epic 4 builds sensors. A sensor's
`unique_id`, `device_class` and `state_class` are effectively permanent: changing
them after release orphans users' long-term statistics and breaks the dashboards
and automations built on them. Durable, trustworthy history is a PRD constraint,
so this is a one-way door and belongs in an ADR.

The same four figures also describe the "Untracked" remainder pseudo-device
(HEA-36).

## Decision

### Sensor identity (Home Assistant convention)

- Every sensor sets `has_entity_name = True` and a `translation_key`. The friendly
  name renders as **"{Device} {Concept}"** — e.g. *"Guest Bedroom Aircon Actual
  Cost"*. All user-facing text lives in `strings.json` + `translations/` (en, es),
  never hardcoded (HEA-37).
- `unique_id = {config_entry_id}_{device_key}_{concept_key}`, stable for the life
  of the entity. Display names may be re-translated or re-worded freely; the
  `unique_id` never changes, so statistics and dashboard references survive.
- `entity_id` auto-derives from device + concept, e.g.
  `sensor.guest_bedroom_aircon_actual_cost`.

### The four concepts

| Concept | Friendly name | `translation_key` | `device_class` | `state_class` | Unit |
|---|---|---|---|---|---|
| Energy used | Energy Used | `energy_used` | `energy` | `total_increasing` | kWh |
| Actual cost | Actual Cost | `actual_cost` | `monetary` | `total_increasing` | currency |
| Cost without solar | Cost Without Solar | `cost_without_solar` | `monetary` | `total_increasing` | currency |
| Cost savings | Cost Savings | `cost_savings` | `monetary` | **`total`** | currency |

The monetary unit is the configured currency (defaulted from the price entity's
unit of measurement).

### Why Cost Savings is `total`, not `total_increasing`

The first three figures only ever grow — energy cannot be un-used, money cannot
be un-spent — so `total_increasing` is correct and lets Home Assistant treat a
drop to a lower value as a genuine meter reset.

Cost Savings (= Cost Without Solar − Actual Cost) is almost always positive, but
it **can** decrease in one rare case: battery arbitrage loss. Energy charged into
the battery at an expensive rate and later discharged when grid import is cheap
genuinely cost more than buying at the moment of use would have, so the
stored-cost model reports a negative saving for that interval (HEA-18 keeps this
exact rather than flooring it at zero). A single negative interval makes the
lifetime accumulator dip. Under `total_increasing`, Home Assistant would misread
that dip as a meter reset and corrupt the long-term statistics; `total` correctly
models a value that can move either way. The trade-off — a value that is not
strictly monotonic — is accepted in exchange for honest, uncorrupted history.

### Untracked remainder

The remainder is a pseudo-device named **"Untracked"** carrying the same four
sensors (*"Untracked Actual Cost"*, etc.). It answers "how much of my bill is not
yet explained" and doubles as a live reconciliation check (HEA-36).

### Cycle variants (daily / monthly …)

Period totals are auto-created native `utility_meter` helpers over the lifetime
sensors (HEA-23; build-on-foundations per ADR-0004), named
**"{Device} {Concept} ({Cycle})"** — e.g. *"Guest Bedroom Aircon Actual Cost
(Daily)"*, `translation_key` `{concept}_{cycle}` (e.g. `actual_cost_daily`).

Only the three `total_increasing` figures get cycle helpers. Cost Savings does
**not**: `utility_meter` expects a monotonic source, which a `total` sensor is
not. Period savings is derived by subtraction — Cost Without Solar (cycle) −
Actual Cost (cycle) — which needs no extra entity and stays exact.

### Rejected alternatives

- **"Solar Saving"** (the original PRD wording): rejected because the figure
  captures savings from both local generation *and* cheap-battery arbitrage, not
  solar alone — "Solar" would misdescribe it. **"Savings"** was the other
  candidate; **"Cost Savings"** was chosen to read as monetary alongside the other
  Cost sensors and to leave room for a distinct energy-saving metric later.
- **"Energy" instead of "Energy Used"**: Home Assistant's bare "Energy" is
  terser, but "Energy Used" matches the product's established vocabulary and reads
  clearly beside the cost figures.
- **Cost Savings as `total_increasing` with the accumulator clamped so it never
  decreases**: rejected — it would break the identity
  Savings = Cost Without Solar − Actual Cost and silently hide the
  battery-arbitrage signal, which is real information.
- **"Unaccounted" / "Other" for the remainder**: rejected in favour of
  "Untracked", the term already used throughout `PLAN.md` and the ticket set.

## Consequences

- Epic 4 (HEA-22) implements exactly these four `translation_key`s per device plus
  the Untracked pseudo-device; i18n (HEA-37) keys off them.
- HEA-23 creates cycle helpers for the three `total_increasing` figures only; the
  dashboard (HEA-25) derives period savings by subtracting the two cost cycles.
- Fixing `unique_id`s here makes later display re-wording free, but the
  `device_class`/`state_class` choices — especially Cost Savings = `total` — are
  effectively permanent: changing them after release breaks statistics and would
  need a superseding ADR plus a migration.
- A negative Cost Savings is real information (battery arbitrage lost money that
  period), so it must be surfaced honestly in the front end, not hidden or floored
  at zero. How best to flag it — a `binary_sensor`/attribute, a conditional
  dashboard card, or colour coding — is an open UX question tracked in HEA-39.
- Revisit if: the export-opportunity-cost strategy variant (HEA-38) redefines how
  saving is calculated, or dogfooding shows users are confused by "Cost Savings".
