# ADR-0004: EnergySource taxonomy and native-helper reuse

## Status

Accepted

## Context

The product tracks *any* device that shares power or energy data, not just the
aircons that motivated it. A survey of every `device_class: energy` and
`device_class: power` sensor on the reference instance
(`docs/notes/DEVICE_SENSOR_SURVEY.md`) found five distinct behaviour patterns
across real hardware — cycle-resetting counters, lifetime counters, cloud-polled
counters, power-only sensors, and unreliable/synthetic sensors — plus "false
friend" sensors that carry an energy/power `device_class` but are not trackable
loads at all (a cycling power meter reporting rider watts; phone battery-power
sensors).

The engine (ADR-0002) consumes energy *deltas*. This ADR records how the varied
real-world sensors are normalised into those deltas, and the standing decision to
build on Home Assistant's own machinery rather than reimplement it.

## Decision

### The EnergySource abstraction

Device sources are normalised behind an `EnergySource` abstraction before they
reach the accounting engine. The MVP ships two implementations:

1. **`CumulativeEnergySource`** — for `total_increasing` counters, covering both
   the *lifetime* pattern (Zigbee plugs, Tuya totals, Huawei meters; monotonic,
   rare resets) and the *resetting* pattern (WF-RAC per-cycle counters, Tuya
   daily counters; frequent resets). One rule handles both: `delta = new − prev`,
   except a fall (`new < prev`) is a reset whose new value is a fresh cycle's
   energy; `unavailable`/`unknown` are skipped. Implemented and validated in
   HEA-16.

2. **Power-only devices** (WiZ lights, Rointe effective power) are supported by
   **programmatically creating a native Integral (Riemann-sum) helper** on the
   selected power sensor; its output energy sensor then feeds the *same*
   `CumulativeEnergySource` pipeline. No power→energy integration is
   reimplemented in the engine (HEA-34).

A device that exposes **both** power and energy (the Zigbee plugs) defaults to
its **energy** counter: it is device-measured and carries no integration error,
with the power sensor left available to improve gating fidelity later.

### Build on native foundations, don't reimplement

Wherever Home Assistant already provides the mechanism, the integration
auto-creates the native helper rather than re-implementing it:

- **Power → energy**: native **Integral** helper (above).
- **Cycle totals** (daily / monthly …): native **`utility_meter`** helpers over
  the lifetime cost/energy sensors (HEA-23), not hand-rolled reset logic.

This is proven in the wild (PowerCalc creates helpers programmatically) but is
not a first-party, guaranteed-stable API. **Fallback:** if programmatic helper
creation proves unreliable, the integration implements the equivalent maths
internally (Riemann sum; period reset). The trigger to switch is a helper-creation
feasibility spike failing early in Epic 4, or helpers proving fragile in
dogfooding (renamed/deleted out from under us faster than Repairs can cope).

### Out of MVP scope

- **`total` state_class net counters** (values that may decrease; `last_reset`
  semantics) — mostly house-level on this instance; deferred for *device*
  tracking until a real device needs it.
- **Forecast sensors** (Solcast, Predbat) — carry energy/power `device_class` but
  are predictions, not measurements.
- **False friends** — a `device_class` alone never onboards a device. The config
  flow filters selectors by `device_class` + `state_class` + unit, but the user
  always chooses explicitly; auto-onboarding by `device_class` is forbidden
  (`CRITICAL_INSTRUCTIONS.md`).
- **Unreliable sources** — persistently `unknown`/`unavailable` sensors (the
  towel-rail energy) are treated as no-data, never phantom deltas, and a
  persistently dead source raises a Repair (HEA-24).

## Consequences

- The engine stays free of unit and integration concerns: units are normalised at
  the `EnergySource` boundary (HEA-16 handles Wh vs kWh), and power integration is
  the native helper's job, so the accounting code speaks only in kWh deltas.
- Epic 4 must prove programmatic helper creation early (HEA-34 for Integral,
  HEA-23 for utility_meter); the internal-implementation fallback is the safety
  net.
- Adding a new device behaviour later (e.g. a `total` net counter) means a new
  `EnergySource` implementation, not a change to the engine or the strategy.
- Explicit, user-curated device selection keeps false friends out and is a
  deliberate usability cost (no "add all energy sensors" button) paid for
  correctness.
- Revisit if: a supported device genuinely needs `total` state_class, or the
  native-helper approach proves too fragile and the internal fallback becomes the
  default.

## Update — feasibility validated (2026-07-21)

Appended, not edited: the decision above stands and its Status remains Accepted.
This note records that the programmatic native-helper path it chose is **proven**,
not merely assumed.

HEA-34 shipped auto-creation of a native Integral (Riemann-sum) helper for
power-only devices — driving the `integration` component's own config flow — with
its output energy sensor feeding the `CumulativeEnergySource` pipeline unchanged.
Verified against real Home Assistant: creation is programmatic and idempotent, and
the helper accrues **no phantom energy across an `unavailable` span** — a device
switched off for months resumes cleanly on recovery. So the reset-on-unavailable
behaviour this ADR requires is inherited from the native helper rather than
reimplemented.

Consequences for the recorded fallback:

- The internal-implementation fallback (Riemann sum in the engine) was **not
  needed** for the Integral path and stays unused.
- HEA-23 (native `utility_meter` cycle helpers) shares this feasibility spike, so
  its native path is de-risked by the same result; reuse the HEA-34 pattern
  (`custom_components/home_energy_advisor/integral_helper.py`).
- The helper's component must be declared in the manifest `dependencies` —
  hassfest enforces this whenever the code imports from that component.
