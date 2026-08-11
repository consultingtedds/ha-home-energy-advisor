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
  aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"),
  aDeviceRow("fine_meter_aircon", "Fine Meter Aircon"),
  aDeviceRow("untracked_energy_devices", "Untracked Energy Devices", true),
];

const THREE_RESPONSE = {
  // energy, actual, at grid price → saved is the difference
  ...bucketsFor("slow_poll_aircon", 38.6, 0.11, 5.78), // saved 5.67
  ...bucketsFor("fine_meter_aircon", 12.0, 3.0, 4.0), // saved 1.00
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

    // Then — the counterfactual and the saving beside what was actually paid,
    // and the unit price that ties the first two together
    expect(rows(card)).toContainEqual([
      "Slow Poll Aircon",
      "38.6 kWh",
      expect.stringMatching(/0[.,]11/),
      expect.stringMatching(/5[.,]78/),
      expect.stringMatching(/5[.,]67/),
      expect.stringMatching(/0[.,]003/),
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
      "Fine Meter Aircon",
      "Untracked Energy Devices",
      "Slow Poll Aircon",
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
      "Slow Poll Aircon",
      "Fine Meter Aircon",
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

  it("shows what each device actually paid per kWh", async () => {
    // Given — three devices whose unit prices differ by two orders of magnitude
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — the rate is cost over energy, per device. This is the figure that
    // exposed HEA-74: a device priced far under the tariff on a night when
    // every kWh came off the grid is visible here and nowhere else.
    const rates = Object.fromEntries(
      rows(card).map((row) => [row[0], row[5]]),
    );
    expect(rates["Fine Meter Aircon"]).toMatch(/0[.,]250/); // 3.00 / 12.0
    expect(rates["Slow Poll Aircon"]).toMatch(/0[.,]003/); // 0.11 / 38.6
    expect(rates["Untracked Energy Devices"]).toMatch(/0[.,]015/); // 1.50 / 100
  });

  it("totals the rate as the period's blended price, not a sum of rates", async () => {
    // Given — the same three devices
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — 4.61 over 150.6 kWh is €0.031/kWh. Adding the three rates would
    // give €0.268, which is not a price anything was bought at: a rate is a
    // ratio, and ratios do not sum.
    const total = [
      ...card.shadowRoot.querySelectorAll("tfoot th, tfoot td"),
    ].map((cell) => cell.textContent.trim());
    expect(total[5]).toMatch(/0[.,]031/);
    expect(total[5]).not.toMatch(/0[.,]268/);
  });

  it("shows no rate for a device that used no energy", async () => {
    // Given — a device that reported nothing over the period
    const hass = aHass({
      devices: [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")],
      response: bucketsFor("slow_poll_aircon", 0, 0, 0),
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then — a dash, not a zero. Dividing by no energy yields no price, and
    // "free" is a different claim from "we cannot say"
    expect(rows(card)[0][5]).toBe("—");
  });

  it("marks a device whose saving is really a loss", async () => {
    // Given — battery arbitrage cost more than the grid would have (HEA-39)
    const hass = aHass({
      devices: [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")],
      response: bucketsFor("slow_poll_aircon", 10, 5, 3),
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
      devices: [aDeviceRow("slow_poll_aircon", "<img src=x onerror=alert(1)>")],
      response: bucketsFor("slow_poll_aircon", 1, 1, 1),
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
    const card = mount(hass, { devices: ["fine_meter_aircon"] });
    await ready(card);

    // Then
    expect(deviceOrder(card)).toEqual(["Fine Meter Aircon"]);
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
