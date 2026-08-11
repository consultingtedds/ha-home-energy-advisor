# Device Sensor Survey — behaviour patterns (2026-07-11)

> Survey of every `device_class: energy` / `device_class: power` sensor on the
> reference instance, to ground the product's device-source model in real
> hardware diversity. Follows the scope clarification that Home Energy Advisor
> tracks **any device sharing power/energy data**, not just air conditioning.
>
> The per-device inventory is deliberately not reproduced: it is a room-by-room
> map of a private home, and what the project actually needs is the *shape* of
> each source's behaviour. Patterns are described by the integration that
> produces them, which is what determines how the engine must treat them.

## Source behaviour patterns found

| Pattern | Seen from | Sensors | Behaviour |
|---|---|---|---|
| **Cycle-resetting cumulative** | a local air-conditioning integration (a local integration) | energy only (kWh, `total_increasing`) | 0.25 kWh steps, resets to 0 each compressor cycle, updates 15 min–hours apart. No power sensor at all. |
| **Lifetime cumulative + live power** | Zigbee plugs over Zigbee2MQTT (`mqtt`) | power (W, `measurement`) + energy (kWh, `total_increasing`) | Monotonic counter climbing for years, resets only on a device reset; power updates near-real-time. |
| **Cloud-polled cumulative** | a cloud metering plug (`tuya` + `xtend_tuya`) | power + a lifetime `total_energy` + device-side daily/monthly/yearly `consumption` | Lifetime counter plus **period-resetting** counters (daily rolls at midnight). Update cadence is at the mercy of cloud polling — tens of minutes between readings. |
| **Unreliable energy + synthetic power** | a cloud heating integration  | `energy` (`total_increasing`, often `unknown`) + an `effective_power` derived from duty cycle, plus a static nominal wattage with no `state_class` | The energy sensor frequently does not report; the power figure is *computed*, not measured. |
| **Power-only** | local smart lighting | power only (W, `measurement`, `unknown` while off or unreachable) | No energy counter at all — energy must be derived by integrating power over time. |

## House-level sensors (product inputs, not tracked devices)

- **Solar inverter with battery** (local Modbus): grid meter (lifetime kWh plus
  instantaneous W), inverter yields, battery charge/discharge — both
  `total_increasing` and `total` variants exist.
- **Derived helpers**: large families of `utility_meter` / Riemann-integral
  helpers built on the inverter sensors — `total` state_class, periodic resets.
- **Forecasts** (solar forecasting, battery scheduling): these carry energy and
  power device classes but are *predictions*, not measurements.
- A `template` price sensor (no device_class) resolving TOU windows to a current
  currency/kWh value.

## False friends (why entity selection must be user-curated)

`device_class: power` alone is not sufficient to identify a trackable device. On
the surveyed instance the matches included a **cycling FTP sensor from a fitness
integration** (a training threshold, in watts) and several phone
`_battery_power` sensors. The config flow should filter selectors by
device_class + state_class + unit, but the user always chooses explicitly —
never auto-onboard.

## Behaviour taxonomy → engine requirements

1. **Lifetime cumulative energy** (`total_increasing`, rare resets) — Zigbee
   plugs, cloud plug totals, grid meters. Baseline case.
2. **Resetting cumulative energy** (`total_increasing`, frequent resets) —
   per-compressor-cycle counters, cloud daily counters. Covered by the validated
   reset rule (`new < prev` → delta = `new`).
3. **Power-only devices** (W, `measurement`) — smart lighting, duty-cycle
   heating. Require power→energy integration (time-weighted Riemann sum) in the
   engine before costing.
4. **`total` state_class** (net counters, may decrease; `last_reset` semantics) —
   mostly house-level here; out of MVP for device tracking until a real device
   needs it.
5. **Unreliable sources** — energy sensors reporting `unknown`, power sensors
   unavailable when the device is off. The engine must treat unavailable spans as
   "no data" (no phantom deltas); Repairs should flag persistently dead sources.

Consequence: the engine needs an **EnergySource abstraction** with two MVP
implementations — `CumulativeEnergySource` (patterns 1–2) and
`PowerIntegratingSource` (pattern 3) — chosen per device in the config flow
based on which sensor the user selects. Devices exposing both (Zigbee plugs)
default to the energy counter (measured by the device, no integration error),
with power available to later improve gating fidelity.

## Long-term statistics (retention question)

Confirmed on this instance: any sensor with a `state_class` is aggregated into
long-term statistics (hourly, retained indefinitely; 5-minute short-term kept
~10 days alongside raw history). Verified back 13+ months for a plug's lifetime
energy (`sum`), the price sensor (`mean`), and a house-level power signal
(`mean`).

So: only **raw full-resolution history** expires at 10 days. Hourly-resolution
fixtures for golden-master tests can be regenerated from statistics at any time;
raw-resolution fixtures (the exact 0.25 kWh event sequence) must be captured
before the window closes. Backfill (Epic 7) is bounded only by each sensor's
statistics start date, which is over a year for the key inputs.
