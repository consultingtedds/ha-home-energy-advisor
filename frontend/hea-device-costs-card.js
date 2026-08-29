/**
 * What each device cost over the period, as bars (HEA-50).
 *
 * The over-time chart answers "how did this week go"; this one answers "which
 * of these is costing me most", side by side for one period.
 *
 * Each device is one bar in its own colour. The bar runs to Cost at Grid Price
 * and the stronger fill stops at what was actually paid, so the paler band
 * above it is the saving - the same three figures the other cards carry, read
 * off a single shape.
 *
 * Only the upper band carries a border. Two stacked segments each with one
 * would draw the shared edge twice, and ECharts has no per-side border width;
 * bordering the saving alone leaves a single line, sitting at the level that
 * was paid.
 *
 * **The bars run sideways, and the device names sit on the axis.** They used to
 * stand up, with the names in the legend, on the reasoning that fourteen names
 * on a category axis overlap into illegibility. That is true of a *vertical*
 * axis; turning the chart on its side removes the premise rather than
 * contradicting it, because a name is then a row label with a whole row to
 * itself.
 *
 * The legend was costing more than it gave. Measured at a 610px viewport with
 * fifteen devices: 164px of legend against 141px of actual plot, because
 * fifteen entries wrap to about seven rows on a narrow card. Landscape looked
 * fine only because the same entries fitted in three. Giving the card more
 * height did not help - the legend simply grew to absorb it (HEA-100).
 *
 * Colour still means device. It is carried per **data point** rather than per
 * series, which is what lets two series hold every device and keep the palette
 * and its link to the Sankey's device colours. Colouring by series would have
 * cost exactly that, and nearly did.
 *
 * What remains of the legend is at most one entry, and only while comparing:
 * the neutral "Earlier period" key. Its id names the ghost series directly now
 * that there is one rather than one per device, so the `secondaryIds` fan-out
 * and the sentinel id it needed are both gone. The component's contract still
 * holds: it looks for an option that is both `show` and `type: "custom"` and
 * draws nothing at all when it finds neither.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import {
  changeTone,
  formatMoney,
  formatMoneyChange,
  formatMoneyRange,
} from "./hea-format.js";
import { fill } from "./hea-labels.js";

export const TAG = "hea-device-costs-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * Hues that stay apart from each other, and apart on either theme.
 *
 * Chosen for distinguishability rather than brand: a household may track a
 * dozen devices, and the palette cycles rather than running out. Adapted from
 * Okabe-Ito, dropping the yellow, which disappears against a light card.
 */
const PALETTE = [
  "#0072b2",
  "#e69f00",
  "#009e73",
  "#cc79a7",
  "#56b4e9",
  "#d55e00",
  "#8c6bb1",
  "#3d9970",
];

/** The remainder is not a device; colouring it like one invites a hunt for it. */
const UNTRACKED_COLOUR = { variable: "--secondary-text-color", fallback: "#8a8a8a" };

/** A loss must not read as a gain, whatever the device's own colour is. */
const LOSS = { variable: "--error-color", fallback: "#db4437" };

/**
 * Neutral, like the over-time chart's earlier line: a period, not a device.
 *
 * The same grey the Untracked remainder wears, which is a real collision in a
 * legend they share - and accepted. The swatch is approximate here whatever it
 * is: the ghost bars are each drawn in their own device's hue, so no single
 * colour represents them, and the words are what carry this entry.
 */
const EARLIER_COLOUR = { variable: "--secondary-text-color", fallback: "#727272" };

/** The three series the chart draws, whatever the household's device count. */
const PAID_ID = "paid";
const SAVED_ID = "saved";
export const EARLIER_ID = "before";

/**
 * How much height one device's row needs, and what the axes take on top.
 *
 * A chart of categories cannot take its height from the viewport: fifteen
 * devices need fifteen rows' worth whatever the screen is, and squeezing them
 * into a viewport-sized box is what made the old chart unreadable. Comparing
 * puts a second bar beside each device, so a row needs more of them.
 */
const ROW_HEIGHT = 30;
const COMPARING_ROW_HEIGHT = 46;
const AXIS_HEADROOM = 64;
/** Below this a two-device household would draw as a sliver of a card. */
const MIN_HEIGHT = 240;

const BORDER_WIDTH = 1.5;
/** How strongly the spend is filled, and how faintly the saving above it. */
const PAID_ALPHA = 0.8;
/**
 * The earlier period's bar, fainter than the spend it is measured against.
 *
 * Weaker than `PAID_ALPHA` so this period reads as the subject and the earlier
 * one as the reference, and stronger than `SAVED_ALPHA` so it is not mistaken
 * for part of the stack beside it (HEA-96).
 */
const BEFORE_ALPHA = 0.45;
const SAVED_ALPHA = 0.22;

const HEX = /^#([\da-f]{3}|[\da-f]{6})$/i;
const RGB = /^rgba?\(([^)]+)\)$/i;

/** The red, green and blue of a colour, or nothing where it is not written so. */
const channelsOf = (colour) => {
  const hex = HEX.exec(colour);
  if (hex) {
    const digits = hex[1];
    const pairs =
      digits.length === 3
        ? [...digits].map((digit) => digit + digit)
        : [0, 2, 4].map((at) => digits.slice(at, at + 2));
    return pairs.map((pair) => Number.parseInt(pair, 16));
  }
  const rgb = RGB.exec(colour);
  if (!rgb) return undefined;
  const parts = rgb[1]
    .split(/[\s,/]+/)
    .filter(Boolean)
    .slice(0, 3)
    .map(Number);
  return parts.length === 3 && parts.every(Number.isFinite) ? parts : undefined;
};

/**
 * A colour at the given alpha, so a fill and its outline read as one hue.
 *
 * A theme is free to write a variable as `rgb()` rather than as hex, and may
 * write it in a form we do not parse at all. An unreadable colour is returned
 * as it came: that loses the fade, where composing `rgba(NaN, NaN, NaN)` would
 * lose the bar.
 */
export const tint = (colour, alpha) => {
  const channels = channelsOf(String(colour).trim());
  return channels ? `rgba(${channels.join(", ")}, ${alpha})` : colour;
};

/**
 * Good news and bad news, as inline colours.
 *
 * The cards wear `.gain` / `.loss` from the shared stylesheet; a tooltip
 * cannot. It is rendered into the chart component's own container, outside
 * this card's shadow root, so no rule of ours reaches it and the colour has to
 * travel on the element (HEA-99).
 */
const TONE_COLOUR = {
  gain: { variable: "--success-color", fallback: "#4caf50" },
  loss: { variable: "--error-color", fallback: "#db4437" },
};

/** One line of the tooltip: what it is, and how much of it. */
const tooltipRow = (label, amount, colour) => {
  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.gap = "16px";
  const name = document.createElement("span");
  name.textContent = label;
  const value = document.createElement("span");
  value.textContent = amount;
  value.style.fontVariantNumeric = "tabular-nums";
  if (colour) value.style.color = colour;
  row.append(name, value);
  return row;
};

/**
 * One device's three figures, as a node.
 *
 * Built rather than written as markup: Home Assistant renders a tooltip
 * formatter's return value with lit, which takes a node as it is and escapes a
 * string - and a device name is whatever the household typed into their own
 * registry.
 */
const tooltipFor = (device, locale, labels, toneColour) => {
  const box = document.createElement("div");
  const title = document.createElement("div");
  title.textContent = device.name;
  title.style.fontWeight = "bold";
  title.style.marginBottom = "4px";
  box.append(
    title,
    tooltipRow(labels.paid, formatMoney(device.actualCost, locale)),
    // A negative saving is a loss, and calling it "Saved" would read as a gain.
    tooltipRow(
      device.costSavings < 0 ? labels.lost : labels.saved,
      formatMoney(device.costSavings, locale),
    ),
    tooltipRow(labels.would_have_paid, formatMoney(device.costAtGridPrice, locale)),
  );
  const change = changeRow(device, locale, labels, toneColour);
  if (change) box.append(change);
  const range = rangeNote(device, locale, labels);
  if (range) box.append(range);
  return box;
};

/**
 * What this device's spend did against the earlier period (HEA-96).
 *
 * A row rather than a sentence, because unlike the range it is a figure in its
 * own right rather than a qualification of the one above it. Signed, and beside
 * what it is measured against, for the reason the totals card gives: a bare
 * amount leaves the direction to be worked out, and a bare "was" makes the
 * reader do the subtraction.
 *
 * Absent unless the household asked to compare, which is the default.
 */
const changeRow = (device, locale, labels, toneColour) => {
  const before = device.before?.actualCost;
  if (!Number.isFinite(before) || !Number.isFinite(device.actualCost)) {
    return undefined;
  }
  const change = device.actualCost - before;
  // A change in spend, so spend's polarity: down is good. Named rather than
  // assumed, because the same fall in Saved would be the opposite verdict.
  const tone = changeTone("actualCost", change);
  return tooltipRow(
    labels.change,
    fill(labels.compared, {
      change: formatMoneyChange(change, locale),
      before: formatMoney(before, locale),
    }),
    tone ? toneColour(tone) : undefined,
  );
};

/**
 * What this device's figure could honestly have been (ADR-0016).
 *
 * A sentence rather than a row, because it qualifies the "Paid" line above it
 * rather than adding a fourth figure - and because the wording is doing work:
 * summing each delta's worst case assumes every kWh landed in that device's own
 * dearest 5-minute slice, which is an outer bound and not an error bar
 * (ADR-0016 decision 4).
 *
 * Absent where the household publishes no per-device range, which is the
 * default: silence beats a range of zero, which would claim exactness.
 */
const rangeNote = ({ costFloor, costCeiling }, locale, labels) => {
  if (![costFloor, costCeiling].every((value) => Number.isFinite(value))) {
    return undefined;
  }
  const note = document.createElement("div");
  note.style.marginTop = "4px";
  note.style.opacity = "0.75";
  // Names its subject. The bounds bracket what was paid and nothing else, so a
  // bare "Could be between…" under three figures left the reader to guess
  // which of them it qualified (HEA-88).
  note.textContent = fill(labels.range_device, {
    range: formatMoneyRange([costFloor, costCeiling], locale),
  });
  return note;
};

class HeaDeviceCostsCard extends HeaChartCard {
  static titleKey = "title_device_costs";

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * Nothing to draw when no configured device recorded anything.
   *
   * A row exists for every device whether or not it reported, so an empty
   * period still yields rows - all of them zero. Bars of nothing read as "it
   * cost nothing", which is a different claim from "there is nothing here".
   */
  _isEmpty() {
    return this._ranked().every(
      (device) => !device.costAtGridPrice && !device.actualCost,
    );
  }

  /**
   * Dearest first, by what was actually paid, and by name where two tie.
   *
   * Ranked by actual cost rather than by bar height, so it answers the same
   * question the table does and in the same order. Bars therefore need not
   * descend - a tall bar on a small fill is a device that ran mostly on
   * generation, which is worth seeing rather than sorting away.
   */
  _ranked() {
    return [...(this._result?.devices ?? [])].sort(
      (left, right) =>
        right.actualCost - left.actualCost || left.name.localeCompare(right.name),
    );
  }

  /** One colour per device, cycling, with the remainder set apart. */
  _colourFor(device, index) {
    return device.untracked
      ? this._colour(UNTRACKED_COLOUR)
      : PALETTE[index % PALETTE.length];
  }

  /** True once any device carries an earlier self, which adds a second bar. */
  _comparing() {
    return this._ranked().some((device) => device.before);
  }

  /**
   * Three series across every device: the spend, the saving above it, and the
   * earlier period beside them.
   *
   * Two series holding every device rather than two series per device, which is
   * what lets the names go on the axis. Colour is carried on each **point**, so
   * a device keeps its own hue - this is the whole reason the palette survives
   * the change (HEA-100).
   *
   * Paid and Saved share one stack, so a device's bar runs to Would have paid.
   * The earlier period takes a stack of its own, so ECharts sets it beside that
   * bar rather than piling it on: the two segments are parts of one bar, and an
   * earlier period is not a part of this one (HEA-96).
   */
  _series() {
    const rows = this._ranked();
    const loss = this._colour(LOSS);
    const labels = this._labels;
    const hue = (device, index) => this._colourFor(device, index);
    return [
      {
        id: PAID_ID,
        name: labels.paid,
        type: "bar",
        stack: "cost",
        // Unbordered: the outline above it would otherwise be drawn twice
        // where the two segments meet.
        data: rows.map((device, index) => ({
          value: device.actualCost,
          itemStyle: { color: tint(hue(device, index), PAID_ALPHA) },
        })),
      },
      {
        id: SAVED_ID,
        name: labels.saved,
        type: "bar",
        stack: "cost",
        data: rows.map((device, index) => {
          const outline = device.costSavings < 0 ? loss : hue(device, index);
          return {
            value: device.costSavings,
            itemStyle: {
              color: tint(outline, SAVED_ALPHA),
              borderColor: outline,
              borderWidth: BORDER_WIDTH,
            },
          };
        }),
      },
      ...(this._comparing()
        ? [
            {
              id: EARLIER_ID,
              name: labels.compared_series,
              type: "bar",
              stack: "earlier",
              data: rows.map((device, index) => ({
                // Null rather than zero for a device the earlier window never
                // saw: ECharts draws no bar, where a zero would draw a device
                // that spent nothing then, which is a different claim.
                value: device.before ? device.before.actualCost : null,
                itemStyle: { color: tint(hue(device, index), BEFORE_ALPHA) },
              })),
            },
          ]
        : []),
    ];
  }

  /**
   * The device a hovered segment belongs to, and its three figures.
   *
   * By row rather than by series: every series now holds every device, so which
   * device was hovered is the data index and nothing else. This used to parse a
   * device key back out of a series id, which is a step that only existed
   * because a device owned its own series (HEA-100).
   */
  _tooltipFor({ dataIndex }, locale) {
    const device = this._ranked()[dataIndex];
    // Undefined suppresses the tooltip, where a half-built one would render an
    // empty box against the cursor.
    return device
      ? tooltipFor(device, locale, this._labels, (tone) =>
          this._colour(TONE_COLOUR[tone]),
        )
      : undefined;
  }

  /**
   * A row per device, not a share of the viewport.
   *
   * Fifteen devices need fifteen rows whatever the screen is. The base class's
   * viewport clamp is right for a chart against time and wrong for one against
   * categories, which is why the height is overridable at all.
   */
  _chartHeight() {
    const rows = this._ranked().length;
    const each = this._comparing() ? COMPARING_ROW_HEIGHT : ROW_HEIGHT;
    return `${Math.max(MIN_HEIGHT, AXIS_HEADROOM + rows * each)}px`;
  }

  /**
   * One key saying the fainter bar is the earlier period, or nothing.
   *
   * The devices are named on the axis; which of a device's two bars is which
   * period is not, so two adjacent strengths of one hue read as two devices
   * before they read as two periods. The same words and the same neutral as the
   * over-time chart's line, so two charts on one screen say it the same way
   * (HEA-99).
   *
   * The id names the ghost series outright. With one ghost series rather than
   * one per device there is nothing left to fan out to, so the `secondaryIds`
   * list and the sentinel id that avoided greying this key out are both gone.
   */
  _earlierKey() {
    if (!this._comparing()) return [];
    return [
      {
        id: EARLIER_ID,
        name: this._labels.compared_series,
        itemStyle: { color: this._colour(EARLIER_COLOUR) },
      },
    ];
  }

  _options(locale) {
    const earlier = this._earlierKey();
    return {
      // Sideways. The value runs along the bottom and the devices down the
      // side, one row each, which is what makes their names readable.
      xAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      yAxis: {
        type: "category",
        data: this._ranked().map((device) => device.name),
        // Dearest at the top. A category axis counts up from the bottom, which
        // would stand the ranking on its head.
        inverse: true,
      },
      // Long names need room, and how much is not knowable here: the household
      // wrote them. Left to the chart to measure rather than guessed at.
      grid: { containLabel: true },
      tooltip: {
        trigger: "item",
        formatter: (params) => this._tooltipFor(params, locale),
      },
      // Only while comparing. A legend of one entry is worth its 24px; a legend
      // naming series a reader can already see labelled is not, and naming
      // fifteen devices cost more of the card than the chart got (HEA-100).
      ...(earlier.length
        ? { legend: { show: true, type: "custom", data: earlier } }
        : {}),
    };
  }
}

/** Nothing beyond the shared fields; the ordering is the question it answers. */
class HeaDeviceCostsCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaDeviceCostsCardEditor);
  registerCard(TAG, HeaDeviceCostsCard, {
    name: "Home Energy Advisor: Device costs (chart)",
    description:
      "What each device cost over the selected period, dearest first.",
  });
};

register();
