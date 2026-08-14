/**
 * Every tracked device for the picked period, ordered by what it cost —
 * the "which device costs most" answer, finally sortable (HEA-50).
 *
 * The table itself lives in `HeaTableCard`; this file is the columns. Nothing
 * here names a device: the rows are whatever the HEA-55 sensor publishes, so a
 * device added to the integration appears without a dashboard edit.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import {
  formatEnergy,
  formatMoney,
  formatMoneyRange,
  formatRate,
  rateUnit,
} from "./hea-format.js";
import { HeaTableCard, sortSchemaFor } from "./hea-table-card.js";

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
 * What the figure beside it could honestly have been (ADR-0016).
 *
 * A counter reporting every 30–90 minutes used that energy somewhere inside the
 * span, and nothing in the data says where — so a device's cost is knowable only
 * to a range. Shown in money: the percentage form explodes on a device that cost
 * under a cent, which is most of them on any given day.
 */
const RANGE = {
  fields: ["costFloor", "costCeiling"],
  derive: ({ costFloor, costCeiling }) => [costFloor, costCeiling],
  label: "Range",
  format: formatMoneyRange,
};

const COLUMNS = [
  { field: "name", label: "Device" },
  { field: "energyUsed", label: "Energy", format: formatEnergy },
  { field: "actualCost", label: "Actual Cost", format: formatMoney },
  RANGE,
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

/** What the range means, wherever one is shown. */
const RANGE_NOTE =
  "Range: the widest these readings allow, not a typical error.";

const SORTS = {
  actual_cost: { field: "actualCost", label: "Actual cost" },
  cost_at_grid_price: { field: "costAtGridPrice", label: "Cost at grid price" },
  cost_savings: { field: "costSavings", label: "Saved" },
  energy_used: { field: "energyUsed", label: "Energy used" },
};

class HeaDevicesCard extends HeaTableCard {
  static defaultTitle = "Cost by device";
  static columns = COLUMNS;
  static sorts = SORTS;
  static defaultSort = "actual_cost";
  static cardStyle = `${HeaTableCard.cardStyle}
    .disclosure {
      margin-top: 12px;
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * The Range column only where every row can fill it.
   *
   * Per-device ranges are opt-in (ADR-0016), and a device the recorder holds no
   * bound for cannot be given one. A column of dashes would read as a fault; a
   * partly-filled one would invite comparing a bounded device with an unbounded
   * one, which is exactly the misranking the ADR rejects.
   */
  _columns() {
    return this._hasEveryBound() ? COLUMNS : COLUMNS.filter((c) => c !== RANGE);
  }

  _hasEveryBound() {
    const rows = this._result?.devices ?? [];
    return (
      rows.length > 0 &&
      rows.every((row) => RANGE.fields.every((f) => Number.isFinite(row[f])))
    );
  }

  /**
   * What the household's figures could honestly have been.
   *
   * Shown whichever way the table went. With the column, the totals row already
   * carries the same range and this is the sentence that says what it means;
   * without it, this is the whole disclosure — the whole-home range is published
   * even when the per-device ones are not, so a household is never told nothing.
   */
  _body(locale) {
    return `${super._body(locale)}${this._disclosure(locale)}`;
  }

  _disclosure(locale) {
    if (this._hasEveryBound()) {
      return `<div class="disclosure">${RANGE_NOTE}</div>`;
    }
    const band = this._result?.wholeHome;
    if (!band) return "";
    const range = formatMoneyRange([band.costFloor, band.costCeiling], locale);
    return `<div class="disclosure">
      These figures could honestly sit anywhere in ${range}. ${RANGE_NOTE}
    </div>`;
  }
}

/**
 * The shared fields plus the ordering — built from the same table the card
 * validates against, so the editor cannot produce a config the card rejects.
 */
class HeaDevicesCardEditor extends HeaCardEditor {
  _extraSchema() {
    return sortSchemaFor(SORTS);
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
