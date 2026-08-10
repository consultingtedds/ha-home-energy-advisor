/**
 * @vitest-environment happy-dom
 *
 * The stacked bar (HEA-50, ADR-0012): the whole bar is Cost at Grid Price, the
 * lower segment what was actually paid and the upper what was saved.
 *
 * It is drawn by Home Assistant's `ha-chart-base` (ADR-0013), which is theirs
 * and never defined in these tests. What is asserted is therefore the contract
 * we hand it — the series and options — not pixels. A chart that draws a
 * convincing picture from the wrong arithmetic is the failure worth catching,
 * and that shows up in the series values.
 */

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { TAG, register } from "../hea-cost-over-time-card.js";
import { aDeviceRow, aHass, mountCard, settled } from "./doubles.js";

const DAY_ONE = new Date(2026, 4, 20);
const DAY_TWO = new Date(2026, 4, 21);

const AIRCON = [aDeviceRow("living_room_aircon", "Living Room Aircon")];

/** Two days: paid 1 of 3, then paid 2 of 3. */
const twoDays = {
  "sensor.living_room_aircon_energy_used": [
    { start: DAY_ONE.getTime(), change: 10 },
    { start: DAY_TWO.getTime(), change: 12 },
  ],
  "sensor.living_room_aircon_actual_cost": [
    { start: DAY_ONE.getTime(), change: 1 },
    { start: DAY_TWO.getTime(), change: 2 },
  ],
  "sensor.living_room_aircon_cost_at_grid_price": [
    { start: DAY_ONE.getTime(), change: 3 },
    { start: DAY_TWO.getTime(), change: 3 },
  ],
};

/** Battery arbitrage costing more than the grid would have (HEA-39). */
const aLoss = {
  "sensor.living_room_aircon_energy_used": [{ start: DAY_ONE.getTime(), change: 10 }],
  "sensor.living_room_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 5 }],
  "sensor.living_room_aircon_cost_at_grid_price": [{ start: DAY_ONE.getTime(), change: 3 }],
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);
const chartOf = (card) => card.shadowRoot.querySelector("ha-chart-base");
const seriesOf = (card, id) => chartOf(card).data.find((s) => s.id === id);

beforeAll(() => {
  // Home Assistant's component, stood in for so the card will render its chart.
  if (!customElements.get("ha-chart-base")) {
    customElements.define("ha-chart-base", class extends HTMLElement {});
  }
});

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

  it("offers the same editor as the other cards", () => {
    // Given / When / Then — one shared editor (HEA-73)
    expect(customElements.get(TAG).getConfigElement()).toBeInstanceOf(HTMLElement);
  });
});

describe("the series handed to the chart", () => {
  it("stacks what was paid and what was saved into one bar", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then — one stack, so the two segments sum to Cost at Grid Price
    expect(seriesOf(card, "paid").stack).toBe("cost");
    expect(seriesOf(card, "saved").stack).toBe(seriesOf(card, "paid").stack);
    expect(seriesOf(card, "paid").type).toBe("bar");
  });

  it("carries each bucket's figures, oldest first", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then — day one paid 1 of 3, day two paid 2 of 3
    expect(seriesOf(card, "paid").data).toEqual([
      [DAY_ONE.getTime(), 1],
      [DAY_TWO.getTime(), 2],
    ]);
    expect(seriesOf(card, "saved").data).toEqual([
      [DAY_ONE.getTime(), 2],
      [DAY_TWO.getTime(), 1],
    ]);
  });

  it("keeps a loss negative, so it stacks below the axis", async () => {
    // Given — paid 5 where the grid would have cost 3
    const card = mount(aHass({ devices: AIRCON, response: aLoss }));
    await ready(card);

    // When
    const [point] = seriesOf(card, "saved").data;

    // Then — negative is how Home Assistant renders exported energy, and
    // ECharts stacks it downwards (ADR-0012 decision 3)
    expect(point.value).toEqual([DAY_ONE.getTime(), -2]);
  });

  it("colours a loss differently from a saving", async () => {
    // Given — the one figure a user must not misread as a gain
    const card = mount(aHass({ devices: AIRCON, response: aLoss }));
    await ready(card);

    // When / Then
    const [point] = seriesOf(card, "saved").data;
    expect(point.itemStyle.color).toBeTruthy();
    expect(point.itemStyle.color).not.toBe(seriesOf(card, "saved").itemStyle.color);
  });

  it("names its series for the legend", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    expect(seriesOf(card, "paid").name).toBe("Paid");
    expect(seriesOf(card, "saved").name).toBe("Saved");
  });
});

describe("the options handed to the chart", () => {
  it("plots against time, so gaps in the period are not squashed away", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    expect(chartOf(card).options.xAxis.type).toBe("time");
  });

  it("labels the value axis in the household's currency", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    const label = chartOf(card).options.yAxis.axisLabel.formatter(3);
    expect(label).toMatch(/€/);
    expect(label).toMatch(/3[.,]00/);
  });

  it("is given the hass object, which the chart needs for theming", async () => {
    // Given / When
    const hass = aHass({ devices: AIRCON, response: twoDays });
    const card = mount(hass);
    await ready(card);

    // Then
    expect(chartOf(card).hass).toBe(hass);
  });
});

describe("when there is nothing to draw", () => {
  it("says so when the period holds no buckets at all", async () => {
    // Given — a range earlier than any recorded statistic. An empty axis reads
    // as "it cost nothing", which is a different claim.
    const card = mount(aHass({ devices: AIRCON, response: {} }));
    await ready(card);

    // Then
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
    expect(chartOf(card)).toBe(null);
  });

  it("says so when Home Assistant's chart component never loaded", async () => {
    // Given — a dashboard carrying only HEA cards, where nothing has pulled
    // ha-chart-base in and the nudge did not work either (ADR-0013)
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When
    card._chartReady = false;
    card._render();

    // Then — an empty box would leave the user with nothing to act on
    expect(card.shadowRoot.textContent).toMatch(/chart component is not loaded/i);
    expect(card.shadowRoot.textContent).toMatch(/energy or statistics card/i);
  });

  it("asks Home Assistant to load the component when it is missing", async () => {
    // Given — creating any built-in chart card imports it as a side effect
    const createCardElement = vi.fn().mockResolvedValue(document.createElement("div"));
    globalThis.loadCardHelpers = vi.fn().mockResolvedValue({ createCardElement });
    const card = document.createElement(TAG);
    card.setConfig({ type: `custom:${TAG}` });
    card._chartReady = false;

    // When
    document.body.append(card);

    // Then
    await vi.waitFor(() => expect(globalThis.loadCardHelpers).toHaveBeenCalled());
    expect(createCardElement).toHaveBeenCalledWith(
      expect.objectContaining({ type: "statistics-graph" }),
    );
    delete globalThis.loadCardHelpers;
  });

  it("survives the nudge itself failing", async () => {
    // Given — loadCardHelpers can reject on an instance where the helper is
    // unavailable; the card must degrade, not throw inside a promise nobody
    // is awaiting
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    globalThis.loadCardHelpers = vi.fn().mockRejectedValue(new Error("no helpers"));
    const card = document.createElement(TAG);
    card.setConfig({ type: `custom:${TAG}` });
    card._chartReady = false;

    // When
    document.body.append(card);

    // Then — it warns and re-checks rather than throwing inside a promise
    // nobody awaits, and here the component turns out to be present anyway
    await vi.waitFor(() => expect(warn).toHaveBeenCalled());
    expect(card._chartReady).toBe(true);
    expect(card.shadowRoot.querySelector("[data-state]")).not.toBe(null);
    warn.mockRestore();
    delete globalThis.loadCardHelpers;
  });
});

describe("the card", () => {
  it("is tall enough for a chart in a masonry view", () => {
    // Given / When / Then
    expect(mount(aHass({ devices: AIRCON, response: twoDays })).getCardSize()).toBeGreaterThan(3);
  });
});
