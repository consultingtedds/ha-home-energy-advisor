# Device Sensor Survey — Paul's HA Instance (2026-07-11)

> Survey of every `device_class: energy` / `device_class: power` sensor on
> homeassistant.tedds.net, to ground the product's device-source model in real
> hardware diversity. Follows the scope clarification that Home Energy Advisor
> tracks **any device sharing power/energy data**, not just the aircons.

## Trackable devices found (per-device sensors)

| Device | Integration | Sensors | Behaviour pattern |
|---|---|---|---|
| 9× Aircon units | `mitsubishi_wf_rac` (local) | energy only (kWh, `total_increasing`) | **Cycle-resetting cumulative**: 0.25 kWh steps, resets to 0 each compressor cycle, updates 15 min–hours apart. No power sensor. |
| Pool pump switch | Zigbee2MQTT (`mqtt`) | power (W, `measurement`) + energy (kWh, `total_increasing`, lifetime 3 377 kWh) | **Lifetime cumulative + live power**: monotonic energy counter, resets only on device reset; power updates near-real-time. |
| Guest bathroom water heater | Zigbee2MQTT (`mqtt`) | power + energy (lifetime) | Same as pool pump. |
| Pool house water heater | Zigbee2MQTT (`mqtt`) | power + energy (lifetime) | Same as pool pump. |
| Well pump switch | `tuya` + `xtend_tuya` (cloud) | power + `total_energy` (lifetime) + daily/monthly/yearly `consumption` | **Cloud-polled cumulative**: lifetime counter plus device-side **period-resetting** counters (daily resets at midnight). Update cadence at the mercy of Tuya cloud polling. |
| Master bathroom towel rail | `rointe` (cloud) | `energy` (`total_increasing`, currently **unknown**) + `effective_power` (W, duty-cycle derived) + `nominal_power` (static 300 W, no state_class) | **Unreliable energy + synthetic power**: energy sensor not currently reporting; effective power is computed (nominal × duty), not measured. |
| Living room wall lights | `wiz` (local) | power only (W, `measurement`, currently unknown while off/unreachable) | **Power-only**: no energy counter at all — energy must be derived by integrating power over time. |

## House-level sensors (product inputs, not tracked devices)

- **Huawei Solar** (`huawei_solar`, local Modbus): grid meter (`power_meter_consumption`/`_exported`, lifetime kWh + `power_meter_active_power` W), inverter yields, battery charge/discharge — both `total_increasing` and `total` variants exist.
- **Derived helpers**: large families of `utility_meter`/Riemann-integral helpers (`hourly_*`/`daily_*`/…`_energy`, `hsem_*`) built on the Huawei sensors — `total` state_class, periodic resets.
- **Forecasts** (Solcast, Predbat): carry energy/power device classes but are predictions, not measurements.
- `sensor.electricity_price_import` — `template` sensor (no device_class), resolves TOU windows to a current EUR/kWh value.
- `sensor.inverter_power_less_consumption` — W, `measurement`; the chosen gating signal.

## False friends (why entity selection must be user-curated)

`device_class: power` alone is not sufficient to identify a trackable device:
`sensor.garmin_connect_ftp_cycling` (cycling FTP in watts) and three phone
`_battery_power` sensors all match. The config flow should filter selectors by
device_class + state_class + unit, but the user always chooses explicitly —
never auto-onboard.

## Behaviour taxonomy → engine requirements

1. **Lifetime cumulative energy** (`total_increasing`, rare resets) — Zigbee plugs, Tuya total, Huawei meters. Baseline case.
2. **Resetting cumulative energy** (`total_increasing`, frequent resets) — WF-RAC per-cycle, Tuya daily counters. Covered by the validated reset rule (`new < prev` → delta = `new`).
3. **Power-only devices** (W, `measurement`) — WiZ lights, Rointe effective power. Require power→energy integration (time-weighted Riemann sum) in the engine before costing.
4. **`total` state_class** (net counters, may decrease; `last_reset` semantics) — mostly house-level here; out of MVP for device tracking until a real device needs it.
5. **Unreliable sources** — towel rail energy `unknown`, WiZ unavailable when off. Engine must treat unavailable spans as "no data" (no phantom deltas); Repairs should flag persistently dead sources.

Consequence: the engine needs an **EnergySource abstraction** with two MVP
implementations — `CumulativeEnergySource` (patterns 1–2) and
`PowerIntegratingSource` (pattern 3) — chosen per device in the config flow
based on which sensor the user selects. Devices with both (Zigbee plugs)
default to the energy counter (measured by the device, no integration error),
with power available to later improve gating fidelity.

## Long-term statistics (retention question)

Confirmed on this instance: any sensor with a `state_class` is aggregated into
long-term statistics (hourly, retained indefinitely; 5-minute short-term kept
~10 days alongside raw history). Verified back 13+ months for
`pool_pump_switch_energy` (sum), `electricity_price_import` (mean), and
`inverter_power_less_consumption` (mean).

So: only **raw full-resolution history** expires at 10 days. Hourly-resolution
fixtures for golden-master tests can be regenerated from statistics at any
time; raw-resolution fixtures (the exact 0.25 kWh event sequence) must be
captured before the window closes. Backfill (Epic 7) is bounded only by each
sensor's statistics start date, which is over a year for the key inputs.
