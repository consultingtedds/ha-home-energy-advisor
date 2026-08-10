/**
 * @vitest-environment happy-dom
 *
 * Every tracked device for the picked period, ordered by what it cost — the
 * "which device costs most" answer, finally sortable (HEA-50).
 *
 * The lifecycle it shares with the totals card is covered by that card's suite;
 * what is tested here is the table: its ordering, its totals row, and the fact
 * that a device name is the household's own text and must be escaped.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { TAG, register } from "../hea-devices-card.js";
import {
  aDeviceRow,
  aHass,
  bucketsFor,
  mountCard,
  settled,
  text,
} from "./doubles.js";

/** Three devices whose costs deliberately do not share an order with savings. */
const THREE_DEVICES = [
  aDeviceRow("living_room_aircon", "Living Room Aircon"),
  aDeviceRow("kitchen_aircon", "Kitchen Aircon"),
  aDeviceRow("untracked_energy_devices", "Untracked Energy Devices", true),
];

const THREE_RESPONSE = {
  // energy, actual, at grid price → saved is the difference
  ...bucketsFor("living_room_aircon", 38.6, 0.11, 5.78), // saved 5.67
  ...bucketsFor("kitchen_aircon", 12.0, 3.0, 4.0), // saved 1.00
  ...bucketsFor("untracked_energy_devices", 100, 1.5, 9.5), // saved 8.00
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);

const rows = (card) =>
  [...card.shadowRoot.querySelectorAll("tbody tr")].map((row) =>
    [...row.querySelectorAll("th, td")].map((cell) => cell.textContent.trim()),
  );

const deviceOrder = (card) => rows(card).map(([name]) => name);

beforeEach(() => {
  document.body.replaceChildren();
});

describe("registration", () => {
  it("is registered, and offers itself in the card picker", () => {
    // Given / When / Then
    expect(customElements.get(TAG)).toBeDefined();
    expect(globalThis.customCards).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: TAG })]),
    );
  });

  it("survives the resource being added to a dashboard twice", () => {
    // Given / When / Then
    expect(() => register()).not.toThrow();
  });
});

describe("the table", () => {
  it("lists every device with its energy, costs and saving", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — the counterfactual and the saving beside what was actually paid
    expect(rows(card)).toContainEqual([
      "Living Room Aircon",
      "38.6 kWh",
      expect.stringMatching(/0[.,]11/),
      expect.stringMatching(/5[.,]78/),
      expect.stringMatching(/5[.,]67/),
    ]);
  });

  it("orders devices by what they actually cost, dearest first", async () => {
    // Given — the question is "which device costs most"
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — 3.00, 1.50, 0.11
    expect(deviceOrder(card)).toEqual([
      "Kitchen Aircon",
      "Untracked Energy Devices",
      "Living Room Aircon",
    ]);
  });

  it("orders by another figure when one is configured", async () => {
    // Given — "which device saved me most" is the same table, sorted differently
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass, { sort_by: "cost_savings" });
    await ready(card);

    // Then — 8.00, 5.67, 1.00
    expect(deviceOrder(card)).toEqual([
      "Untracked Energy Devices",
      "Living Room Aircon",
      "Kitchen Aircon",
    ]);
  });

  it("rejects a sort nobody can satisfy", () => {
    // Given — a hand-edited dashboard yaml
    const card = document.createElement(TAG);

    // When / Then — the message names the options, since the editor shows it
    expect(() => card.setConfig({ type: `custom:${TAG}`, sort_by: "vibes" })).toThrow(
      /sort_by/,
    );
  });

  it("totals the devices it lists", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — 0.11 + 3.00 + 1.50 actual, against 5.78 + 4.00 + 9.50 at grid price
    const total = [...card.shadowRoot.querySelectorAll("tfoot th, tfoot td")].map(
      (cell) => cell.textContent.trim(),
    );
    expect(total[2]).toMatch(/4[.,]61/);
    expect(total[3]).toMatch(/19[.,]28/);
    expect(total[4]).toMatch(/14[.,]67/);
  });

  it("marks a device whose saving is really a loss", async () => {
    // Given — battery arbitrage cost more than the grid would have (HEA-39)
    const hass = aHass({
      devices: [aDeviceRow("living_room_aircon", "Living Room Aircon")],
      response: bucketsFor("living_room_aircon", 10, 5, 3),
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then
    const saving = card.shadowRoot.querySelector("tbody tr .loss");
    expect(saving.textContent).toMatch(/-/);
  });

  it("escapes a device name, which is the household's own text", async () => {
    // Given — a device a user named awkwardly
    const hass = aHass({
      devices: [aDeviceRow("living_room_aircon", "<img src=x onerror=alert(1)>")],
      response: bucketsFor("living_room_aircon", 1, 1, 1),
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — shown as text, never parsed as markup
    expect(card.shadowRoot.querySelector("tbody img")).toBe(null);
    expect(text(card)).toContain("<img src=x onerror=alert(1)>");
  });

  it("counts only the devices a filter names", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass, { devices: ["kitchen_aircon"] });
    await ready(card);

    // Then
    expect(deviceOrder(card)).toEqual(["Kitchen Aircon"]);
  });

  it("grows its card size with the number of devices it shows", async () => {
    // Given — masonry lays out from this estimate, and a 15-device table is
    // nothing like the height of a one-device one
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then
    expect(card.getCardSize()).toBeGreaterThan(3);
  });
});
