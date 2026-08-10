/**
 * Cost over time, stacked — the headline chart of the family (HEA-50).
 *
 * The whole bar is Cost at Grid Price; the lower segment is what was actually
 * paid, the upper what was saved. One glance gives spend, counterfactual and
 * saving, and the segments sum to something real (ADR-0012).
 *
 * The drawing is hand-rolled SVG rather than a charting library: the flagship
 * view must work with no separate install (ADR-0008), which rules out
 * ApexCharts and Plotly, and the shape needed here is a stacked bar with a
 * signed segment — not enough to justify shipping a chart engine.
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { escapeText, formatMoney, formatPeriod } from "./hea-format.js";

export const TAG = "hea-cost-over-time-card";
const EDITOR_TAG = `${TAG}-editor`;

/** The drawing surface. Unitless: the svg scales to whatever width it gets. */
const VIEW = { width: 600, height: 220 };
const PAD = { top: 12, right: 8, bottom: 22, left: 48 };
const PLOT = {
  width: VIEW.width - PAD.left - PAD.right,
  height: VIEW.height - PAD.top - PAD.bottom,
};

/** Share of each slot the bar occupies, the rest being the gap. */
const BAR_FILL = 0.7;

const round = (value) => Math.round(value * 100) / 100;

class HeaCostOverTimeCard extends HeaCard {
  static cardStyle = `
    svg { width: 100%; height: auto; display: block; }
    .paid { fill: var(--primary-color, #03a9f4); }
    .saved { fill: var(--success-color, #4caf50); }
    .saved.loss { fill: var(--error-color, #db4437); }
    .baseline { stroke: var(--divider-color, #e0e0e0); stroke-width: 1; }
    .tick {
      fill: var(--secondary-text-color);
      font-size: 11px;
      font-family: inherit;
    }
    .legend {
      display: flex;
      gap: 16px;
      margin-top: 8px;
      color: var(--secondary-text-color);
      font-size: 0.85em;
    }
    .key { display: inline-flex; align-items: center; gap: 6px; }
    .swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
    .swatch.paid { background: var(--primary-color, #03a9f4); }
    .swatch.saved { background: var(--success-color, #4caf50); }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** A chart needs real height, unlike a row of figures. */
  getCardSize() {
    return 6;
  }

  _body(locale) {
    const series = this._result?.series ?? [];
    if (series.length === 0) {
      return `<p class="message">No cost recorded in this period.</p>`;
    }
    return `${this._chart(series, locale)}${LEGEND}`;
  }

  _chart(series, locale) {
    const scale = scaleFor(series);
    const slot = PLOT.width / series.length;
    const barWidth = slot * BAR_FILL;
    const bars = series
      .map((row, index) => {
        const x = PAD.left + index * slot + (slot - barWidth) / 2;
        return this._bar(row, x, barWidth, scale, locale);
      })
      .join("");
    return `
      <svg viewBox="0 0 ${VIEW.width} ${VIEW.height}" role="img"
           aria-label="Cost over time, actual against grid price">
        ${bars}
        <line class="baseline" x1="${PAD.left}" y1="${round(scale.zero)}"
              x2="${round(PAD.left + PLOT.width)}" y2="${round(scale.zero)}" />
        ${this._ticks(series, scale, locale)}
      </svg>`;
  }

  /**
   * One bar: what was paid, and what was saved stacked on top of it.
   *
   * A negative saving is drawn below the axis instead, which is how the Energy
   * Dashboard already renders exported energy and battery charge — the
   * convention a household has seen before (ADR-0012 decision 3).
   */
  _bar(row, x, width, scale, locale) {
    const saved = row.costSavings;
    const savedSpan =
      saved < 0 ? span(scale, 0, saved) : span(scale, row.actualCost, row.costAtGridPrice);
    return `
      <g class="bar">
        <title>${escapeText(this._label(row, locale))}</title>
        <rect class="paid" x="${round(x)}" width="${round(width)}"
              y="${round(span(scale, 0, row.actualCost).y)}"
              height="${round(span(scale, 0, row.actualCost).height)}" />
        <rect class="saved${saved < 0 ? " loss" : ""}" x="${round(x)}" width="${round(width)}"
              y="${round(savedSpan.y)}" height="${round(savedSpan.height)}" />
      </g>`;
  }

  _label(row, locale) {
    const day = formatPeriod({ start: row.start, end: row.start }, locale);
    return [
      day,
      `paid ${formatMoney(row.actualCost, locale)}`,
      `at grid price ${formatMoney(row.costAtGridPrice, locale)}`,
      `saved ${formatMoney(row.costSavings, locale)}`,
    ].join(" · ");
  }

  /** The top of the scale, the zero line, and the range the bars cover. */
  _ticks(series, scale, locale) {
    const first = formatPeriod({ start: series[0].start, end: series[0].start }, locale);
    const last = series.at(-1);
    const lastLabel = formatPeriod({ start: last.start, end: last.start }, locale);
    return `
      <text class="tick" x="${PAD.left - 6}" y="${round(PAD.top + 4)}" text-anchor="end">${escapeText(formatMoney(scale.max, locale))}</text>
      <text class="tick" x="${PAD.left - 6}" y="${round(scale.zero + 4)}" text-anchor="end">${escapeText(formatMoney(0, locale))}</text>
      <text class="tick" x="${PAD.left}" y="${VIEW.height - 6}">${escapeText(first)}</text>
      <text class="tick" x="${round(PAD.left + PLOT.width)}" y="${VIEW.height - 6}" text-anchor="end">${escapeText(lastLabel)}</text>`;
  }
}

const LEGEND = `
  <div class="legend">
    <span class="key"><span class="swatch paid"></span>Paid</span>
    <span class="key"><span class="swatch saved"></span>Saved</span>
  </div>`;

/**
 * A value-to-pixel scale covering every bar.
 *
 * The top is the dearest bar at grid price and the bottom is the deepest loss,
 * so bars are comparable with each other rather than each filling its own
 * height. A period in which nothing ran has no range at all — dividing by it
 * would put NaN in the geometry and collapse the card silently — so it falls
 * back to a nominal range and draws flat.
 */
const scaleFor = (series) => {
  const max = Math.max(0, ...series.map((row) => Math.max(row.actualCost, row.costAtGridPrice)));
  const min = Math.min(0, ...series.map((row) => row.costSavings));
  const range = max - min || 1;
  const y = (value) => PAD.top + ((max - value) / range) * PLOT.height;
  return { max, min, y, zero: y(0) };
};

/** The rectangle between two values, whichever way round they are. */
const span = (scale, from, to) => {
  const a = scale.y(from);
  const b = scale.y(to);
  return { y: Math.min(a, b), height: Math.abs(a - b) };
};

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
