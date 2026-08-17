/**
 * Every tracked device for the picked period, ordered by what it cost -
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
import { fill, labelsFor } from "./hea-labels.js";
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
 * A counter reporting every 30-90 minutes used that energy somewhere inside the
 * span, and nothing in the data says where - so a device's cost is knowable only
 * to a range. Shown in money: the percentage form explodes on a device that cost
 * under a cent, which is most of them on any given day.
 */
const RANGE = {
  fields: ["costFloor", "costCeiling"],
  derive: ({ costFloor, costCeiling }) => [costFloor, costCeiling],
  // Named for the figure it brackets. The bounds cover Actual Cost and nothing
  // else, so a column headed "Range" between Paid and Would have paid could
  // honestly be read as either, or as the saving (HEA-88).
  label: "range_column",
  format: formatMoneyRange,
};

const COLUMNS = [
  { field: "name", label: "device" },
  { field: "energyUsed", label: "energy", format: formatEnergy },
  { field: "actualCost", label: "paid", format: formatMoney },
  RANGE,
  { field: "costAtGridPrice", label: "would_have_paid", format: formatMoney },
  { field: "costSavings", label: "saved", format: formatMoney },
  {
    derive: effectiveRate,
    // The only column whose unit varies with the household's currency, so its
    // label is built at render time rather than fixed here.
    label: (locale, labels) => ({ text: labels.rate, unit: rateUnit(locale) }),
    format: formatRate,
  },
];

const SORTS = {
  actual_cost: { field: "actualCost", label: "paid" },
  cost_at_grid_price: { field: "costAtGridPrice", label: "would_have_paid" },
  cost_savings: { field: "costSavings", label: "saved" },
  energy_used: { field: "energyUsed", label: "energy_used" },
};

class HeaDevicesCard extends HeaTableCard {
  static titleKey = "title_devices";
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
   * without it, this is the whole disclosure - the whole-home range is published
   * even when the per-device ones are not, so a household is never told nothing.
   */
  _body(locale) {
    return `${super._body(locale)}${this._disclosure(locale)}`;
  }

  _disclosure(locale) {
    const labels = this._labels;
    if (this._hasEveryBound()) {
      return `<div class="disclosure">${labels.range_note}</div>`;
    }
    const band = this._result?.wholeHome;
    if (!band) return "";
    const range = formatMoneyRange([band.costFloor, band.costCeiling], locale);
    // Names what it qualifies. "These figures" sat under three of them and left
    // the reader to work out which one had a range (HEA-88).
    return `<div class="disclosure">
      ${fill(labels.range_whole_home, { range })}
    </div>`;
  }
}

/**
 * The shared fields plus the ordering - built from the same table the card
 * validates against, so the editor cannot produce a config the card rejects.
 */
class HeaDevicesCardEditor extends HeaCardEditor {
  _extraSchema() {
    return sortSchemaFor(SORTS, labelsFor(this._hass));
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
