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
  it("plots one bar per device, against the devices themselves", async () => {
    // Given — the comparison is device against device, so the axis is
    // categorical rather than the over-time chart's time axis
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.xAxis.type).toBe("category");
    expect(chartOf(card).options.xAxis.data).toEqual([
      "Cloud Polled Pump",
      "Slow Poll Aircon",
    ]);
  });

  it("stacks what was paid under what was saved", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — one stack, so each bar totals Cost at Grid Price
    expect(seriesOf(card, "paid").stack).toBe("cost");
    expect(seriesOf(card, "saved").stack).toBe("cost");
    expect(seriesOf(card, "paid").data.map((point) => point.value)).toEqual([3.0, 0.5]);
    expect(seriesOf(card, "saved").data.map((point) => point.value)).toEqual([1.0, 5.0]);
  });

  it("orders the dearest device first", async () => {
    // Given — "which device costs most" is the question the bars answer
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.xAxis.data[0]).toBe("Cloud Polled Pump");
  });

  it("gives each device its own colour, in both segments", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — the hue identifies the device, so paid and saved share it; the
    // segments are told apart by opacity, not by a second palette
    const paid = seriesOf(card, "paid").data;
    const saved = seriesOf(card, "saved").data;
    expect(paid[0].itemStyle.color).not.toBe(paid[1].itemStyle.color);
    expect(saved[0].itemStyle.color).toBe(paid[0].itemStyle.color);
    expect(saved[1].itemStyle.color).toBe(paid[1].itemStyle.color);
  });

  it("fades the saved segment rather than recolouring it", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — solid is what left the household's pocket
    expect(seriesOf(card, "paid").itemStyle.opacity).toBe(1);
    expect(seriesOf(card, "saved").itemStyle.opacity).toBeLessThan(1);
  });

  it("gives the Untracked remainder a colour of its own", async () => {
    // Given — it is not a device, and colouring it like one invites the reader
    // to hunt for an appliance that does not exist
    const card = mount(aHass({ devices: [AIRCON, UNTRACKED], response: THREE }));
    await ready(card);

    // Then
    const byName = Object.fromEntries(
      chartOf(card).options.xAxis.data.map((name, index) => [
        name,
        seriesOf(card, "paid").data[index].itemStyle.color,
      ]),
    );
    expect(byName["Untracked"]).not.toBe(byName["Slow Poll Aircon"]);
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
    // loss carries the error colour so it is not read as a gain
    const [point] = seriesOf(card, "saved").data;
    const [paid] = seriesOf(card, "paid").data;
    expect(point.value).toBe(-2);
    expect(point.itemStyle.color).not.toBe(paid.itemStyle.color);
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
