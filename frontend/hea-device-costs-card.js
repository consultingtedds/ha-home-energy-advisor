/**
 * What each device cost over the period, as bars (HEA-50).
 *
 * The over-time chart answers "how did this week go"; this one answers "which
 * of these is costing me most", side by side for one period.
 *
 * Each device is one outlined bar. The outline runs to Cost at Grid Price and
 * the fill stops at what was actually paid, so the empty space between them is
 * the saving — the same three figures the other cards carry, read off a single
 * shape.
 *
 * Devices are named in the legend rather than along the axis. Fourteen device
 * names on a category axis overlap into illegibility, and Home Assistant's own
 * charts solve it the same way: `ha-chart-base` builds its legend from the
 * series it is given and collapses the overflow behind a "more" chip, so the
 * axis is left to the period. Each device is drawn as two stacked series, so
 * `options.legend.data` names the devices explicitly rather than letting the
 * legend list every segment.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { formatMoney, formatPeriod } from "./hea-format.js";

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
/** How far the fill is lightened from the outline it sits inside. */
const FILL_ALPHA = 0.45;

/** `#rrggbb` at the given alpha, so fill and outline read as one colour. */
const tint = (hex, alpha) => {
  const [red, green, blue] = [1, 3, 5].map((at) =>
    Number.parseInt(hex.slice(at, at + 2), 16),
  );
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
};

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
   * descend — a tall outline on a small fill is a device that ran mostly on
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
   * Two series per device sharing one stack: the fill, then the empty saving
   * standing on top of it.
   *
   * A device's own stack, never a shared one — stacking every device together
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
          itemStyle: {
            color: tint(colour, FILL_ALPHA),
            borderColor: colour,
            borderWidth: BORDER_WIDTH,
          },
          data: [device.actualCost],
        },
        {
          id: `${device.key}:saved`,
          name: device.name,
          type: "bar",
          stack: device.key,
          // Unfilled, so the outline alone carries what it would have cost.
          itemStyle: {
            color: "transparent",
            borderColor: outline,
            borderWidth: BORDER_WIDTH,
          },
          data: [device.costSavings],
        },
      ];
    });
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
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value) => formatMoney(value, locale),
      },
      // Named explicitly: each device is two series, and the legend should
      // name the device once rather than list both of its segments.
      legend: {
        type: "custom",
        data: this._ranked().map((device, index) => ({
          id: device.key,
          name: device.name,
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
