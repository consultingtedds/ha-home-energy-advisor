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
import { formatDateTime, formatMoney, savingTone } from "./hea-format.js";
import { fill, loadLabels } from "./hea-labels.js";

export const TAG = "hea-plans-card";
const EDITOR_TAG = `${TAG}-editor`;
const COMPARE_PLANS = "home_energy_advisor/compare_plans";

/**
 * What each total is made of, in the order it is built.
 *
 * Each as the money it is: the export credit is income, and the label says so,
 * so it reads as a figure coming in rather than a cost below zero. The total
 * still takes it off (HEA-277, discussion 58).
 */
const PARTS = [
  { key: "energy", label: "plans_energy" },
  { key: "export", label: "plans_export", figure: "export_credit" },
  { key: "daily", label: "plans_daily", figure: "daily_charges" },
];

/** A plan with no figure: bands that leave hours unpriced, or no market price. */
const unpriced = (plan) => Boolean(plan.incomplete || plan.no_price);

/** A plan priced from a market price entity, which says what it rests on. */
const followsTheMarket = (plan) => "carried_hours" in plan;

/** Cheapest first, and a plan that cannot be priced after every one that can. */
const byTotal = (a, b) => {
  if (unpriced(a) || unpriced(b)) return (unpriced(a) ? 1 : 0) - (unpriced(b) ? 1 : 0);
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
    const priced = plans.filter((plan) => !unpriced(plan));
    const current = priced.find((plan) => plan.current);
    // Only worth saying where there is something it is cheaper than.
    const cheapest = priced.length > 1 ? priced[0] : undefined;
    const notes = [
      this._compared.hours === 0 ? this._labels.plans_no_readings : "",
      current ? "" : this._labels.plans_no_current,
      this._labels.plans_note,
      priced.some(followsTheMarket) ? this._resolution(locale) : "",
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
    const total = unpriced(plan) ? "" : this._total(plan, locale);
    const head = `
      <div class="head">
        <span class="name">${escape(plan.name)}${tags}</span>
        ${total}
      </div>`;
    if (unpriced(plan)) {
      const why = plan.no_price ? this._labels.plans_no_price : this._labels.plans_incomplete;
      return `<div class="plan" data-plan="${plan.id}">${head}
        <div class="incomplete">${why}</div></div>`;
    }
    return `<div class="plan" data-plan="${plan.id}">${head}
      <div class="parts">${PARTS.map((part) => this._part(plan, part, locale)).join("")}</div>
      ${this._exportNotes(plan, locale)}
      ${current && plan !== current ? this._difference(plan, current, locale) : ""}
      ${this._marketNotes(plan, locale)}
    </div>`;
  }

  /**
   * Export a capped plan did not pay, where its cap bit (HEA-258).
   *
   * Without it, a plan with a high export price would simply total less than
   * the price suggests, and a household could not see why.
   */
  _exportNotes(plan, locale) {
    return [
      ["unpaid", plan.export_unpaid, this._labels.plans_export_unpaid],
      ["carried", plan.export_carried, this._labels.plans_export_carried],
    ]
      .filter(([, amount]) => amount > 0)
      .map(
        ([kind, amount, wording]) =>
          `<div class="difference" data-figure="export-${kind}:${plan.id}">${fill(
            wording,
            { amount: formatMoney(amount, locale) },
          )}</div>`,
      )
      .join("");
  }

  /** What a market-priced plan's figures rest on, where there is anything to say. */
  _marketNotes(plan, locale) {
    const notes = [];
    if (plan.priced_from) {
      const date = formatDateTime(new Date(plan.priced_from), locale);
      notes.push(fill(this._labels.plans_priced_from, { date }));
    }
    if (plan.carried_hours > 0) {
      const hours = new Intl.NumberFormat(locale.language, {
        maximumFractionDigits: 1,
      }).format(plan.carried_hours);
      notes.push(fill(this._labels.plans_carried, { hours }));
    }
    return notes.map((note) => `<div class="difference">${note}</div>`).join("");
  }

  /**
   * How finely market prices were applied over the period (ADR-0037): five
   * minutes at a time where the recorder still keeps them, hourly before.
   */
  _resolution(locale) {
    const from = this._compared.five_minute_from;
    if (!from) return this._labels.plans_market_hourly;
    const fine = new Date(from);
    if (fine <= this._period.start) return this._labels.plans_market_five_minutes;
    return fill(this._labels.plans_market_from, { date: formatDateTime(fine, locale) });
  }

  _total(plan, locale) {
    return `<span class="total" data-figure="total:${plan.id}">${formatMoney(
      plan.total,
      locale,
    )}</span>`;
  }

  _part(plan, { key, label, figure = key }, locale) {
    return `
      <span class="part">${this._labels[label]}
        <span class="value" data-figure="${key}:${plan.id}">${formatMoney(
          plan[figure],
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
