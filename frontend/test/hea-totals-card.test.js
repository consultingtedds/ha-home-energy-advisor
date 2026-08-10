/**
 * @vitest-environment happy-dom
 *
 * The first card on the data layer (HEA-50): what the period actually cost,
 * what it would have cost at grid price, and the difference.
 *
 * The element's lifecycle is where card bugs live — a subscription left behind
 * on a removed card, a stale response overwriting a newer one, a dashboard
 * placed before the integration is set up — so it is exercised here as a real
 * DOM element rather than through a view-model standing in for one.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { TAG, register } from "../hea-totals-card.js";
import {
  AIRCON_BUCKETS,
  aDeviceRow,
  aHass,
  anEnergyCollection,
  bucketsFor,
  mountCard,
  settled as settledOn,
  stateOf,
  text,
} from "./doubles.js";

const figure = (card, name) =>
  card.shadowRoot.querySelector(`[data-figure="${name}"]`);

const mount = (hass, config = {}) => mountCard(TAG, hass, config);

/** Wait for the card to settle on something other than its first paint. */
const settled = (card, state = "ready") => settledOn(expect, card, state);

beforeEach(() => {
  document.body.replaceChildren();
});

describe("registration", () => {
  it("is registered as a custom element", () => {
    // Given / When / Then
    expect(customElements.get(TAG)).toBeDefined();
  });

  it("survives the resource being added to a dashboard twice", () => {
    // Given — a user who lists the same resource url twice; a second
    // `customElements.define` throws and takes the whole dashboard with it
    // When / Then
    expect(() => register()).not.toThrow();
  });

  it("offers itself in the card picker", () => {
    // Given / When / Then
    expect(globalThis.customCards).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: TAG })]),
    );
  });
});

describe("configuration", () => {
  it("rejects a device filter that is not a list", () => {
    // Given — a hand-edited dashboard yaml
    const card = document.createElement(TAG);

    // When / Then — Home Assistant shows the thrown message in the card editor
    expect(() => card.setConfig({ type: `custom:${TAG}`, devices: "kitchen_aircon" })).toThrow(
      /devices/,
    );
  });

  it("takes a title when one is configured", () => {
    // Given / When
    const card = mount(aHass(), { title: "Running costs" });

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "Running costs",
    );
  });

  it("has a card size, so it lays out in a masonry view", () => {
    // Given / When / Then
    expect(mount(aHass()).getCardSize()).toBe(3);
  });
});

describe("the figures", () => {
  it("shows what the period cost, what it would have cost, and the difference", async () => {
    // Given
    const card = mount(aHass());

    // When
    await settled(card);

    // Then — Saved is the difference, so the three always reconcile on screen
    expect(figure(card, "actualCost").textContent).toMatch(/0[.,]11/);
    expect(figure(card, "costAtGridPrice").textContent).toMatch(/5[.,]78/);
    expect(figure(card, "costSavings").textContent).toMatch(/5[.,]67/);
  });

  it("labels each figure by the name the project settled on", async () => {
    // Given / When — "Cost at Grid Price", never "Cost Without Solar" (ADR-0009)
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(text(card)).toContain("Actual Cost");
    expect(text(card)).toContain("Cost at Grid Price");
    expect(text(card)).not.toContain("Without Solar");
  });

  it("totals the whole house, the Untracked remainder included", async () => {
    // Given — the remainder is part of what the household actually paid
    const hass = aHass({
      devices: [
        aDeviceRow("living_room_aircon", "Living Room Aircon"),
        aDeviceRow("untracked_energy_devices", "Untracked", true),
      ],
      response: {
        ...AIRCON_BUCKETS,
        ...bucketsFor("untracked_energy_devices", 100, 4, 5),
      },
    });

    // When
    const card = mount(hass);
    await settled(card);

    // Then
    expect(figure(card, "actualCost").textContent).toMatch(/4[.,]11/);
  });

  it("counts only the devices a filter names", async () => {
    // Given — "this device, or these devices, cost x"
    const hass = aHass({
      devices: [
        aDeviceRow("living_room_aircon", "Living Room Aircon"),
        aDeviceRow("kitchen_aircon", "Kitchen Aircon"),
      ],
    });

    // When
    const card = mount(hass, { devices: ["living_room_aircon"] });
    await settled(card);

    // Then — the other device is never even asked about
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({
        statistic_ids: [
          "sensor.living_room_aircon_energy_used",
          "sensor.living_room_aircon_actual_cost",
          "sensor.living_room_aircon_cost_at_grid_price",
        ],
      }),
    );
  });

  it("marks a saving that is really a loss", async () => {
    // Given — battery arbitrage cost more than the grid would have (HEA-39)
    const hass = aHass({
      response: bucketsFor("living_room_aircon", 10, 5, 3),
    });

    // When
    const card = mount(hass);
    await settled(card);

    // Then — signed, and marked so it can be styled as the loss it is
    expect(figure(card, "costSavings").textContent).toMatch(/-/);
    expect(figure(card, "costSavings").classList.contains("loss")).toBe(true);
  });
});

describe("the period", () => {
  it("says which range the figures cover", async () => {
    // Given / When
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(text(card)).toMatch(/20 May/);
    expect(text(card)).toMatch(/15 Jul/);
  });

  it("follows the picker to a new range", async () => {
    // Given — a card already showing May to July
    const collection = anEnergyCollection();
    const hass = aHass({ collection });
    const card = mount(hass);
    await settled(card);

    // When — the user picks a different range
    collection.announce(new Date(2026, 7, 1), new Date(2026, 7, 9));

    // Then — the figures are fetched again for it
    await vi.waitFor(() => expect(text(card)).toMatch(/9 Aug 2026/));
    expect(hass.callWS).toHaveBeenCalledTimes(2);
  });

  it("says so when it is showing a default range", async () => {
    // Given — a dashboard with no energy-date-selection card on it
    const card = mount(aHass({ collection: null }));

    // When
    await settled(card);

    // Then — the user is told why the range is not the one they expected
    expect(text(card)).toMatch(/date picker/i);
  });

  it("does not claim a default range once it is following the picker", async () => {
    // Given / When
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(text(card)).not.toMatch(/date picker/i);
  });
});

describe("when there is nothing to show", () => {
  it("says so when no devices are tracked yet", async () => {
    // Given — HEA installed but no devices added
    const hass = aHass({ devices: [] });

    // When
    const card = mount(hass);
    await settled(card, "empty");

    // Then — and the recorder is never asked for every statistic in the house
    expect(text(card)).toMatch(/no devices/i);
    expect(hass.callWS).not.toHaveBeenCalled();
  });

  it("says so when the integration is not loaded at all", async () => {
    // Given — a dashboard placed before HEA is set up
    const hass = aHass({ devices: null });

    // When
    const card = mount(hass);

    // Then
    await settled(card, "empty");
  });

  it("reports a failure rather than showing a house that cost nothing", async () => {
    // Given — the recorder is unavailable
    const hass = aHass({ callWS: vi.fn().mockRejectedValue(new Error("no recorder")) });

    // When
    const card = mount(hass);
    await settled(card, "error");

    // Then — zeroes would read as a free week, which is worse than an error
    expect(text(card)).toMatch(/could not/i);
  });
});

describe("lifecycle", () => {
  it("waits for the picker when the card renders first", async () => {
    // Given — card order within a view is not guaranteed, so the collection
    // may not exist on the first hass update
    const hass = aHass({ collection: null });
    const card = mount(hass);
    await settled(card);
    expect(text(card)).toMatch(/date picker/i);

    // When — the picker appears and a later hass update carries it
    const collection = anEnergyCollection();
    card.hass = { ...hass, connection: { "_energy_hea-costs": collection } };

    // Then — the card switches to the picker's range
    await vi.waitFor(() => expect(text(card)).not.toMatch(/date picker/i));
  });

  it("leaves no subscription behind when removed from the dashboard", async () => {
    // Given
    const collection = anEnergyCollection();
    const card = mount(aHass({ collection }));
    await settled(card);
    expect(collection.listenerCount).toBe(1);

    // When
    card.remove();

    // Then
    expect(collection.listenerCount).toBe(0);
  });

  it("subscribes again when the dashboard moves it", async () => {
    // Given — Home Assistant re-appends cards when a view is edited, and a card
    // that does not re-subscribe silently freezes on the range it last saw
    const collection = anEnergyCollection();
    const card = mount(aHass({ collection }));
    await settled(card);

    // When
    card.remove();
    document.body.append(card);

    // Then
    expect(collection.listenerCount).toBe(1);
  });

  it("ignores a failure from a request that has been overtaken", async () => {
    // Given — the first fetch fails, but only after a later one has succeeded;
    // letting it through would replace good figures with an error
    const collection = anEnergyCollection();
    const pending = [];
    const callWS = vi.fn(
      () => new Promise((resolve, reject) => pending.push({ resolve, reject })),
    );
    const card = mount(aHass({ collection, callWS }));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(1));

    // When
    collection.announce(new Date(2026, 3, 1), new Date(2026, 7, 9));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(2));
    pending[1].resolve(bucketsFor("living_room_aircon", 1, 2, 3));
    await settled(card);
    pending[0].reject(new Error("too late"));
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Then
    expect(stateOf(card)).toBe("ready");
    expect(figure(card, "actualCost").textContent).toMatch(/2[.,]00/);
  });

  it("ignores a stale response that lands after a newer one", async () => {
    // Given — a slow first fetch and a fast second; without a guard the slow
    // one lands last and the card shows the range the user already left
    const collection = anEnergyCollection();
    const resolvers = [];
    const callWS = vi.fn(
      () => new Promise((resolve) => resolvers.push(resolve)),
    );
    const card = mount(aHass({ collection, callWS }));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(1));

    // When — the user picks another range before the first answer arrives,
    // and the answers come back out of order
    collection.announce(new Date(2026, 3, 1), new Date(2026, 7, 9));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(2));
    resolvers[1](bucketsFor("living_room_aircon", 1, 2, 3));
    await settled(card);
    resolvers[0](bucketsFor("living_room_aircon", 9, 9, 9));

    // Then — the newer figures stand
    await vi.waitFor(() => expect(figure(card, "actualCost").textContent).toMatch(/2[.,]00/));
    expect(figure(card, "actualCost").textContent).toMatch(/2[.,]00/);
  });
});
