/**
 * @vitest-environment happy-dom
 *
 * What each device cost over the period, as bars (HEA-50).
 *
 * One bar per device in that device's own colour, stacked: solid below is what
 * was paid, faded above is what was saved, and the whole bar is Cost at Grid
 * Price - the same meaning the over-time chart's bars carry, turned on its side
 * so devices can be compared against each other rather than against yesterday.
 *
 * `ha-chart-base` is Home Assistant's (ADR-0013) and is stubbed here, so what
 * is asserted is the contract we hand it - series and options - not pixels.
 * That contract is exact rather than approximate: the component ignores a
 * legend it does not recognise and silently draws none, so the shape it
 * requires is asserted here field by field.
 */

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { EARLIER_ID, TAG, register, tint } from "../hea-device-costs-card.js";
import { DEFAULTS as LABELS } from "../hea-labels.js";
import {
  aDeviceRow,
  aHass,
  anEnergyCollection,
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

afterEach(() => {
  // The layout tests stand up a screen size; left in place it would decide
  // which way every later test's bars ran.
  vi.unstubAllGlobals();
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

  it("offers an editor, so Home Assistant stops showing raw yaml", () => {
    // Given / When / Then - HEA-73; without one the user is asked to know that
    // a device is called `cloud_polled_pump`
    expect(customElements.get(TAG).getConfigElement()).toBeInstanceOf(HTMLElement);
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
    // Given - the outline carries the counterfactual and the fill carries the
    // spend, so the lighter space between them is the saving
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then - 3.00 paid of 4.00 at grid price, so 1.00 stands above it
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    expect(paid.data[0]).toBe(3.0);
    expect(saved.data[0]).toBe(1.0);
  });

  it("tints the saving rather than leaving it hollow", async () => {
    // Given - an empty box reads as absence; the saving is a quantity, and a
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
    // Given - stacked segments each carrying a border meet at the shared edge
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

    // Then - the outline and the fill beneath it are one colour at two
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

    // Then - a shared stack would pile every device into one column
    const [paid, saved] = deviceSeries(card, "cloud_polled_pump");
    const [otherPaid] = deviceSeries(card, "slow_poll_aircon");
    expect(paid.stack).toBe(saved.stack);
    expect(paid.stack).not.toBe(otherPaid.stack);
  });

  it("orders the dearest device first", async () => {
    // Given - "which device costs most" is the question the bars answer
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.legend.data[0].name).toBe("Cloud Polled Pump");
  });

  it("gives the Untracked remainder a colour of its own", async () => {
    // Given - it is not a device, and colouring it like one invites the reader
    // to hunt for an appliance that does not exist
    const card = mount(aHass({ devices: [AIRCON, UNTRACKED], response: THREE }));
    await ready(card);

    // Then
    const [, untracked] = deviceSeries(card, "untracked_energy_devices");
    const [, aircon] = deviceSeries(card, "slow_poll_aircon");
    expect(untracked.itemStyle.borderColor).not.toBe(aircon.itemStyle.borderColor);
  });

  it("keeps a loss below the axis and marks it apart from the device", async () => {
    // Given - battery arbitrage cost more than the grid would have (HEA-39)
    const saving = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 3, 5),
      }),
    );
    await ready(saving);
    const [, gained] = deviceSeries(saving, "slow_poll_aircon");
    const gainedOutline = gained.itemStyle.borderColor;

    // When - the same device, having lost rather than saved
    document.body.replaceChildren();
    const losing = mount(
      aHass({
        devices: [AIRCON],
        response: bucketsFor("slow_poll_aircon", 10, 5, 3),
      }),
    );
    await ready(losing);

    // Then - negative is how Home Assistant renders exported energy, and the
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

describe("comparing against an earlier period", () => {
  const comparing = async () => {
    const collection = anEnergyCollection();
    const hass = aHass({ devices: [AIRCON, PUMP], response: THREE, collection });
    const card = mount(hass);
    await ready(card);

    // One bucket in each window, so the data layer separates them by which
    // period it was asked for: the aircon cost EUR 0.50 now and EUR 1.70 then.
    const may = new Date(2026, 4, 20);
    const april = new Date(2026, 3, 1);
    hass.callWS = vi.fn().mockResolvedValue({
      ...THREE,
      "sensor.slow_poll_aircon_actual_cost": [
        { start: may.getTime(), change: 0.5 },
        { start: april.getTime(), change: 1.7 },
      ],
    });
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });
    await vi.waitFor(() =>
      expect(chartOf(card).data.some((s) => s.id.endsWith(":before"))).toBe(true),
    );
    return card;
  };

  it("draws no earlier bar when nobody asked to compare", async () => {
    // Given / When - the normal case
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - two series per device and no more
    expect(chartOf(card).data).toHaveLength(4);
    expect(chartOf(card).data.some((s) => s.id.endsWith(":before"))).toBe(false);
  });

  it("puts the earlier period beside each device, not on top of it", async () => {
    // Given / When
    const card = await comparing();

    // Then - a third series in a stack of its own. Its own stack is what makes
    // ECharts place it beside the device rather than piling it on: the two
    // segments that share `stack: device.key` are the parts of one bar, and an
    // earlier period is not a part of this one
    const before = chartOf(card).data.find(
      (s) => s.id === "slow_poll_aircon:before",
    );
    expect(before.data).toEqual([1.7]);
    expect(before.stack).not.toBe("slow_poll_aircon");
  });

  /** The legend entries that name a device, as against the period key. */
  const deviceEntries = (card) =>
    legendOf(card).data.filter((entry) => entry.id !== EARLIER_ID);

  it("keeps one legend entry per device, covering its earlier bar too", async () => {
    // Given / When
    const card = await comparing();

    // Then - still one entry per device, and clicking it hides every series
    // the device owns. An entry that missed the new one would leave a stray
    // bar behind when the user hid the device
    const entries = deviceEntries(card);
    expect(entries).toHaveLength(2);
    const ids = new Set(chartOf(card).data.map((s) => s.id));
    for (const entry of entries) {
      expect([entry.id, ...entry.secondaryIds].every((id) => ids.has(id))).toBe(true);
    }
    expect(
      entries.flatMap((e) => [e.id, ...e.secondaryIds]).length,
    ).toBe(ids.size);
  });

  it("says which bar is the earlier period", async () => {
    // Given - two adjacent bars in near-identical strengths of one hue read as
    // two devices long before they read as two periods, and the legend named
    // only the devices. The sibling over-time chart carries an "Earlier period"
    // entry on the same screen; this one carried nothing (HEA-99).
    // When
    const card = await comparing();

    // Then - the same words that card uses, from the same string
    const entry = legendOf(card).data.find((item) => item.id === EARLIER_ID);
    expect(entry.name).toBe(LABELS.compared_series);
  });

  it("hides every device's earlier bar together from that one entry", async () => {
    // Given / When - the component hides a legend entry's `id` plus its
    // `secondaryIds` as one set, so the entry has to name all of them
    const card = await comparing();

    // Then
    const entry = legendOf(card).data.find((item) => item.id === EARLIER_ID);
    const ghosts = chartOf(card)
      .data.filter((series) => series.id.endsWith(":before"))
      .map((series) => series.id);
    expect(ghosts).toHaveLength(2);
    expect(new Set(entry.secondaryIds)).toEqual(new Set(ghosts));
  });

  it("does not grey itself out when a single device is hidden", async () => {
    // Given - `ha-chart-base` marks an entry hidden by testing its *own* id
    // against the hidden set, not its secondaryIds. Every `:before` series is
    // already owned by its device's entry, so an "Earlier period" entry whose
    // id was one of them would grey out the moment that one device was hidden,
    // while the other devices' ghost bars stayed on the chart.
    const card = await comparing();

    // When - the ids hiding one device puts into the hidden set
    const aircon = deviceEntries(card).find((entry) =>
      entry.id.startsWith("slow_poll_aircon:"),
    );
    const hiddenByDevice = new Set([aircon.id, ...aircon.secondaryIds]);

    // Then - the period entry's own id is not among them, so it stays lit
    const entry = legendOf(card).data.find((item) => item.id === EARLIER_ID);
    expect(hiddenByDevice.has(entry.id)).toBe(false);
    expect(chartOf(card).data.some((series) => series.id === entry.id)).toBe(false);
  });

  it("offers no period entry when nobody asked to compare", async () => {
    // Given / When - the default, where there is only one period on the chart
    // and a key distinguishing it from nothing would be noise
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(legendOf(card).data.some((item) => item.id === EARLIER_ID)).toBe(false);
  });

  it("colours the tooltip's change by whether it is good news", async () => {
    // Given - the tooltip renders outside this card's shadow root, in the
    // chart component's own container, so the `.gain` / `.loss` rules cannot
    // reach it and the colour has to travel as an inline style (HEA-99).
    // When - the aircon cost EUR 1.20 less than the period before
    const card = await comparing();
    const shown = chartOf(card).options.tooltip.formatter({
      seriesId: "slow_poll_aircon:before",
    });

    // Then - a fall in what was paid is good news, and says so
    const change = [...shown.querySelectorAll("div")].find((row) =>
      row.textContent.startsWith(LABELS.change),
    );
    expect(change.textContent).toMatch(/[-−]\D*1[.,]20/);
    expect(change.querySelector("span:last-child").style.color).toBe("#4caf50");
  });

  it("answers for the device from its earlier bar as well", async () => {
    // Given / When - the tooltip resolves a device from the hovered series id,
    // and a new suffix it did not know would render nothing at all
    const card = await comparing();

    // Then
    const shown = chartOf(card).options.tooltip.formatter({
      seriesId: "slow_poll_aircon:before",
    }).textContent;
    expect(shown).toContain("Slow Poll Aircon");
    expect(shown).toMatch(/[-−]\D*1[.,]20/);
  });
});

describe("the legend", () => {
  it("puts the devices in the legend, not on the axis", async () => {
    // Given - fourteen device names along an axis is what made the first
    // attempt unreadable; Home Assistant's own charts name series in a legend
    // and leave the axis to the period
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - one category for the whole period, and the names in the legend
    expect(chartOf(card).options.xAxis.type).toBe("category");
    expect(chartOf(card).options.xAxis.data).toHaveLength(1);
    expect(legendOf(card).data.map((entry) => entry.name)).toEqual([
      "Cloud Polled Pump",
      "Slow Poll Aircon",
    ]);
  });

  it("asks for the legend in the only shape that renders one", async () => {
    // Given - `ha-chart-base` builds its legend from the first option that is
    // both `show` and `type: "custom"`, and silently draws none otherwise. A
    // custom legend omitting `show` is the defect this card shipped with.
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(legendOf(card).show).toBe(true);
    expect(legendOf(card).type).toBe("custom");
  });

  it("gives every device one legend entry, not one per segment", async () => {
    // Given - each device is drawn as two stacked series, which would
    // otherwise put its name in the legend twice
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).data).toHaveLength(4);
    expect(legendOf(card).data).toHaveLength(2);
  });

  it("names series that exist, so clicking an entry hides the device", async () => {
    // Given - the component hides by matching a legend entry's `id` against a
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
    // Given - the swatch is the key to the bar, and a wash of a colour is
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
    // Given - an axis tooltip lists every series at the category, which for a
    // dozen devices is two dozen rows, each device named twice with nothing
    // to say which row is the spend and which the saving
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - one device, its three figures, and the same answer from either
    // half of its bar
    const shown = hover(card, "cloud_polled_pump:paid");
    expect(shown).toContain("Cloud Polled Pump");
    expect(shown).not.toContain("Slow Poll Aircon");
    expect(shown).toMatch(/Paid.*€3[.,]00/);
    expect(shown).toMatch(/Saved.*€1[.,]00/);
    expect(shown).toMatch(/Would have paid.*€4[.,]00/);
    expect(hover(card, "cloud_polled_pump:saved")).toBe(shown);
  });

  it("formats the figures as money", async () => {
    // Given - an allocated share divides into a long recurring decimal, and a
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
    // Given - labelling a negative saving "Saved" would read as a gain (HEA-39)
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
    // Given - a household that opted into per-device ranges
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

    // Then - a sentence, not a fourth figure: it qualifies what was paid rather
    // than adding to it, and the wording keeps an outer bound from reading as an
    // error bar (ADR-0016 decision 4).
    //
    // It names its subject. The bounds bracket what was *paid* and nothing else
    // - `floor = kwh × min(blends)` over the actual blended price - so a bare
    // "Could be between…" beneath three figures left the reader to guess
    // which one it qualified (HEA-88)
    const shown = hover(card, "slow_poll_aircon:paid");
    expect(shown).toMatch(/What you paid could be between/);
    expect(shown).toMatch(/0[.,]40/);
    expect(shown).toMatch(/2[.,]10/);
  });

  it("says nothing about a range the household does not publish", async () => {
    // Given - per-device ranges are opt-in, and the default is off
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then - silence, never "€0.00 - €0.00", which would claim exactness
    expect(hover(card, "slow_poll_aircon:paid")).not.toMatch(/between/);
  });

  it("says nothing for a series it cannot place", async () => {
    // Given - returning undefined suppresses the tooltip, where a half-built
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
    // Given - the category holds every device, so an axis trigger answers for
    // all of them at once
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.tooltip.trigger).toBe("item");
  });

  it("says so when no device recorded anything in the period", async () => {
    // Given - a range earlier than any recorded statistic. Bars of nothing read
    // as "it cost nothing", which is a different claim from "there is nothing
    // here", and every configured device still yields a row.
    const card = mount(aHass({ devices: [AIRCON], response: {} }));
    await ready(card);

    // Then
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
    expect(chartOf(card)).toBe(null);
  });
});

describe("laid out sideways", () => {
  const sideways = async (devices = [AIRCON, PUMP], response = THREE) => {
    const card = mount(aHass({ devices, response }), { layout: "horizontal" });
    await ready(card);
    return card;
  };
  const seriesOf = (card, id) => chartOf(card).data.find((s) => s.id === id);
  const rowsOf = (card) => chartOf(card).options.yAxis.data;
  const pointFor = (card, id, name) =>
    seriesOf(card, id).data[rowsOf(card).indexOf(name)];

  it("puts the devices on the axis and the value along the bottom", async () => {
    // Given / When - names overlap on a *vertical* category axis, which is why
    // they sit in the legend by default. Turned on its side each name is a row
    // label with a row to itself, and the premise is gone (HEA-100)
    const card = await sideways();

    // Then - dearest at the top, and the axis inverted to make first topmost:
    // a category axis counts up from the bottom and would otherwise stand the
    // ranking on its head
    expect(chartOf(card).options.yAxis.type).toBe("category");
    expect(rowsOf(card)).toEqual(["Cloud Polled Pump", "Slow Poll Aircon"]);
    expect(chartOf(card).options.yAxis.inverse).toBe(true);
    expect(chartOf(card).options.xAxis.type).toBe("value");
  });

  it("keeps each device's own colour, carried on the point", async () => {
    // Given - two series hold every device here, so a colour on the series
    // would encode Paid and Saved and every device would share one hue. That
    // would cost the palette and its link to the Sankey's device colours
    const card = await sideways();

    // Then
    const pump = pointFor(card, "paid", "Cloud Polled Pump");
    const aircon = pointFor(card, "paid", "Slow Poll Aircon");
    expect(channelsOf(pump.itemStyle.color)).not.toBe(
      channelsOf(aircon.itemStyle.color),
    );
    expect(seriesOf(card, "paid").itemStyle).toBeUndefined();
  });

  it("stacks the spend and the saving, and sets the earlier period beside them", async () => {
    // Given / When
    const card = await sideways();

    // Then - one stack, so a device's bar runs to Would have paid
    expect(seriesOf(card, "paid").stack).toBe(seriesOf(card, "saved").stack);
    expect(pointFor(card, "paid", "Cloud Polled Pump").value).toBe(3.0);
    expect(pointFor(card, "saved", "Cloud Polled Pump").value).toBe(1.0);
  });

  it("takes its height from the device count, not the viewport", async () => {
    // Given - fifteen devices need fifteen rows whatever the screen is, which
    // is what no clamp can know
    const few = await sideways();
    const shortest = Number.parseInt(chartOf(few).height, 10);

    // When - ten devices instead of two
    document.body.replaceChildren();
    const many = Array.from({ length: 10 }, (_, index) =>
      aDeviceRow(`tracked_device_${index}`, `Tracked Device ${index}`),
    );
    const card = await sideways(
      many,
      Object.assign(
        {},
        ...many.map((device, index) =>
          bucketsFor(device.key, 10, index + 1, index + 2),
        ),
      ),
    );

    // Then
    expect(Number.parseInt(chartOf(card).height, 10)).toBeGreaterThan(shortest);
    expect(chartOf(card).height).toMatch(/^\d+px$/);
  });

  it("keeps a small household off a sliver of a card", async () => {
    // Given / When - two devices would otherwise ask for two rows and little
    // else, which reads as a broken card rather than a short list
    const card = await sideways();

    // Then
    expect(Number.parseInt(chartOf(card).height, 10)).toBeGreaterThanOrEqual(240);
  });

  it("pulls the plot out to the edges of the card", async () => {
    // Given - ECharts' default margins leave roughly 80px above and 90px below,
    // which on a card sized to its own rows is dead space rather than breathing
    // room. `containLabel` still keeps names of any length inside
    const card = await sideways();

    // Then
    expect(chartOf(card).options.grid).toMatchObject({
      top: 8,
      containLabel: true,
    });
    expect(chartOf(card).options.grid.bottom).toBeLessThan(40);
  });

  it("offers no legend at all when nobody asked to compare", async () => {
    // Given / When - the names are on the axis, so there is nothing left for a
    // legend to index
    const card = await sideways();

    // Then
    expect(chartOf(card).options.legend).toBeUndefined();
  });

  it("labels the money axis in the household's currency", async () => {
    // Given / When - the value axis swaps sides with the layout, and a bare
    // number on it would say nothing about what was being counted
    const card = await sideways();

    // Then
    const label = chartOf(card).options.xAxis.axisLabel.formatter(3);
    expect(label).toMatch(/^€\s?3([.,]00)?$/);
  });

  it("names the ghost series outright when comparing", async () => {
    // Given - one ghost series rather than one per device, so the entry's id
    // can simply be it: nothing to fan out to through `secondaryIds`, and no
    // sentinel needed to stop the key greying itself out with one device
    const collection = anEnergyCollection();
    const hass = aHass({ devices: [AIRCON, PUMP], response: THREE, collection });
    const card = mount(hass, { layout: "horizontal" });
    await ready(card);

    // When
    const may = new Date(2026, 4, 20);
    hass.callWS = vi.fn().mockResolvedValue({
      ...THREE,
      "sensor.slow_poll_aircon_actual_cost": [
        { start: may.getTime(), change: 0.5 },
        { start: new Date(2026, 3, 1).getTime(), change: 1.7 },
      ],
    });
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });

    // Then - one entry, and its id resolves to a real series, which is what
    // the component hides by
    await vi.waitFor(() => expect(chartOf(card).options.legend).toBeDefined());
    const [entry] = chartOf(card).options.legend.data;
    expect(chartOf(card).options.legend.data).toHaveLength(1);
    expect(entry.name).toBe(LABELS.compared_series);
    expect(entry.secondaryIds).toBeUndefined();
    expect(chartOf(card).data.some((s) => s.id === entry.id)).toBe(true);
  });

  it("answers the tooltip from the row rather than the series", async () => {
    // Given - every series holds every device, so which device was hovered is
    // the data index and nothing else
    const card = await sideways();

    // When
    const shown = chartOf(card).options.tooltip.formatter({
      dataIndex: rowsOf(card).indexOf("Cloud Polled Pump"),
    }).textContent;

    // Then
    expect(shown).toContain("Cloud Polled Pump");
    expect(shown).not.toContain("Slow Poll Aircon");
    expect(shown).toMatch(/Paid.*€3[.,]00/);
  });

  it("stands the bars up when a household asks for it", async () => {
    // Given / When - vertical keeps the legend, and with it the only way to
    // hide a device and see the rest against each other
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }), {
      layout: "vertical",
    });
    await ready(card);

    // Then
    expect(chartOf(card).options.xAxis.type).toBe("category");
    expect(legendOf(card).data).toHaveLength(2);
  });
});

describe("choosing a layout by the screen", () => {
  const withScreen = (matches) =>
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches,
        addEventListener() {},
        removeEventListener() {},
      }),
    );
  const axisOf = (card) => chartOf(card).options.xAxis.type;

  it("lays the bars down on a phone, unasked", async () => {
    // Given - measured at 500px card width with fifteen devices, the standing
    // chart is not merely cramped: 156px of plot has to carry a value axis too,
    // so the bars compress to about 20px and the axis labels collapse into an
    // illegible smudge. A household should not have to know the option exists
    // to avoid that (HEA-100)
    withScreen(true);

    // When - no layout configured at all
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - sideways, where the same fifteen devices read cleanly
    expect(axisOf(card)).toBe("value");
    expect(chartOf(card).options.legend).toBeUndefined();
  });

  it("stands them up on a wide screen, where the toggles are free", async () => {
    // Given - the trade-off only exists where both are readable, and there the
    // legend's click-to-hide is worth having
    withScreen(false);

    // When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(axisOf(card)).toBe("category");
    expect(legendOf(card).data).toHaveLength(2);
  });

  it("honours a household that has chosen, whatever the screen", async () => {
    // Given - a choice is a choice; `auto` is only what happens absent one
    withScreen(true);

    // When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }), {
      layout: "vertical",
    });
    await ready(card);

    // Then - standing up on a phone, because that is what was asked for
    expect(axisOf(card)).toBe("category");
  });

  it("turns itself over when the window crosses the breakpoint", async () => {
    // Given - `auto` is answered when the card renders, and a resize is not a
    // render. Asked once and never again, the card picks a layout on load and
    // then holds it however the window changes, which reads as `auto` doing
    // nothing at all (HEA-100)
    const listeners = [];
    const screen = {
      matches: false,
      addEventListener: (_, handler) => listeners.push(handler),
      removeEventListener: () => {},
    };
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(screen));
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);
    expect(axisOf(card)).toBe("category");

    // When - the window narrows past the breakpoint
    screen.matches = true;
    for (const handler of listeners) handler();

    // Then - sideways, without waiting for a period change to redraw it
    await vi.waitFor(() => expect(axisOf(card)).toBe("value"));
  });

  it("stops listening once it leaves the page", async () => {
    // Given - a card removed from a view that went on answering resize events
    // would redraw a detached element for as long as the tab lived
    const removed = [];
    const screen = {
      matches: false,
      addEventListener: () => {},
      removeEventListener: (_, handler) => removed.push(handler),
    };
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(screen));
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // When
    card.remove();

    // Then
    expect(removed).toHaveLength(1);
  });

  it("stands them up where the browser cannot answer", async () => {
    // Given - `matchMedia` is not universally present, and an unknown screen
    // size is not a reason to give up the legend and its toggles
    vi.stubGlobal("matchMedia", undefined);

    // When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(axisOf(card)).toBe("category");
  });

  it("asks the screen for a layout it does not offer", async () => {
    // Given - a hand-edited dashboard yaml. Anything unrecognised is no choice
    // at all, so it falls to the same question as no choice
    withScreen(true);

    // When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }), {
      layout: "diagonal",
    });
    await ready(card);

    // Then
    expect(axisOf(card)).toBe("value");
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
    // Given - Untracked and a loss take their colour from a CSS variable, and
    // a theme is free to write that as `rgb()` rather than as hex
    expect(tint("rgb(20, 30, 40)", 0.25)).toBe("rgba(20, 30, 40, 0.25)");
    expect(tint("rgba(20, 30, 40, 0.8)", 0.25)).toBe("rgba(20, 30, 40, 0.25)");
  });

  it("leaves a colour it cannot read alone rather than inventing one", () => {
    // Given - a named colour or a function we do not parse. Returning it
    // unchanged loses the fade; composing `rgba(NaN, NaN, NaN)` would lose
    // the bar.
    expect(tint("teal", 0.3)).toBe("teal");
    expect(tint("color-mix(in srgb, red, blue)", 0.3)).toBe(
      "color-mix(in srgb, red, blue)",
    );
  });
});
