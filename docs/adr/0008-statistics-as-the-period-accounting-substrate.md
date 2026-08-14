# ADR-0008: Long-term statistics are the period-accounting substrate; cycle meters are convenience

## Status

Accepted

Supersedes the *cycle-totals rationale* of ADR-0004 — its "period totals come from
auto-created `utility_meter` helpers" framing. ADR-0004's other decisions (the
EnergySource taxonomy, Integral-helper reuse for power-only devices, the
build-on-native-foundations principle) stand unchanged, as does ADR-0007's
metered set for the helpers that remain.

## Context

The product promise (`PRD.md`, ADR-0000) is to answer, for any device and **any
period**: what did it cost, what would it have cost without solar and battery,
and what did that save. The delivery plan met that with auto-created
`utility_meter` cycle helpers — daily and monthly by default, longer cycles
opt-in — and HEA-40 was raised to revisit the resulting entity multiplication.

Measured on the reference instance (2026-07-28,
14 tracked devices):

- **120 `utility_meter` config entries**, every one created by HEA
  (4 concepts × 15 device-slots × 2 cycles; 90 after ADR-0007 removes the
  Cost Savings meters). HEA accounts for roughly 185 of the instance's 1607
  sensor entities.
- HEA's own sensors **already record full long-term statistics** — `sum`,
  `state` and `change` per hour/day/month for `energy_used`, `actual_cost` and
  `cost_without_solar` — because they carry a `device_class` and a `state_class`
  (ADR-0007). Verified directly against the recorder.

The decisive observation is structural, not numeric: **a `utility_meter` is a
fixed-period accumulator.** No arrangement of daily/weekly/monthly/yearly meters
can answer "what did this device cost from 20 May to 15 July" — the question the
product exists to answer. Long-term statistics can, at any range, and that is
precisely the mechanism Home Assistant's own Energy Dashboard date picker uses
(`recorder/statistics_during_period`).

The cycle meters were therefore solving the *convenience* problem ("today so
far") while the *core* problem was already solved, for free, by data the
integration was emitting anyway.

## Decision

**1. Long-term statistics are the substrate for period accounting.** Any
arbitrary-range question — per device, per set of devices, per room or floor —
is answered by reading `sum`/`change` between two timestamps over HEA's own
lifetime sensors. Period savings derives by subtraction of Cost Without Solar
and Actual Cost over the same range. This requires no helper entities and no
new storage: the capability exists today.

Accepted limitation: beyond the recorder's retention window HA keeps **hourly**
statistics, not 5-minute. Sub-hourly resolution for old periods is therefore not
available. This was weighed and accepted — the value of resolving a half-hour
window from a year ago is negligible against the cost of retaining it.

**2. `utility_meter` cycle helpers are a day-to-day convenience, not the
mechanism for the promise.** They remain, unchanged, for what statistics cannot
give: a *live* entity carrying the current cycle's value, which automations,
templates, and the entity-driven core cards (`tile`, `gauge`, `distribution`)
require. The metered set stays as ADR-0007 fixed it — `energy_used`,
`actual_cost`, `cost_without_solar` × daily and monthly by default.

**3. The per-device energy-by-source sensors (HEA-51) are never cycle-metered.**
Their per-period figures are a chart question, answered from statistics. Metering
them would add ~90 helpers on a 14-device home for no capability that the
statistics path does not already provide. This is firm.

**4. Home Energy Advisor ships its own Lovelace card**, served by the integration
itself (static path + Lovelace resource registration) rather than requiring a
HACS install. Core cards cannot express the product's central view: `statistic`
takes a fixed period, `statistics-graph` a fixed window, and the `energy` card is
hardwired to HA's own energy collections. None accept a user-driven date range
with a device filter.

> **Amended by ADR-0017.** The conclusion stands — re-examined there, and no
> community card accepts an arbitrary date range × device filter over our own
> statistics either. The *reasoning* does not: this decision assessed core cards
> only, and excluded community ones by a premise it never argued ("must not
> require a separate install"). ADR-0012 and ADR-0013 then cited that premise as
> settled law. A separate install is a cost to weigh, not a disqualifier, and
> rejecting an existing component now needs a reason of its own.

### Rejected alternatives

- **Reduce the metered concept set** (drop Cost Without Solar cycles): rejected —
  period savings is derived as Cost Without Solar − Actual Cost across the two
  cycle meters (ADR-0007), so cutting it removes the derivation as well.
- **Monthly-only cycles**: rejected — "what did this cost today" is a PRD success
  criterion, and statistics lag up to an hour for today-so-far.
- **Per-device opt-in metering**: rejected for now — it adds config-flow
  complexity and makes the dashboard's device list conditional, to solve a
  symptom (recorder load) that publish-precision addresses more directly.
- **Storing period figures in HEA's own structures**: rejected — it would
  duplicate what the recorder already keeps correctly and permanently, and make
  HEA responsible for statistics surgery on every config change. The same
  reasoning that deferred historical backfill (PLAN.md, Epic 7).

## Consequences

- The central product capability — arbitrary date range × device filter × cost /
  would-have-cost / saved — becomes **frontend work**, not backend. HEA-50 is
  promoted from optional polish to the flagship deliverable; HEA-25's core-cards
  dashboard is explicitly the secondary, day-to-day convenience layer.
- Once that card can render preset ranges (today / week / month / year — the same
  code path as an arbitrary range), the cycle meters' remaining justification
  narrows to automations and non-card consumers. **Revisit making them opt-in,
  default off, at that point** (HEA-40 stays closed until then; reopening is the
  trigger below).
- Roll-ups by room, floor, or label depend on the **device registry**, which
  statistics do not carry — and HEA currently assigns no area to the devices it
  creates, so every HEA device is unattached. Inheriting the source sensor's
  device area is tracked separately and gates every hierarchy view.
- Publishing full `Decimal` precision to the recorder (28 significant digits per
  state, ~1/min, mirrored by each cycle meter) is a materially larger recorder
  cost than the entity count, and contradicts the project's own "round only at
  presentation" rule. Tracked separately.
- **Revisit this decision if** Home Assistant changes long-term statistics
  retention or granularity, if the statistics API stops serving arbitrary ranges
  cheaply at scale, or if shipping a card from the integration proves
  incompatible with HACS distribution or hassfest validation.
