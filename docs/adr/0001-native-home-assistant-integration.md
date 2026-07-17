# ADR-0001: Native Home Assistant custom integration

## Status

Accepted

## Context

Home Energy Advisor complements Home Assistant's Energy Dashboard by explaining
money rather than energy flows (ADR-0000). That framing already assumes the
product lives *inside* Home Assistant — but the delivery form was still a choice,
and it shapes everything downstream: how users install and configure it, what
kind of entities it produces, how history is retained, and how it is distributed.

The July 2026 exploration (`docs/notes/AIRCON_COST_EXPLORATION.md`) prototyped the
accounting with hand-created **template helpers** and proved the data foundations
were sound. But that was a throwaway validation, not a shippable shape: the target
users run a dozen-plus measurable devices, each needing four cost sensors plus
cycle totals.

## Decision

Ship as a **native Home Assistant custom integration** —
`custom_components/home_energy_advisor/`, config-flow-installed, HACS-distributed.

This buys, as first-class citizens rather than bolt-ons:

- **Config flow / options flow** — guided setup and later reconfiguration,
  pre-filled from Energy Dashboard preferences; no YAML surgery.
- **First-class entities** with `unique_id`, `device_class`, `state_class` and
  device grouping (ADR-0003), so the sensors behave like any other HA entity.
- **Recorder + long-term statistics** — the durable, trustworthy history the PRD
  demands, and the substrate for historical backfill (Epic 7).
- **Repairs and diagnostics** — to explain any cost figure and flag broken source
  entities, meeting the PRD's transparency constraint.
- **HACS distribution** — the norm for community integrations, matching the
  charter's open-source-first principle.

Internally this pairs with a strict separation (ADR-0002/0004): a pure-Python
accounting engine with zero `homeassistant` imports, wrapped by a thin adapter
layer that maps HA state to engine inputs and publishes results to entities. The
integration form is what makes that adapter layer possible and keeps the engine
unit-testable.

## Rejected alternatives

- **Template / helper sensors (the prototype shape).** Rejected: they do not
  scale past a handful of devices. A dozen devices × four figures × cycle
  variants is hundreds of hand-created helpers, with no config flow, no device
  grouping, no Repairs, and fragile manual wiring. Fine as a one-off proof, unfit
  as a product.
- **AppDaemon app.** Rejected: its entities are second-class in Home Assistant
  (weaker `unique_id`/statistics/device integration), it adds a separate runtime
  dependency users must install and maintain, and its distribution story is
  weaker than HACS.
- **External service (e.g. a Spring Boot app talking to HA over the API).**
  Rejected: out-of-process, no native entities, heavy for a local-first product,
  and it forfeits the recorder/statistics/config-flow machinery entirely. It
  contradicts the charter's local-first principle.

## Consequences

- Commits the project to the Home Assistant integration toolchain and its
  constraints: Python, async event loop, `hassfest`/HACS validation, and the
  Unix-only test story (`pytest-homeassistant-custom-component`; see
  `CLAUDE.md`).
- Enables the whole downstream plan — config flow (HEA-20), native helper reuse
  (ADR-0004), long-term statistics and backfill (Epic 7), Repairs/diagnostics
  (HEA-24) — none of which the alternatives support cleanly.
- The engine/adapter split (this ADR + ADR-0002) keeps the financial core
  portable in principle; if the integration form ever had to change, the engine
  would survive intact.
- Revisit if: Home Assistant's integration model changes fundamentally, or a use
  case emerges that genuinely cannot be served from inside HA (none is foreseen —
  the product is defined as complementing the Energy Dashboard).
