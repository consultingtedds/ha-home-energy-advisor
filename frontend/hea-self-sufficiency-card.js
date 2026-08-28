/**
 * How much of the period's energy the household produced itself (HEA-91).
 *
 * `hea-sources-card` already answers this numerically - grid, generation and
 * battery kWh per device, with a "from the grid" column - but a table is read,
 * not glanced at, and this is the one figure a household with solar wants at a
 * glance. ADR-0012's layout table has always mapped Home Assistant's
 * self-sufficiency gauge onto HEA-51's by-source split; this is that gauge.
 *
 * Drawn with Home Assistant's own `ha-gauge`, the same element its energy
 * gauges use, so ours looks native beside them. Neither HA gauge *card* could
 * be reused: the plain one requires an `entity` and reads its current state,
 * which cannot express a figure computed over the picker's range, and the
 * energy one binds to `getEnergyDataCollection` and the household's energy
 * preferences, which cannot see our per-device statistics. The component
 * beneath them takes numbers and a locale and nothing else, so the drawing is
 * HA's and only the arithmetic is ours (ADR-0017's ladder, recorded on the
 * ticket).
 *
 * **Battery discharge is not in the headline.** HA's own formula is a grid
 * complement, `1 - from_grid / consumption`, which silently counts battery
 * discharge as self-produced whatever charged it - and counts the unaccounted
 * remainder that way too. We cannot make that claim: `BatteryLedger` records
 * what the stored energy cost, never what share of it was generated, and on the
 * reference instance Predbat force-charges from the grid overnight, so a
 * battery-heavy evening would read as self-sufficiency that was really cheap
 * grid power. The battery share is shown beside the headline instead, named,
 * with the reason on the card (maintainer's decision, 2026-08-28).
 *
 * No severity colouring, deliberately. HA's card grades its gauge red to green,
 * but a "good" self-sufficiency figure is a property of the household's roof,
 * not of the reading - a flat with two panels and a house with twenty have
 * different honest expectations - so a single accent makes no claim we cannot
 * support.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { formatPercent } from "./hea-format.js";

export const TAG = "hea-self-sufficiency-card";
const EDITOR_TAG = `${TAG}-editor`;

/** The energy fields the shares are built from, summed across the rows shown. */
const FIELDS = [
  "energyUsed",
  "energyFromGrid",
  "energyFromGeneration",
  "energyFromBattery",
];

/**
 * The gauge reads a percentage, and `ha-gauge` takes the number, not a fraction.
 *
 * Whole percent, matching `formatPercent`: the split is an allocation of a
 * coarse counter's energy and a decimal place would claim a precision the
 * estimate has not got.
 */
const GAUGE_FORMAT = { maximumFractionDigits: 0 };

/**
 * Below which a remainder is rounding rather than a shortfall.
 *
 * The shares are ratios of floating-point sums, so an exactly-covered period
 * lands a hair either side of zero. Half of the smallest percentage the card
 * can render: anything smaller would draw "0%" under a heading that says
 * something is missing, which reads as a fault rather than as nothing to
 * report.
 */
const ROUNDING = 0.005;

class HeaSelfSufficiencyCard extends HeaChartCard {
  static titleKey = "title_self_sufficiency";

  /**
   * A different component from the chart cards, and a different card pulls it
   * in. Creating an `energy-self-sufficiency-gauge` imports `ha-gauge` as a
   * side effect, and it is safe to create with no configuration: its
   * `setConfig` validates only a `collection_key` it was not given, and it
   * subscribes in `hassSubscribe`, which `createCardElement` never reaches.
   * The plain `gauge` card imports the same element but throws without an
   * `entity`, so it would fail on every load.
   */
  static chartTag = "ha-gauge";
  static bearingCard = { type: "energy-self-sufficiency-gauge" };

  static cardStyle = `
    ha-gauge { display: block; margin: 0 auto; --gauge-color: var(--primary-color); }
    .headline {
      margin-top: 8px;
      text-align: center;
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .shares { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; }
    .share { flex: 1 1 6em; display: flex; flex-direction: column; gap: 4px; }
    .label {
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value { color: var(--primary-text-color); font-size: 1.2em; font-weight: 500; }
    .note {
      margin-top: 12px;
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** A gauge and a row of figures, not a full graph. */
  getCardSize() {
    return 4;
  }

  /**
   * Nothing to show is a period with no energy, not a period with no buckets.
   *
   * A share of nothing is undefined, never nought percent: "none of it came
   * from generation" and "we cannot say" are different claims, and a gauge
   * resting on zero makes the first one.
   */
  _isEmpty() {
    return this._totals().energyUsed <= 0;
  }

  /**
   * The energy of the rows on screen, summed.
   *
   * Summed and then divided, never a mean of the rows' own shares -
   * `hea-sources-card` settled this: averaging weights a device that used a
   * tenth of a kilowatt-hour the same as one that used twenty. With no filter
   * these rows are the house, since the allocations sum to the real total and
   * Untracked is one of them (ADR-0002); with one, they are what the card is
   * showing, which is what its figure must describe.
   */
  _totals() {
    return (this._result?.devices ?? []).reduce(
      (totals, device) => {
        for (const field of FIELDS) totals[field] += device[field];
        return totals;
      },
      Object.fromEntries(FIELDS.map((field) => [field, 0])),
    );
  }

  /**
   * Each source as a fraction of the energy used, plus whatever is left over.
   *
   * The three need not add up. A bucket with draw the house-level meters never
   * accounted for contributes to energy and to no source, so the remainder is
   * real and is shown rather than folded into one of the three.
   */
  _shares() {
    const totals = this._totals();
    const used = totals.energyUsed;
    const share = (field) => totals[field] / used;
    const generation = share("energyFromGeneration");
    const battery = share("energyFromBattery");
    const grid = share("energyFromGrid");
    return {
      generation,
      battery,
      grid,
      // Never negative: sources that overshoot the energy are the same rounding
      // as ones that fall short, and a negative remainder means nothing.
      unaccounted: Math.max(0, 1 - generation - battery - grid),
    };
  }

  _body(locale) {
    const body = super._body(locale);
    if (!this._chartReady || this._isEmpty()) return body;
    return `${body}${this._breakdown(locale)}`;
  }

  /** The gauge, and the concept its number is a share of. */
  _chartMarkup() {
    return `<ha-gauge></ha-gauge>
      <div class="headline">${this._labels.from_generation}</div>`;
  }

  /** What the rest of the energy was, and why the battery is its own figure. */
  _breakdown(locale) {
    const { battery, grid, unaccounted } = this._shares();
    const figures = [
      { label: "from_battery", value: battery },
      { label: "from_grid", value: grid },
      { label: "unaccounted", value: unaccounted },
    ]
      // A nought-percent remainder is nothing to report, and a row saying so
      // would read as a fault. The named sources stay whatever their share.
      .filter(({ label, value }) => label !== "unaccounted" || value > ROUNDING)
      .map(
        ({ label, value }) => `
        <div class="share">
          <span class="label">${this._labels[label]}</span>
          <span class="value" data-share="${label}">${formatPercent(value, locale)}</span>
        </div>`,
      )
      .join("");
    return `<div class="shares">${figures}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`;
  }

  /** `ha-gauge` renders from properties; an attribute would be a string. */
  _draw(gauge) {
    gauge.min = 0;
    gauge.max = 100;
    gauge.value = this._shares().generation * 100;
    gauge.label = "%";
    gauge.formatOptions = GAUGE_FORMAT;
    gauge.locale = this._hass?.locale;
  }
}

/** Nothing beyond the shared fields, but it needs a tag of its own. */
class HeaSelfSufficiencyCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaSelfSufficiencyCardEditor);
  registerCard(TAG, HeaSelfSufficiencyCard, {
    name: "Home Energy Advisor: Self-sufficiency",
    description:
      "What share of the selected period's energy came from the household's own generation.",
  });
};

register();
