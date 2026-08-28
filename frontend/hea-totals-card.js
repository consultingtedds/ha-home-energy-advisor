/**
 * What the picked period cost, what it would have cost at grid price, and the
 * difference - the summary card of the family (HEA-50).
 *
 * The lifecycle lives in `HeaCard`; this file is the three figures and nothing
 * else. Period selection is Home Assistant's own picker (ADR-0012).
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { changeTone, formatMoney, formatMoneyChange } from "./hea-format.js";
import { fill } from "./hea-labels.js";

export const TAG = "hea-totals-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * The three figures, in the order they answer the question: what it cost, what
 * it would have cost, and the difference.
 *
 * Labelled from the shared vocabulary, so this card cannot drift from the others
 * as it had (HEA-88). ADR-0009's rule is unchanged - the concept names a pricing
 * rule, never absent hardware - and "would have paid" states the counterfactual
 * outright where "at grid price" left it to be inferred.
 */
const FIGURES = [
  { key: "actualCost", label: "paid" },
  { key: "costAtGridPrice", label: "would_have_paid" },
  { key: "costSavings", label: "saved" },
];

class HeaTotalsCard extends HeaCard {
  static titleKey = "title_totals";

  static cardStyle = `
    .figures { display: flex; flex-wrap: wrap; gap: 16px; }
    .figure { flex: 1 1 8em; display: flex; flex-direction: column; gap: 4px; }
    .compare { color: var(--secondary-text-color); font-size: 0.8em; }
    .label {
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value {
      color: var(--primary-text-color);
      font-size: 1.6em;
      font-weight: 500;
      white-space: nowrap;
    }
  `;

  /** Everything this card offers is the shared configuration (HEA-73). */
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** Masonry needs a height estimate; three figures and a caption is about 3. */
  getCardSize() {
    return 3;
  }

  _body(locale) {
    const totals = this._result?.totals;
    const figures = FIGURES.map(({ key, label }) => {
      const value = totals?.[key];
      // A negative saving is a battery arbitrage loss (HEA-39); it keeps its
      // sign and is marked so it reads as the loss it is.
      const loss = key === "costSavings" && value < 0 ? " loss" : "";
      return `
        <div class="figure">
          <span class="label">${this._labels[label]}</span>
          <span class="value${loss}" data-figure="${key}">${formatMoney(value, locale)}</span>
          ${this._comparedTo(key, value, locale)}
        </div>`;
    }).join("");
    return `<div class="figures">${figures}</div>`;
  }

  /**
   * What this figure was last time, and by how much it moved (HEA-96).
   *
   * Absent unless the household turned comparison on in Home Assistant's own
   * picker, which is the normal case - so the card is unchanged for anyone who
   * has not asked.
   *
   * The change is signed and the earlier figure is shown beside it. Either
   * alone is weaker: a bare "EUR 1.20" leaves the direction to be worked out,
   * and a bare "was EUR 13.54" makes the reader do the subtraction. A
   * percentage is deliberately not offered - the base is a device-shaped
   * number that is often pennies, and dividing by it explodes (ADR-0016
   * decision 5, HEA-75).
   */
  _comparedTo(key, value, locale) {
    const before = this._result?.totals?.before?.[key];
    if (!Number.isFinite(before) || !Number.isFinite(value)) return "";
    // Which way is good news depends on the concept: a fall in what was paid
    // and a fall in what was saved are opposite verdicts, and rendering both
    // the same grey left the sign meaning nothing (HEA-99).
    const tone = changeTone(key, value - before);
    const classes = tone ? `compare ${tone}` : "compare";
    return `<span class="${classes}" data-compare="${key}">${fill(
      this._labels.compared,
      {
        change: formatMoneyChange(value - before, locale),
        before: formatMoney(before, locale),
      },
    )}</span>`;
  }
}

/** Nothing beyond the shared fields, but it needs a tag of its own. */
class HeaTotalsCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaTotalsCardEditor);
  registerCard(TAG, HeaTotalsCard, {
    name: "Home Energy Advisor: Totals",
    description:
      "What the selected period cost, what it would have cost at grid price, and the difference.",
  });
};

register();
