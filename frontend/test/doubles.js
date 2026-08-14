/**
 * Stand-ins for the parts of Home Assistant a card talks to, shared by every
 * card suite so the harness is written — and corrected — once.
 *
 * Each double mirrors something measured on the live instance rather than
 * imagined: the energy collection as the picker creates it, the HEA-55 device
 * rows in their own snake_case, and the recorder's bucket shape.
 */

import { vi } from "vitest";

import { DEVICES_SENSOR } from "../hea-devices.js";

export const MAY = new Date(2026, 4, 20);
export const JULY = new Date(2026, 6, 15);

/** A stand-in for Home Assistant's energy collection, as the picker creates it. */
export const anEnergyCollection = (start = MAY, end = JULY) => {
  const listeners = new Set();
  return {
    start,
    end,
    subscribe(callback) {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    announce(newStart, newEnd) {
      this.start = newStart;
      this.end = newEnd;
      for (const callback of listeners) callback();
    },
    get listenerCount() {
      return listeners.size;
    },
  };
};

/** A row as the HEA-55 devices sensor publishes it. */
export const aDeviceRow = (key, name, untracked = false) => ({
  key,
  name,
  device_id: `device-${key}`,
  untracked,
});

/** One day's worth of buckets for a device, dated inside the picked period. */
export const bucketsFor = (
  key,
  energyUsed,
  actualCost,
  costAtGridPrice,
  at = MAY,
) => ({
  [`sensor.${key}_energy_used`]: [{ start: at.getTime(), change: energyUsed }],
  [`sensor.${key}_actual_cost`]: [{ start: at.getTime(), change: actualCost }],
  [`sensor.${key}_cost_at_grid_price`]: [
    { start: at.getTime(), change: costAtGridPrice },
  ],
});

export const AIRCON_BUCKETS = bucketsFor("slow_poll_aircon", 38.6, 0.11, 5.78);

/**
 * The cost range a key's counter permits (ADR-0016) — absent for a household
 * that has not opted into per-device ranges, which is the case a card has to
 * tell apart from a range of zero.
 */
export const boundsFor = (key, costFloor, costCeiling, at = MAY) => ({
  [`sensor.${key}_cost_floor`]: [{ start: at.getTime(), change: costFloor }],
  [`sensor.${key}_cost_ceiling`]: [{ start: at.getTime(), change: costCeiling }],
});

/** The grid / generation / battery split a device's HEA-51 sensors record. */
export const sourcesFor = (key, grid, generation, battery, at = MAY) => ({
  [`sensor.${key}_energy_from_grid`]: [{ start: at.getTime(), change: grid }],
  [`sensor.${key}_energy_from_generation`]: [
    { start: at.getTime(), change: generation },
  ],
  [`sensor.${key}_energy_from_battery`]: [
    { start: at.getTime(), change: battery },
  ],
});

/**
 * The `hass` object a card is handed. The collection is cached at `_` + the
 * collection key, which is how Home Assistant does it (verified live).
 */
export const aHass = ({
  collection = anEnergyCollection(),
  devices = [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")],
  response = AIRCON_BUCKETS,
  // The whole-home aggregate rides the same sensor, beside the device list
  // rather than in it: cards sum that list, so a row there would double every
  // figure. Present on any current integration.
  wholeHome = aDeviceRow("whole_home", "Whole Home"),
  callWS,
} = {}) => ({
  connection: collection ? { "_energy_hea-costs": collection } : {},
  states: devices
    ? {
        [DEVICES_SENSOR]: {
          state: String(devices.length),
          attributes: { devices, whole_home: wholeHome ?? undefined },
        },
      }
    : {},
  config: { currency: "EUR" },
  locale: { language: "en-GB" },
  callWS: callWS ?? vi.fn().mockResolvedValue(response),
});

export const text = (card) => card.shadowRoot.textContent;

export const stateOf = (card) =>
  card.shadowRoot.querySelector("[data-state]").dataset.state;

/** Put a configured card on the page, as Home Assistant would. */
export const mountCard = (tag, hass, config = {}) => {
  const card = document.createElement(tag);
  card.setConfig({ type: `custom:${tag}`, collection_key: "energy_hea-costs", ...config });
  document.body.append(card);
  card.hass = hass;
  return card;
};

/** Wait for a card to settle on a state. */
export const settled = (expect, card, state = "ready") =>
  vi.waitFor(() => expect(stateOf(card)).toBe(state));
