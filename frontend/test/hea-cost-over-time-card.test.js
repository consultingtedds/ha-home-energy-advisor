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

import { tint } from "../hea-colour.js";
import { PAID } from "../hea-concepts.js";
import { TAG, register } from "../hea-cost-over-time-card.js";
import { resetFilters, setFilter } from "../hea-filter.js";
import { formatMoney, formatPeriod } from "../hea-format.js";
import { DEFAULTS as LABELS } from "../hea-labels.js";
import {
  JULY,
  MAY,
  aDeviceRow,
  aHass,
  anEnergyCollection,
  mountCard,
  settled,
  text,
} from "./doubles.js";

const EURO = { language: "en-GB", currency: "EUR" };

const DAY_ONE = new Date(2026, 4, 20);
const DAY_TWO = new Date(2026, 4, 21);

/**
 * Where a day's bar is plotted, which is its middle rather than its start.
 *
 * ECharts centres a bar on its x value, so a bucket plotted at the instant it
 * begins is drawn half a bucket to the left of the span it represents - the
 * "bars sit offset from their bucket" suspect carried over from HEA-50 and
 * confirmed against HA's own `getPeriodMidpointOffset` (HEA-93).
 */
const HALF_DAY = 12 * 60 * 60 * 1000;
const middleOf = (day) => day.getTime() + HALF_DAY;

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

/**
 * A point's `[x, y, start]`, whichever of the two shapes ECharts accepts it
 * arrived in - a bare triple, or one wrapped with a style of its own.
 */
const valuesOf = (point) => (Array.isArray(point) ? point : point.value);
const valuesIn = (card, id) => seriesOf(card, id).data.map(valuesOf);

beforeAll(() => {
  // Home Assistant's component, stood in for so the card will render its chart.
  if (!customElements.get("ha-chart-base")) {
    customElements.define("ha-chart-base", class extends HTMLElement {});
  }
});

beforeEach(() => {
  document.body.replaceChildren();
  // The page filter is a module-global store, so a selection left by one test
  // would narrow the next one's chart without it ever saying so (HEA-98).
  resetFilters();
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
  /**
   * The title, wherever this card is carrying it.
   *
   * Most cards hand `ha-card` a header attribute and let it draw the heading.
   * This one draws its own, because a figure sits beside the title - and Home
   * Assistant styles a slotted `.card-header` exactly as it styles the one it
   * makes itself, so the heading still matches every other card on the
   * dashboard (HEA-141).
   */
  const headerOf = (card) => {
    const card_ = card.shadowRoot.querySelector("ha-card");
    const own = card_.querySelector(".card-header .title");
    return own ? own.textContent : card_.getAttribute("header");
  };

  const chipOf = (card) =>
    card.shadowRoot.querySelector("ha-card .card-header .chip")?.textContent;

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

    // Then - absent means "use the default"; empty means "show nothing", and
    // the figure that rides beside the title goes with it
    expect(headerOf(card)).toBe(null);
    expect(chipOf(card)).toBeUndefined();
  });

  it("carries the period's spend beside the title", async () => {
    // Given - the two days, of which 3 was paid
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - what the household actually paid, which is what a figure on a
    // card titled "Cost over time" is read as. The bars' own total is Would
    // have paid, and a bare counterfactual in the corner would be read as the
    // bill (ADR-0019)
    expect(chipOf(card)).toBe(formatMoney(3, EURO));
  });

  it("holds the figure back until there is one", async () => {
    // Given - a period with nothing recorded in it
    const card = mount(aHass({ devices: AIRCON, response: {} }));
    await ready(card);

    // Then - the chip is where a total goes, and "€0.00" is a claim about the
    // period rather than an admission that nothing is known about it
    expect(chipOf(card)).toBe("");
    expect(headerOf(card)).toBe("Cost over time");
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

    // Then - day one paid 1 of 3, day two paid 2 of 3, each plotted at the
    // middle of the day it covers and carrying the instant that day began, so
    // a hover can name the span rather than the midpoint (HEA-141). The rest
    // of the range is filled with empty buckets, which have their own test
    const recorded = (id) => valuesIn(card, id).filter(([, value]) => value !== 0);
    expect(recorded("paid")).toEqual([
      [middleOf(DAY_ONE), 1, DAY_ONE.getTime()],
      [middleOf(DAY_TWO), 2, DAY_TWO.getTime()],
    ]);
    expect(recorded("saved")).toEqual([
      [middleOf(DAY_ONE), 2, DAY_ONE.getTime()],
      [middleOf(DAY_TWO), 1, DAY_TWO.getTime()],
    ]);
  });

  it("centres each bar on the span it covers, not on the instant it began", async () => {
    // Given - ECharts centres a bar on its x value. Plotting a bucket at its
    // start therefore draws it half a bucket early: a Monday's spending
    // straddles Sunday midday to Monday midday, and every bar in the chart
    // disagrees with the axis beneath it. Home Assistant offsets by
    // `min(measuredGap, nominalPeriod) / 2` for exactly this reason
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));

    // When
    await ready(card);

    // Then - half a day on, so the bar spans the day it is about
    const [[first], [second]] = valuesIn(card, "paid");
    expect(first).toBe(DAY_ONE.getTime() + HALF_DAY);
    expect(second - first).toBe(DAY_TWO.getTime() - DAY_ONE.getTime());
  });

  it("caps how wide a bar can get, so a short period is not one huge block", async () => {
    // Given / When - a range with two buckets in it has enormous room per bar
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - the same cap Home Assistant puts on its own energy bars
    expect(seriesOf(card, "paid").barMaxWidth).toBe(50);
    expect(seriesOf(card, "saved").barMaxWidth).toBe(50);
  });

  it("keeps a loss negative, so it stacks below the axis", async () => {
    // Given - paid 5 where the grid would have cost 3
    const card = mount(aHass({ devices: AIRCON, response: aLoss }));
    await ready(card);

    // When
    const [point] = seriesOf(card, "saved").data;

    // Then - negative is how Home Assistant renders exported energy, and
    // ECharts stacks it downwards (ADR-0012 decision 3)
    expect(point.value).toEqual([middleOf(DAY_ONE), -2, DAY_ONE.getTime()]);
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

  it("fills a segment at half strength and outlines it in the colour itself", async () => {
    // Given - how Home Assistant draws its own energy bars: the fill is the
    // series colour at half alpha and the edge is that colour solid, which is
    // what stops a stack of pale blocks losing its boundaries (HEA-141)
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When / Then - the hue is still the concept's own (ADR-0019); only its
    // rendering has changed
    const paid = seriesOf(card, "paid").itemStyle;
    expect(paid.borderColor).toBe(PAID.fallback);
    expect(paid.color).not.toBe(paid.borderColor);
    expect(paid.color).toBe(tint(PAID.fallback, 0.5));
    expect(paid.borderWidth).toBe(1);
  });

  it("rounds the top of a bar, and leaves the segment under it square", async () => {
    // Given - a cap belongs to the bar, not to each of its parts. Rounding
    // every segment would draw a stack of lozenges with gaps down the middle
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When / Then - the top of this stack is Saved, so it carries the cap
    expect(seriesOf(card, "saved").data[0].itemStyle.borderRadius).toEqual([4, 4, 0, 0]);
    expect(seriesOf(card, "paid").data[0].itemStyle?.borderRadius).toBeUndefined();
  });

  it("rounds a loss at the bottom, where it hangs below the axis", async () => {
    // Given - battery arbitrage: paid 5 where the grid would have cost 3, so
    // the saving stacks downwards (HEA-39)
    const card = mount(aHass({ devices: AIRCON, response: aLoss }));
    await ready(card);

    // When / Then - the bar now has two ends, and each is the outermost
    // segment in its own direction
    expect(seriesOf(card, "saved").data[0].itemStyle.borderRadius).toEqual([0, 0, 4, 4]);
    expect(seriesOf(card, "paid").data[0].itemStyle.borderRadius).toEqual([4, 4, 0, 0]);
  });

  it("draws no outline on a segment of no height", async () => {
    // Given - an hour covered entirely by generation, so nothing was paid
    const freeHour = {
      "sensor.slow_poll_aircon_energy_used": [{ start: DAY_ONE.getTime(), change: 4 }],
      "sensor.slow_poll_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 0 }],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: DAY_ONE.getTime(), change: 1.14 },
      ],
    };
    const card = mount(aHass({ devices: AIRCON, response: freeHour }));
    await ready(card);

    // When / Then - a border on a segment of zero height is a hairline drawn
    // across the axis, which reads as a bar that is not there
    expect(seriesOf(card, "paid").data[0].itemStyle.borderWidth).toBe(0);
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
   * These windows are exactly two days, and `bucketPeriodFor` switches to daily
   * only *above* two - so the buckets here are hourly and a bar is centred half
   * an hour on, not half a day. The offset follows the bucket, which is the
   * point of deriving it rather than fixing it.
   */
  const HALF_HOUR = 30 * 60 * 1000;

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
    expect(before.data).toEqual([[DAY_ONE.getTime() + HALF_HOUR, 6]]);
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
    expect(seriesOf(card, "before").data).toEqual([
      [DAY_ONE.getTime() + HALF_HOUR, 1.14],
    ]);
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
    const [[, paid]] = valuesIn(card, "paid");
    const [[, saved]] = valuesIn(card, "saved");
    const [[, line]] = valuesIn(card, "before");
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

  it("swatches each entry in its series colour, at full strength", async () => {
    // Given - the swatch is the key to the bar. The saved series recolours an
    // individual losing point to the error colour, so the entry must carry the
    // series colour rather than inherit whatever the last point happened to be
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - the outline's colour, not the half-strength fill inside it. Home
    // Assistant keys its own legend to the fill, which at this alpha is a tick
    // barely there; both colours are in the bar, and this is the legible one
    for (const entry of legendOf(card).data) {
      const series = seriesOf(card, entry.id);
      expect(entry.itemStyle.color).toBe(
        series.itemStyle.borderColor ?? series.itemStyle.color,
      );
      expect(entry.itemStyle.color).not.toMatch(/rgba/);
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

  it("gives the chart a height, so a phone in portrait is not a sliver", async () => {
    // Given - with no height set, `ha-chart-base` sizes itself
    // `max(clientWidth / 2, 200)`, so a card about 360px wide across a phone in
    // portrait floors at 200px while the same chart reaches its 350px cap on a
    // desktop. Reported on a real phone against "what each device cost", which
    // shares this base (HEA-93)
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));

    // When
    await ready(card);

    // Then - set as the property the component reads. CSS height on the host
    // does not reach the inner container that does the sizing, so styling it
    // would look like a fix and change nothing
    expect(chartOf(card).height).toBe("clamp(320px, 40vw, 480px)");
  });

  it("lifts the height cap that asking for a height turns on", async () => {
    // Given - measured on the reference instance: with no height set the chart
    // stood at 418px on a desktop, and asking for one *shortened* it to 350,
    // because `.container.has-height` carries `max-height:
    // var(--chart-max-height, 350px)`. The cap is inert until the moment you
    // ask, so a height request silently costs height on any card wide enough
    // to want it - which is how this shipped as a regression (HEA-93)
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));

    // When
    await ready(card);

    // Then - a custom property, because it has to cross into the component's
    // own shadow root where an ordinary rule of ours could never reach
    const styles = card.shadowRoot.querySelector("style").textContent;
    expect(styles).toContain("--chart-max-height");
  });

  it("names the currency once, at the top of the value axis", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - as Home Assistant heads its own energy axis "kWh". A symbol on
    // every tick is the same word five times over, in the column where a
    // phone-width card has least room to spare (HEA-103)
    const { yAxis } = chartOf(card).options;
    expect(yAxis.name).toBe("€");
    const label = yAxis.axisLabel.formatter(3);
    expect(label).toMatch(/3[.,]00/);
    expect(label).not.toMatch(/€/);
  });

  it("writes the zero tick as zero, not as a sum of money", async () => {
    // Given / When
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // Then - the axis crosses at nothing, and "0.00" claims a precision that
    // the one tick standing for "none" does not need. Home Assistant's own
    // rule (HEA-141)
    expect(chartOf(card).options.yAxis.axisLabel.formatter(0)).toBe("0");
  });

  it("still labels the axis where the instance has no currency set", async () => {
    // Given - an instance that never filled the currency in
    const hass = aHass({ devices: AIRCON, response: twoDays });
    hass.config = {};
    const card = mount(hass);
    await ready(card);

    // Then - bare numbers and no heading, rather than a guessed symbol
    const { yAxis } = chartOf(card).options;
    expect(yAxis.name).toBe("");
    expect(yAxis.axisLabel.formatter(3)).toMatch(/3[.,]00/);
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

describe("where the plot sits, and what fills it", () => {
  /** Three hours of window, with the middle one never recorded. */
  const aGap = {
    "sensor.slow_poll_aircon_actual_cost": [
      { start: DAY_ONE.getTime(), change: 1 },
      { start: DAY_ONE.getTime() + 2 * 3600000, change: 3 },
    ],
    "sensor.slow_poll_aircon_cost_at_grid_price": [
      { start: DAY_ONE.getTime(), change: 2 },
      { start: DAY_ONE.getTime() + 2 * 3600000, change: 4 },
    ],
  };

  const overHours = async (response, hours) => {
    const collection = anEnergyCollection(
      DAY_ONE,
      new Date(DAY_ONE.getTime() + hours * 3600000),
    );
    const card = mount(aHass({ devices: AIRCON, response, collection }));
    await ready(card);
    return card;
  };

  it("runs the axis across the period asked for, not the buckets that arrived", async () => {
    // Given - three hours asked for, with nothing recorded in the last one
    const card = await overHours(aGap, 3);

    // When / Then - an axis drawn only as wide as the data makes a quiet hour
    // look like the end of the period, and moves every bar when one arrives.
    // The far end is the last bucket's midpoint, because that is where its bar
    // is centred and padding past it is empty chart (Home Assistant's own
    // `getSuggestedMax`)
    const { xAxis } = chartOf(card).options;
    expect(xAxis.min).toBe(DAY_ONE.getTime());
    expect(xAxis.max).toBe(DAY_ONE.getTime() + 2.5 * 3600000);
  });

  it("ends a daily axis on the last day, not part-way through it", async () => {
    // Given - a range wide enough for daily buckets, ending mid-afternoon as
    // the picker's "today" does
    const lastDay = new Date(DAY_ONE.getTime() + 3 * 86400000);
    const collection = anEnergyCollection(
      DAY_ONE,
      new Date(lastDay.getTime() + 14 * 3600000),
    );
    const card = mount(aHass({ devices: AIRCON, response: twoDays, collection }));
    await ready(card);

    // When / Then - a daily bar sits at the start of its day, so the axis ends
    // there too
    expect(chartOf(card).options.xAxis.max).toBe(lastDay.getTime());
  });

  it("lets the plot run to the card's own edges", async () => {
    // Given / When
    const card = await overHours(aGap, 3);

    // Then - Home Assistant's own grid: the labels are kept inside, and what
    // is left over is the plot. Left alone, ECharts holds a tenth of the width
    // back on each side and the chart floats in the middle of the card
    expect(chartOf(card).options.grid).toEqual({
      top: 15,
      bottom: 0,
      left: 1,
      right: 1,
      containLabel: true,
    });
  });

  it("fills an hour nothing was recorded in, so the bars keep their width", async () => {
    // Given - a window of three hours with the middle one missing. ECharts
    // takes a bar's width from the smallest gap between points, so two hours
    // two apart draw as two double-width blocks
    const card = await overHours(aGap, 3);

    // When
    const paid = valuesIn(card, "paid");

    // Then - three buckets, the middle one worth nothing
    expect(paid.map((point) => point[2])).toEqual([
      DAY_ONE.getTime(),
      DAY_ONE.getTime() + 3600000,
      DAY_ONE.getTime() + 2 * 3600000,
    ]);
    expect(paid[1][1]).toBe(0);
  });

  it("draws nothing at all for an hour it filled in", async () => {
    // Given / When
    const card = await overHours(aGap, 3);

    // Then - no outline either, or an empty hour draws a hairline on the axis
    // that reads as a bar of nothing rather than as no bar
    expect(seriesOf(card, "paid").data[1].itemStyle.borderWidth).toBe(0);
    expect(seriesOf(card, "saved").data[1].itemStyle.borderWidth).toBe(0);
  });

  it("steps daily buckets on the household's own midnights", async () => {
    // Given - a fortnight, which is daily buckets
    const collection = anEnergyCollection(
      DAY_ONE,
      new Date(DAY_ONE.getTime() + 14 * 86400000),
    );
    const card = mount(aHass({ devices: AIRCON, response: twoDays, collection }));
    await ready(card);

    // When / Then - stepping by a fixed 24 hours would walk the buckets off
    // midnight the first time the clocks changed, and every bar after it would
    // sit an hour out. Only a runner whose own zone has daylight saving can
    // fail this one
    for (const [, , start] of valuesIn(card, "paid")) {
      expect(new Date(start).getHours()).toBe(0);
    }
  });

  it("still says a period holds nothing rather than filling it with zeroes", async () => {
    // Given - a range earlier than any recorded statistic
    const card = await overHours({}, 3);

    // When / Then - the filling is for gaps between buckets, and a period with
    // no buckets at all has nothing to fill between. A chart of flat zeroes
    // would claim the hours cost nothing, which is a different statement
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
    expect(chartOf(card)).toBe(null);
  });
});

describe("what a hovered bar says", () => {
  /** Where an hourly bar sits: half its own bucket on from the hour it covers. */
  const HALF_HOUR = 30 * 60 * 1000;

  /**
   * The params ECharts hands a tooltip formatter, built from the card's own
   * series so a fixture cannot agree with the card by construction.
   *
   * Every bar series at one bucket, which is what `trigger: "axis"` collects.
   * `componentSubType` is how a bar is told from the earlier period's line -
   * the property ECharts sets, not one invented here.
   */
  const hovering = (card, index) =>
    chartOf(card)
      .data.map((series, order) => ({ series, order }))
      .filter(({ series }) => series.data[index] !== undefined)
      .map(({ series, order }) => {
        const point = series.data[index];
        return {
          seriesId: series.id,
          seriesName: series.name,
          componentSubType: series.type,
          componentIndex: order,
          value: point.value ?? point,
          color: series.itemStyle?.color,
        };
      });

  const hoverText = (card, index = 0) =>
    chartOf(card).options.tooltip.formatter(hovering(card, index))?.textContent;

  /** The same two days, read over a window narrow enough for hourly buckets. */
  const hourly = async (response = twoDays) => {
    const collection = anEnergyCollection();
    const card = mount(aHass({ devices: AIRCON, response, collection }));
    await ready(card);
    collection.announce(DAY_ONE, new Date(DAY_ONE.getTime() + 2 * 86400000));
    await vi.waitFor(() =>
      expect(valuesIn(card, "paid")[0][0]).toBe(DAY_ONE.getTime() + HALF_HOUR),
    );
    return card;
  };

  it("names the hour a bar covers, not an instant inside it", async () => {
    // Given - a bar is drawn at its bucket's midpoint, because that is where
    // ECharts centres it. Nothing happened at 00:30, and the figure is the
    // whole hour's - so the hover naming that midpoint was the one thing in
    // this chart that was actually wrong (HEA-141)
    const card = await hourly();

    // When / Then - the span, as Home Assistant's own energy charts name it
    expect(hoverText(card)).toContain("0:00 – 1:00");
  });

  it("names the day itself where a bar covers one", async () => {
    // Given - a range wide enough for daily buckets
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When / Then - midnight to midnight is the day, and a time of day here
    // would claim the bar was about some moment within it
    const shown = hoverText(card);
    expect(shown).toMatch(/Wed/);
    expect(shown).toMatch(/20 May/);
    expect(shown).not.toMatch(/12:00/);
  });

  it("names each segment and what it came to", async () => {
    // Given - day one paid 1 of 3
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When
    const shown = hoverText(card);

    // Then - as money, because an allocated share divides into a long
    // recurring decimal and a raw hover reads out fourteen places of a euro
    expect(shown).toContain(LABELS.paid);
    expect(shown).toContain(formatMoney(1, EURO));
    expect(shown).toContain(LABELS.saved);
    expect(shown).toContain(formatMoney(2, EURO));
  });

  it("totals the stack as what the hour would have cost at grid price", async () => {
    // Given - the two segments sum to Would have paid by construction
    // (ADR-0012), which is the figure the whole bar's height means
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When / Then - stated rather than left to be added up
    const shown = hoverText(card);
    expect(shown).toContain(LABELS.would_have_paid);
    expect(shown).toContain(formatMoney(3, EURO));
  });

  it("calls a negative saving a loss, and keeps its sign", async () => {
    // Given - battery arbitrage that cost more than the grid would have
    const card = mount(aHass({ devices: AIRCON, response: aLoss }));
    await ready(card);

    // When
    const shown = hoverText(card);

    // Then - "Saved -€2.00" reads as a gain of some kind; the word is what
    // carries the verdict (HEA-102)
    expect(shown).toContain(LABELS.lost);
    expect(shown).not.toContain(LABELS.saved);
    expect(shown).toContain(formatMoney(-2, EURO));
  });

  it("leaves out a segment that is not there", async () => {
    // Given - an hour covered entirely by generation: nothing was paid for it
    const freeHour = {
      "sensor.slow_poll_aircon_energy_used": [{ start: DAY_ONE.getTime(), change: 4 }],
      "sensor.slow_poll_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 0 }],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: DAY_ONE.getTime(), change: 1.14 },
      ],
    };
    const card = mount(aHass({ devices: AIRCON, response: freeHour }));
    await ready(card);

    // When / Then - a segment of no height is not in the bar, so a row for it
    // is a line of nothing between the two figures that matter
    const shown = hoverText(card);
    expect(shown).not.toContain(LABELS.paid);
    expect(shown).toContain(LABELS.saved);
  });

  it("says nothing at all where the bucket holds nothing", async () => {
    // Given - a bucket with neither spend nor saving in it
    const emptyHour = {
      "sensor.slow_poll_aircon_actual_cost": [{ start: DAY_ONE.getTime(), change: 0 }],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: DAY_ONE.getTime(), change: 0 },
      ],
    };
    const card = mount(aHass({ devices: AIRCON, response: emptyHour }));
    await ready(card);

    // When / Then - undefined suppresses the tooltip, where a half-built one
    // would render an empty box against the cursor
    expect(chartOf(card).options.tooltip.formatter(hovering(card, 0))).toBeUndefined();
  });

  it("warns that the interval being hovered is still being counted", async () => {
    // Given - the trailing bucket, which will still grow (HEA-140)
    const card = mount(
      aHass({
        devices: AIRCON,
        response: twoDays,
        settledUntil: new Date(DAY_ONE.getTime() + 3600000).toISOString(),
      }),
    );
    await ready(card);

    // When / Then - the bar is faded, and a hover is where a reader asks what
    // the fade means
    expect(hoverText(card, 1)).toContain(LABELS.still_accruing);
  });

  it("takes the span from the bar, not from the earlier period beside it", async () => {
    // Given - a bucket carries the instant it began, because the x it is
    // plotted at is half a bucket later. The earlier period's line is drawn on
    // this period's axis, so its own dates must not be read as the header
    const card = mount(aHass({ devices: AIRCON, response: twoDays }));
    await ready(card);

    // When / Then
    const [point] = seriesOf(card, "paid").data;
    expect(point[2]).toBe(DAY_ONE.getTime());
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

/**
 * What an hourly shape may honestly claim about one device (HEA-98).
 *
 * A device reporting every 30-90 minutes has its energy spread across the
 * buckets its counter spanned (ADR-0006), so the chart is an accrual estimate
 * rather than a profile of when the energy was used. Aggregated over a house
 * that washes out; pointed at one device it is the whole picture, and ADR-0016's
 * bounds exist precisely because the moment is unknowable.
 */
describe("the accrual caveat", () => {
  /** Exactly two days, which `bucketPeriodFor` still buckets hourly. */
  const TWO_DAYS = new Date(DAY_ONE.getTime() + 2 * 86400000);

  const KETTLE = aDeviceRow("fine_meter_kettle", "Fine Meter Kettle");

  const bothDevices = {
    ...twoDays,
    "sensor.fine_meter_kettle_energy_used": [{ start: DAY_ONE.getTime(), change: 4 }],
    "sensor.fine_meter_kettle_actual_cost": [{ start: DAY_ONE.getTime(), change: 1 }],
    "sensor.fine_meter_kettle_cost_at_grid_price": [
      { start: DAY_ONE.getTime(), change: 2 },
    ],
  };

  const house = (start, end) =>
    aHass({
      devices: [...AIRCON, KETTLE],
      response: bothDevices,
      collection: anEnergyCollection(start, end),
    });

  it("says so when the page is narrowed to a single device at hourly buckets", async () => {
    // Given - a house of two, drilled into one, which is the gesture HEA-98
    // adds to the filter
    const card = mount(house(DAY_ONE, TWO_DAYS));
    await ready(card);

    // When
    setFilter("energy_hea-costs", { kind: "device", id: "slow_poll_aircon" });

    // Then - stated rather than left for the reader to infer from a shape that
    // looks like a measurement
    await vi.waitFor(() =>
      expect(text(card)).toContain(LABELS.hourly_shape_estimate),
    );
  });

  it("stays quiet while the chart is a house rather than a device", async () => {
    // Given - the same hourly buckets, unfiltered. Across a house the accrual
    // averages out, and a caveat on every chart is a caveat nobody reads
    const card = mount(house(DAY_ONE, TWO_DAYS));

    // Then
    await ready(card);
    expect(text(card)).not.toContain(LABELS.hourly_shape_estimate);
  });

  it("stays quiet at daily buckets, where a counter's spread is invisible", async () => {
    // Given - a 90-minute counter cannot move energy out of the day it was
    // used in, so the caveat would be true of nothing the reader can see
    const card = mount(house(MAY, JULY));
    await ready(card);

    // When
    setFilter("energy_hea-costs", { kind: "device", id: "slow_poll_aircon" });

    // Then
    await vi.waitFor(() => expect(seriesOf(card, "paid").data.length).toBeGreaterThan(0));
    expect(text(card)).not.toContain(LABELS.hourly_shape_estimate);
  });

  it("says so for a card configured to one device, however it got there", async () => {
    // Given - a room dashboard pinning a single device in its config reads the
    // same chart with the same caveat, and never touches the page filter
    const card = mount(house(DAY_ONE, TWO_DAYS), { devices: ["slow_poll_aircon"] });

    // Then
    await ready(card);
    expect(text(card)).toContain(LABELS.hourly_shape_estimate);
  });
});

describe("the card", () => {
  it("is tall enough for a chart in a masonry view", () => {
    // Given / When / Then
    expect(mount(aHass({ devices: AIRCON, response: twoDays })).getCardSize()).toBeGreaterThan(3);
  });
});

describe("an interval the accounting has not finished with", () => {
  /** Two hourly buckets, the later of which is still filling. */
  const twoHours = {
    "sensor.slow_poll_aircon_energy_used": [
      { start: DAY_ONE.getTime(), change: 10 },
      { start: DAY_ONE.getTime() + 3600000, change: 4 },
    ],
    "sensor.slow_poll_aircon_actual_cost": [
      { start: DAY_ONE.getTime(), change: 1 },
      { start: DAY_ONE.getTime() + 3600000, change: 0.4 },
    ],
    "sensor.slow_poll_aircon_cost_at_grid_price": [
      { start: DAY_ONE.getTime(), change: 3 },
      { start: DAY_ONE.getTime() + 3600000, change: 1 },
    ],
  };

  const anHourlyPeriod = () =>
    anEnergyCollection(DAY_ONE, new Date(DAY_ONE.getTime() + 2 * 3600000));

  it("draws the accruing bar differently from the finished ones", async () => {
    // Given - the integration has settled to the end of the first hour, so the
    // second is still being counted
    const card = mount(
      aHass({
        devices: AIRCON,
        response: twoHours,
        collection: anHourlyPeriod(),
        settledUntil: new Date(DAY_ONE.getTime() + 3600000).toISOString(),
      }),
    );
    await ready(card);

    // Then - the finished bar is drawn plainly and the accruing one is not. A
    // household comparing the last hour with the Energy Dashboard's otherwise
    // reads a lag as a disagreement (HEA-140, GitHub #20)
    const paid = seriesOf(card, "paid").data;
    expect(paid[0].itemStyle?.opacity).toBeUndefined();
    expect(paid[1].itemStyle.opacity).toBeLessThan(1);
  });

  it("says in words that the last interval is still being counted", async () => {
    // Given - the same period
    const card = mount(
      aHass({
        devices: AIRCON,
        response: twoHours,
        collection: anHourlyPeriod(),
        settledUntil: new Date(DAY_ONE.getTime() + 3600000).toISOString(),
      }),
    );
    await ready(card);

    // Then - the caption says so. The faded bar is the signal; this is what
    // tells somebody what the signal means
    expect(text(card)).toContain(LABELS.still_accruing);
  });

  it("says nothing when every interval on the chart is finished", async () => {
    // Given - a chart of whole days, all of them settled
    const card = mount(
      aHass({
        devices: AIRCON,
        response: twoDays,
        settledUntil: new Date(DAY_TWO.getTime() + 86400000).toISOString(),
      }),
    );
    await ready(card);

    // Then - no note and no fading. A caveat shown always is a caveat nobody
    // reads
    expect(text(card)).not.toContain(LABELS.still_accruing);
    expect(
      seriesOf(card, "paid").data.every(
        (point) => point.itemStyle?.opacity === undefined,
      ),
    ).toBe(true);
  });
});
