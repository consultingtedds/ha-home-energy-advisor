/**
 * What the picked period cost, what it would have cost at grid price, and the
 * difference — the summary card of the family (HEA-50).
 *
 * The lifecycle lives in `HeaCard`; this file is the three figures and nothing
 * else. Period selection is Home Assistant's own picker (ADR-0012).
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { formatMoney } from "./hea-format.js";

export const TAG = "hea-totals-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * The three figures, in the order they answer the question: what it cost, what
 * it would have cost, and the difference. Names settled in ADR-0009 — "Cost at
 * Grid Price", never "Cost Without Solar".
 */
const FIGURES = [
  { key: "actualCost", label: "Actual Cost" },
  { key: "costAtGridPrice", label: "Cost at Grid Price" },
  { key: "costSavings", label: "Saved" },
];

class HeaTotalsCard extends HeaCard {
  static cardStyle = `
    .figures { display: flex; flex-wrap: wrap; gap: 16px; }
    .figure { flex: 1 1 8em; display: flex; flex-direction: column; gap: 4px; }
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
          <span class="label">${label}</span>
          <span class="value${loss}" data-figure="${key}">${formatMoney(value, locale)}</span>
        </div>`;
    }).join("");
    return `<div class="figures">${figures}</div>`;
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
