/**
 * A table of devices, one row each, ranked — the shape more than one HEA card
 * turns out to want (HEA-50).
 *
 * Subclasses supply `columns` and `sorts` and nothing else: the rendering, the
 * ordering, the totals row and the sort validation live here. Extracted when a
 * second table card arrived, rather than copied — two near-identical tables is
 * the kind of duplication that goes on to drift.
 *
 * A column either names a `field`, which the totals row sums, or `derive`s its
 * value, which the totals row derives again from the summed fields. A rate is a
 * ratio, and ratios do not add up.
 *
 * A column's `label` may be a function of the locale, returning `{text, unit}`,
 * for the one case where the unit depends on the household's currency.
 */

import { HeaCard } from "./hea-card-base.js";
import { escapeText } from "./hea-format.js";

export const TABLE_STYLE = `
  .scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
  th, td { padding: 6px 8px; text-align: right; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; white-space: normal; }
  thead th {
    color: var(--secondary-text-color);
    font-weight: 400;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }
  thead .unit { text-transform: none; letter-spacing: 0; }
  tbody td { border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  tbody tr:last-child td { border-bottom: none; }
  tfoot th, tfoot td {
    font-weight: 500;
    border-top: 2px solid var(--divider-color, #e0e0e0);
  }
`;

export class HeaTableCard extends HeaCard {
  /** @type {Array<object>} set by the subclass. */
  static columns = [];
  /** @type {object} what `sort_by` may name, in the sensor's own vocabulary. */
  static sorts = {};
  static defaultSort = "";

  static cardStyle = TABLE_STYLE;

  setConfig(config) {
    const { sorts } = this.constructor;
    if (config.sort_by !== undefined && !(config.sort_by in sorts)) {
      throw new Error(
        `\`sort_by\` must be one of: ${Object.keys(sorts).join(", ")}`,
      );
    }
    super.setConfig(config);
  }

  /** A table of n devices is nothing like the height of a one-device one. */
  getCardSize() {
    return 3 + Math.ceil((this._result?.devices.length ?? 3) / 2);
  }

  _body(locale) {
    const { columns } = this.constructor;
    return `
      <div class="scroll">
        <table>
          <thead><tr>${columns
            .map((column) => this._heading(column, locale))
            .join("")}</tr></thead>
          <tbody>${this._ranked()
            .map((device) => this._row(device, locale))
            .join("")}</tbody>
          <tfoot>${this._total(locale)}</tfoot>
        </table>
      </div>`;
  }

  /**
   * A column heading, with its unit kept out of the row's uppercasing.
   *
   * `text-transform: uppercase` would render c/kWh as C/KWH — which is not
   * merely shouty, it is the wrong symbol.
   */
  _heading({ label }, locale) {
    if (typeof label !== "function") return `<th>${label}</th>`;
    const { text, unit } = label(locale);
    return `<th>${text} <span class="unit">${escapeText(unit)}</span></th>`;
  }

  /** Largest first, and by name where two devices tie. */
  _ranked() {
    const { sorts, defaultSort } = this.constructor;
    const { field } = sorts[this._config?.sort_by ?? defaultSort];
    return [...(this._result?.devices ?? [])].sort(
      (left, right) =>
        right[field] - left[field] || left.name.localeCompare(right.name),
    );
  }

  _row(device, locale) {
    return `<tr>${this.constructor.columns
      .map((column) => this._cell(column, device, locale))
      .join("")}</tr>`;
  }

  _cell({ field, derive, format }, device, locale) {
    // A device name is the household's own text, so it is escaped rather than
    // trusted; the figures are Intl output and carry no markup.
    if (!format) return `<th scope="row">${escapeText(device[field])}</th>`;
    const value = derive ? derive(device) : device[field];
    const loss = field === "costSavings" && value < 0 ? ` class="loss"` : "";
    return `<td${loss}>${format(value, locale)}</td>`;
  }

  _total(locale) {
    const totals = this._sumOfShown();
    const cells = this.constructor.columns
      .map(({ field, derive, format }) => {
        if (!format) return `<th scope="row">Total</th>`;
        // Derived from the summed fields, never from the rows' own derived
        // values: a table's rate is what the period came to overall.
        const value = derive ? derive(totals) : totals[field];
        return `<td>${format(value, locale)}</td>`;
      })
      .join("");
    return `<tr>${cells}</tr>`;
  }

  /**
   * The total of the rows on screen, not of the house.
   *
   * With no filter these are the same thing — the allocations sum to the real
   * cost (ADR-0002) — but a filtered card must add up to what it is showing.
   */
  _sumOfShown() {
    const summed = this.constructor.columns.filter(
      ({ field, derive, format }) => format && !derive && field,
    );
    return (this._result?.devices ?? []).reduce(
      (totals, device) => {
        for (const { field } of summed) totals[field] += device[field];
        return totals;
      },
      Object.fromEntries(summed.map(({ field }) => [field, 0])),
    );
  }
}

/** The ordering dropdown, built from the same table the card validates against. */
export const sortSchemaFor = (sorts) => [
  {
    name: "sort_by",
    selector: {
      select: {
        mode: "dropdown",
        options: Object.entries(sorts).map(([value, { label }]) => ({
          value,
          label,
        })),
      },
    },
  },
];
