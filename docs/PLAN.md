# MVP Delivery Plan — Device Cost Accounting

> Agreed 2026-07-11. This is the working plan for the MVP defined in `PRD.md`.
> Tracked in Linear: team **HEA**, project
> [MVP — Device Cost Accounting](https://linear.app/tedds-consulting/project/mvp-device-cost-accounting-91efc52dfd67)
> (HEA-1…8 are the epics below, HEA-9…32 their child issues).
> Decisions recorded here are candidates for ADRs (see Epic 2); once an ADR is
> accepted it supersedes the corresponding summary below.

## Decisions made

| Decision | Choice | Rationale |
|---|---|---|
| Product form | Native Home Assistant custom integration (`custom_components/`, config flow, HACS-installable) | Preferred direction in `IMPLEMENTATION_IDEAS.md`; the manual validation (`notes/AIRCON_COST_EXPLORATION.md`) already proved the accounting model, so template-helper prototyping would be throwaway work that doesn't scale to 9+ devices |
| Cost attribution | Binary solar gate behind a pluggable `CostAllocationStrategy` interface | Ships the validated model (deficit → import price, surplus → free) while leaving room for proportional/weighted allocation (the open question in ADR-0000) without rework |
| Gating signal fidelity | Time-weighted average of the surplus sensor between energy deltas, not an instantaneous sample | The validation gated on hourly means; energy deltas arrive 15 min–hours apart in 0.25 kWh steps, so a point sample at the delta would be a worse approximation than the method already proven |
| Daily/monthly totals | Provided by the integration (cycle sensors), not user-stacked `utility_meter` helpers | The PRD's headline question is "what did this cost me *today*?" — that should work out of the box |
| Quality gates | ruff (strict) + mypy (strict) + pytest coverage ≥90% in CI; no SonarQube | Sonar adds marginal value for a single Python repo and would couple this project to retirement-platform infrastructure |
| Workflow | TDD, conventional commits with ticket scope (`fix(HEA-nn):`), direct-to-main, append-only ADRs, adapted ways-of-working doc set | Same principles as `ai-shared-config/CRITICAL_INSTRUCTIONS.md`, tuned for Python/HA |
| Tracking | New Linear team **Home Energy Advisor (HEA)**, one project "MVP — Device Cost Accounting", epics as parent issues | Clean separation from retirement-platform work |
| Distribution | Public GitHub repo under `consultingtedds`, MIT licence, HACS custom repository first; HACS default store later | HACS requires a public repo; matches the charter's Open Source First principle (MIT is the norm for HA custom integrations; HA core itself is Apache-2.0). Public repos get unlimited GitHub Actions minutes |

## Architecture

Three layers, per `IMPLEMENTATION_IDEAS.md` — financial calculation independent of presentation:

Scope note (2026-07-11): the product tracks **any device sharing power or
energy data**, not just the aircon units. The instance survey
(`notes/DEVICE_SENSOR_SURVEY.md`) found five behaviour patterns; the engine
abstracts them behind an `EnergySource` interface with two MVP
implementations: `CumulativeEnergySource` (lifetime and resetting kWh
counters) and `PowerIntegratingSource` (power-only devices, W → kWh via
time-weighted integration).

```
Accounting engine (pure Python, no HA imports)
  • EnergySource abstraction:
      CumulativeEnergySource — total_increasing counters, handling resets
      PowerIntegratingSource — power-only devices (Riemann integration)
  • Time-weighted surplus tracker
  • CostAllocationStrategy interface → BinaryGateStrategy (MVP)
        │
        ▼
HA integration layer (custom_components/home_energy_advisor/)
  • Config flow: global (import price entity, surplus entity, currency)
    + per-device (name, energy sensor); options flow for edit/remove
  • State-change listeners on each tracked energy sensor
  • Four sensors per device: Energy Used, Actual Cost, Cost Without Solar,
    Solar Saving (= naive − actual)
  • Daily/monthly cycle sensors; RestoreEntity; monetary/total_increasing
    classes so long-term statistics work; diagnostics + Repairs
        │
        ▼
Presentation
  • Documented Lovelace dashboard using core cards (comparison + per-device)
  • Custom card only if evidence demands it
```

## Epics and tickets

### Epic 1 — Foundation
1. Create public GitHub repo; hassfest-compliant integration skeleton (`manifest.json`, `hacs.json`, licence)
2. CI: ruff, mypy, pytest + coverage gate, hassfest action, HACS validation action, commitlint
3. Pre-commit hooks + husky/commitlint local setup
4. Ways-of-working docs adapted from `ai-shared-config`: `CRITICAL_INSTRUCTIONS.md`, `TESTING_STANDARDS.md`, `DOCUMENTATION_STANDARDS.md`, `CLAUDE.md`, ADR template

### Epic 2 — ADRs
1. ADR-0001: Native HA integration (over template helpers / AppDaemon)
2. ADR-0002: Cost attribution — binary gate behind strategy interface; time-weighted gating signal; export-opportunity-cost recorded as a future strategy variant, not built
3. ADR-0003: Entity naming — finalise Energy Used / Actual Cost / Cost Without Solar / Solar Saving as entity IDs and display names
4. ADR-0004: EnergySource taxonomy — cumulative vs power-integrating sources; `total` state_class and forecast/false-friend sensors out of MVP scope

### Epic 3 — Accounting engine (pure Python, TDD)
1. Delta calculator with `total_increasing` reset handling (`CumulativeEnergySource`)
2. `PowerIntegratingSource`: W → kWh via time-weighted integration for power-only devices
3. Time-weighted surplus tracker (accumulate surplus·dt between deltas)
4. `CostAllocationStrategy` interface + `BinaryGateStrategy`
5. Golden-master tests: fixtures from the July 2026 exploration must reproduce the €19.30 naive / €7.63 gated tables

### Epic 4 — Integration layer
1. Config flow (global settings) + add-device flow + options flow
2. Runtime wiring: listeners/coordinator connecting engine to HA state machine
3. Per-device sensors (×4) with restore-on-restart
4. Daily/monthly cycle sensors
5. Diagnostics + Repairs (e.g. source sensor unavailable/renamed)

### Epic 5 — Dashboard & documentation
1. Lovelace dashboard: devices-by-cost comparison + per-device detail (consult HA best-practices skill)
2. README per documentation standards (purpose, quick start, entities table, testing)

### Epic 6 — Dogfood on production instance
1. Install and configure a diverse device set on homeassistant.tedds.net: 9 aircons (cycle-resetting), pool pump + water heaters (lifetime counters via Zigbee2MQTT), well pump (cloud-polled Tuya), wall lights (power-only)
2. One-week parallel run vs the manual methodology; reconcile discrepancies
3. Fixes arising

### Epic 7 — Historical backfill
1. Backfill via `recorder.import_statistics` on device setup (validated in exploration; bounded by price/surplus statistics history)
2. Validate backfilled statistics against the manual tables

### Epic 8 — Release
1. Semver tagging + GitHub release CI
2. HACS custom-repository install docs + first tagged release
3. (Backlog) HACS default store submission

Sequencing: 1 → 2 → 3 → 4 → 5 → 6, then 7 and 8 in either order. Epic 3 has no HA
dependencies and can start as soon as Epic 1 lands.

## Risks and open questions

- **Sensor coarseness.** The WF-RAC units report energy in 0.25 kWh steps with no
  instantaneous power; accuracy is inherently "rough snapshot", not billing-grade.
  Dogfooding (Epic 6) decides whether this is good enough or per-device power
  monitoring is needed.
- **Gating definition.** Solar-vs-consumption chosen over true grid import
  (`predbat.grid_power`); a battery covering a shortfall reads as "free" here.
  Revisit as a second strategy if bill-accuracy is demanded.
- **Price sensor generality.** MVP assumes any sensor reporting a current price in
  currency/kWh. Tariff integrations vary (Nordpool, Octopus, PVPC); no adapter work
  in MVP.
- **Linear free plan** caps the workspace at 250 non-archived issues and 2 teams.
  HEA is the second team; keep the backlog lean and archive Done issues if the cap
  approaches.

## Out of scope (MVP)

Per `PRD.md`: forecasting, optimisation, automation, scheduling recommendations.
Additionally deferred: proportional/weighted allocation, export opportunity cost,
devices without energy sensors, custom Lovelace card, non-EUR/tariff adapters.
