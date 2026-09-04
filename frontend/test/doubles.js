/**
 * Stand-ins for the parts of Home Assistant a card talks to, shared by every
 * card suite so the harness is written - and corrected - once.
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
    /**
     * Announce a new period, optionally with a comparison window.
     *
     * Home Assistant hands subscribers an `EnergyData` object, and the compare
     * window lives *only* there - the collection itself carries the compare
     * mode but not its dates. So the payload is passed through, and a double
     * that called back with nothing could never tell the two apart (HEA-96).
     */
    announce(newStart, newEnd, compare = undefined) {
      this.start = newStart;
      this.end = newEnd;
      const data = { start: newStart, end: newEnd, ...compare };
      for (const callback of listeners) callback(data);
    },
    get listenerCount() {
      return listeners.size;
    },
  };
};

/** A row as the HEA-55 devices sensor publishes it. */
/** Every concept the devices sensor publishes an entity id for. */
export const STAT_CONCEPTS = [
  "energy_used",
  "actual_cost",
  "cost_at_grid_price",
  "cost_savings",
  "energy_from_grid",
  "energy_from_generation",
  "energy_from_battery",
  "lowest_possible_cost",
  "highest_possible_cost",
];

/**
 * A row as `sensor.home_energy_advisor_devices` publishes it.
 *
 * `statistics` defaults to the ids an English instance happens to produce, which
 * is what the other doubles here key off. Pass it explicitly to build a row whose
 * ids do *not* follow that pattern - a Spanish instance, or a renamed entity -
 * which is the only way a test can tell reading the map apart from composing the
 * id, since composing gives the right answer on every English install (HEA-89).
 */
export const aDeviceRow = (key, name, untracked = false, statistics = undefined) => ({
  key,
  name,
  device_id: `device-${key}`,
  untracked,
  statistics:
    statistics ??
    Object.fromEntries(
      STAT_CONCEPTS.map((concept) => [concept, `sensor.${key}_${concept}`]),
    ),
});

/**
 * A device row filed into an area, a floor, both or neither (HEA-58).
 *
 * Ids are deliberately nothing like their names. A double that derived
 * `area_id` from `area_name` could not tell code reading the id apart from code
 * reading the name, and would agree with either - the fixture has to be able to
 * disagree.
 *
 * Both halves are optional because both are really absent on the reference
 * instance: one tracked device sits in no area at all, and four sit in areas
 * belonging to no floor.
 */
export const placed = (
  row,
  { areaId = null, areaName = null, floorId = null, floorName = null } = {},
) => ({
  ...row,
  area_id: areaId,
  area_name: areaName,
  floor_id: floorId,
  floor_name: floorName,
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
 * The cost range a key's counter permits (ADR-0016) - absent for a household
 * that has not opted into per-device ranges, which is the case a card has to
 * tell apart from a range of zero.
 *
 * The suffixes are the entity ids as they exist on a real instance, verified
 * against the reference instance 2026-08-14. They are written out rather than built
 * from the card's own `BOUNDS`, so this fixture can disagree with the card - and
 * it once should have: HEA-84 shipped `_cost_floor` on both sides against a
 * sensor Home Assistant had really named `_lowest_possible_cost`.
 */
export const boundsFor = (key, costFloor, costCeiling, at = MAY) => ({
  [`sensor.${key}_lowest_possible_cost`]: [
    { start: at.getTime(), change: costFloor },
  ],
  [`sensor.${key}_highest_possible_cost`]: [
    { start: at.getTime(), change: costCeiling },
  ],
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
  // What each label is called, keyed by id - published beside the rows because
  // a name belongs to the label rather than to each device wearing it.
  labels,
  callWS,
} = {}) => ({
  connection: collection ? { "_energy_hea-costs": collection } : {},
  states: devices
    ? {
        [DEVICES_SENSOR]: {
          state: String(devices.length),
          attributes: {
            devices,
            whole_home: wholeHome ?? undefined,
            labels: labels ?? undefined,
          },
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
