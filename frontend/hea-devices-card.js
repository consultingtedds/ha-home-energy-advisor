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
import { formatEnergy, formatMoney, formatRate, rateUnit } from "./hea-format.js";
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

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
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
