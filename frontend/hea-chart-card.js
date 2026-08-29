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
 *
 * `ha-chart-base` is not the only component worth reusing: the Sankey view
 * draws with `ha-sankey-chart`, which is a different element loaded by a
 * different card (HEA-90). So which component to wait for, and what to create
 * to get it, are the subclass's to name - the waiting itself is the same.
 */

import { HeaCard } from "./hea-card-base.js";

export class HeaChartCard extends HeaCard {
  /** Home Assistant's chart component, and a card known to pull it in. */
  static chartTag = "ha-chart-base";
  static bearingCard = { type: "statistics-graph", entities: [] };

  /** The vocabulary key for an empty period; money, unless a card says otherwise. */
  static emptyKey = "no_cost_in_period";

  /**
   * How tall the chart stands, because left alone it is half its own width.
   *
   * `ha-chart-base` sizes itself `max(clientWidth / 2, 200)` when no height is
   * given, so the same chart is 350px on a desktop and 200px across a phone in
   * portrait - which is where "what each device cost" was reported as having
   * almost no vertical scale (HEA-93).
   *
   * The clamp only ever raises that floor: any card wide enough to reach 350px
   * still does, since the component caps at `--chart-max-height` (350px) too.
   * Set as a property rather than as CSS on the host, which would size the
   * element without reaching the inner container that actually draws.
   */
  static chartHeight = "clamp(300px, 50vw, 350px)";

  static cardStyle = `
    ha-chart-base { display: block; }
  `;

  constructor() {
    super();
    this._chartReady = Boolean(customElements.get(this.constructor.chartTag));
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
   * Nudge Home Assistant into loading its chart component, and draw whenever
   * it arrives.
   *
   * Creating any built-in card that draws a chart imports it as a side effect.
   * If it never arrives the card says so, rather than leaving an empty box the
   * user cannot interpret.
   *
   * The waiting is `whenDefined` rather than a check, because registration is a
   * race this card does not control and need not win. Our nudge is not
   * necessarily what causes it - another card on the dashboard can pull the
   * same component in a moment later, and a dashboard still loading its cards
   * routinely registers it after the nudge has returned. Asking once, at that
   * instant, is how HEA-90 first shipped: on the live dashboard the card sat on
   * "not loaded" beside a working chart of the very same kind, with the element
   * already defined and nothing left to re-check it.
   */
  async _loadChartComponent() {
    const { chartTag, bearingCard } = this.constructor;
    customElements.whenDefined(chartTag).then(() => {
      this._chartReady = true;
      this._render();
    });
    try {
      const helpers = await globalThis.loadCardHelpers?.();
      await helpers?.createCardElement(bearingCard);
    } catch (error) {
      console.warn(`${chartTag}: could not be loaded`, error);
    }
  }

  /** Whether the period holds anything worth drawing. */
  _isEmpty() {
    return (this._result?.series ?? []).length === 0;
  }

  _body() {
    if (!this._chartReady) {
      return `<p class="message">${this._labels.chart_not_loaded}</p>`;
    }
    if (this._isEmpty()) {
      return `<p class="message">${this._labels[this._emptyKey()]}</p>`;
    }
    return this._chartMarkup();
  }

  /**
   * What "nothing to draw" says, since not every chart draws money.
   *
   * A card measuring energy told a household no *cost* was recorded, which is
   * a claim about a different quantity from the one it was showing (HEA-93).
   * Static like `titleKey`, with the same override for a card whose answer
   * depends on how it has been configured.
   */
  _emptyKey() {
    return this.constructor.emptyKey;
  }

  /** The element itself, for a card drawing with something other than ECharts axes. */
  _chartMarkup() {
    return `<ha-chart-base chart-type="bar"></ha-chart-base>`;
  }

  /** The chart takes its data and options as properties, not as markup. */
  _afterRender() {
    const chart = this.shadowRoot.querySelector(this.constructor.chartTag);
    if (!chart) return;
    chart.hass = this._hass;
    this._draw(chart);
  }

  /** What to set on the component once it is in the tree. */
  _draw(chart) {
    chart.height = this.constructor.chartHeight;
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
