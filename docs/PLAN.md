# MVP Delivery Plan — Device Cost Accounting

> Agreed 2026-07-11, revised 2026-07-11 after critical review (see Revision
> note below). This is the working plan for the MVP defined in `PRD.md`.
> Tracked in Linear: team **HEA**, project
> [MVP — Device Cost Accounting](https://linear.app/tedds-consulting/project/mvp-device-cost-accounting-91efc52dfd67).
> Decisions recorded here are candidates for ADRs (see Epic 2); once an ADR is
> accepted it supersedes the corresponding summary below.

## Revision note (2026-07-11)

The original plan shipped a binary solar gate as the MVP accounting model.
Critical review showed it violates the aggregate invariant — the sum of
device "actual costs" can exceed the house's real import cost by an order of
magnitude when the deficit is small relative to tracked draw, and it prices
battery-covered energy at live import rates. Decision: **accuracy is the
product** — the MVP implements full source allocation from day one, falling
back to a deficit-capped model only if a hard blocker emerges. The July 2026
binary-gate validation figures remain useful as fixtures and historical
reference, not as target outputs.

## Decisions made

| Decision | Choice | Rationale |
|---|---|---|
| Product form | Native Home Assistant custom integration (`custom_components/`, config flow, HACS-installable) | Preferred direction in `IMPLEMENTATION_IDEAS.md`; the manual validation (`notes/AIRCON_COST_EXPLORATION.md`) proved the data foundations; template-helper prototyping would be throwaway work that doesn't scale to 14+ devices |
| Cost attribution | **Full proportional source allocation** behind a pluggable `CostAllocationStrategy` interface | Per interval, house consumption is served by grid import (live price), solar (0 at margin), and battery discharge (stored cost). Each bucket is allocated across tracked devices + remainder in proportion to draw. Restores the invariant Σ device costs = real costs; honest in the winter Predbat regime. Binary gate rejected (aggregate over-charge); deficit-capped model is the recorded fallback |
| Battery pricing | **Tracked stored cost**: charge ledger (grid charge at live import price, solar charge at 0), discharge priced at weighted average stored cost | Predbat charges cheap overnight (€0.093) and discharges at peak; flat-rate or free would misprice winter substantially |
| Energy-balance decomposition | **Adaptive** (ADR-0005): derive house-served sources (grid→house = import − grid-charge, battery→house = discharge, solar→house = remainder) from raw meters — residual model (house-load anchor) when a load sensor exists, else full-balance (generation + export). Added during HEA-21 | Raw grid import includes battery charging; feeding it in raw double-counts and breaks the aggregate invariant. Households differ in available sensors, so adaptive serves both Energy-Dashboard users (export + generation) and those with a house-load sensor. Requires adding grid-export to the HEA-20 config |
| Interval model | Engine buckets on **5-minute intervals**; coarse energy deltas are spread across the intervals they span | Allocation needs synchronized cross-device intervals; 5 min balances fidelity vs noise; to be justified in ADR-0002 |
| Solar & battery inputs | **Optional** in config | Without them, Actual = naive cost and the product still serves the (large) no-solar HA population as a per-device TOU cost tracker — PRD target users explicitly include tariff-only households |
| Remainder bucket | House consumption minus tracked devices = an "Untracked" pseudo-device with the same cost sensors | Answers "which devices drive my bill" honestly (shows the unexplained share) and doubles as a live reconciliation check |
| Build on native foundations | Prefer existing HA machinery over reimplementation: config flow pre-fills from **Energy Dashboard preferences**; daily/weekly/monthly/quarterly/yearly totals via **auto-created native `utility_meter` helpers** (PowerCalc-style); power-only devices via **auto-created native Integral helper** | "Don't rebuild what exists." Default cycles: daily + monthly; weekly/quarterly/yearly as a global opt-in (entity-count discipline: all-on would create ~200+ helper entities across 14 devices). Lifetime totals are the integration's own sensors. Feasibility of programmatic helper creation validated early in Epic 4; internal implementation is the recorded fallback |
| Export opportunity cost | **Deferred, post-MVP** — explicitly documented | Solar-covered energy forgoes export revenue, so MVP Solar Saving is knowingly optimistic; documented in ADR-0002 and README, tracked as a backlog issue |
| i18n | **Day one**: `strings.json` + `translations/` (en, es) | Same discipline as the retirement platform; retrofitting translations is worse than starting with them |
| Quality gates | ruff (strict) + mypy (strict) + pytest coverage ≥90% enforced in CI; **SonarQube as a local pre-commit gate** (existing local server, same `sonar-check.sh` workflow as the retirement repos), never a CI-blocking step | Revised 2026-07-12: with the server and workflow already in place the marginal cost is near zero, and Sonar adds what ruff+mypy don't — cognitive-complexity enforcement (the mechanism behind the "orchestrators read as linear steps" rule), cross-file duplication detection, and the new-code quality-gate ratchet. CI stays green without it so external contributors are never blocked; revisit SonarCloud (free for OSS) if the project attracts contributors |
| Local dev environment | **WSL (Ubuntu-24.04) + uv**, Python 3.14, venv at `~/.venvs/hea` — not Windows | Discovered 2026-07-12 while building the CI pipeline: Home Assistant imports `fcntl` (Unix-only) and `pytest-homeassistant-custom-component` loads as a pytest plugin, so on Windows `pytest` dies at collection even for tests with no HA imports. Windows is not a supported HA platform and never will be. WSL also makes the local pre-commit gate byte-identical to CI (same Linux, Python and HA versions), so the gate genuinely predicts CI rather than approximating it. ruff and mypy do still run natively on Windows — they never execute the code — but the split is not worth maintaining |
| Workflow | TDD, conventional commits with ticket scope (`fix(HEA-nn):`), direct-to-main, append-only ADRs, adapted ways-of-working doc set | Same principles as `ai-shared-config/CRITICAL_INSTRUCTIONS.md`, tuned for Python/HA |
| Tracking | Linear team **Home Energy Advisor (HEA)**, one project "MVP — Device Cost Accounting", epics as parent issues | Clean separation from retirement-platform work |
| Distribution | Public GitHub repo under `consultingtedds`, MIT licence, HACS custom repository first; HACS default store later | HACS requires a public repo; matches the charter's Open Source First principle (MIT is the norm for HA custom integrations). Public repos get unlimited GitHub Actions minutes |

## Architecture

Scope: the product tracks **any device sharing power or energy data**. The
instance survey (`notes/DEVICE_SENSOR_SURVEY.md`) found five behaviour
patterns; energy sources are normalised before allocation.

```
Accounting engine (pure Python, no HA imports)
  • EnergySource normalisation:
      CumulativeEnergySource — total_increasing counters, handling resets
      (power-only devices arrive as energy via auto-created Integral helpers)
  • Interval ledger (5-min buckets): per-bucket house energy balance —
    consumption = import + solar_used + battery_discharge; device deltas
    spread across the buckets they span
  • Battery stored-cost ledger — charge events priced at source
    (grid @ live import price, solar @ 0); discharge at weighted avg cost
  • CostAllocationStrategy interface →
      ProportionalAllocationStrategy (MVP): each source bucket allocated
      across tracked devices + remainder by share of draw
      (fallback if blocked: deficit-capped per-device model)
        │
        ▼
HA integration layer (custom_components/home_energy_advisor/)
  • Config flow: house-level inputs (grid import, solar, battery,
    house consumption — pre-filled from Energy Dashboard preferences;
    solar/battery optional) + price entity + currency
    + per-device (name, energy or power sensor); options flow
  • Auto-created native helpers: utility_meter cycles (daily+monthly
    default; weekly/quarterly/yearly opt-in), Integral for power-only
  • Per tracked device + "Untracked" remainder: Energy Used, Actual Cost,
    Cost Without Solar, Solar Saving; RestoreEntity; monetary/
    total_increasing classes; diagnostics + Repairs; strings.json + en/es
        │
        ▼
Presentation
  • Documented Lovelace dashboard using core cards (comparison + per-device
    + untracked share)
  • Custom card only if evidence demands it
```

## Epics and tickets

### Epic 1 — Foundation
1. ~~Create public GitHub repo~~ (done 2026-07-11); hassfest-compliant integration skeleton (`manifest.json`, `hacs.json`)
2. CI: ruff, mypy, pytest + coverage gate, hassfest action, HACS validation action, commitlint
3. Pre-commit hooks + husky/commitlint local setup
4. Ways-of-working docs adapted from `ai-shared-config`: `CRITICAL_INSTRUCTIONS.md`, `TESTING_STANDARDS.md`, `DOCUMENTATION_STANDARDS.md`, `CLAUDE.md`, ADR template

### Epic 2 — ADRs
1. ADR-0001: Native HA integration (over template helpers / AppDaemon)
2. ADR-0002: Cost attribution — full proportional source allocation; 5-min interval model; battery stored-cost pricing; binary gate rejected with reasons; deficit-capped fallback; export opportunity cost deferred with bias documented
3. ADR-0003: Entity naming — finalise Energy Used / Actual Cost / Cost Without Solar / Solar Saving + Untracked remainder naming
4. ADR-0004: EnergySource taxonomy — cumulative counters natively; power-only via auto-created native Integral helpers; `total` state_class and forecast/false-friend sensors out of MVP scope

### Epic 3 — Accounting engine (pure Python, TDD)
1. Delta calculator with `total_increasing` reset handling (`CumulativeEnergySource`)
2. Interval ledger: 5-min energy balance from house-level inputs; device delta spreading
3. Battery stored-cost ledger (charge pricing, weighted-average discharge cost)
4. `CostAllocationStrategy` interface + `ProportionalAllocationStrategy` (+ remainder computation)
5. Golden-master tests: fixtures from the July 2026 exploration; energy (107.75 kWh) and naive (€19.30) figures unchanged; allocated-cost expectations recomputed under the new model; binary-gate €7.63 retained as reference only; invariant tests (Σ allocations = bucket totals)

### Epic 4 — HA integration layer
1. Config flow: house-level inputs pre-filled from Energy Dashboard preferences (solar/battery optional), price entity, currency, per-device energy-or-power sensor selection; options flow
2. Feasibility spike + implementation: programmatic creation of native utility_meter / Integral helpers (fallback: internal implementation, recorded in ADR-0004)
3. Runtime wiring: listeners/coordinator connecting engine to HA state machine
4. Per-device + Untracked remainder sensors (×4) with restore-on-restart
5. Cycle totals via auto-created utility_meter helpers (daily + monthly default; weekly/quarterly/yearly global opt-in)
6. i18n: strings.json + translations (en, es) for config flow, entities, Repairs
7. Diagnostics + Repairs (source sensor unavailable/renamed, price unavailable policy, helper-creation failures)

### Epic 5 — Dashboard & documentation
1. Lovelace dashboard: devices-by-cost comparison + per-device detail + untracked share (consult HA best-practices skill)
2. README per documentation standards (including a plain-language explanation of the allocation model and its known limitations — export opportunity cost, interval approximation)

### Epic 6 — Dogfood on production instance
1. Install and configure a diverse device set on homeassistant.tedds.net: 9 aircons (cycle-resetting), pool pump + water heaters (lifetime counters via Zigbee2MQTT), well pump (cloud-polled Tuya), wall lights (power-only)
2. One-week parallel run; reconciliation checks: Σ device+remainder cost vs actual import cost; remainder plausibility; battery ledger vs Predbat's own accounting
3. Fixes arising; note: July dogfooding cannot exercise the winter battery regime — revisit accuracy after the first winter month (tracked as follow-up)

### Epic 7 — Historical backfill
1. Backfill via `recorder.import_statistics` on device setup (bounded by price/solar/battery statistics history — 13+ months confirmed for key inputs)
2. Validate backfilled statistics against manual tables

### Epic 8 — Release
1. Semver tagging + GitHub release CI
2. HACS custom-repository install docs + first tagged release
3. (Backlog) HACS default store submission; community forum post for demand validation

Sequencing: 1 → 2 → 3 → 4 → 5 → 6, then 7 and 8 in either order. Epic 3 has no HA
dependencies and can start as soon as Epic 1 lands.

## Risks and open questions

- **Model complexity risk.** Full allocation from day one is meaningfully more
  work than the binary gate (interval ledger, battery ledger, cross-device
  allocation). Accepted deliberately: accuracy is the product. Fallback if
  blocked: deficit-capped per-device model (documented in ADR-0002).
- **Helper auto-creation feasibility.** ~~Programmatic utility_meter/Integral
  creation is proven in the wild (PowerCalc) but not first-party API; spike
  early in Epic 4, internal implementation as fallback.~~ **Resolved (2026-07-21,
  HEA-34):** the Integral path shipped — programmatic native-helper creation is
  proven against real HA (idempotent, and no phantom energy across `unavailable`
  spans). The internal-implementation fallback was not needed. The shared spike
  de-risks the native `utility_meter` path (HEA-23). See ADR-0004 → Update.
- **Sensor coarseness.** WF-RAC units report 0.25 kWh steps with no power
  sensor; spreading deltas across 5-min buckets is an approximation.
  Dogfooding decides whether it is good enough.
- **Seasonality.** One summer week cannot validate the winter battery regime;
  explicit post-winter accuracy review required before claiming the model is
  proven.
- **Price sensor generality.** MVP assumes a sensor reporting current price in
  currency/kWh. Tariff-integration adapters (Nordpool, Octopus, PVPC) are
  post-MVP.
- **Linear free plan** caps the workspace at 250 non-archived issues and 2
  teams. HEA is the second team; archive Done issues if the cap approaches.

## Out of scope (MVP)

Per `PRD.md`: forecasting, optimisation, automation, scheduling recommendations.
Additionally deferred: **export opportunity cost** (documented bias, backlog
issue), tariff-integration adapters, devices with neither power nor energy
data, custom Lovelace card, `total` state_class device sources.
