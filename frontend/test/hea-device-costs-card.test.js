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
 * That contract is exact rather than approximate: the component ignores a
 * legend it does not recognise and silently draws none, so the shape it
 * requires is asserted here field by field.
 */

import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import { TAG, register, tint } from "../hea-device-costs-card.js";
import {
  aDeviceRow,
  aHass,
  boundsFor,
  bucketsFor,
  mountCard,
  settled,
} from "./doubles.js";

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
const legendOf = (card) => chartOf(card).options.legend;

/** A device's two segments, paid first, in the order the card emits them. */
const deviceSeries = (card, key) =>
  chartOf(card).data.filter((series) => series.id.startsWith(`${key}:`));

/** The `r, g, b` of a colour, so two strengths of one hue compare equal. */
const channelsOf = (colour) =>
  colour.replace(/^rgba?\(|\)$/g, "").split(",").slice(0, 3).join(",").trim();

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
  it("fills to what was paid and outlines to what it would have cost", async () => {
    // Given — the outline carries the counterfactual and the fill carries the
    // spend, so the lighter space between them is the saving
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then — 3.00 paid of 4.00 at grid price, so 1.00 stands above it
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(paid.data[0]).toBe(3.0);
    expect(saved.data[0]).toBe(1.0);
  });

  it("tints the saving rather than leaving it hollow", async () => {
    // Given — an empty box reads as absence; the saving is a quantity, and a
    // wash of the device's own colour says so while still ranking below the
    // spend it sits on
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(saved.itemStyle.color).not.toBe("transparent");
    expect(saved.itemStyle.color).not.toBe(paid.itemStyle.color);
    expect(saved.itemStyle.color).toMatch(/^rgba\(/);
  });

  it("outlines only the upper segment, so the boundary is a single line", async () => {
    // Given — stacked segments each carrying a border meet at the shared edge
    // and draw it twice, and ECharts has no per-side border width. Bordering
    // the saving alone leaves one line, at the level that was paid.
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(paid.itemStyle.borderWidth).toBeFalsy();
    expect(saved.itemStyle.borderWidth).toBeGreaterThan(0);
  });

  it("draws each device in a hue of its own", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — the outline and the fill beneath it are one colour at two
    // strengths, and the next device does not borrow it
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(channelsOf(saved.itemStyle.color)).toBe(
      channelsOf(tint(saved.itemStyle.borderColor, 1)),
    );
    expect(channelsOf(paid.itemStyle.color)).toBe(
      channelsOf(saved.itemStyle.color),
    );
    const [otherPaid] = deviceSeries(card, "slow_poll_aircon");
    expect(channelsOf(otherPaid.itemStyle.color)).not.toBe(
      channelsOf(paid.itemStyle.color),
    );
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
    const [, untracked] = deviceSeries(card, "untracked_energy_devices");
    const [, aircon] = deviceSeries(card, "slow_poll_aircon");
    expect(untracked.itemStyle.borderColor).not.toBe(aircon.itemStyle.borderColor);
  });

  it("keeps a loss below the axis and marks it apart from the device", async () => {
    // Given — battery arbitrage cost more than the grid would have (HEA-39)
    const saving = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 3, 5),
      }),
    );
    await ready(saving);
    const [, gained] = deviceSeries(saving, "slow_poll_aircon");
    const gainedOutline = gained.itemStyle.borderColor;

    // When — the same device, having lost rather than saved
    document.body.replaceChildren();
    const losing = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 5, 3),
      }),
    );
    await ready(losing);

    // Then — negative is how Home Assistant renders exported energy, and the
    // loss takes the error colour rather than the device's, so it is not read
    // as a gain
    const [, lost] = deviceSeries(losing, "slow_poll_aircon");
    expect(lost.data[0]).toBe(-2);
    expect(lost.itemStyle.borderColor).not.toBe(gainedOutline);
    expect(channelsOf(lost.itemStyle.color)).toBe(
      channelsOf(tint(lost.itemStyle.borderColor, 1)),
    );
  });
});

describe("the legend", () => {
  it("puts the devices in the legend, not on the axis", async () => {
    // Given — fourteen device names along an axis is what made the first
    // attempt unreadable; Home Assistant's own charts name series in a legend
    // and leave the axis to the period
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — one category for the whole period, and the names in the legend
    expect(chartOf(card).options.xAxis.type).toBe("category");
    expect(chartOf(card).options.xAxis.data).toHaveLength(1);
    expect(legendOf(card).data.map((entry) => entry.name)).toEqual([
      "Cloud Polled Pump",
      "Slow Poll Aircon",
    ]);
  });

  it("asks for the legend in the only shape that renders one", async () => {
    // Given — `ha-chart-base` builds its legend from the first option that is
    // both `show` and `type: "custom"`, and silently draws none otherwise. A
    // custom legend omitting `show` is the defect this card shipped with.
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(legendOf(card).show).toBe(true);
    expect(legendOf(card).type).toBe("custom");
  });

  it("gives every device one legend entry, not one per segment", async () => {
    // Given — each device is drawn as two stacked series, which would
    // otherwise put its name in the legend twice
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).data).toHaveLength(4);
    expect(legendOf(card).data).toHaveLength(2);
  });

  it("names series that exist, so clicking an entry hides the device", async () => {
    // Given — the component hides by matching a legend entry's `id` against a
    // series `id`, and toggles the rest of the device through `secondaryIds`.
    // An entry naming neither would render and then do nothing when clicked.
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then
    const ids = new Set(chartOf(card).data.map((series) => series.id));
    const [entry] = legendOf(card).data;
    expect(ids.has(entry.id)).toBe(true);
    expect(entry.secondaryIds.every((id) => ids.has(id))).toBe(true);
    expect([entry.id, ...entry.secondaryIds]).toHaveLength(ids.size);
  });

  it("swatches the device in its solid colour, not the faded fill", async () => {
    // Given — the swatch is the key to the bar, and a wash of a colour is
    // harder to tell from its neighbour than the colour itself
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then
    const [entry] = legendOf(card).data;
    const [, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(entry.itemStyle.color).toBe(saved.itemStyle.borderColor);
  });
});

describe("the tooltip", () => {
  const hover = (card, seriesId) =>
    chartOf(card).options.tooltip.formatter({ seriesId }).textContent;

  it("answers for the whole device, whichever segment is hovered", async () => {
    // Given — an axis tooltip lists every series at the category, which for a
    // dozen devices is two dozen rows, each device named twice with nothing
    // to say which row is the spend and which the saving
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then — one device, its three figures, and the same answer from either
    // half of its bar
    const shown = hover(card, "cloud_polled_pump:paid");
    expect(shown).toContain("Cloud Polled Pump");
    expect(shown).not.toContain("Slow Poll Aircon");
    expect(shown).toMatch(/Paid.*€3[.,]00/);
    expect(shown).toMatch(/Saved.*€1[.,]00/);
    expect(shown).toMatch(/At grid price.*€4[.,]00/);
    expect(hover(card, "cloud_polled_pump:saved")).toBe(shown);
  });

  it("formats the figures as money", async () => {
    // Given — an allocated share divides into a long recurring decimal, and a
    // raw hover reads out fourteen places of a euro
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 1.2345678901234, 2),
      }),
    );
    await ready(card);

    // Then
    const shown = hover(card, "slow_poll_aircon:paid");
    expect(shown).toMatch(/€/);
    expect(shown).not.toMatch(/\d[.,]\d{3}/);
  });

  it("calls a loss a loss", async () => {
    // Given — labelling a negative saving "Saved" would read as a gain (HEA-39)
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 5, 3),
      }),
    );
    await ready(card);

    // Then
    const shown = hover(card, "slow_poll_aircon:saved");
    expect(shown).not.toMatch(/Saved/);
    expect(shown).toMatch(/Lost.*€-?2[.,]00/);
  });

  it("says what the figure could honestly have been", async () => {
    // Given — a household that opted into per-device ranges
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: {
          ...bucketsFor("slow_poll_aircon", 10, 1.2, 2),
          ...boundsFor("slow_poll_aircon", 0.4, 2.1),
        },
      }),
    );
    await ready(card);

    // Then — a sentence, not a fourth figure: it qualifies what was paid rather
    // than adding to it, and the wording keeps an outer bound from reading as an
    // error bar (ADR-0016 decision 4)
    const shown = hover(card, "slow_poll_aircon:paid");
    expect(shown).toMatch(/Could be anywhere in/);
    expect(shown).toMatch(/0[.,]40/);
    expect(shown).toMatch(/2[.,]10/);
  });

  it("says nothing about a range the household does not publish", async () => {
    // Given — per-device ranges are opt-in, and the default is off
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then — silence, never "€0.00 – €0.00", which would claim exactness
    expect(hover(card, "slow_poll_aircon:paid")).not.toMatch(/anywhere in/);
  });

  it("says nothing for a series it cannot place", async () => {
    // Given — returning undefined suppresses the tooltip, where a half-built
    // one would render an empty box against the cursor
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.tooltip.formatter({ seriesId: "gone:paid" })).toBe(
      undefined,
    );
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

  it("hovers a bar rather than the whole category", async () => {
    // Given — the category holds every device, so an axis trigger answers for
    // all of them at once
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.tooltip.trigger).toBe("item");
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

describe("tinting a colour", () => {
  it("weakens a colour the palette gives it", () => {
    // Given / When / Then
    expect(tint("#0072b2", 0.22)).toBe("rgba(0, 114, 178, 0.22)");
  });

  it("takes the short hex a theme may be written in", () => {
    // Given / When / Then
    expect(tint("#1a3", 0.5)).toBe("rgba(17, 170, 51, 0.5)");
  });

  it("takes a colour a theme hands over already resolved", () => {
    // Given — Untracked and a loss take their colour from a CSS variable, and
    // a theme is free to write that as `rgb()` rather than as hex
    expect(tint("rgb(20, 30, 40)", 0.25)).toBe("rgba(20, 30, 40, 0.25)");
    expect(tint("rgba(20, 30, 40, 0.8)", 0.25)).toBe("rgba(20, 30, 40, 0.25)");
  });

  it("leaves a colour it cannot read alone rather than inventing one", () => {
    // Given — a named colour or a function we do not parse. Returning it
    // unchanged loses the fade; composing `rgba(NaN, NaN, NaN)` would lose
    // the bar.
    expect(tint("teal", 0.3)).toBe("teal");
    expect(tint("color-mix(in srgb, red, blue)", 0.3)).toBe(
      "color-mix(in srgb, red, blue)",
    );
  });
});
