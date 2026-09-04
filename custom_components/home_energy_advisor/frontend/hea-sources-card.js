/**
 * Where each device's energy came from - grid, generation or battery (HEA-51).
 *
 * The table lives in `HeaTableCard`; this file is the columns. Every label
 * shares its bucket's source mix, so a device that ran while the sun was out
 * shows generation whether or not that particular appliance was "on solar" -
 * the house is served by a blend, not by circuits (ADR-0002).
 *
 * The three sources are shown as recorded rather than normalised to a hundred
 * percent. Where they fail to sum to the device's energy that is worth seeing:
 * it means an interval had draw the house-level meters never accounted for, and
 * a contradiction between a device's split and its price is exactly how HEA-74
 * announced itself.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { formatEnergy, formatPercent } from "./hea-format.js";
import { labelsFor } from "./hea-labels.js";
import { HeaTableCard, sortSchemaFor } from "./hea-table-card.js";

export const TAG = "hea-sources-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * The share that came off the grid, for one row or for the whole table.
 *
 * A proportion of a whole, so the totals row derives it from the summed
 * columns; the mean of the rows' own shares would weight a device that used a
 * tenth of a kilowatt-hour the same as one that used twenty.
 *
 * Undefined rather than zero when there is no energy: no share can be derived
 * from nothing, and "none of it" is a different claim from "we cannot say".
 */
const gridShare = ({ energyFromGrid, energyUsed }) =>
  energyUsed > 0 ? energyFromGrid / energyUsed : undefined;

const COLUMNS = [
  { field: "name", label: "device" },
  { field: "energyUsed", label: "energy", format: formatEnergy },
  { field: "energyFromGrid", label: "grid", format: formatEnergy },
  { field: "energyFromGeneration", label: "generation", format: formatEnergy },
  { field: "energyFromBattery", label: "battery", format: formatEnergy },
  { derive: gridShare, label: "from_grid", format: formatPercent },
];

const SORTS = {
  energy_used: { field: "energyUsed", label: "energy_used" },
  energy_from_grid: { field: "energyFromGrid", label: "from_grid" },
  energy_from_generation: {
    field: "energyFromGeneration",
    label: "from_generation",
  },
  energy_from_battery: { field: "energyFromBattery", label: "from_battery" },
};

class HeaSourcesCard extends HeaTableCard {
  static titleKey = "title_sources";
  static columns = COLUMNS;
  static sorts = SORTS;
  static defaultSort = "energy_used";

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }
}

class HeaSourcesCardEditor extends HeaCardEditor {
  _extraSchema() {
    return sortSchemaFor(SORTS, labelsFor(this._hass));
  }
}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaSourcesCardEditor);
  registerCard(TAG, HeaSourcesCard, {
    name: "Home Energy Advisor: Energy sources",
    description:
      "Grid, generation and battery behind each device's energy over the period.",
  });
};

register();
