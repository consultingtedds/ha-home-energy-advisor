/**
 * Every tracked device for the picked period, ordered by what it cost —
 * the "which device costs most" answer, finally sortable (HEA-50).
 *
 * The lifecycle lives in `HeaCard`; this file is the table. Nothing here names
 * a device: the rows are whatever the HEA-55 sensor publishes, so a device
 * added to the integration appears without a dashboard edit.
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import {
  escapeText,
  formatEnergy,
  formatMoney,
  formatRate,
  rateUnit,
} from "./hea-format.js";

export const TAG = "hea-devices-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * What a kWh cost, for one row or for the whole table.
 *
 * Undefined rather than zero when there is no energy: no price can be derived
 * from nothing, and "free" is a different claim from "we cannot say".
 */
const effectiveRate = ({ actualCost, energyUsed }) =>
  energyUsed > 0 ? actualCost / energyUsed : undefined;

/**
 * The columns. A column either reads a `field` — which the totals row sums —
 * or derives its value, which the totals row derives again from the summed
 * fields. A rate is a ratio, and ratios do not add up.
 */
const COLUMNS = [
  { field: "name", label: "Device" },
  { field: "energyUsed", label: "Energy", format: formatEnergy },
  { field: "actualCost", label: "Actual Cost", format: formatMoney },
  { field: "costAtGridPrice", label: "At Grid Price", format: formatMoney },
  { field: "costSavings", label: "Saved", format: formatMoney },
  {
    derive: effectiveRate,
    // The only column whose unit varies with the household's currency, so its
    // label is built at render time rather than fixed here.
    label: (locale) => ({ text: "Rate", unit: rateUnit(locale) }),
    format: formatRate,
  },
];

/** What `sort_by` may name, in the sensor's own vocabulary, and how it reads. */
const SORTS = {
  actual_cost: { field: "actualCost", label: "Actual cost" },
  cost_at_grid_price: { field: "costAtGridPrice", label: "Cost at grid price" },
  cost_savings: { field: "costSavings", label: "Saved" },
  energy_used: { field: "energyUsed", label: "Energy used" },
};

const DEFAULT_SORT = "actual_cost";

class HeaDevicesCard extends HeaCard {
  static defaultTitle = "Cost by device";

  static cardStyle = `
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

  setConfig(config) {
    if (config.sort_by !== undefined && !(config.sort_by in SORTS)) {
      throw new Error(`\`sort_by\` must be one of: ${Object.keys(SORTS).join(", ")}`);
    }
    super.setConfig(config);
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** A table of n devices is nothing like the height of a one-device one. */
  getCardSize() {
    return 3 + Math.ceil((this._result?.devices.length ?? 3) / 2);
  }

  _body(locale) {
    const devices = this._ranked();
    return `
      <div class="scroll">
        <table>
          <thead><tr>${COLUMNS.map((column) => this._heading(column, locale)).join("")}</tr></thead>
          <tbody>${devices.map((device) => this._row(device, locale)).join("")}</tbody>
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

  /** Dearest first, and by name where two devices cost the same. */
  _ranked() {
    const { field } = SORTS[this._config?.sort_by ?? DEFAULT_SORT];
    return [...(this._result?.devices ?? [])].sort(
      (left, right) =>
        right[field] - left[field] || left.name.localeCompare(right.name),
    );
  }

  _row(device, locale) {
    return `<tr>${COLUMNS.map((column) => this._cell(column, device, locale)).join("")}</tr>`;
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
    const cells = COLUMNS.map(({ field, derive, format }) => {
      if (!format) return `<th scope="row">Total</th>`;
      // Derived from the summed fields, never from the rows' own derived
      // values: the table's rate is what the period cost per kWh overall.
      const value = derive ? derive(totals) : totals[field];
      return `<td>${format(value, locale)}</td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }

  /**
   * The total of the rows on screen, not of the house.
   *
   * With no filter these are the same thing — the allocations sum to the real
   * cost (ADR-0002) — but a filtered card must add up to what it is showing.
   */
  _sumOfShown() {
    return (this._result?.devices ?? []).reduce(
      (totals, device) => {
        for (const { field, derive, format } of COLUMNS) {
          if (format && !derive) totals[field] += device[field];
        }
        return totals;
      },
      { energyUsed: 0, actualCost: 0, costAtGridPrice: 0, costSavings: 0 },
    );
  }
}

/**
 * The shared fields plus the ordering — built from the same table the card
 * validates against, so the editor cannot produce a config the card rejects.
 */
class HeaDevicesCardEditor extends HeaCardEditor {
  _extraSchema() {
    return [
      {
        name: "sort_by",
        selector: {
          select: {
            mode: "dropdown",
            options: Object.entries(SORTS).map(([value, { label }]) => ({
              value,
              label,
            })),
          },
        },
      },
    ];
  }
}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaDevicesCardEditor);
  registerCard(TAG, HeaDevicesCard, {
    name: "Home Energy Advisor: Devices",
    description:
      "Every tracked device over the selected period, ordered by what it cost.",
  });
};

register();
