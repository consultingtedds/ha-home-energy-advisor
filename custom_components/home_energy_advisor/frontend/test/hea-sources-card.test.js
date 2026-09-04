/**
 * @vitest-environment happy-dom
 *
 * Where each device's energy came from - grid, generation or battery (HEA-51).
 *
 * The table mechanics are `HeaTableCard`'s and are covered by the devices
 * card's suite; what is tested here is this card's own columns, and one thing
 * that matters more than presentation: the three sources must add up to the
 * device's energy. A split that does not sum is the shape a real accounting
 * defect takes, and it is the contradiction that announced HEA-74.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { TAG, register } from "../hea-sources-card.js";
import {
  aDeviceRow,
  aHass,
  bucketsFor,
  mountCard,
  settled,
  sourcesFor,
} from "./doubles.js";

const AIRCON = aDeviceRow("slow_poll_aircon", "Slow Poll Aircon");
const PUMP = aDeviceRow("cloud_polled_pump", "Cloud Polled Pump");

/** Ten kWh: four off the grid, five from generation, one from the battery. */
const SPLIT = {
  ...bucketsFor("slow_poll_aircon", 10, 1, 2),
  ...sourcesFor("slow_poll_aircon", 4, 5, 1),
  ...bucketsFor("cloud_polled_pump", 20, 1, 2),
  ...sourcesFor("cloud_polled_pump", 2, 18, 0),
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);

const rows = (card) =>
  [...card.shadowRoot.querySelectorAll("tbody tr")].map((row) =>
    [...row.querySelectorAll("th, td")].map((cell) => cell.textContent.trim()),
  );

const totalRow = (card) =>
  [...card.shadowRoot.querySelectorAll("tfoot th, tfoot td")].map((cell) =>
    cell.textContent.trim(),
  );

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

  it("names itself when no title is configured", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON], response: SPLIT }));
    await ready(card);

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "Where the energy came from",
    );
  });
});

describe("what this table does not claim", () => {
  it("carries no cost verdict, because its rows are energy", async () => {
    // Given - the saving-rate band belongs to the column that carries the same
    // verdict as a figure (HEA-106). Built on the shared table base it painted
    // here too, down a table whose rows are kWh by source: this card names no
    // cost at all, so a red or green band beside a device would be answering a
    // question nobody asked of it. Caught on the live dashboard, not in a test
    const hass = aHass({ devices: [AIRCON, PUMP], response: SPLIT });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - no band, and no tinted figure either
    const cells = [...card.shadowRoot.querySelectorAll("tbody th, tbody td")];
    expect(cells.length).toBeGreaterThan(0);
    expect(cells.every((cell) => cell.style.boxShadow === "")).toBe(true);
    expect(cells.every((cell) => cell.style.color === "")).toBe(true);
  });
});

describe("the split", () => {
  it("shows each source beside the energy it accounts for", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON], response: SPLIT }));
    await ready(card);

    // Then - energy, then grid, generation and battery, which sum back to it
    expect(rows(card)[0]).toEqual([
      "Slow Poll Aircon",
      "10 kWh",
      "4 kWh",
      "5 kWh",
      "1 kWh",
      "40%",
    ]);
  });

  it("shows what share came off the grid", async () => {
    // Given - a pump that ran almost entirely on generation
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: SPLIT }));
    await ready(card);

    // Then - 2 of 20 kWh
    const shares = Object.fromEntries(rows(card).map((row) => [row[0], row[5]]));
    expect(shares["Cloud Polled Pump"]).toBe("10%");
  });

  it("derives the total share rather than averaging the rows", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: SPLIT }));
    await ready(card);

    // Then - 6 kWh of grid across 30 kWh is 20 %. Averaging the two rows'
    // shares would give 25 %, which is not a share of anything: a proportion
    // of a whole is not the mean of its parts' proportions
    const total = totalRow(card);
    expect(total[1]).toBe("30 kWh");
    expect(total[5]).toBe("20%");
    expect(total[5]).not.toBe("25%");
  });

  it("orders by energy, largest first", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: SPLIT }));
    await ready(card);

    // Then
    expect(rows(card).map(([name]) => name)).toEqual([
      "Cloud Polled Pump",
      "Slow Poll Aircon",
    ]);
  });

  it("shows no share for a device that used no energy", async () => {
    // Given - a device that reported nothing over the period
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: {
          ...bucketsFor("slow_poll_aircon", 0, 0, 0),
          ...sourcesFor("slow_poll_aircon", 0, 0, 0),
        },
      }),
    );
    await ready(card);

    // Then - a dash, not 0 %: no share can be derived from no energy
    expect(rows(card)[0][5]).toBe("-");
  });

  it("does not hide a split that fails to account for the energy", async () => {
    // Given - a device whose sources sum to less than its energy, which is what
    // a real defect looks like. HEA-77 documents one legitimate cause: a device
    // whose by-source sensors started later than its energy sensor carries a
    // permanent skew.
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: {
          ...bucketsFor("slow_poll_aircon", 10, 1, 2),
          ...sourcesFor("slow_poll_aircon", 1, 1, 1),
        },
      }),
    );
    await ready(card);

    // Then - the figures are shown as recorded, so the shortfall is visible
    // rather than silently normalised away into percentages that always total
    // a hundred
    expect(rows(card)[0].slice(1, 5)).toEqual(["10 kWh", "1 kWh", "1 kWh", "1 kWh"]);
    expect(rows(card)[0][5]).toBe("10%");
  });
});
