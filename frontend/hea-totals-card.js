/**
 * What the picked period cost, what it would have cost at grid price, and the
 * difference - the summary card of the family (HEA-50).
 *
 * The lifecycle lives in `HeaCard`; this file is the three figures and nothing
 * else. Period selection is Home Assistant's own picker (ADR-0012).
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import {
  changeTone,
  formatMoney,
  formatMoneyChange,
  savingTone,
} from "./hea-format.js";
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
    .figures { display: flex; flex-wrap: wrap; gap: var(--hea-space-l); }
    .figure {
      flex: 1 1 8em;
      display: flex;
      flex-direction: column;
      gap: var(--hea-space-xs);
    }
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
    /*
     * Three figures at 8em plus two gaps need about 368px, and a phone leaves
     * roughly 340px of card - so they wrapped two-then-one, orphaning Saved on
     * a line of its own, and the comparison line wrapped again inside its
     * column (HEA-103). One per row reads better than an uneven grid: the
     * label sits against its figure and nothing is squeezed.
     */
    @media (max-width: 767px) {
      .figures { flex-direction: column; gap: var(--hea-space-m); }
      .figure {
        flex: 1 1 auto;
        flex-direction: row;
        flex-wrap: wrap;
        align-items: baseline;
        justify-content: space-between;
        gap: var(--hea-space-m);
      }
      /* Its own line beneath the pair, rather than a third thing competing
         for the same row - it is a qualification of the figure, not a peer. */
      .compare { flex-basis: 100%; text-align: right; }
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
      // The saving is the one figure here with a direction of its own: more is
      // better, and less than none is a battery-arbitrage loss (HEA-39). Both
      // ways round, because marking only the loss left the absence of red
      // meaning either "fine" or "no rule here" (HEA-102). Paid and Would have
      // paid get nothing - spending is the bill, not bad news.
      const verdict = key === "costSavings" ? savingTone(value) : "";
      const tone = verdict ? ` ${verdict}` : "";
      return `
        <div class="figure">
          <span class="label">${this._labels[label]}</span>
          <span class="value${tone}" data-figure="${key}">${formatMoney(value, locale)}</span>
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
