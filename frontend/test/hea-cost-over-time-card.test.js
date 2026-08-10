/**
 * @vitest-environment happy-dom
 *
 * The stacked bar (HEA-50, ADR-0012): the whole bar is Cost at Grid Price,
 * the lower segment what was actually paid and the upper what was saved. One
 * glance gives spend, counterfactual and saving, and the segments sum to
 * something real.
 *
 * The geometry is the contract here. A chart that draws the right shape from
 * the wrong arithmetic looks fine and lies, so the tests assert the *ratios*
 * between segments rather than pixel values.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { TAG, register } from "../hea-cost-over-time-card.js";
import { aDeviceRow, aHass, mountCard, settled } from "./doubles.js";

const DAY_ONE = new Date(2026, 4, 20);
const DAY_TWO = new Date(2026, 4, 21);

const AIRCON = [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")];

/** Two days of buckets: paid 1 of 3, then paid 2 of 3. */
const twoDays = {
  "sensor.slow_poll_aircon_energy_used": [
    { start: DAY_ONE.getTime(), change: 10 },
    { start: DAY_TWO.getTime(), change: 12 },
  ],
  "sensor.slow_poll_aircon_actual_cost": [
    { start: DAY_ONE.getTime(), change: 1 },
    { start: DAY_TWO.getTime(), change: 2 },
  ],
  "sensor.slow_poll_aircon_cost_at_grid_price": [
    { start: DAY_ONE.getTime(), change: 3 },
    { start: DAY_TWO.getTime(), change: 3 },
  ],
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);

const bars = (card) => [...card.shadowRoot.querySelectorAll("g.bar")];
const segment = (bar, name) => bar.querySelector(`rect.${name}`);
const heightOf = (rect) => Number(rect.getAttribute("height"));
const topOf = (rect) => Number(rect.getAttribute("y"));
const baseline = (card) =>
  Number(card.shadowRoot.querySelector("line.baseline").getAttribute("y1"));

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

describe("the bars", () => {
  it("draws one bar per bucket in the period", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    expect(bars(card)).toHaveLength(2);
  });

  it("splits each bar into what was paid and what was saved", async () => {
    // Given — day one: paid 1, would have cost 3, so saved 2
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When
    const [dayOne] = bars(card);

    // Then — the saved segment is twice the paid one, because 2 is twice 1
    const ratio = heightOf(segment(dayOne, "saved")) / heightOf(segment(dayOne, "paid"));
    expect(ratio).toBeCloseTo(2, 5);
  });

  it("scales bars against each other, not each to its own height", async () => {
    // Given — both days cost 3 at grid price, so both bars are the same height
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When
    const whole = (bar) =>
      heightOf(segment(bar, "paid")) + heightOf(segment(bar, "saved"));

    // Then
    const [dayOne, dayTwo] = bars(card);
    expect(whole(dayOne)).toBeCloseTo(whole(dayTwo), 5);
    // and day two paid twice as much as day one
    expect(heightOf(segment(dayTwo, "paid")) / heightOf(segment(dayOne, "paid"))).toBeCloseTo(2, 5);
  });

  it("draws a saving that is really a loss below the axis", async () => {
    // Given — battery arbitrage cost more than the grid would have (HEA-39).
    // The Energy Dashboard puts exported energy and battery charge below the
    // axis; a negative saving reads the same way (ADR-0012 decision 3).
    const loss = {
      "sensor.slow_poll_aircon_energy_used": [{ start: DAY_ONE.getTime(), change: 10 }],
      "sensor.slow_poll_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 5 }],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: DAY_ONE.getTime(), change: 3 },
      ],
    };

    // When
    const card = mount(aHass({ devices: AIRCON, response: loss }));
    await ready(card);

    // Then — marked as a loss, and its top edge sits at or below the baseline
    const saved = segment(bars(card)[0], "saved");
    expect(saved.classList.contains("loss")).toBe(true);
    expect(topOf(saved)).toBeGreaterThanOrEqual(baseline(card) - 0.01);
  });

  it("labels each bar with its date and its three figures", async () => {
    // Given — the chart has no room for per-bar text, so the detail lives in
    // the title a browser shows on hover and a screen reader announces
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When
    const title = bars(card)[0].querySelector("title").textContent;

    // Then
    expect(title).toMatch(/20 May/);
    expect(title).toMatch(/1[.,]00/);
    expect(title).toMatch(/3[.,]00/);
    expect(title).toMatch(/2[.,]00/);
  });
});

describe("when the period is flat", () => {
  it("draws without producing NaN geometry", async () => {
    // Given — a period in which nothing ran at all, so every figure is zero
    // and the scale has no range to divide by
    const nothing = {
      "sensor.slow_poll_aircon_energy_used": [{ start: DAY_ONE.getTime(), change: 0 }],
      "sensor.slow_poll_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 0 }],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: DAY_ONE.getTime(), change: 0 },
      ],
    };

    // When
    const card = mount(aHass({ devices: AIRCON, response: nothing }));
    await ready(card);

    // Then — a broken viewBox silently collapses the whole card
    expect(card.shadowRoot.innerHTML).not.toContain("NaN");
    expect(bars(card)).toHaveLength(1);
  });

  it("says so when the period holds no buckets at all", async () => {
    // Given — a range earlier than any recorded statistic
    const card = mount(aHass({ devices: AIRCON, response: {} }));
    await ready(card);

    // Then — an empty axis would read as "it cost nothing"
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
  });
});

describe("the card", () => {
  it("is tall enough for a chart in a masonry view", async () => {
    // Given / When / Then
    expect(mount(aHass({ devices: AIRCON, response: twoDays })).getCardSize()).toBeGreaterThan(3);
  });

  it("offers the same editor as the other cards", () => {
    // Given / When / Then — one shared editor (HEA-73)
    expect(customElements.get(TAG).getConfigElement()).toBeInstanceOf(HTMLElement);
  });
});
