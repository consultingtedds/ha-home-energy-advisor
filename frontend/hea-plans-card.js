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
import { drawsOnDark } from "./hea-colour.js";
import {
  formatClockTime,
  formatDate,
  formatDateTime,
  formatEnergy,
  formatMoney,
  formatRate,
  rateUnit,
  savingTone,
} from "./hea-format.js";
import { fill, loadLabels } from "./hea-labels.js";
import { TABLE_STYLE } from "./hea-table-card.js";
import { verdictColour } from "./hea-verdict-scale.js";

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

/** A plan priced from a market price entity, which says how finely it was priced. */
const followsTheMarket = (plan) =>
  Boolean(plan.rates?.import_market || plan.rates?.export_market);

/** What a stretch left out had no data for, when it was not a price entity. */
const GRID_METERS = "grid";

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
    /* Heads in the main text colour and a heavier weight, so the table's shape
       reads at a glance (HEA-296). */
    .plans thead th {
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      font-weight: 500;
    }
    .plans thead tr.groups th { border-bottom: none; text-align: center; }
    /* One heading over two rows, so both halves sit where its figures do. */
    .plans thead tr.groups th.without, .plans thead th.without { text-align: right; }
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
    /* Each badge in a colour of its own, so a plan's standing stands out:
       the theme's own colours, so a dark theme reads too (HEA-296). */
    .tag.current {
      background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent);
      color: var(--primary-color, #03a9f4);
    }
    .tag.cheapest {
      background: color-mix(in srgb, var(--success-color, #4caf50) 18%, transparent);
      color: var(--success-color, #4caf50);
    }
    td.total { font-weight: 500; }
    .saves { font-size: 0.85em; }
    .saves:not(.gain):not(.loss) { color: var(--secondary-text-color); }
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
    /* A plan's row opens its bill (HEA-300): the whole row takes the pointer,
       and its name is the button a keyboard reaches. */
    tr.figures { cursor: pointer; }
    button.open {
      all: unset;
      cursor: pointer;
      font: inherit;
      color: inherit;
    }
    button.open:focus-visible {
      outline: 2px solid var(--primary-color, #03a9f4);
      outline-offset: 2px;
    }
    button.open::before {
      content: "▸";
      display: inline-block;
      width: 1em;
      color: var(--secondary-text-color);
    }
    button.open[aria-expanded="true"]::before { content: "▾"; }
    /* Context, not money: in the secondary colour unless its verdict colours
       it, never in the red or green of the figure above it. */
    .average { font-size: 0.85em; color: var(--secondary-text-color); }
    /* Allowed to wrap under the import cost, so the column stays as wide as
       its figure rather than its note. */
    td > div > .average { display: inline-block; white-space: normal; max-width: 7em; }
    tr.bill-row > td {
      padding: 0 12px 12px 14px;
      text-align: left;
      white-space: normal;
    }
    .plans .bill {
      width: auto;
      border: none;
      margin-top: var(--hea-space-xs);
      font-size: 0.9em;
    }
    .plans .bill th, .plans .bill td {
      padding: 2px 10px;
      text-align: right;
      white-space: nowrap;
      border: none;
    }
    .plans .bill th { text-align: left; font-weight: normal; }
    .plans .bill thead th {
      background: none;
      color: var(--secondary-text-color);
      font-weight: 400;
      font-size: 0.8em;
    }
    .plans .bill tr.subtotal > *, .plans .bill tr.total > * {
      font-weight: 500;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    /* On a phone the bill fits the three columns the table keeps, rather than
       widening the table past the screen: tighter, and an average may wrap. */
    @media (max-width: 767px) {
      tr.bill-row > td { padding: 0 4px 8px; }
      .plans .bill { font-size: 0.8em; }
      .plans .bill th, .plans .bill td { padding: 2px 5px; }
      .plans .bill .average { white-space: normal; }
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
      priced.some((plan) => plan.breakdown) ? this._labels.plans_open : "",
      wide ? "" : this._labels.plans_breakdown_hidden,
      priced.some(followsTheMarket) ? this._resolution(locale) : "",
    ].filter(Boolean);
    // Only for a house with an installation, which is the only kind the
    // comparison gives the figure for (HEA-293).
    const without = wide && plans.some((plan) => "without_installation" in plan);
    const layout = { current, cheapest, parts, prices: wide, without };
    return `
      ${this._flows(locale)}
      ${this._leftOut(locale)}
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
  _head({ parts, prices, without }) {
    const leading = [this._labels.plans_plan, ...(prices ? [this._labels.plans_prices] : [])];
    const cell = (label, classes = "") => `<th${classAttribute(classes)}>${label}</th>`;
    const trailing = [
      cell(this._labels.plans_total, "rule"),
      ...(without ? [cell(this._labels.plans_without, "rule without")] : []),
      cell(this._labels.plans_vs_current),
    ];
    const columns = [
      cell(this._labels.plans_plan),
      ...(prices ? [cell(this._labels.plans_prices, "prices")] : []),
      ...parts.map((part, index) =>
        cell(this._labels[part.label], this._partClasses(part, index)),
      ),
      ...trailing,
    ].join("");
    if (!parts.length) return `<tr>${columns}</tr>`;
    const groups = GROUPS.map((group) => {
      const span = parts.filter((part) => part.group === group.key).length;
      const classes = group.key === "earn" ? "rule earn" : "rule";
      return `<th class="${classes}" colspan="${span}">${this._labels[group.label]}</th>`;
    }).join("");
    // The installation's column is headed over both rows, as the groups are:
    // "Buying everything" above "from the grid" (HEA-300).
    const after = without
      ? `<th class="rule"></th><th class="rule without">${this._labels.plans_without_group}</th><th></th>`
      : `<th colspan="${trailing.length}" class="rule"></th>`;
    return `<tr class="groups"><th colspan="${leading.length}"></th>${groups}${after}</tr>
      <tr>${columns}</tr>`;
  }

  /**
   * What the plan would have cost buying everything from the grid, and what the
   * installation saved on it beneath: the figure a household weighs its panels
   * and battery by, on every plan (HEA-293). A cost, so signed as one; the
   * saving beneath in its own favour's colour (HEA-296).
   */
  _without(plan, locale) {
    if (!("without_installation" in plan)) return `<td class="rule"></td>`;
    const cost = signed(-plan.without_installation, locale);
    const saved = plan.without_installation - plan.total;
    const amount = formatMoney(Math.abs(saved), locale);
    const tone = savingTone(saved, locale);
    const wording =
      tone === "loss"
        ? fill(this._labels.plans_costs_more, { amount })
        : fill(this._labels.plans_saves, { amount });
    const saves = ["saves", tone].filter(Boolean).join(" ");
    const classes = ["rule", cost.tone].filter(Boolean).join(" ");
    return `<td class="${classes}" data-figure="without:${plan.id}">${cost.text}<div class="${saves}">${wording}</div></td>`;
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
   * kWh are the household's and only the prices are the plan's (HEA-280). Only
   * the hours compared are counted, so with any left out it says so, and the kWh
   * read against the costs beneath them (HEA-299).
   */
  _flows(locale) {
    if (!this._compared.hours) return "";
    const wording = this._compared.left_out?.length
      ? this._labels.plans_flows_compared
      : this._labels.plans_flows;
    return `<div class="flows">${fill(wording, {
      imported: formatEnergy(this._compared.imported_kwh, locale),
      exported: formatEnergy(this._compared.exported_kwh, locale),
    })}</div>`;
  }

  /**
   * What every plan left out, said once above the table: the stretches with no
   * data, each under what had none - the grid meters, or a price sensor named,
   * with where to look (HEA-299, ADR-0043). Every plan is compared over the same
   * hours, so a year that became a month can be traced to the sensor that made
   * it so. Nothing where the meters recorded nothing at all: a note says that.
   */
  _leftOut(locale) {
    const stretches = this._compared.left_out ?? [];
    if (!stretches.length || !this._compared.hours) return "";
    const bySource = new Map();
    for (const stretch of stretches) {
      const from = new Date(stretch.from);
      const to = new Date(stretch.to);
      // A stretch inside one day names that day once: "3 Jun 2026, 14:00 to 20:00".
      const sameDay = formatDate(from, locale) === formatDate(to, locale);
      const when = fill(this._labels.plans_stretch, {
        from: formatDateTime(from, locale),
        to: sameDay ? formatClockTime(to, locale) : formatDateTime(to, locale),
      });
      bySource.set(stretch.source, [...(bySource.get(stretch.source) ?? []), when]);
    }
    return [...bySource]
      .map(([source, whens]) => {
        const when = whens.join(", ");
        const wording =
          source === GRID_METERS
            ? fill(this._labels.plans_left_out_meters, { when })
            : fill(this._labels.plans_left_out_price, {
                when,
                sensor: this._sensor(source),
              });
        return `<div class="flows left-out" data-source="${escape(source)}">${wording}</div>`;
      })
      .join("");
  }

  /** A price sensor as the household finds it: its name, and its entity ID. */
  _sensor(entityId) {
    const name = this._hass?.states?.[entityId]?.attributes?.friendly_name;
    const id = escape(entityId);
    return name && name !== entityId ? `${escape(name)} (${id})` : id;
  }

  /**
   * One plan: a row of its figures, and any notes on it beneath, together in a
   * group of their own so a note is never read as the next plan's.
   */
  _plan(plan, { current, cheapest, parts, prices, without }, locale) {
    const opened = this._opened.has(plan.id);
    const name = this._name(plan, cheapest, opened);
    const rates = prices ? this._prices(plan, locale) : "";
    const leading = prices ? 2 : 1;
    const columns = leading + parts.length + 2 + (without ? 1 : 0);
    if (unpriced(plan)) {
      const why = plan.no_price
        ? fill(this._labels.plans_no_price, {
            sensors: (plan.no_price_entities ?? []).map((id) => this._sensor(id)).join(", "),
          })
        : this._labels.plans_incomplete;
      return `<tbody data-plan="${plan.id}"><tr>${name}${rates}
        <td class="incomplete rule" colspan="${columns - leading}">${why}</td></tr></tbody>`;
    }
    const figures = parts
      .map((part, index) => this._part(plan, part, locale, this._partClasses(part, index)))
      .join("");
    const difference = current && plan !== current ? this._difference(plan, current, locale) : "<td></td>";
    const notes = this._exportNotes(plan, locale).trim();
    const bill =
      opened && plan.breakdown
        ? `<tr class="bill-row"><td colspan="${columns}">${this._bill(plan, locale)}</td></tr>`
        : "";
    return `<tbody data-plan="${plan.id}">
      <tr class="figures">${name}${rates}${figures}${this._total(plan, locale)}${without ? this._without(plan, locale) : ""}${difference}</tr>
      ${notes ? `<tr class="note"><td colspan="${columns}">${notes}</td></tr>` : ""}
      ${bill}
    </tbody>`;
  }

  /**
   * A plan's name and its badges. A plan with a bill to open names itself on
   * the button that opens it, which says whether it is open (HEA-300).
   */
  _name(plan, cheapest, opened) {
    const tags = [
      plan.current ? ["current", this._labels.plans_your_plan] : undefined,
      plan === cheapest ? ["cheapest", this._labels.plans_cheapest] : undefined,
    ]
      .filter(Boolean)
      .map(([kind, label]) => `<span class="tag ${kind}">${label}</span>`)
      .join("");
    const title =
      plan.breakdown && !unpriced(plan)
        ? `<button class="open" type="button" aria-expanded="${opened}">${escape(plan.name)}</button>`
        : escape(plan.name);
    return `<th>${title}${tagLine(tags)}</th>`;
  }

  /** The plans whose bills are open, kept across a redraw or a new fetch. */
  get _opened() {
    this._openPlans ??= new Set();
    return this._openPlans;
  }

  /**
   * One listener for the whole card, on the shadow root that outlives every
   * redraw: a plan's row, or the button on its name, opens and closes its bill.
   */
  _afterRender() {
    if (this._listening) return;
    this._listening = true;
    this.shadowRoot.addEventListener("click", (event) => {
      const row = event.target.closest?.("tr.figures");
      const id = row?.closest("tbody[data-plan]")?.dataset.plan;
      if (!id) return;
      if (this._opened.has(id)) this._opened.delete(id);
      else this._opened.add(id);
      this._render();
    });
  }

  /**
   * A plan's total line by line, as a bill lists it (HEA-300): its daily
   * charges first, being charged by the day; then each price's kWh and what
   * they cost, and the import cost they add up to; then export, and what any
   * cap did not pay of it; then the total. Every amount signed as the table
   * signs it, so each line can be matched to a column above and to a bill.
   */
  _bill(plan, locale) {
    const { daily } = plan.breakdown;
    const days = new Intl.NumberFormat(locale.language, { maximumFractionDigits: 2 });
    const lines = [
      billRow(locale, {
        name: this._labels.plans_daily,
        rate: fill(this._labels.plans_per_day, { amount: formatMoney(daily.rate, locale) }),
        used: fill(daily.days === 1 ? this._labels.plans_day : this._labels.plans_days, {
          days: days.format(daily.days),
        }),
        favour: -daily.amount,
        key: "daily",
      }),
      ...this._importLines(plan, locale),
      ...this._exportLines(plan, locale),
      billRow(locale, {
        name: this._labels.plans_total,
        favour: -plan.total,
        key: "total",
        classes: "total",
      }),
    ];
    const head = ["", this._labels.plans_rate, this._labels.plans_used, this._labels.plans_amount]
      .map((label) => `<th>${label}</th>`)
      .join("");
    const note =
      plan.breakdown.average_import_rate === null ? "" : hint(this._labels.plans_average_note);
    return `<table class="bill"><thead><tr>${head}</tr></thead><tbody>${lines.join("")}</tbody></table>${note}`;
  }

  /** A rate per kWh as the card writes one, its unit beside it. */
  _rate(value, locale) {
    return `${formatRate(value, locale)} ${rateUnit(locale)}`;
  }

  /** What a market line averaged, since it has no one rate of its own. */
  _averageOf({ kwh, amount }, locale) {
    return kwh ? fill(this._labels.plans_average, { rate: this._rate(amount / kwh, locale) }) : "";
  }

  /**
   * Each import price's line, then the import cost they add up to: its kWh,
   * and the average rate they came to, carrying its verdict as a device's does
   * on the devices table - the figure coloured, and a band down its row.
   */
  _importLines(plan, locale) {
    const { imports } = plan.breakdown;
    const verdict = this._averageVerdict(plan, locale);
    const lines = imports.map((line, index) =>
      billRow(locale, {
        name:
          line.rate === null
            ? this._labels.plans_market_price
            : line.name || this._labels.plans_unnamed_price,
        rate: line.rate === null ? this._averageOf(line, locale) : this._rate(line.rate, locale),
        used: formatEnergy(line.kwh, locale),
        favour: -line.amount,
        key: "import-" + index,
      }),
    );
    const band = verdict?.colour ? "box-shadow: inset 4px 0 0 " + verdict.colour.edge : "";
    lines.push(
      billRow(locale, {
        name: this._labels.plans_energy,
        rate: this._average(plan, locale, "bill-average", verdict),
        used: formatEnergy(sum(imports, "kwh"), locale),
        favour: -plan.energy,
        key: "energy",
        classes: "subtotal",
        style: band,
      }),
    );
    return lines;
  }

  /**
   * Each export price's line, what they add up to where there is more than
   * one, and what any cap did not pay of them, so the bill still adds up to the
   * total (HEA-258).
   */
  _exportLines(plan, locale) {
    const { exports } = plan.breakdown;
    const lines = exports.map((line, index) =>
      billRow(locale, {
        name: this._exportName(line),
        rate: line.rate === null ? this._averageOf(line, locale) : this._rate(line.rate, locale),
        used: formatEnergy(line.kwh, locale),
        favour: line.amount,
        key: "export-" + index,
      }),
    );
    if (exports.length > 1) {
      lines.push(
        billRow(locale, {
          name: this._labels.plans_export,
          used: formatEnergy(sum(exports, "kwh"), locale),
          favour: sum(exports, "amount"),
          key: "export",
          classes: "subtotal",
        }),
      );
    }
    const capped = (plan.export_unpaid ?? 0) + (plan.export_carried ?? 0);
    if (capped > 0) {
      lines.push(
        billRow(locale, { name: this._labels.plans_capped, favour: -capped, key: "capped" }),
      );
    }
    return lines;
  }

  /** An export line's name: its price's, or the plan's own export price. */
  _exportName(line) {
    if (line.rate === null) return this._labels.plans_market_price;
    if (line.name) return line.name;
    return line.beyond_allowance
      ? this._labels.plans_export_beyond
      : this._labels.plans_export_rate;
  }

  /**
   * The plan's average import rate, coloured by where it falls between the
   * plan's dearest price and its cheapest, and said in words on its title.
   */
  _average(plan, locale, figure, verdict = this._averageVerdict(plan, locale)) {
    if (!verdict) return "";
    const style = verdict.colour ? ` style="color: ${verdict.colour.text}"` : "";
    return `<span class="average" data-figure="${figure}"${style} title="${escape(verdict.title)}">${verdict.text}</span>`;
  }

  /**
   * Where the average falls on the device table's verdict scale (HEA-106): red
   * at the plan's dearest import price, green at its cheapest. Full weight,
   * since every plan prices the same kWh. No colour where the plan has only one
   * price, which leaves nothing to compare.
   */
  _averageVerdict(plan, locale) {
    const breakdown = plan.breakdown;
    const average = breakdown?.average_import_rate;
    if (average === null || average === undefined) return undefined;
    const rate = (value) => this._rate(value, locale);
    const cheapest = breakdown.cheapest_import_rate;
    const dearest = breakdown.dearest_import_rate;
    const spread = dearest - cheapest;
    const colour =
      spread > 0
        ? verdictColour((dearest - average) / spread, { dark: drawsOnDark(this) })
        : undefined;
    const wording = plan.rates?.import_market
      ? this._labels.plans_average_title_market
      : this._labels.plans_average_title;
    return {
      colour,
      // The figure kept with its unit where the line wraps under the cost.
      text: fill(this._labels.plans_average, { rate: rate(average).replace(" ", " ") }),
      title: fill(wording, {
        average: rate(average),
        cheapest: rate(cheapest),
        dearest: rate(dearest),
      }),
    };
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

  /** What the plan costs, or what it leaves in the household's favour. */
  _total(plan, locale) {
    return moneyCell(`total:${plan.id}`, -plan.total, locale, "total rule");
  }

  /**
   * What is paid is against the household, what is earned in its favour. The
   * import cost carries the plan's average rate beneath it, coloured, with no
   * band down the row: a band would read as a verdict on the whole plan, and a
   * plan can be the cheapest while its import timing is poor (HEA-300).
   */
  _part(plan, { key, figure = key, group }, locale, classes = "") {
    const favour = group === "earn" ? plan[figure] : -plan[figure];
    if (key !== "energy" || !plan.breakdown) {
      return moneyCell(`${key}:${plan.id}`, favour, locale, classes);
    }
    const { text, tone } = signed(favour, locale);
    const all = [classes, tone].filter(Boolean).join(" ");
    const average = this._average(plan, locale, "average:" + plan.id);
    const beneath = average ? "<div>" + average + "</div>" : "";
    return `<td${classAttribute(all)} data-figure="${key}:${plan.id}">${text}${beneath}</td>`;
  }

  /**
   * By how much the plan is cheaper or dearer than the household's own, signed
   * the same way: cheaper is in its favour. The head says what it is against,
   * so no word beside it doubles the sign.
   */
  _difference(plan, current, locale) {
    const saving = current.total - plan.total;
    if (!savingTone(saving, locale)) {
      return `<td class="difference" data-figure="difference:${plan.id}">${this._labels.plans_same_short}</td>`;
    }
    return moneyCell(`difference:${plan.id}`, saving, locale, "difference");
  }
}

const hint = (note) => `<div class="hint">${note}</div>`;

/** The sum of one field over a bill's lines. */
const sum = (lines, field) => lines.reduce((total, line) => total + line[field], 0);

/** A cell's style attribute, or nothing for a cell with no style. */
const styleAttribute = (style) => (style ? ` style="${style}"` : "");

/**
 * One line of a plan's bill: what it is, its rate, what was used, and the
 * money signed as the table above signs it. `name` is escaped, since a price's
 * name is the household's own words; `rate` and `used` are the card's.
 */
const billRow = (locale, { name, rate = "", used = "", favour, key, classes = "", style = "" }) => {
  const money = moneyCell("bill-" + key, favour, locale);
  return `<tr${classAttribute(classes)}><th${styleAttribute(style)}>${escape(name)}</th><td>${rate}</td><td>${used}</td>${money}</tr>`;
};

/** A cell's class attribute, or nothing for a cell with no class. */
const classAttribute = (classes) => (classes ? ` class="${classes}"` : "");

/**
 * Money signed by whose favour it is in, the one rule the whole table follows
 * (HEA-296, discussion 58): what the household pays is -€ in red, what is in
 * its favour € in green, and nothing is plain. A total in credit read as a loss
 * when it carried a minus, and a saving written as a word read differently
 * from the total beside it.
 *
 * `favour` is the amount in the household's favour, below zero for a cost. Its
 * tone is judged as `savingTone` judges every saving, on the figure as shown,
 * so a fraction of a cent is never coloured.
 */
const signed = (favour, locale) => {
  const tone = savingTone(favour, locale);
  const shown = tone === "loss" ? -Math.abs(favour) : Math.abs(favour);
  return { text: formatMoney(shown, locale), tone };
};

/** A table cell holding one signed figure, its tone among its classes. */
const moneyCell = (figure, favour, locale, classes = "") => {
  const { text, tone } = signed(favour, locale);
  const all = [classes, tone].filter(Boolean).join(" ");
  return `<td${classAttribute(all)} data-figure="${figure}">${text}</td>`;
};

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
