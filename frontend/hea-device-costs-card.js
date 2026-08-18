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
 * Devices are named in the legend rather than along the axis. Fourteen device
 * names on a category axis overlap into illegibility, and Home Assistant's own
 * charts solve it the same way: `ha-chart-base` builds an HTML legend and
 * collapses the overflow behind a "more" chip, so the axis is left to the
 * period.
 *
 * That legend has an exact contract, and failing it is silent. The component
 * looks for an option that is both `show` and `type: "custom"`, draws nothing
 * at all when it finds neither, and hides a series by matching a legend entry's
 * `id` against a series `id` - so an entry names one of the device's two
 * series and reaches the other through `secondaryIds`. A custom legend without
 * `show` renders nothing; ECharts does not step in, because the component
 * rewrites a custom legend to `{ show: false }` before handing the options on.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import {
  formatMoney,
  formatMoneyChange,
  formatMoneyRange,
  formatPeriod,
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

/** Which of a device's two segments a series id belongs to. */
const SEGMENT = /:(?:paid|saved|before)$/;

/** One line of the tooltip: what it is, and how much of it. */
const tooltipRow = (label, amount) => {
  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.gap = "16px";
  const name = document.createElement("span");
  name.textContent = label;
  const value = document.createElement("span");
  value.textContent = amount;
  value.style.fontVariantNumeric = "tabular-nums";
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
const tooltipFor = (device, locale, labels) => {
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
  const change = changeRow(device, locale, labels);
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
const changeRow = (device, locale, labels) => {
  const before = device.before?.actualCost;
  if (!Number.isFinite(before) || !Number.isFinite(device.actualCost)) {
    return undefined;
  }
  return tooltipRow(
    labels.change,
    fill(labels.compared, {
      change: formatMoneyChange(device.actualCost - before, locale),
      before: formatMoney(before, locale),
    }),
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

  /**
   * Two series per device sharing one stack: the spend, and the saving above.
   *
   * A device's own stack, never a shared one - stacking every device together
   * would pile the whole household into a single column.
   */
  _series() {
    const loss = this._colour(LOSS);
    return this._ranked().flatMap((device, index) => {
      const colour = this._colourFor(device, index);
      const outline = device.costSavings < 0 ? loss : colour;
      return [
        {
          id: `${device.key}:paid`,
          name: device.name,
          type: "bar",
          stack: device.key,
          // Unbordered: the outline above it would otherwise be drawn twice
          // where the two segments meet.
          itemStyle: { color: tint(colour, PAID_ALPHA) },
          data: [device.actualCost],
        },
        {
          id: `${device.key}:saved`,
          name: device.name,
          type: "bar",
          stack: device.key,
          itemStyle: {
            color: tint(outline, SAVED_ALPHA),
            borderColor: outline,
            borderWidth: BORDER_WIDTH,
          },
          data: [device.costSavings],
        },
        // A stack of its own, so ECharts sets it beside the device rather than
        // piling it on. The two segments sharing `stack: device.key` are parts
        // of one bar; an earlier period is not a part of this one (HEA-96).
        ...(device.before
          ? [
              {
                id: `${device.key}:before`,
                name: device.name,
                type: "bar",
                stack: `${device.key}:before`,
                itemStyle: { color: tint(colour, BEFORE_ALPHA) },
                data: [device.before.actualCost],
              },
            ]
          : []),
      ];
    });
  }

  /**
   * The device a hovered segment belongs to, and its three figures.
   *
   * By device rather than by segment: an axis tooltip lists every series at the
   * category, which for a dozen devices is two dozen rows, each device named
   * twice with nothing to say which row is the spend and which the saving.
   */
  _tooltipFor({ seriesId }, locale) {
    const key = String(seriesId ?? "").replace(SEGMENT, "");
    const device = this._ranked().find((candidate) => candidate.key === key);
    // Undefined suppresses the tooltip, where a half-built one would render an
    // empty box against the cursor.
    return device ? tooltipFor(device, locale, this._labels) : undefined;
  }

  _options(locale) {
    return {
      xAxis: {
        type: "category",
        // One column for the whole period: the comparison is device against
        // device, not against time.
        data: [formatPeriod(this._period, locale)],
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      tooltip: {
        trigger: "item",
        formatter: (params) => this._tooltipFor(params, locale),
      },
      // Named explicitly: each device is two series, and the legend should name
      // the device once rather than list both of its segments. `show` is what
      // the component filters on, and the ids are what it hides by.
      legend: {
        show: true,
        type: "custom",
        data: this._ranked().map((device, index) => ({
          id: `${device.key}:paid`,
          // Every series the device owns, or hiding it would strand one behind.
          secondaryIds: [
            `${device.key}:saved`,
            ...(device.before ? [`${device.key}:before`] : []),
          ],
          name: device.name,
          // The solid colour, not the fill: a wash of a hue is harder to tell
          // from its neighbour than the hue itself.
          itemStyle: { color: this._colourFor(device, index) },
        })),
      },
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
