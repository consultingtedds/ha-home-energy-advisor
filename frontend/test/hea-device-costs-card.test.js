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

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

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

const seriesOf = (card, id) => chartOf(card).data.find((series) => series.id === id);

/** The device names down the axis, dearest first. */
const rowsOf = (card) => chartOf(card).options.yAxis.data;

/**
 * One device's point in one series.
 *
 * Every series now holds every device, so a device is a position rather than a
 * series of its own - which is the whole shape of the change (HEA-100). Found
 * by name through the axis, never by a fixed index, so a test cannot pass by
 * agreeing with the card about an ordering neither of them checked.
 */
const pointFor = (card, id, name) =>
  seriesOf(card, id).data[rowsOf(card).indexOf(name)];

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

    // Then - 3.00 paid of 4.00 at grid price, so 1.00 stands beyond it
    expect(pointFor(card, "paid", "Cloud Polled Pump").value).toBe(3.0);
    expect(pointFor(card, "saved", "Cloud Polled Pump").value).toBe(1.0);
  });

  it("tints the saving rather than leaving it hollow", async () => {
    // Given - an empty box reads as absence; the saving is a quantity, and a
    // wash of the device's own colour says so while still ranking below the
    // spend it sits on
    const card = mount(aHass({ devices: [PUMP], response: THREE }));
    await ready(card);

    // Then
    const paid = pointFor(card, "paid", "Cloud Polled Pump");
    const saved = pointFor(card, "saved", "Cloud Polled Pump");
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
    expect(
      pointFor(card, "paid", "Cloud Polled Pump").itemStyle.borderWidth,
    ).toBeFalsy();
    expect(
      pointFor(card, "saved", "Cloud Polled Pump").itemStyle.borderWidth,
    ).toBeGreaterThan(0);
  });

  it("draws each device in a hue of its own", async () => {
    // Given - two series now hold every device, so the colour has to travel on
    // each point. Carried on the series instead it would encode Paid and Saved,
    // and every device on the chart would share one colour - which is what the
    // palette exists to prevent (HEA-100)
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - the outline and the fill beneath it are one colour at two
    // strengths, and the next device does not borrow it
    const paid = pointFor(card, "paid", "Cloud Polled Pump");
    const saved = pointFor(card, "saved", "Cloud Polled Pump");
    expect(channelsOf(saved.itemStyle.color)).toBe(
      channelsOf(tint(saved.itemStyle.borderColor, 1)),
    );
    expect(channelsOf(paid.itemStyle.color)).toBe(
      channelsOf(saved.itemStyle.color),
    );
    const otherPaid = pointFor(card, "paid", "Slow Poll Aircon");
    expect(channelsOf(otherPaid.itemStyle.color)).not.toBe(
      channelsOf(paid.itemStyle.color),
    );
  });

  it("stacks the spend and the saving into one bar per device", async () => {
    // Given / When
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - one stack, so a device's bar runs to Would have paid. Devices are
    // separated by their row on the axis now, not by a stack of their own
    expect(seriesOf(card, "paid").stack).toBe(seriesOf(card, "saved").stack);
  });

  it("puts the dearest device at the top", async () => {
    // Given - "which device costs most" is the question the bars answer
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - first in the axis data, and the axis inverted so first reads as
    // topmost: a category axis counts up from the bottom and would otherwise
    // stand the ranking on its head
    expect(rowsOf(card)[0]).toBe("Cloud Polled Pump");
    expect(chartOf(card).options.yAxis.inverse).toBe(true);
  });

  it("gives the Untracked remainder a colour of its own", async () => {
    // Given - it is not a device, and colouring it like one invites the reader
    // to hunt for an appliance that does not exist
    const card = mount(aHass({ devices: [AIRCON, UNTRACKED], response: THREE }));
    await ready(card);

    // Then
    expect(pointFor(card, "saved", "Untracked").itemStyle.borderColor).not.toBe(
      pointFor(card, "saved", "Slow Poll Aircon").itemStyle.borderColor,
    );
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
    const gainedOutline = pointFor(saving, "saved", "Slow Poll Aircon").itemStyle
      .borderColor;

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
    const lost = pointFor(losing, "saved", "Slow Poll Aircon");
    expect(lost.value).toBe(-2);
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
      expect(chartOf(card).data.some((s) => s.id === EARLIER_ID)).toBe(true),
    );
    return card;
  };

  it("draws no earlier bar when nobody asked to compare", async () => {
    // Given / When - the normal case
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - the spend and the saving, whatever the device count, and no more
    expect(chartOf(card).data).toHaveLength(2);
    expect(chartOf(card).data.some((s) => s.id === EARLIER_ID)).toBe(false);
  });

  it("puts the earlier period beside each device, not on top of it", async () => {
    // Given / When
    const card = await comparing();

    // Then - a third series in a stack of its own, which is what makes ECharts
    // set it beside the device's bar rather than piling it on: the two
    // segments sharing the cost stack are parts of one bar, and an earlier
    // period is not a part of this one
    expect(pointFor(card, EARLIER_ID, "Slow Poll Aircon").value).toBe(1.7);
    expect(seriesOf(card, EARLIER_ID).stack).not.toBe(seriesOf(card, "paid").stack);
  });

  it("reports a device with no earlier bucket as having spent nothing then", async () => {
    // Given / When - the pump has no bucket in the earlier window, only the
    // aircon does
    const card = await comparing();

    // Then - zero, not absent. Both windows are fetched for the same device
    // list, so every row comes back with an earlier self and a device that did
    // not run reads as zero - the same deliberate choice the devices table
    // makes, where statistics cannot tell "did not run" from "was not tracked
    // yet" and the first is far the commoner
    expect(pointFor(card, EARLIER_ID, "Cloud Polled Pump").value).toBe(0);
  });

  it("says which bar is the earlier period", async () => {
    // Given - two adjacent bars in near-identical strengths of one hue read as
    // two devices long before they read as two periods. The sibling over-time
    // chart carries an "Earlier period" entry on the same screen (HEA-99).
    // When
    const card = await comparing();

    // Then - the same words that card uses, from the same string
    const entry = legendOf(card).data.find((item) => item.id === EARLIER_ID);
    expect(entry.name).toBe(LABELS.compared_series);
  });

  it("names the ghost series outright, with nothing to fan out to", async () => {
    // Given - there is one ghost series now rather than one per device, so the
    // entry's id can simply be it. The `secondaryIds` fan-out existed only to
    // gather a device's several series, and the sentinel id existed only so
    // this key would not grey itself out when one device was hidden - both are
    // gone with the thing that needed them (HEA-100)
    const card = await comparing();

    // When
    const entry = legendOf(card).data.find((item) => item.id === EARLIER_ID);

    // Then - the id resolves to a real series, which is what the component
    // hides by
    expect(entry.secondaryIds).toBeUndefined();
    expect(chartOf(card).data.some((series) => series.id === entry.id)).toBe(true);
  });

  it("offers no legend at all when nobody asked to compare", async () => {
    // Given / When - the default. One entry per device cost 164px of a 305px
    // card and left 141px of chart; with the names on the axis there is
    // nothing left for a legend to say (HEA-100)
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.legend).toBeUndefined();
  });

  it("carries exactly one entry while comparing", async () => {
    // Given / When
    const card = await comparing();

    // Then - a legend of one is worth its 24px; a legend of fifteen was not
    expect(legendOf(card).data).toHaveLength(1);
  });

  it("colours the tooltip's change by whether it is good news", async () => {
    // Given - the tooltip renders outside this card's shadow root, in the
    // chart component's own container, so the `.gain` / `.loss` rules cannot
    // reach it and the colour has to travel as an inline style (HEA-99).
    // When - the aircon cost EUR 1.20 less than the period before
    const card = await comparing();
    const shown = chartOf(card).options.tooltip.formatter({
      dataIndex: rowsOf(card).indexOf("Slow Poll Aircon"),
    });

    // Then - a fall in what was paid is good news, and says so
    const change = [...shown.querySelectorAll("div")].find((row) =>
      row.textContent.startsWith(LABELS.change),
    );
    expect(change.textContent).toMatch(/[-−]\D*1[.,]20/);
    expect(change.querySelector("span:last-child").style.color).toBe("#4caf50");
  });

  it("answers for the device whichever of its bars is hovered", async () => {
    // Given / When - every series holds every device now, so the row is what
    // identifies the device and the series hovered does not matter
    const card = await comparing();
    const row = rowsOf(card).indexOf("Slow Poll Aircon");

    // Then
    const shown = chartOf(card).options.tooltip.formatter({ dataIndex: row })
      .textContent;
    expect(shown).toContain("Slow Poll Aircon");
    expect(shown).toMatch(/[-−]\D*1[.,]20/);
  });
});

describe("naming the devices", () => {
  it("puts the devices on the axis, not in a legend", async () => {
    // Given - the reverse of what this card first did, and for a reason that
    // only holds one way round. Names along a *vertical* axis overlap into
    // illegibility, which is why they went to the legend; turned on its side
    // each name is a row label with a whole row to itself (HEA-100)
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - dearest first, down the side
    expect(chartOf(card).options.yAxis.type).toBe("category");
    expect(rowsOf(card)).toEqual(["Cloud Polled Pump", "Slow Poll Aircon"]);
  });

  it("runs the value along the bottom", async () => {
    // Given / When - the axes swap with the bars
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.xAxis.type).toBe("value");
  });

  it("leaves room for names the household wrote", async () => {
    // Given - how wide a name is cannot be known here: it is whatever was
    // typed into the device registry. Measuring it is the chart's job, and
    // without being told to, it will crop them
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(chartOf(card).options.grid.containLabel).toBe(true);
  });

  it("asks for the legend in the only shape that renders one", async () => {
    // Given - `ha-chart-base` builds its legend from the first option that is
    // both `show` and `type: "custom"`, and silently draws none otherwise. A
    // custom legend omitting `show` is a defect this card has shipped before,
    // and the one remaining entry still has to satisfy it.
    const collection = anEnergyCollection();
    const hass = aHass({ devices: [AIRCON, PUMP], response: THREE, collection });
    const card = mount(hass);
    await ready(card);

    // When - the only case that draws a legend at all
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

    // Then
    await vi.waitFor(() => expect(legendOf(card)).toBeDefined());
    expect(legendOf(card).show).toBe(true);
    expect(legendOf(card).type).toBe("custom");
  });
});

describe("how tall the card stands", () => {
  /** Ten devices, which is nearer the fourteen the reference instance tracks. */
  const TEN = Array.from({ length: 10 }, (_, index) =>
    aDeviceRow(`tracked_device_${index}`, `Tracked Device ${index}`),
  );
  const TEN_RESPONSE = Object.assign(
    {},
    ...TEN.map((device, index) =>
      bucketsFor(device.key, 10, index + 1, index + 2),
    ),
  );

  it("takes a row per device rather than a share of the screen", async () => {
    // Given - fifteen devices need fifteen rows whatever the screen is. The
    // base class's viewport clamp is right for a chart against time and wrong
    // for one against categories, which is why it is overridable (HEA-100)
    const few = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(few);
    const shortest = Number.parseInt(chartOf(few).height, 10);

    // When - the same card carrying ten devices instead of two
    document.body.replaceChildren();
    const many = mount(aHass({ devices: TEN, response: TEN_RESPONSE }));
    await ready(many);

    // Then - taller, because it has more rows to draw. A height that ignored
    // the count is what let fifteen devices squeeze into a 141px plot
    expect(Number.parseInt(chartOf(many).height, 10)).toBeGreaterThan(shortest);
    expect(chartOf(many).height).toMatch(/^\d+px$/);
  });

  it("keeps a small household off a sliver of a card", async () => {
    // Given / When - two devices would otherwise ask for two rows and little
    // else, which reads as a broken card rather than a short list
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then
    expect(Number.parseInt(chartOf(card).height, 10)).toBeGreaterThanOrEqual(240);
  });
});

describe("the tooltip", () => {
  /** Hover a device's row, which is what identifies it now. */
  const hover = (card, name) =>
    chartOf(card).options.tooltip.formatter({
      dataIndex: rowsOf(card).indexOf(name),
    }).textContent;

  it("answers for the whole device, whichever segment is hovered", async () => {
    // Given - an axis tooltip lists every series at the category, which for a
    // dozen devices is two dozen rows, each device named twice with nothing
    // to say which row is the spend and which the saving
    const card = mount(aHass({ devices: [AIRCON, PUMP], response: THREE }));
    await ready(card);

    // Then - one device and its three figures. Both halves of a bar share a
    // row, so both resolve to the same device without the tooltip having to
    // know which series was under the cursor
    const shown = hover(card, "Cloud Polled Pump");
    expect(shown).toContain("Cloud Polled Pump");
    expect(shown).not.toContain("Slow Poll Aircon");
    expect(shown).toMatch(/Paid.*€3[.,]00/);
    expect(shown).toMatch(/Saved.*€1[.,]00/);
    expect(shown).toMatch(/Would have paid.*€4[.,]00/);
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
    const shown = hover(card, "Slow Poll Aircon");
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
    const shown = hover(card, "Slow Poll Aircon");
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
    const shown = hover(card, "Slow Poll Aircon");
    expect(shown).toMatch(/What you paid could be between/);
    expect(shown).toMatch(/0[.,]40/);
    expect(shown).toMatch(/2[.,]10/);
  });

  it("says nothing about a range the household does not publish", async () => {
    // Given - per-device ranges are opt-in, and the default is off
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then - silence, never "€0.00 - €0.00", which would claim exactness
    expect(hover(card, "Slow Poll Aircon")).not.toMatch(/between/);
  });

  it("says nothing for a row it cannot place", async () => {
    // Given - returning undefined suppresses the tooltip, where a half-built
    // one would render an empty box against the cursor
    const card = mount(aHass({ devices: [AIRCON], response: THREE }));
    await ready(card);

    // Then - one device on the chart, so there is no second row to hover
    expect(chartOf(card).options.tooltip.formatter({ dataIndex: 7 })).toBe(
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
    const label = chartOf(card).options.xAxis.axisLabel.formatter(3);
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
