/**
 * Where the money went: household to floor to room to device (HEA-90).
 *
 * The last card in HEA-50's family, and the only one answering a different
 * question from the rest - not which device cost most, but which part of the
 * house did. It needs the hierarchy HEA-58 publishes on every device row, so it
 * could not be built until that existed.
 *
 * Drawn by Home Assistant's own `ha-sankey-chart`. Its *card* is bound to the
 * energy preferences and cannot show our statistics, but the component beneath
 * it takes `{nodes, links}` and nothing else, so the diagram is HA's and only
 * the arrangement is ours (ADR-0017's ladder, recorded on the ticket). That
 * component wraps ECharts' native `sankey` series through `ha-chart-base`,
 * which keeps this inside ADR-0013 and brings themed colours, label spacing, a
 * resize observer, tooltips and click-to-more-info with it.
 *
 * The arrangement lives in `hea-sankey-layout.js`, free of the DOM, because the
 * part worth testing hardest is arithmetic: every level has to sum to the one
 * above it.
 *
 * This card shows cost, not saving. A negative saving has no meaning in a flow
 * diagram, and there is nowhere honest to draw it.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { formatEnergy, formatMoney } from "./hea-format.js";
import { buildDistribution } from "./hea-sankey-layout.js";

export const TAG = "hea-distribution-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * What the diagram measures, and how each half of that reads.
 *
 * Cost is the default: this is a cost integration, and "what did the house
 * spend, and where" is the question the other cards cannot answer by room.
 *
 * Energy earns its place rather than duplicating Home Assistant's own Sankey.
 * On a sunny day almost everything a household uses is free, so a cost diagram
 * collapses to the untracked remainder and whatever ran overnight - a pump can
 * be the second largest consumer in the house and draw as a hairline because it
 * cost nothing. That is honest and it is the point of a cost view, but it is
 * not the whole picture, and the energy view is where the source column lives
 * (see `METRICS` in the layout for why cost cannot have one).
 */
const METRICS = {
  cost: { titleKey: "title_distribution", format: formatMoney },
  energy: { titleKey: "title_distribution_energy", format: formatEnergy },
};

/**
 * Where four columns stop fitting across a screen.
 *
 * Home Assistant's own Sankey card turns at its `_isMobileSize` breakpoint;
 * this is that width, so the two cards turn together rather than one going
 * sideways beside another that has not.
 */
const NARROW = "(max-width: 767px)";

/** As Home Assistant's card names them, so a household meets one vocabulary. */
const LAYOUTS = ["auto", "horizontal", "vertical"];

class HeaDistributionCard extends HeaChartCard {
  static titleKey = "title_distribution";

  /**
   * A different component from the other chart cards, and a different card
   * pulls it in. Creating an `energy-sankey` imports `ha-sankey-chart` as a side
   * effect; it is safe to create with no configuration, because its `setConfig`
   * only merges defaults when no collection key is given and it subscribes to
   * the energy collection on connect, which `createCardElement` never does.
   */
  static chartTag = "ha-sankey-chart";
  static bearingCard = { type: "energy-sankey" };

  static cardStyle = `
    ha-sankey-chart { display: block; height: 400px; }
    :host([data-vertical]) ha-sankey-chart { height: 600px; }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * Nothing to draw is a period in which nothing cost anything - which is not
   * the same as no buckets, since a device can record a bucket of zero.
   */
  _isEmpty() {
    return this._layout().nodes.length === 0;
  }

  /** Cost unless the household asked for energy; an unknown value is cost. */
  _metric() {
    return METRICS[this._config?.metric] ? this._config.metric : "cost";
  }

  _titleKey() {
    return METRICS[this._metric()].titleKey;
  }

  _layout() {
    return buildDistribution(this._result?.devices ?? [], this._labels, {
      metric: this._metric(),
      // The layout knows which token each source wants; only the card can read
      // one, so it resolves them against the household's theme (HEA-93).
      colour: (source) => this._colour(source),
    });
  }

  _chartMarkup() {
    return `<ha-sankey-chart></ha-sankey-chart>`;
  }

  _draw(chart) {
    chart.data = this._layout();
    chart.vertical = this._isVertical();
    // An allocated share is a proportion of a blended price, so it divides into
    // a long recurring decimal. Left raw, a hover reads out fourteen places of
    // a euro - unreadable, and claiming a precision money does not have.
    const locale = this._chartLocale();
    const { format } = METRICS[this._metric()];
    chart.valueFormatter = (value) => format(value, locale);
    // The taller layout needs the card to know, and CSS cannot ask the chart.
    this.toggleAttribute("data-vertical", chart.vertical);
  }

  /**
   * Sideways on a phone, across the page otherwise.
   *
   * A household that has chosen decides; `auto` asks the screen. Where the
   * browser cannot answer - `matchMedia` is not universally present - the
   * answer is horizontal, because an unreadable screen size is not a reason to
   * refuse to draw.
   */
  _isVertical() {
    const layout = this._config?.layout;
    if (layout === "vertical") return true;
    if (layout === "horizontal") return false;
    return Boolean(globalThis.matchMedia?.(NARROW)?.matches);
  }
}

class HeaDistributionCardEditor extends HeaCardEditor {
  _extraSchema() {
    return [
      {
        name: "metric",
        selector: { select: { mode: "dropdown", options: Object.keys(METRICS) } },
      },
      {
        name: "layout",
        selector: { select: { mode: "dropdown", options: LAYOUTS } },
      },
    ];
  }
}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaDistributionCardEditor);
  registerCard(TAG, HeaDistributionCard, {
    name: "Home Energy Advisor: Cost distribution",
    description: "Where the period's cost went, by floor, room and device.",
  });
};

register();
