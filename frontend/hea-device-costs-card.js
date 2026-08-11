/**
 * What each device cost over the period, as bars (HEA-50).
 *
 * The over-time chart answers "how did this week go"; this one answers "which
 * of these cost me most", which is the same stacked bar turned on its side —
 * devices along the axis instead of days. Each bar totals Cost at Grid Price:
 * solid below is what was paid, faded above is what was saved.
 *
 * Colour identifies the device, opacity identifies the segment. Two palettes
 * would fight each other, and a reader can only track one hue per bar.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { formatMoney } from "./hea-format.js";

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

/** How far the saved segment is faded from the device's own hue. */
const SAVED_OPACITY = 0.45;

class HeaDeviceCostsCard extends HeaChartCard {
  static defaultTitle = "What each device cost";

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * Nothing to draw when no configured device recorded anything.
   *
   * A row exists for every device whether or not it reported, so an empty
   * period still yields rows — all of them zero. Bars of nothing read as "it
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
   * descend — a tall bar with a small solid base is a device that ran mostly on
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

  _series() {
    const devices = this._ranked();
    const loss = this._colour(LOSS);
    const point = (value, colour) => ({ value, itemStyle: { color: colour } });
    return [
      {
        id: "paid",
        name: "Paid",
        type: "bar",
        stack: "cost",
        itemStyle: { opacity: 1 },
        data: devices.map((device, index) =>
          point(device.actualCost, this._colourFor(device, index)),
        ),
      },
      {
        id: "saved",
        name: "Saved",
        type: "bar",
        stack: "cost",
        itemStyle: { opacity: SAVED_OPACITY },
        data: devices.map((device, index) =>
          point(
            device.costSavings,
            device.costSavings < 0 ? loss : this._colourFor(device, index),
          ),
        ),
      },
    ];
  }

  _options(locale) {
    return {
      xAxis: {
        type: "category",
        data: this._ranked().map((device) => device.name),
        axisLabel: { interval: 0, rotate: 30, hideOverlap: true },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value) => formatMoney(value, locale),
      },
      legend: { show: true },
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
