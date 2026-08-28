/**
 * @vitest-environment happy-dom
 *
 * The stacked bar (HEA-50, ADR-0012): the whole bar is Cost at Grid Price, the
 * lower segment what was actually paid and the upper what was saved.
 *
 * It is drawn by Home Assistant's `ha-chart-base` (ADR-0013), which is theirs
 * and never defined in these tests. What is asserted is therefore the contract
 * we hand it - the series and options - not pixels. A chart that draws a
 * convincing picture from the wrong arithmetic is the failure worth catching,
 * and that shows up in the series values.
 */

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { TAG, register } from "../hea-cost-over-time-card.js";
import { formatMoney, formatPeriod } from "../hea-format.js";
import { DEFAULTS as LABELS } from "../hea-labels.js";
import {
  aDeviceRow,
  aHass,
  anEnergyCollection,
  mountCard,
  settled,
} from "./doubles.js";

const EURO = { language: "en-GB", currency: "EUR" };

const DAY_ONE = new Date(2026, 4, 20);
const DAY_TWO = new Date(2026, 4, 21);

const AIRCON = [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")];

/** Two days: paid 1 of 3, then paid 2 of 3. */
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

/** Battery arbitrage costing more than the grid would have (HEA-39). */
const aLoss = {
  "sensor.slow_poll_aircon_energy_used": [{ start: DAY_ONE.getTime(), change: 10 }],
  "sensor.slow_poll_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 5 }],
  "sensor.slow_poll_aircon_cost_at_grid_price": [{ start: DAY_ONE.getTime(), change: 3 }],
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
    // Given / When / Then - one shared editor (HEA-73)
    expect(customElements.get(TAG).getConfigElement()).toBeInstanceOf(HTMLElement);
  });
});

describe("the card header", () => {
  const headerOf = (card) =>
    card.shadowRoot.querySelector("ha-card").getAttribute("header");

  it("names itself, so a chart on a dashboard says what it shows", async () => {
    // Given - a card added with no configuration at all, which is how the
    // picker adds it
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - a bare chart of coloured bars says nothing about what is being
    // measured; the legend names the segments but not the subject
    expect(headerOf(card)).toBe("Cost over time");
  });

  it("lets the household title it themselves", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }), {
      title: "Aircon spend",
    });
    await ready(card);

    // Then
    expect(headerOf(card)).toBe("Aircon spend");
  });

  it("takes an empty title as a deliberate request for no header", async () => {
    // Given - a user stacking several cards under one heading of their own
    const card = mount(aHass({ devices: AIRCON, response: twoDays }), {
      title: "",
    });
    await ready(card);

    // Then - absent means "use the default"; empty means "show nothing"
    expect(headerOf(card)).toBe(null);
  });
});

describe("the series handed to the chart", () => {
  it("stacks what was paid and what was saved into one bar", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - one stack, so the two segments sum to Cost at Grid Price
    expect(seriesOf(card, "paid").stack).toBe("cost");
    expect(seriesOf(card, "saved").stack).toBe(seriesOf(card, "paid").stack);
    expect(seriesOf(card, "paid").type).toBe("bar");
  });

  it("carries each bucket's figures, oldest first", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - day one paid 1 of 3, day two paid 2 of 3
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
    // Given - paid 5 where the grid would have cost 3
    const card = mount(aHass({ devices: AIRCON, response: aLoss }));
    await ready(card);

    // When
    const [point] = seriesOf(card, "saved").data;

    // Then - negative is how Home Assistant renders exported energy, and
    // ECharts stacks it downwards (ADR-0012 decision 3)
    expect(point.value).toEqual([DAY_ONE.getTime(), -2]);
  });

  it("colours a loss differently from a saving", async () => {
    // Given - the one figure a user must not misread as a gain
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

describe("comparing against an earlier period", () => {
  it("draws no earlier line when nobody asked to compare", async () => {
    // Given / When - the normal case
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - the two stacked bars and nothing else
    expect(chartOf(card).data).toHaveLength(2);
    expect(chartOf(card).data.every((s) => s.type === "bar")).toBe(true);
  });

  /** A week earlier, so the response carries buckets in both windows. */
  const WEEK_BEFORE = new Date(DAY_ONE.getTime() - 7 * 86400000);

  /**
   * Both windows in one response, with Paid and Would have paid far enough
   * apart in the earlier one that a line drawn from either is distinguishable.
   * A fixture where the two agreed could not fail whichever the card plotted.
   */
  const bothWindows = {
    "sensor.slow_poll_aircon_energy_used": [
      { start: DAY_ONE.getTime(), change: 10 },
      { start: WEEK_BEFORE.getTime(), change: 14 },
    ],
    "sensor.slow_poll_aircon_actual_cost": [
      { start: DAY_ONE.getTime(), change: 1 },
      { start: WEEK_BEFORE.getTime(), change: 4 },
    ],
    "sensor.slow_poll_aircon_cost_at_grid_price": [
      { start: DAY_ONE.getTime(), change: 3 },
      { start: WEEK_BEFORE.getTime(), change: 6 },
    ],
  };

  /**
   * A sunny earlier day, which is where the two quantities part company: the
   * generation covered the draw, so nothing was paid for it, while at grid
   * price the same energy would have cost EUR 1.14 (HEA-99, measured on the
   * reference instance). Overnight the two nearly coincide and nothing is
   * visibly wrong; from mid-morning on they diverge completely.
   */
  const solarEarlierDay = {
    "sensor.slow_poll_aircon_energy_used": [
      { start: DAY_ONE.getTime(), change: 10 },
      { start: WEEK_BEFORE.getTime(), change: 4.9 },
    ],
    "sensor.slow_poll_aircon_actual_cost": [
      { start: DAY_ONE.getTime(), change: 1 },
      { start: WEEK_BEFORE.getTime(), change: 0 },
    ],
    "sensor.slow_poll_aircon_cost_at_grid_price": [
      { start: DAY_ONE.getTime(), change: 3 },
      { start: WEEK_BEFORE.getTime(), change: 1.14 },
    ],
  };

  const comparing = async (response = bothWindows) => {
    const collection = anEnergyCollection();
    const hass = aHass({ devices: AIRCON, response, collection });
    const card = mount(hass);
    await ready(card);

    collection.announce(DAY_ONE, new Date(DAY_ONE.getTime() + 2 * 86400000), {
      startCompare: WEEK_BEFORE,
      endCompare: new Date(WEEK_BEFORE.getTime() + 2 * 86400000),
      compareMode: "previous",
    });
    await vi.waitFor(() =>
      expect(chartOf(card).data.some((s) => s.id === "before")).toBe(true),
    );
    return card;
  };

  it("draws the earlier period as a line over the bars, not more stack", async () => {
    // Given - the bars already stack Paid and Saved to make Would have paid.
    // A third bar in that stack would stop the total meaning anything, so the
    // comparison is drawn over them instead of inside them.
    // When
    const card = await comparing();

    // Then
    const before = chartOf(card).data.find((s) => s.id === "before");
    expect(before.type).toBe("line");
    expect(before.stack).toBeUndefined();
  });

  it("plots the earlier period over the current axis, not off to its left", async () => {
    // Given / When - a chart against time would put a week-old bucket a week
    // to the left of everything drawn, where nobody would ever see it
    const card = await comparing();

    // Then - the earlier bucket lands on the current period's first day
    const before = chartOf(card).data.find((s) => s.id === "before");
    expect(before.data).toEqual([[DAY_ONE.getTime(), 6]]);
  });

  it("traces the earlier period's Would have paid, which is what a bar's height means", async () => {
    // Given - the eye reads a line against the top of a bar, not against a
    // segment boundary inside it, and the top of these bars is Would have paid.
    // A line drawn from the earlier period's Paid compares a different quantity
    // from the one the reader is measuring it against (HEA-99).
    // When
    const card = await comparing(solarEarlierDay);

    // Then - EUR 1.14, the outline the bars mean, not the EUR 0.00 that was
    // paid on a day the sun covered the draw
    expect(seriesOf(card, "before").data).toEqual([[DAY_ONE.getTime(), 1.14]]);
  });

  it("lands the line on the top of the bars when the two periods match", async () => {
    // Given - a week that repeated itself exactly. Two identical periods are
    // the case where "compares like with like" is checkable without naming a
    // field: the line has to sit on the bars' full height, and a line drawn
    // from Paid would sit at the segment boundary two thirds of the way down.
    const repeatedWeek = {
      "sensor.slow_poll_aircon_energy_used": [
        { start: DAY_ONE.getTime(), change: 10 },
        { start: WEEK_BEFORE.getTime(), change: 10 },
      ],
      "sensor.slow_poll_aircon_actual_cost": [
        { start: DAY_ONE.getTime(), change: 1 },
        { start: WEEK_BEFORE.getTime(), change: 1 },
      ],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: DAY_ONE.getTime(), change: 3 },
        { start: WEEK_BEFORE.getTime(), change: 3 },
      ],
    };

    // When
    const card = await comparing(repeatedWeek);

    // Then - the bars' height is Paid plus Saved, and the line is on it
    const [[, paid]] = seriesOf(card, "paid").data;
    const [[, saved]] = seriesOf(card, "saved").data;
    const [[, line]] = seriesOf(card, "before").data;
    expect(line).toBe(paid + saved);
  });

  it("wears the same caption naming both windows as every other card", async () => {
    // Given - the comparison read four different ways on one screen because it
    // was built card by card. The caption is the shared base's, so this asserts
    // a chart card really is served by it rather than that the base works
    // (HEA-99).
    const card = await comparing();

    // When
    const period = { start: DAY_ONE, end: new Date(DAY_ONE.getTime() + 2 * 86400000) };
    const compared = {
      start: WEEK_BEFORE,
      end: new Date(WEEK_BEFORE.getTime() + 2 * 86400000),
    };

    // Then
    expect(card.shadowRoot.querySelector(".period").textContent).toBe(
      `${formatPeriod(period, EURO)} vs ${formatPeriod(compared, EURO)}`,
    );
  });

  it("gives the earlier line a legend entry that can hide it", async () => {
    // Given - every series in this chart is nameable and hideable; one that
    // was not would be the only thing on the card a user could not turn off
    // When
    const card = await comparing();

    // Then
    expect(chartOf(card).options.legend.data).toHaveLength(3);
    const ids = new Set(chartOf(card).data.map((s) => s.id));
    expect(
      chartOf(card).options.legend.data.every((entry) => ids.has(entry.id)),
    ).toBe(true);
  });
});

describe("the legend", () => {
  const legendOf = (card) => chartOf(card).options.legend;

  it("asks for the legend in the only shape that renders one", async () => {
    // Given - `ha-chart-base` builds its legend from the first option that is
    // both `show` and `type: "custom"`. With `show` alone the option falls
    // through to ECharts, which draws its own inside the canvas - so the card
    // never looks broken, it just wears a different legend from every other
    // card on the dashboard, with no overflow chip and no toggling (HEA-87)
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    expect(legendOf(card).show).toBe(true);
    expect(legendOf(card).type).toBe("custom");
  });

  it("names series that exist, so clicking an entry hides one", async () => {
    // Given - the component resolves an entry against the series by id and
    // silently renders an entry that matches nothing, which then does nothing
    // when clicked. This card's series are one per concept rather than a pair
    // per device, so an entry owns exactly one and needs no `secondaryIds`
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    const ids = new Set(chartOf(card).data.map((series) => series.id));
    const entries = legendOf(card).data;
    expect(entries).toHaveLength(ids.size);
    expect(entries.every((entry) => ids.has(entry.id))).toBe(true);
  });

  it("labels its entries in the household's language", async () => {
    // Given - the legend names the same two figures the cards name everywhere
    // else, so it reads from the shared vocabulary rather than repeating it
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    expect(legendOf(card).data.map((entry) => entry.name)).toEqual([
      LABELS.paid,
      LABELS.saved,
    ]);
  });

  it("swatches each entry in its series colour", async () => {
    // Given - the swatch is the key to the bar. The saved series recolours an
    // individual losing point to the error colour, so the entry must carry the
    // series colour rather than inherit whatever the last point happened to be
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then
    const entries = legendOf(card).data;
    for (const entry of entries) {
      expect(entry.itemStyle.color).toBe(seriesOf(card, entry.id).itemStyle.color);
    }
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

  it("formats hovered figures as money, not as raw numbers", async () => {
    // Given - a bucket whose cost divides into recurring decimals, which is
    // what an allocated share normally does
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - the tooltip reads like a price. Unrounded, this shows fourteen
    // decimal places of a euro, which is unreadable and says nothing true:
    // money is not accurate to the femto-cent
    const shown = chartOf(card).options.tooltip.valueFormatter(1.2345678901234);
    expect(shown).toMatch(/€/);
    expect(shown).toBe(formatMoney(1.2345678901234, EURO));
    expect(shown).not.toMatch(/\d[.,]\d{3}/);
  });

  it("keeps a hovered loss signed, so it is not read as a gain", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - the minus survives formatting (HEA-39)
    expect(chartOf(card).options.tooltip.valueFormatter(-0.5)).toMatch(/-/);
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
    // Given - a range earlier than any recorded statistic. An empty axis reads
    // as "it cost nothing", which is a different claim.
    const card = mount(aHass({ devices: AIRCON, response: {} }));
    await ready(card);

    // Then
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
    expect(chartOf(card)).toBe(null);
  });

  it("says so when Home Assistant's chart component never loaded", async () => {
    // Given - a dashboard carrying only HEA cards, where nothing has pulled
    // ha-chart-base in and the nudge did not work either (ADR-0013)
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When
    card._chartReady = false;
    card._render();

    // Then - an empty box would leave the user with nothing to act on
    expect(card.shadowRoot.textContent).toMatch(/chart component is not loaded/i);
    expect(card.shadowRoot.textContent).toMatch(/energy or statistics card/i);
  });

  it("asks Home Assistant to load the component when it is missing", async () => {
    // Given - creating any built-in chart card imports it as a side effect
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
    // Given - loadCardHelpers can reject on an instance where the helper is
    // unavailable; the card must degrade, not throw inside a promise nobody
    // is awaiting
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    globalThis.loadCardHelpers = vi.fn().mockRejectedValue(new Error("no helpers"));
    const card = document.createElement(TAG);
    card.setConfig({ type: `custom:${TAG}` });
    card._chartReady = false;

    // When
    document.body.append(card);

    // Then - it warns and re-checks rather than throwing inside a promise
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
