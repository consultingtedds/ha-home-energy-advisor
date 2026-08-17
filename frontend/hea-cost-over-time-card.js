/**
 * Cost over time, stacked - the headline chart of the family (HEA-50).
 *
 * The whole bar is Cost at Grid Price; the lower segment is what was actually
 * paid, the upper what was saved. One glance gives spend, counterfactual and
 * saving, and the segments sum to something real (ADR-0012).
 *
 * The chart component and its loading live in `HeaChartCard` (ADR-0013); this
 * file is the two series and the axes. A negative saving is fed in as a
 * negative value, which is how Home Assistant renders exported energy: ECharts
 * stacks it below the axis (ADR-0012 decision 3).
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { formatMoney } from "./hea-format.js";

export const TAG = "hea-cost-over-time-card";
const EDITOR_TAG = `${TAG}-editor`;

/** `name` is a key into the household's vocabulary, resolved at render. */
const SERIES = {
  paid: { id: "paid", name: "paid", variable: "--primary-color", fallback: "#03a9f4" },
  saved: {
    id: "saved",
    name: "saved",
    variable: "--success-color",
    fallback: "#4caf50",
  },
};
const LOSS = { variable: "--error-color", fallback: "#db4437" };

class HeaCostOverTimeCard extends HeaChartCard {
  static titleKey = "title_cost_over_time";

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * Two stacked bar series: what was paid, and what was saved on top of it.
   *
   * A negative saving keeps its sign so ECharts stacks it below the axis, and
   * carries the error colour per point - the loss is the one figure a user
   * must not misread as a gain (HEA-39).
   */
  _series() {
    const rows = this._result?.series ?? [];
    const loss = this._colour(LOSS);
    const labels = this._labels;
    return [
      {
        ...seriesShape(SERIES.paid, this._colour(SERIES.paid), labels),
        data: rows.map((row) => [row.start.getTime(), row.actualCost]),
      },
      {
        ...seriesShape(SERIES.saved, this._colour(SERIES.saved), labels),
        data: rows.map((row) => {
          const point = [row.start.getTime(), row.costSavings];
          return row.costSavings < 0
            ? { value: point, itemStyle: { color: loss } }
            : point;
        }),
      },
    ];
  }

  _options(locale) {
    return {
      xAxis: { type: "time" },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      // The three figures belong together on hover: paid, saved, and the bar.
      // Formatted as money, because an allocated share is a proportion of a
      // blended price and divides into a long recurring decimal - a raw hover
      // reads out fourteen places of a euro, which is unreadable and claims a
      // precision money does not have. The axis is already in currency; the
      // tooltip should match it rather than contradict it.
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value) => formatMoney(value, locale),
      },
      legend: { show: true },
    };
  }
}

const seriesShape = ({ id, name }, colour, labels) => ({
  id,
  name: labels[name],
  type: "bar",
  // One stack, so the segments sit on each other and sum to the whole bar.
  stack: "cost",
  itemStyle: { color: colour },
});

/** Nothing beyond the shared fields; the chart has no options of its own yet. */
class HeaCostOverTimeCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaCostOverTimeCardEditor);
  registerCard(TAG, HeaCostOverTimeCard, {
    name: "Home Energy Advisor: Cost over time",
    description:
      "What the period cost, stacked against what it would have cost at grid price.",
  });
};

register();
