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

export const TUMBLE_DRYER_BUCKETS = bucketsFor("tumble_dryer_switch", 38.6, 0.11, 5.78);

/**
 * The `hass` object a card is handed. The collection is cached at `_` + the
 * collection key, which is how Home Assistant does it (verified live).
 */
export const aHass = ({
  collection = anEnergyCollection(),
  devices = [aDeviceRow("tumble_dryer_switch", "Tumble Dryer Switch")],
  response = TUMBLE_DRYER_BUCKETS,
  callWS,
} = {}) => ({
  connection: collection ? { "_energy_hea-costs": collection } : {},
  states: devices
    ? { [DEVICES_SENSOR]: { state: String(devices.length), attributes: { devices } } }
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
