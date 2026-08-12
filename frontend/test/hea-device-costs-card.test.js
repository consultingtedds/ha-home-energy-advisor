/**
 * @vitest-environment happy-dom
 *
 * What each device cost over the period, as bars (HEA-50).
 *
 * One bar per device in that device's own colour, stacked: solid below is what
 * was paid, faded above is what was saved, and the whole bar is Cost at Grid
 * Price — the same meaning the over-time chart's bars carry, turned on its side
 * so devices can be compared against each other rather than against yesterday.
 *
 * `ha-chart-base` is Home Assistant's (ADR-0013) and is stubbed here, so what
 * is asserted is the contract we hand it — series and options — not pixels.
 */

import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import { TAG, register } from "../hea-device-costs-card.js";
import { aDeviceRow, aHass, bucketsFor, mountCard, settled } from "./doubles.js";

const AIRCON = aDeviceRow("slow_poll_aircon", "Slow Poll Aircon");
const PUMP = aDeviceRow("cloud_polled_pump", "Cloud Polled Pump");
const UNTRACKED = aDeviceRow("untracked_energy_devices", "Untracked", true);

/** The pump cost most; the aircon saved most. */
const THREE = {
  ...bucketsFor("slow_poll_aircon", 38.6, 0.5, 5.5), // saved 5.0
  ...bucketsFor("cloud_polled_pump", 12.0, 3.0, 4.0), // saved 1.0
  ...bucketsFor("untracked_energy_devices", 100, 1.0, 2.0), // saved 1.0
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);
const chartOf = (card) => card.shadowRoot.querySelector("ha-chart-base");
const seriesOf = (card, id) => chartOf(card).data.find((s) => s.id === id);

beforeAll(() => {
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

  it("names itself when no title is configured", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "What each device cost",
    );
  });
});

describe("the bars", () => {
  const deviceSeries = (card, key) =>
    chartOf(card).data.filter((series) => series.id.startsWith(`${key}:`));

  it("puts the devices in the legend, not on the axis", async () => {
    // Given — fourteen device names along an axis is what made the first
    // attempt unreadable; Home Assistant's own charts name series in a legend
    // and leave the axis to the period
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — one category for the whole period, and the names in the legend
    expect(chartOf(card).options.xAxis.type).toBe("category");
    expect(chartOf(card).options.xAxis.data).toHaveLength(1);
    expect(chartOf(card).options.legend.data.map((entry) => entry.name)).toEqual([
      "Cloud Polled Pump",
      "Slow Poll Aircon",
    ]);
  });

  it("gives every device one legend entry, not one per segment", async () => {
    // Given — each device is drawn as two stacked series, which would
    // otherwise put its name in the legend twice
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).data).toHaveLength(4);
    expect(chartOf(card).options.legend.data).toHaveLength(2);
  });

  it("fills to what was paid and outlines to what it would have cost", async () => {
    // Given — the outline carries the counterfactual and the fill carries the
    // spend, so the empty space between them is the saving
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then — 3.00 paid of 4.00 at grid price, so 1.00 stands empty above it
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(paid.data[0]).toBe(3.0);
    expect(saved.data[0]).toBe(1.0);
    expect(paid.itemStyle.color).not.toBe("transparent");
    expect(saved.itemStyle.color).toBe("transparent");
  });

  it("draws both segments with the same outline, in the device's colour", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — one hue per device, carried by the border so the bar reads as a
    // single outlined shape rather than two stacked blocks
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(paid.itemStyle.borderColor).toBe(saved.itemStyle.borderColor);
    expect(paid.itemStyle.borderWidth).toBeGreaterThan(0);
    expect(saved.itemStyle.borderWidth).toBeGreaterThan(0);
    const [otherPaid] = deviceSeries(card, "slow_poll_aircon");
    expect(otherPaid.itemStyle.borderColor).not.toBe(paid.itemStyle.borderColor);
  });

  it("stacks each device on its own, so devices sit side by side", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — a shared stack would pile every device into one column
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    const [otherPaid] = deviceSeries(card, "slow_poll_aircon");
    expect(paid.stack).toBe(saved.stack);
    expect(paid.stack).not.toBe(otherPaid.stack);
  });

  it("orders the dearest device first", async () => {
    // Given — "which device costs most" is the question the bars answer
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.legend.data[0].name).toBe("Cloud Polled Pump");
  });

  it("gives the Untracked remainder a colour of its own", async () => {
    // Given — it is not a device, and colouring it like one invites the reader
    // to hunt for an appliance that does not exist
    const card = mount(aHass({ devices: [AIRCON, UNTRACKED], response: THREE }));
    await ready(card);

    // Then
    const [untracked] = deviceSeries(card, "untracked_energy_devices");
    const [aircon] = deviceSeries(card, "slow_poll_aircon");
    expect(untracked.itemStyle.borderColor).not.toBe(aircon.itemStyle.borderColor);
  });

  it("keeps a loss below the axis and marks it", async () => {
    // Given — battery arbitrage cost more than the grid would have (HEA-39)
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 5, 3),
      }),
    );
    await ready(card);

    // Then — negative is how Home Assistant renders exported energy, and the
    // loss outline is the error colour so it is not read as a gain
    const [paid, saved] = deviceSeries(card, "slow_poll_aircon");
    expect(saved.data[0]).toBe(-2);
    expect(saved.itemStyle.borderColor).not.toBe(paid.itemStyle.borderColor);
  });
});

describe("the options handed to the chart", () => {
  it("labels the value axis in the household's currency", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then
    const label = chartOf(card).options.yAxis.axisLabel.formatter(3);
    expect(label).toMatch(/€/);
    expect(label).toMatch(/3[.,]00/);
  });

  it("formats hovered figures as money", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then — an allocated share divides into a long recurring decimal, and a
    // raw hover reads out fourteen places of a euro
    const shown = chartOf(card).options.tooltip.valueFormatter(1.2345678901234);
    expect(shown).toMatch(/€/);
    expect(shown).not.toMatch(/\d[.,]\d{3}/);
  });

  it("says so when no device recorded anything in the period", async () => {
    // Given — a range earlier than any recorded statistic. Bars of nothing read
    // as "it cost nothing", which is a different claim from "there is nothing
    // here", and every configured device still yields a row.
    const card = mount(aHass({ devices: [AIRCON], response: {} }));
    await ready(card);

    // Then
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
    expect(chartOf(card)).toBe(null);
  });
});
