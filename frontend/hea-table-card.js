/**
 * A table of devices, one row each, ranked - the shape more than one HEA card
 * turns out to want (HEA-50).
 *
 * Subclasses supply `columns` and `sorts` and nothing else: the rendering, the
 * ordering, the totals row and the sort validation live here. Extracted when a
 * second table card arrived, rather than copied - two near-identical tables is
 * the kind of duplication that goes on to drift.
 *
 * A column either names a `field`, which the totals row sums, or `derive`s its
 * value, which the totals row derives again from the summed fields. A rate is a
 * ratio, and ratios do not add up. A derived column may name the `fields` it is
 * built from, so the totals row can sum those and derive from the sums - a cost
 * range is two numbers that each add up, presented as one cell.
 *
 * Where every row carries an earlier self, those same fields are summed again
 * into a `before` sub-total, so a column comparing two periods totals like any
 * other instead of reporting a dash under a column of real figures.
 *
 * A column's `label` may be a function of the locale, returning `{text, unit}`,
 * for the one case where the unit depends on the household's currency.
 *
 * `columns` is static, but `_columns()` is what renders, so a card can drop a
 * column the period's data cannot support rather than fill it with dashes.
 */

import { HeaCard } from "./hea-card-base.js";
import { CONCEPT_STYLE, swatch } from "./hea-concepts.js";
import { changeTone, escapeText, savingTone } from "./hea-format.js";

export const TABLE_STYLE = `${CONCEPT_STYLE}
  /*
   * A table too wide for the card scrolls sideways - and said so nowhere, which
   * on a phone means the Saved and Rate columns simply do not exist as far as
   * the reader is concerned (HEA-103).
   *
   * Shadows at the edges, drawn only while there is something past them: the
   * two local-attachment gradients are painted in the content's own
   * coordinates and so slide away as it scrolls, uncovering the fixed shadows
   * beneath. Reaching the end hides that end's shadow, and a table that fits
   * shows neither - which is why this is CSS rather than a cue we would have
   * to remember to turn off.
   */
  .scroll {
    overflow-x: auto;
    background:
      linear-gradient(to right, var(--card-background-color, #fff), transparent) 0 0 / 32px 100% no-repeat local,
      linear-gradient(to left, var(--card-background-color, #fff), transparent) 100% 0 / 32px 100% no-repeat local,
      radial-gradient(farthest-side at 0 50%, rgba(0, 0, 0, 0.18), transparent) 0 0 / 12px 100% no-repeat scroll,
      radial-gradient(farthest-side at 100% 50%, rgba(0, 0, 0, 0.18), transparent) 100% 0 / 12px 100% no-repeat scroll;
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
  th, td { padding: 6px 8px; text-align: right; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; white-space: normal; }
  /*
   * A device name gets its own line on a phone. Wrapping it saves width the
   * table does not need - it already scrolls sideways - and spends height it
   * has none of: "Untracked Energy Devices" broke over three lines, making
   * every row 74px and the table 1461px on a 412px screen (HEA-103).
   */
  @media (max-width: 767px) {
    th:first-child, td:first-child { white-space: nowrap; }
  }
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

/**
 * A cell's tone class, from either of the two things that carry one.
 *
 * They are different claims and both belong. An *absolute* Saved below zero is
 * a battery-arbitrage loss and must never read as a gain (HEA-39). A *change*
 * column carries a verdict on a direction instead, and which direction is good
 * depends on the concept it derives from - so a column declares that concept
 * in `tone` rather than the table guessing from a field it does not have
 * (HEA-99).
 */
const classFor = (field, tone, value) => {
  const verdict = field === "costSavings" ? savingTone(value) : changeTone(tone, value);
  return verdict ? ` class="${verdict}"` : "";
};

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

  /** The columns to render now - every one, unless a card says otherwise. */
  _columns() {
    return this.constructor.columns;
  }

  _body(locale) {
    const columns = this._columns();
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
   * `text-transform: uppercase` would render c/kWh as C/KWH - which is not
   * merely shouty, it is the wrong symbol.
   *
   * A column naming a cost concept carries that concept's mark, so Paid means
   * blue here and on the chart above it rather than in one place only
   * (HEA-104). The vocabulary decides which columns those are, from the label
   * they already wear - Device, Energy and the rate get nothing, and a table
   * added later is marked without having to know this happens.
   */
  _heading({ label }, locale) {
    const labels = this._labels;
    // A plain label is a key into the household's own vocabulary (ADR-0018);
    // only the rate column, whose unit follows the currency, builds its own.
    if (typeof label !== "function") {
      return `<th>${swatch(label)}${labels[label]}</th>`;
    }
    const { text, unit } = label(locale, labels);
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
    return `<tr>${this._columns()
      .map((column) => this._cell(column, device, locale))
      .join("")}</tr>`;
  }

  _cell({ field, derive, format, tone }, device, locale) {
    // A device name is the household's own text, so it is escaped rather than
    // trusted; the figures are Intl output and carry no markup.
    if (!format) return `<th scope="row">${escapeText(device[field])}</th>`;
    const value = derive ? derive(device) : device[field];
    return `<td${classFor(field, tone, value)}>${format(value, locale)}</td>`;
  }

  _total(locale) {
    const totals = this._sumOfShown();
    const cells = this._columns()
      .map(({ field, derive, format, tone }) => {
        if (!format) return `<th scope="row">${this._labels.total}</th>`;
        // Derived from the summed fields, never from the rows' own derived
        // values: a table's rate is what the period came to overall.
        const value = derive ? derive(totals) : totals[field];
        // Through the same verdict as every row above it. Rendered plain, the
        // total was the one uncoloured figure in a coloured column (HEA-99).
        return `<td${classFor(field, tone, value)}>${format(value, locale)}</td>`;
      })
      .join("");
    return `<tr>${cells}</tr>`;
  }

  /**
   * The total of the rows on screen, not of the house.
   *
   * With no filter these are the same thing - the allocations sum to the real
   * cost (ADR-0002) - but a filtered card must add up to what it is showing.
   */
  _sumOfShown() {
    // A Set because two columns may want the same field - a change column and
    // the column it is a change in - and a field summed twice is doubled.
    const summed = [
      ...new Set(
        this._columns().flatMap(({ field, fields, derive, format }) => {
          if (!format) return [];
          // A derived column sums the fields it names, if it names any;
          // otherwise it is a ratio and is derived again from the sums.
          if (derive) return fields ?? [];
          return field ? [field] : [];
        }),
      ),
    ];
    const rows = this._result?.devices ?? [];
    const sum = (of) =>
      rows.reduce(
        (totals, device) => {
          for (const field of summed) totals[field] += of(device)[field];
          return totals;
        },
        Object.fromEntries(summed.map((field) => [field, 0])),
      );

    const totals = sum((device) => device);
    // The earlier period's sub-total, on the same fields, so a change column
    // derives its total from sums the way the rate column does - the table used
    // to leave it blank because nothing here could reach a nested field.
    //
    // Only when every row has an earlier self. Summing just the rows that do
    // would leave a Total that disagrees with the column above it, and a change
    // that does not reconcile is worse than no change at all (HEA-99).
    if (rows.length > 0 && rows.every((row) => row.before)) {
      totals.before = sum((device) => device.before);
    }
    return totals;
  }
}

/** The ordering dropdown, built from the same table the card validates against. */
export const sortSchemaFor = (sorts, labels) => [
  {
    name: "sort_by",
    selector: {
      select: {
        mode: "dropdown",
        options: Object.entries(sorts).map(([value, { label }]) => ({
          value,
          label: labels[label],
        })),
      },
    },
  },
];
