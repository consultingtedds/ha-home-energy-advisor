# Aircon Cost Exploration — Session Notes (2026-07-11)

> Working notes from an ad-hoc exploration session. Nothing described here was built —
> no Home Assistant config, helpers, or entities were created. This is a manual, one-off
> validation of the MVP accounting model (see `PRD.md` → Minimum Viable Product,
> `IMPLEMENTATION_IDEAS.md` → Device Cost Model) against real data from Paul's HA instance.

## Why this happened

Started as a simple question — "what does my Guest Bedroom Aircon actually cost to run?" —
and turned into a hand-computed proof of the exact concepts the PRD defines for the MVP:
**Energy Used**, **Cost Without Solar** ("naive cost" below), **Actual Cost**, and
**Solar Saving** (the delta between the two). Doing this manually against live HA history
was useful evidence that the accounting model is sound before building it as a real
integration.

## Home Assistant instance context

- HA 2026.7.1, `https://homeassistant.tedds.net`, Europe/Madrid.
- Solar + battery system: Huawei Solar inverter, managed by **Predbat** (battery
  charge/discharge scheduling AppDaemon-style integration).
- Existing house convention for "run this on solar surplus": a reusable blueprint
  `codex/solar-powered-device.yaml`, used by automations like
  `automation.guest_bedroom_hvac_solar`. It already gates on
  `sensor.inverter_power_less_consumption` (solar power minus house consumption, in W;
  positive = surplus, negative = deficit) plus battery SoC. This is the established
  "are we running on solar" signal in this house — reused it rather than inventing a new one.

## Key entities

| Purpose | Entity | Notes |
|---|---|---|
| Per-device energy | `sensor.<room>_aircon_energy_usage_cycle` | Mitsubishi WF-RAC integration. `device_class: energy`, `state_class: total_increasing`. Updates in coarse 0.25 kWh steps, resets to 0 per compressor cycle. No instantaneous power sensor exists on these units. |
| Live import price | `sensor.electricity_price_import` | EUR/kWh, already resolves peak/standard/off-peak windows into one current value. Observed pattern: 00:00–08:00 €0.093, 08:00–10:00 & 14:00–18:00 & 22:00–24:00 €0.152, 10:00–14:00 & 18:00–22:00 €0.234 (repeats daily). |
| Solar vs. consumption gate (chosen) | `sensor.inverter_power_less_consumption` | W. Negative = house consuming more than solar generates → "actual cost" applies. Same sensor the house's existing solar-HVAC automations use. |
| Alternative gate (not used) | `predbat.grid_power` | True grid import/export (kW), positive = importing. More accurate for "money actually leaving your account" since it accounts for the battery covering a solar shortfall — but doesn't match how Paul framed the question ("using more than solar generates"), so parked for later. |

**Decision made:** gate on solar-vs-consumption (`inverter_power_less_consumption < 0`),
not true grid import. Worth revisiting if the product wants strict bill-accuracy rather
than "was this solar-covered."

## Methodology used for the manual calculation

No HA helpers were created — this was done by pulling history/statistics via the HA MCP
tools and computing in a Python script (Bash tool), asc-ordered:

1. Pull raw `history` for each aircon's `_energy_usage_cycle` sensor (10-day retention).
2. Walk the state sequence chronologically; for each transition, delta = `new − prev`,
   except when `new < prev` (a cycle reset) in which case delta = `new` (treat as a fresh
   cycle start rather than a negative delta). `unavailable`/`unknown` states are skipped.
3. For each delta event, look up:
   - the import price active at that timestamp (step function above), and
   - the hourly **mean** of `inverter_power_less_consumption` for that hour (pulled via
     `ha_get_history(source="statistics", period="hour")`, since raw history for a
     fast-changing power sensor over 7 days is too large to pull as raw state history).
4. `naive_cost = delta_kWh × price`. `gated_cost = naive_cost if hourly_mean < 0 else 0`.
5. Sum per device / per day.

**Known limitation:** gating on an hourly *average* is an approximation — it assumes the
solar/deficit state was constant across the hour, and the underlying energy sensor itself
only reports in 0.25 kWh jumps every 15 min–few hours, so this is "rough snapshot"
accuracy, not billing-grade. Good enough for validating the concept; a real
implementation would ideally have finer-grained power sensors per device, which don't
currently exist for these Mitsubishi WF-RAC units.

## Results

### Guest Bedroom Aircon, day-by-day (Jul 8–11)

| Day | Energy used | Cost ignoring solar | Actual cost (solar-gated) |
|---|---|---|---|
| Jul 8 | 3.25 kWh | €0.58 | €0.58 |
| Jul 9 | 3.25 kWh | €0.52 | €0.31 |
| Jul 10 | 2.75 kWh | €0.41 | €0.19 |
| Jul 11 (partial) | 1.75 kWh | €0.16 | €0.16 |
| **Total** | **11.0 kWh** | **€1.67** | **€1.25** |

### All 9 aircon units, last 7 days (some units have less than a full week of real cycling)

| Aircon | Energy used | Cost ignoring solar | Actual cost (solar-gated) |
|---|---|---|---|
| Living Room | 22.00 kWh | €4.78 | €1.93 |
| Tommy's Bedroom | 20.25 kWh | €3.01 | €1.41 |
| Master Bedroom | 16.25 kWh | €2.87 | €0.82 |
| Becky's Office | 10.75 kWh | €2.23 | €0.00 |
| Kitchen | 9.75 kWh | €2.10 | €1.30 |
| Guest Bedroom | 11.00 kWh | €1.67 | €1.25 |
| Izzy's Bedroom | 10.00 kWh | €1.16 | €0.86 |
| Games Room | 5.25 kWh | €1.04 | €0.06 |
| Paul's Office | 2.50 kWh | €0.44 | €0.00 |
| **Total** | **107.75 kWh** | **€19.30** | **€7.63** |

Roughly 60% of aircon energy this week fell in solar-deficit hours — actual cost is
~40% of the naive figure. Becky's and Paul's offices happened to run entirely during
solar surplus (€0 gated cost); Kitchen and Guest Bedroom skew the other way.

## Backfill capability (confirmed, not yet used)

- `recorder.import_statistics` (native HA service) can inject historical values into a
  new sensor's **long-term statistics** table — the same mechanism integrations use to
  backfill on first setup. It doesn't rewrite raw state history, but long-term stats are
  what drive the Energy Dashboard / History graphs / Statistics cards, which is what
  matters for a running-cost total.
- Confirmed `sensor.guest_bedroom_aircon_energy_usage_cycle` already has long-term `sum`
  statistics going back to at least mid-April 2026 (90+ days), and they correctly handle
  the cycle resets. So a real cost sensor could be backfilled much further than the
  10-day raw-history window used for the tables above — bounded by how far back the
  price and solar sensors' own statistics extend (not yet checked).

## Proposed live-sensor design (discussed, not built)

1. A trigger-based **Template Helper** sensor (via HA config flow / UI, not YAML),
   triggered on state changes of the per-device `_energy_usage_cycle` sensor. Computes
   the delta (handling resets as above), multiplies by `sensor.electricity_price_import`,
   accumulates into its own state (`device_class: monetary`, `state_class:
   total_increasing`). This is a legitimate template-helper use case per HA best
   practices — no dedicated helper does "priced delta accumulation," so it's the
   documented escape hatch, not an anti-pattern.
2. A `utility_meter` helper on top for clean daily/monthly resets ("cost today", "cost
   this month") instead of hand-rolling reset logic.
3. Same trigger template, extended: only add to the running total when
   `inverter_power_less_consumption < 0` at the moment of the update, for the "actual
   cost" variant. Would produce both a "naive" and "actual" cost entity side by side —
   directly matching the PRD's `Cost Without Solar` / `Actual Cost` pair.
4. Backfill via `recorder.import_statistics` once the live sensor exists, using the same
   calculation approach as this session but sourced from long-term statistics instead of
   raw history (to reach further back than 10 days).

## Open questions / not decided

- Scope: build this for all 9 aircon units, or prototype on Guest Bedroom only first?
- Does this become a real HA integration (per `IMPLEMENTATION_IDEAS.md` → "Native Home
  Assistant Integration" preference), or stay as manually-created Template Helpers per
  device for now? The manual approach doesn't scale well to "every measurable device"
  from the PRD — probably validates the need for the real integration.
- Entity/attribute naming still undecided per `IMPLEMENTATION_IDEAS.md` (`Actual Cost`,
  `Cost Without Solar`, `Solar Saving`, `Energy Used` are the candidate concepts, not
  final names).
- Gating definition: solar-vs-consumption (used here) vs. true grid import
  (`predbat.grid_power`) — may want both as configurable strategies eventually (ties into
  the "Cost Allocation" open question in `IMPLEMENTATION_IDEAS.md`).
- No decision yet on whether/how to handle devices without per-device energy sensors
  (most of the Mitsubishi WF-RAC units only expose the coarse cycle-energy sensor, no
  instantaneous power).
