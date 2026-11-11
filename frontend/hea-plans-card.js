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

import { HeaCard, NARROW, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import {
  formatDateTime,
  formatEnergy,
  formatMoney,
  formatRate,
  rateUnit,
  savingTone,
} from "./hea-format.js";
import { fill, loadLabels } from "./hea-labels.js";
import { TABLE_STYLE } from "./hea-table-card.js";

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
  { key: "energy", label: "plans_energy", group: "pay" },
  { key: "daily", label: "plans_daily", figure: "daily_charges", group: "pay" },
  { key: "export", label: "plans_export", figure: "export_credit", group: "earn" },
];

/**
 * The parts under a heading each, in the order a bill reads: what is paid, then
 * what is earned, then the total. Told apart by heading and by a faint tint on
 * what is earned, never by a minus or a coloured figure (HEA-280).
 */
const GROUPS = [
  { key: "pay", label: "plans_you_pay" },
  { key: "earn", label: "plans_you_earn" },
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

  /** Wide and narrow draw different columns, so the card redraws between them. */
  static narrowQuery = NARROW;

  static cardStyle = `${TABLE_STYLE}
    .flows {
      margin-bottom: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    /* As wide as the figures, not the card: spread across a full-width tab, a
       plan's figures sat too far apart to read across (HEA-280). The wrapper
       hugs the table too, so its scroll shadows sit at the table's own edges. */
    .scroll { width: fit-content; max-width: 100%; }
    /* A table that reads as one: bordered, its head shaded, a rule wherever a
       group of columns starts, so the figures never run into the notes below. */
    .plans {
      width: auto;
      font-variant-numeric: tabular-nums;
      border: 1px solid var(--divider-color, #e0e0e0);
    }
    .plans th, .plans td { padding-inline: 12px; }
    .plans thead th { background: var(--secondary-background-color); }
    .plans thead tr.groups th { border-bottom: none; text-align: center; }
    .plans .rule { border-left: 1px solid var(--divider-color, #e0e0e0); }
    .plans .earn {
      background: color-mix(in srgb, var(--success-color, #4caf50) 9%, transparent);
    }
    .plans thead .earn {
      background: color-mix(
        in srgb,
        var(--success-color, #4caf50) 9%,
        var(--secondary-background-color)
      );
    }
    th.prices { text-align: left; }
    td.prices {
      text-align: left;
      color: var(--secondary-text-color);
      font-size: 0.85em;
      line-height: 1.6;
    }
    td.prices .rate { color: var(--primary-text-color); }
    .plans tbody td, .plans tbody th { border-bottom: none; vertical-align: top; }
    .plans tbody + tbody tr:first-child > * {
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .plans tbody th { font-weight: 500; color: var(--primary-text-color); }
    .tags { display: block; margin-top: 2px; font-weight: normal; }
    .tag {
      display: inline-block;
      margin-inline-end: var(--hea-space-s);
      padding: 0 var(--hea-space-s);
      border-radius: var(--ha-border-radius-pill, 9px);
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
    td.total { font-weight: 500; }
    tr.note td {
      padding-top: 0;
      padding-left: 14px;
      text-align: left;
      white-space: normal;
      color: var(--secondary-text-color);
      font-size: 0.85em;
    }
    td.incomplete {
      text-align: left;
      white-space: normal;
      color: var(--secondary-text-color);
    }
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
    const wide = !this._isNarrow();
    const parts = wide ? PARTS : [];
    const notes = [
      this._compared.hours === 0 ? this._labels.plans_no_readings : "",
      current ? "" : this._labels.plans_no_current,
      this._labels.plans_note,
      wide ? "" : this._labels.plans_breakdown_hidden,
      priced.some(followsTheMarket) ? this._resolution(locale) : "",
    ].filter(Boolean);
    const layout = { current, cheapest, parts, prices: wide };
    return `
      ${this._flows(locale)}
      <div class="scroll">
        <table class="plans">
          <thead>${this._head(layout)}</thead>
          ${plans.map((plan) => this._plan(plan, layout, locale)).join("")}
        </table>
      </div>
      ${notes.map(hint).join("")}`;
  }

  /**
   * The column heads, under a heading for each group where the breakdown is
   * shown: what the household would pay, and what it would earn.
   */
  _head({ parts, prices }) {
    const leading = [this._labels.plans_plan, ...(prices ? [this._labels.plans_prices] : [])];
    const cell = (label, classes = "") => `<th${classAttribute(classes)}>${label}</th>`;
    const columns = [
      cell(this._labels.plans_plan),
      ...(prices ? [cell(this._labels.plans_prices, "prices")] : []),
      ...parts.map((part, index) =>
        cell(this._labels[part.label], this._partClasses(part, index)),
      ),
      cell(this._labels.plans_total, "rule"),
      cell(this._labels.plans_vs_current),
    ].join("");
    if (!parts.length) return `<tr>${columns}</tr>`;
    const groups = GROUPS.map((group) => {
      const span = parts.filter((part) => part.group === group.key).length;
      const classes = group.key === "earn" ? "rule earn" : "rule";
      return `<th class="${classes}" colspan="${span}">${this._labels[group.label]}</th>`;
    }).join("");
    return `<tr class="groups"><th colspan="${leading.length}"></th>${groups}<th colspan="2" class="rule"></th></tr>
      <tr>${columns}</tr>`;
  }

  /** Where a part's group starts, a rule; what is earned, a tint. */
  _partClasses(part, index) {
    const starts = index === 0 || PARTS[index - 1].group !== part.group;
    return [starts ? "rule" : "", part.group === "earn" ? "earn" : ""]
      .filter(Boolean)
      .join(" ");
  }

  /**
   * A plan's own prices, one to a line as an offer lists them: each named price
   * per kWh, what export pays, and the daily charge. A plan at the market says
   * so instead of naming a price it does not have.
   */
  _prices(plan, locale) {
    const rates = plan.rates;
    if (!rates) return "<td></td>";
    const unit = rateUnit(locale);
    const line = (label, value) =>
      `<div>${escape(label)} <span class="rate">${value}</span></div>`;
    const imports = rates.import_market
      ? [line(this._labels.plans_market_price, "")]
      : rates.prices.map((price) =>
          line(price.name, `${formatRate(price.import, locale)} ${unit}`),
        );
    const exportRate = rates.export_market
      ? this._labels.plans_market_price
      : `${formatRate(rates.export, locale)} ${unit}`;
    const daily = fill(this._labels.plans_per_day, {
      amount: formatMoney(rates.daily_charge, locale),
    });
    const lines = [
      ...imports,
      line(this._labels.plans_export_rate, exportRate),
      line(this._labels.plans_daily_rate, daily),
    ];
    return `<td class="prices">${lines.join("")}</td>`;
  }

  /**
   * What the meters recorded, said once: the same for every plan, because the
   * kWh are the household's and only the prices are the plan's (HEA-280).
   */
  _flows(locale) {
    if (!this._compared.hours) return "";
    return `<div class="flows">${fill(this._labels.plans_flows, {
      imported: formatEnergy(this._compared.imported_kwh, locale),
      exported: formatEnergy(this._compared.exported_kwh, locale),
    })}</div>`;
  }

  /**
   * One plan: a row of its figures, and any notes on it beneath, together in a
   * group of their own so a note is never read as the next plan's.
   */
  _plan(plan, { current, cheapest, parts, prices }, locale) {
    const tags = [
      plan.current ? this._labels.plans_your_plan : "",
      plan === cheapest ? this._labels.plans_cheapest : "",
    ]
      .filter(Boolean)
      .map((tag) => `<span class="tag">${tag}</span>`)
      .join("");
    const name = `<th>${escape(plan.name)}${tagLine(tags)}</th>`;
    const rates = prices ? this._prices(plan, locale) : "";
    const columns = parts.length + 3 + (prices ? 1 : 0);
    if (unpriced(plan)) {
      const why = plan.no_price ? this._labels.plans_no_price : this._labels.plans_incomplete;
      return `<tbody data-plan="${plan.id}"><tr>${name}${rates}
        <td class="incomplete rule" colspan="${columns - 1 - (prices ? 1 : 0)}">${why}</td></tr></tbody>`;
    }
    const figures = parts
      .map((part, index) => this._part(plan, part, locale, this._partClasses(part, index)))
      .join("");
    const difference = current && plan !== current ? this._difference(plan, current, locale) : "<td></td>";
    const notes = [this._exportNotes(plan, locale), this._marketNotes(plan, locale)]
      .join("")
      .trim();
    return `<tbody data-plan="${plan.id}">
      <tr>${name}${rates}${figures}${this._total(plan, locale)}${difference}</tr>
      ${notes ? `<tr class="note"><td colspan="${columns}">${notes}</td></tr>` : ""}
    </tbody>`;
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
    return `<td class="total rule" data-figure="total:${plan.id}">${formatMoney(
      plan.total,
      locale,
    )}</td>`;
  }

  _part(plan, { key, figure = key }, locale, classes = "") {
    return `<td${classAttribute(classes)} data-figure="${key}:${plan.id}">${formatMoney(
      plan[figure],
      locale,
    )}</td>`;
  }

  /** How much less or more than the household's own plan, as a saving is toned. */
  _difference(plan, current, locale) {
    const saving = current.total - plan.total;
    const tone = savingTone(saving, locale);
    const amount = formatMoney(Math.abs(saving), locale);
    let wording = this._labels.plans_same_short;
    if (tone === "gain") wording = fill(this._labels.plans_less_short, { amount });
    if (tone === "loss") wording = fill(this._labels.plans_more_short, { amount });
    const classes = tone ? `difference ${tone}` : "difference";
    return `<td class="${classes}" data-figure="difference:${plan.id}">${wording}</td>`;
  }
}

const hint = (note) => `<div class="hint">${note}</div>`;

/** A cell's class attribute, or nothing for a cell with no class. */
const classAttribute = (classes) => (classes ? ` class="${classes}"` : "");

/** A plan's badges on a line of their own under its name, where it has any. */
const tagLine = (tags) => (tags ? `<span class="tags">${tags}</span>` : "");

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
