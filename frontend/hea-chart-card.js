/**
 * A card that draws with Home Assistant's own chart component (ADR-0013).
 *
 * `ha-chart-base` is what the Energy Dashboard uses, wrapping ECharts bundled
 * into the frontend. Tooltips, legend, zoom, theming and dark mode come with
 * it, and our charts look like the graphs beside them because they are the same
 * engine.
 *
 * Home Assistant loads card modules lazily, so a dashboard carrying only HEA
 * cards may never have pulled that component in. Coaxing it into existence -
 * and saying so plainly when it will not come - lives here, so a second chart
 * card is its series and its options and nothing else.
 *
 * Subclasses implement `_series()` and `_options(locale)`, and may override
 * `_isEmpty()` where "nothing to draw" means something other than no buckets.
 */

import { HeaCard } from "./hea-card-base.js";

/** Home Assistant's chart component, and a card that is known to pull it in. */
const CHART_TAG = "ha-chart-base";
const CHART_BEARING_CARD = { type: "statistics-graph", entities: [] };

export class HeaChartCard extends HeaCard {
  static cardStyle = `
    ha-chart-base { display: block; }
  `;

  constructor() {
    super();
    this._chartReady = Boolean(customElements.get(CHART_TAG));
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
      console.warn(`${CHART_TAG}: could not be loaded`, error);
    }
    this._chartReady = Boolean(customElements.get(CHART_TAG));
    this._render();
  }

  /** Whether the period holds anything worth drawing. */
  _isEmpty() {
    return (this._result?.series ?? []).length === 0;
  }

  _body() {
    if (!this._chartReady) {
      return `<p class="message">Home Assistant's chart component is not loaded.
        Adding any energy or statistics card to this dashboard will load it.</p>`;
    }
    if (this._isEmpty()) {
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
    chart.options = this._options(this._chartLocale());
  }

  /** The language and currency the axis and tooltip label themselves with. */
  _chartLocale() {
    return {
      language: this._hass?.locale?.language,
      currency: this._hass?.config?.currency,
    };
  }

  /** A themed colour, resolved from the card's own computed style. */
  _colour({ variable, fallback }) {
    const value = getComputedStyle(this).getPropertyValue(variable).trim();
    return value || fallback;
  }
}
