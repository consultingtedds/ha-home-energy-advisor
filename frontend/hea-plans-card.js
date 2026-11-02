/**
 * Every tariff plan, priced against what the meters recorded (HEA-255, ADR-0036).
 *
 * The integration prices each plan the household has entered at the electricity
 * it actually imported and exported over the period, and this card lists them
 * cheapest first: each plan's total and what it is made of, the household's own
 * plan marked, and how much more or less every other would have cost.
 *
 * Like the installation card it covers the whole home and ignores the page
 * filter: a plan prices the grid meters, which no device or room divides. And it
 * does not lead with Paid (ADR-0029). Paid is priced from the engine's
 * allocation without daily charges, so every plan, the household's own
 * included, is priced here the same way instead, and compared with that.
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { formatMoney, savingTone } from "./hea-format.js";
import { fill, loadLabels } from "./hea-labels.js";

export const TAG = "hea-plans-card";
const EDITOR_TAG = `${TAG}-editor`;
const COMPARE_PLANS = "home_energy_advisor/compare_plans";

/** What each total is made of, in the order it is built. */
const PARTS = [
  { key: "energy", label: "plans_energy", sign: 1 },
  { key: "export", label: "plans_export", figure: "export_credit", sign: -1 },
  { key: "daily", label: "plans_daily", figure: "daily_charges", sign: 1 },
];

/** Cheapest first, and a plan that cannot be priced after every one that can. */
const byTotal = (a, b) => {
  if (a.incomplete || b.incomplete) return (a.incomplete ? 1 : 0) - (b.incomplete ? 1 : 0);
  return a.total - b.total;
};

class HeaPlansCard extends HeaCard {
  static titleKey = "title_plans";

  static cardStyle = `
    .plans { display: flex; flex-direction: column; gap: var(--hea-space-m); }
    .plan + .plan {
      padding-top: var(--hea-space-m);
      border-top: 1px solid var(--divider-color);
    }
    .head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: var(--hea-space-m);
    }
    .name { color: var(--primary-text-color); font-weight: 500; }
    .tag {
      margin-inline-start: var(--hea-space-s);
      padding: 0 var(--hea-space-s);
      border-radius: var(--ha-border-radius-pill, 9px);
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      font-size: 0.8em;
      font-weight: normal;
    }
    .total { font-size: 1.4em; white-space: nowrap; }
    .parts, .difference, .incomplete {
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    .parts { display: flex; flex-wrap: wrap; gap: 0 var(--hea-space-m); }
    .part .value { color: var(--primary-text-color); white-space: nowrap; }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** A few plans, each a line and its parts, and a note. */
  getCardSize() {
    return 5;
  }

  /** The whole home, never the filtered subset: plans price the grid meters. */
  async _fetch() {
    if (!this._hass || !this._period) return;
    const request = ++this._request;
    await loadLabels(this._hass);
    try {
      const compared = await this._hass.callWS({
        type: COMPARE_PLANS,
        start_time: this._period.start.toISOString(),
        end_time: this._period.end.toISOString(),
      });
      if (request !== this._request) return;
      this._compared = compared;
      this._state = compared?.plans?.length ? "ready" : "empty";
    } catch (error) {
      if (request !== this._request) return;
      this._state = "error";
      console.error(`${this.localName}: could not compare the plans`, error);
    }
    this._render();
  }

  _content(locale) {
    if (this._state === "empty") {
      return `<p class="message">${this._labels.no_plans}</p>`;
    }
    return super._content(locale);
  }

  _body(locale) {
    // Drawn while loading too, before there is anything to list.
    if (!this._compared?.plans) return "";
    const plans = [...this._compared.plans].sort(byTotal);
    const priced = plans.filter((plan) => !plan.incomplete);
    const current = priced.find((plan) => plan.current);
    // Only worth saying where there is something it is cheaper than.
    const cheapest = priced.length > 1 ? priced[0] : undefined;
    const notes = [
      this._compared.hours === 0 ? this._labels.plans_no_readings : "",
      current ? "" : this._labels.plans_no_current,
      this._labels.plans_note,
    ].filter(Boolean);
    return `
      <div class="plans">
        ${plans.map((plan) => this._plan(plan, { current, cheapest }, locale)).join("")}
      </div>
      ${notes.map(hint).join("")}`;
  }

  /** One plan: its name and total, what the total is made of, and the difference. */
  _plan(plan, { current, cheapest }, locale) {
    const tags = [
      plan.current ? this._labels.plans_your_plan : "",
      plan === cheapest ? this._labels.plans_cheapest : "",
    ]
      .filter(Boolean)
      .map((tag) => `<span class="tag">${tag}</span>`)
      .join("");
    const total = plan.incomplete ? "" : this._total(plan, locale);
    const head = `
      <div class="head">
        <span class="name">${escape(plan.name)}${tags}</span>
        ${total}
      </div>`;
    if (plan.incomplete) {
      return `<div class="plan" data-plan="${plan.id}">${head}
        <div class="incomplete">${this._labels.plans_incomplete}</div></div>`;
    }
    return `<div class="plan" data-plan="${plan.id}">${head}
      <div class="parts">${PARTS.map((part) => this._part(plan, part, locale)).join("")}</div>
      ${current && plan !== current ? this._difference(plan, current, locale) : ""}
    </div>`;
  }

  _total(plan, locale) {
    return `<span class="total" data-figure="total:${plan.id}">${formatMoney(
      plan.total,
      locale,
    )}</span>`;
  }

  _part(plan, { key, label, figure = key, sign }, locale) {
    return `
      <span class="part">${this._labels[label]}
        <span class="value" data-figure="${key}:${plan.id}">${formatMoney(
          sign * plan[figure],
          locale,
        )}</span>
      </span>`;
  }

  /** How much less or more than the household's own plan, as a saving is toned. */
  _difference(plan, current, locale) {
    const saving = current.total - plan.total;
    const tone = savingTone(saving, locale);
    const amount = formatMoney(Math.abs(saving), locale);
    let wording = this._labels.plans_same;
    if (tone === "gain") wording = fill(this._labels.plans_less, { amount });
    if (tone === "loss") wording = fill(this._labels.plans_more, { amount });
    const classes = tone ? `difference ${tone}` : "difference";
    return `<div class="${classes}" data-figure="difference:${plan.id}">${wording}</div>`;
  }
}

const hint = (note) => `<div class="hint">${note}</div>`;

/** A plan's name is the household's own words, so it is shown as text, not markup. */
const escape = (value) =>
  String(value).replaceAll(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character],
  );

/** Nothing beyond the shared fields, but it needs a tag of its own. */
class HeaPlansCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaPlansCardEditor);
  registerCard(TAG, HeaPlansCard, {
    name: "Home Energy Advisor: Compare tariff plans",
    description:
      "What each tariff plan you have entered would have cost over the selected period, for the whole home.",
  });
};

register();
