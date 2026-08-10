/**
 * Cost over time, stacked — the headline chart of the family (HEA-50).
 *
 * The whole bar is Cost at Grid Price; the lower segment is what was actually
 * paid, the upper what was saved. One glance gives spend, counterfactual and
 * saving, and the segments sum to something real (ADR-0012).
 *
 * Drawn by Home Assistant's own `ha-chart-base` (ADR-0013) — the component its
 * Energy Dashboard uses, wrapping ECharts bundled into the frontend. Tooltips,
 * legend, zoom, theming and dark mode come with it, and our chart looks like
 * the graphs beside it because it is the same engine. A negative saving is fed
 * in as a negative value, which is how Home Assistant renders exported energy:
 * ECharts stacks it below the axis (ADR-0012 decision 3).
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { formatMoney } from "./hea-format.js";

export const TAG = "hea-cost-over-time-card";
const EDITOR_TAG = `${TAG}-editor`;

/** Home Assistant's chart component, and a card that is known to pull it in. */
const CHART_TAG = "ha-chart-base";
const CHART_BEARING_CARD = { type: "statistics-graph", entities: [] };

const SERIES = {
  paid: { id: "paid", name: "Paid", variable: "--primary-color", fallback: "#03a9f4" },
  saved: { id: "saved", name: "Saved", variable: "--success-color", fallback: "#4caf50" },
};
const LOSS = { variable: "--error-color", fallback: "#db4437" };

class HeaCostOverTimeCard extends HeaCard {
  static cardStyle = `
    ha-chart-base { display: block; }
  `;

  constructor() {
    super();
    // Home Assistant loads card modules lazily, so a dashboard carrying only
    // HEA cards may never have pulled the chart component in (ADR-0013).
    this._chartReady = Boolean(customElements.get(CHART_TAG));
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** A chart needs real height, unlike a row of figures. */
  getCardSize() {
    return 6;
  }

  connectedCallback() {
    super.connectedCallback();
    if (!this._chartReady) this._loadChartComponent();
  }

  /**
   * Nudge Home Assistant into loading its chart component.
   *
   * Creating any built-in card that draws a chart imports it as a side effect.
   * If that still leaves it unregistered the card says so, rather than leaving
   * an empty box the user cannot interpret.
   */
  async _loadChartComponent() {
    try {
      const helpers = await globalThis.loadCardHelpers?.();
      await helpers?.createCardElement(CHART_BEARING_CARD);
    } catch (error) {
      console.warn(`${TAG}: could not load ${CHART_TAG}`, error);
    }
    this._chartReady = Boolean(customElements.get(CHART_TAG));
    this._render();
  }

  _body() {
    if (!this._chartReady) {
      return `<p class="message">Home Assistant's chart component is not loaded.
        Adding any energy or statistics card to this dashboard will load it.</p>`;
    }
    if ((this._result?.series ?? []).length === 0) {
      return `<p class="message">No cost recorded in this period.</p>`;
    }
    return `<${CHART_TAG} chart-type="bar"></${CHART_TAG}>`;
  }

  /** The chart takes its data and options as properties, not as markup. */
  _afterRender() {
    const chart = this.shadowRoot.querySelector(CHART_TAG);
    if (!chart) return;
    chart.hass = this._hass;
    chart.data = this._series();
    chart.options = this._options();
  }

  /**
   * Two stacked bar series: what was paid, and what was saved on top of it.
   *
   * A negative saving keeps its sign so ECharts stacks it below the axis, and
   * carries the error colour per point — the loss is the one figure a user
   * must not misread as a gain (HEA-39).
   */
  _series() {
    const rows = this._result?.series ?? [];
    const loss = this._colour(LOSS);
    return [
      {
        ...seriesShape(SERIES.paid, this._colour(SERIES.paid)),
        data: rows.map((row) => [row.start.getTime(), row.actualCost]),
      },
      {
        ...seriesShape(SERIES.saved, this._colour(SERIES.saved)),
        data: rows.map((row) => {
          const point = [row.start.getTime(), row.costSavings];
          return row.costSavings < 0
            ? { value: point, itemStyle: { color: loss } }
            : point;
        }),
      },
    ];
  }

  _options() {
    const locale = { language: this._hass?.locale?.language, currency: this._hass?.config?.currency };
    return {
      xAxis: { type: "time" },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      // The three figures belong together on hover: paid, saved, and the bar.
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { show: true },
    };
  }

  /** A themed colour, resolved from the card's own computed style. */
  _colour({ variable, fallback }) {
    const value = getComputedStyle(this).getPropertyValue(variable).trim();
    return value || fallback;
  }
}

const seriesShape = ({ id, name }, colour) => ({
  id,
  name,
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
