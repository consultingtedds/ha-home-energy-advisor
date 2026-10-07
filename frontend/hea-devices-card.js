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
  formatMoneyChange,
  formatMoneyRange,
  formatRate,
  rateUnit,
} from "./hea-format.js";
import { fill, labelsFor } from "./hea-labels.js";
import { BOUNDS } from "./hea-statistics.js";
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
 * Whether the integration publishes a range for this row at all.
 *
 * Read off `statistics`, which omits a concept whose entity does not exist - so
 * this asks what the integration created rather than what the recorder happens
 * to hold yet, and tells "this row never has a range" apart from "its range has
 * not arrived".
 */
const offersARange = (row) =>
  Object.values(BOUNDS).every((concept) => concept in (row.statistics ?? {}));

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
  /**
   * A row with no range of its own contributes its cost to the total's.
   *
   * The Untracked remainder and the battery carry no bounds, and that is not
   * missing data: both are derived per interval from meters that reported for
   * that interval, so there is no span to be uncertain about and - as `sensor.py`
   * puts it - *their bounds are their cost*. Left out of the sum, the household's
   * range would come to less than what they paid, and on a house where Untracked
   * is half the energy it would be wrong by half.
   *
   * Their own cell still shows a dash rather than a range of zero width, which
   * would read as a precision claim about a figure that simply has no span.
   */
  readField: (row, field) =>
    Number.isFinite(row[field]) ? row[field] : row.actualCost,
};

/**
 * How much more or less this device cost than over the comparison window.
 *
 * Present only when the household has turned comparison on in Home Assistant's
 * own picker, so the table is untouched for anyone who has not (HEA-96).
 *
 * A device with nothing in the earlier window compares against zero, so its
 * whole figure reads as an increase. That is deliberate rather than ideal:
 * statistics cannot tell "the device did not run" from "the device was not
 * tracked yet", and the first is far the commoner - a seasonal heater, an
 * aircon in a cool month - where the increase is exactly right. It overstates
 * only for a device genuinely added since, which the household knows about.
 *
 * The `undefined` guard below is for a row carrying no earlier self at all,
 * which the card path does not currently produce (both windows are fetched for
 * the same device list) but `withComparison` is written to allow.
 */
const CHANGE = {
  // Declared so the totals row sums it on both sides of the comparison, the way
  // the range column declares its two bounds. Paid already names it, but a
  // column that depends on a field says so rather than relying on a neighbour.
  fields: ["actualCost"],
  derive: ({ actualCost, before }) =>
    before && Number.isFinite(actualCost) && Number.isFinite(before.actualCost)
      ? actualCost - before.actualCost
      : undefined,
  label: "change",
  format: formatMoneyChange,
  // The concept this column is a change *in*, which is what says which
  // direction is good news. Spend falling is good; the same fall in Saved
  // would not be (HEA-99).
  tone: "actualCost",
};

/**
 * What was paid, with what it could honestly have been behind it.
 *
 * The range used to be a column of its own, and a column puts an uncertainty
 * band at the same weight as the figure it qualifies - which read as a second
 * headline rather than as a footnote about the first (HEA-198). It is a rollover
 * on Paid by default, which is where it was first asked for, and the column
 * remains available to anyone who wants to sort or scan by it.
 */
const PAID = {
  field: "actualCost",
  label: "paid",
  format: formatMoney,
  reveal: (row, locale) => {
    if (!offersARange(row) || !RANGE.fields.every((f) => Number.isFinite(row[f]))) {
      return null;
    }
    const range = formatMoneyRange(RANGE.derive(row), locale);
    return { text: range, label: `${formatMoney(row.actualCost, locale)} (${range})` };
  },
};

const COLUMNS = [
  { field: "name", label: "device" },
  { field: "energyUsed", label: "energy", format: formatEnergy },
  PAID,
  CHANGE,
  RANGE,
  // The one column that carries how well the device did, not just what it came
  // to (HEA-106). Would have paid is the right home for it because the verdict
  // is precisely this figure measured against Paid beside it: a row where the
  // two nearly agree avoided nothing, and one where Paid is a fraction of it
  // avoided almost everything.
  {
    field: "costAtGridPrice",
    label: "would_have_paid",
    format: formatMoney,
    carriesVerdict: true,
  },
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
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * The Range column only where every row that *could* carry a bound does.
   *
   * Per-device ranges are opt-in (ADR-0016), and a device the recorder holds no
   * bound for cannot be given one. A column of dashes would read as a fault; a
   * partly-filled one would invite comparing a bounded device with an unbounded
   * one, which is exactly the misranking the ADR rejects.
   *
   * **"Every row" was the wrong set, and made the column unreachable.** Two rows
   * never carry bounds under any configuration - the Untracked remainder and the
   * battery - so asking it of all of them was a condition no household could
   * meet, and the column had never once rendered. Asked of the rows the
   * integration publishes bounds *for*, the ADR's objection is preserved exactly:
   * what it rejects is comparing devices with each other on unequal footing, and
   * a row that cannot have a range is not competing in that comparison.
   *
   * The discriminator is already published and needs no flag: `statistics` omits
   * a concept whose entity does not exist, so a row offering the bound concepts
   * is a row the integration bounds.
   */
  /**
   * The columns this table can honestly fill.
   *
   * Range goes when any row lacks a bound (see below). Change goes when the
   * household has not asked to compare, which is the normal case - a column of
   * dashes on every row would read as a fault rather than as a question nobody
   * put.
   */
  _columns() {
    // Opt-in now, and a rollover on Paid otherwise. The band is still dropped
    // entirely where no row can carry one, which is the condition HEA-194 fixed
    // and this does not reopen (HEA-198).
    const asColumn = this._config?.range === "column" && this._hasEveryBound();
    const dropped = new Set();
    if (!asColumn) dropped.add(RANGE);
    if (!this._hasComparison()) dropped.add(CHANGE);
    return COLUMNS.filter((column) => !dropped.has(column)).map((column) =>
      // Shown once or the other way, never both: a rollover repeating the column
      // beside it is noise, and the column is the explicit request.
      column === PAID && asColumn ? { ...PAID, reveal: undefined } : column,
    );
  }

  /**
   * True once any row carries an earlier self.
   *
   * Any, not every: unlike the range, a partly-filled Change column is honest.
   * A device the earlier window never saw genuinely has no change to show, and
   * a dash beside its neighbours says exactly that - where a partly-filled
   * *range* would invite comparing a bounded device against an unbounded one,
   * which is the misranking ADR-0016 rejects.
   */
  _hasComparison() {
    return (this._result?.devices ?? []).some((row) => row.before);
  }

  _hasEveryBound() {
    const bounded = (this._result?.devices ?? []).filter(offersARange);
    return (
      bounded.length > 0 &&
      bounded.every((row) => RANGE.fields.every((f) => Number.isFinite(row[f])))
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
    const labels = labelsFor(this._hass);
    return [
      ...sortSchemaFor(SORTS, labels),
      // Offered rather than decided, because the two readings trade off: a
      // rollover keeps Paid as the single figure on the row, and a column can be
      // sorted and read down the page (HEA-198, HEA-100's precedent).
      {
        name: "range",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "rollover", label: labels.editor_range_rollover },
              { value: "column", label: labels.editor_range_column },
            ],
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
