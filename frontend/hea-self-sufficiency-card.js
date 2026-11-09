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
 * **The battery counts as far as it held sunshine.** HA's own formula is a grid
 * complement, `1 - from_grid / consumption`, which silently counts battery
 * discharge as self-produced whatever charged it - and counts the unaccounted
 * remainder that way too. A battery filled from cheap overnight import would
 * read as self-sufficiency that was really grid power. The battery's ledger
 * knows the split, so each device's Energy From Battery (Solar) is the part
 * that was stored sunshine: the headline counts that, and the rest of the
 * discharge is shown beside it as bought (ADR-0033, revising the maintainer's
 * 2026-08-28 decision to leave the battery out altogether).
 *
 * No severity colouring, deliberately. HA's card grades its gauge red to green,
 * but a "good" self-sufficiency figure is a property of the household's roof,
 * not of the reading - a flat with two panels and a house with twenty have
 * different honest expectations - so each gauge takes its source's colour from
 * Home Assistant's energy tokens, as the flow diagram does, and makes no claim
 * we cannot support.
 *
 * **A row of gauges, each source its own (HEA-248, discussion 48).** One gauge
 * the width of the card dazzled on a wide screen, and the figures beside it
 * were read rather than glanced at. So each source gets a gauge the size of
 * Home Assistant's, capped at its 250px: generation first as the headline, then
 * the battery's stored solar and grid-bought parts, then the grid. Every one is
 * a share of the energy the rows on screen used, so all four hold under any
 * filter, which Home Assistant's whole-home gauges never have to. The battery's
 * two are drawn only where the rows used any battery energy, so a home without
 * one is not shown two gauges resting on nought.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { formatEnergy, formatPercent, localeFrom } from "./hea-format.js";
import { fill } from "./hea-labels.js";

export const TAG = "hea-self-sufficiency-card";
const EDITOR_TAG = `${TAG}-editor`;

/** The energy fields the shares are built from, summed across the rows shown. */
const FIELDS = [
  "energyUsed",
  "energyFromGrid",
  "energyFromGeneration",
  "energyFromBattery",
  "energyFromBatterySolar",
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

  /** This card never shows money, so an empty period is one with no energy. */
  static emptyKey = "no_energy_in_period";

  static cardStyle = `
    .intro {
      margin-bottom: var(--hea-space-m);
      color: var(--secondary-text-color);
    }
    .gauges {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: var(--hea-space-l);
    }
    /* One column, as wide as the cell up to Home Assistant's own cap on an
       energy gauge. A grid rather than a flex column, whose centring would
       shrink the gauge to nothing: its arc sizes itself to the width given. */
    .gauge {
      display: grid;
      grid-template-columns: minmax(0, 250px);
      justify-content: center;
    }
    ha-gauge { display: block; }
    .headline {
      margin-top: var(--hea-space-s);
      text-align: center;
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .share { margin-top: var(--hea-space-l); color: var(--secondary-text-color); }
    .value { color: var(--primary-text-color); font-weight: 500; }
    .note {
      margin-top: var(--hea-space-m);
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
   * Generation is the household's own: what the panels served directly, and
   * what they stored in the battery for later. The battery's share is only the
   * rest of its discharge, the energy it was charged with from the grid.
   *
   * The three need not add up. A bucket with draw the house-level meters never
   * accounted for contributes to energy and to no source, so the remainder is
   * real and is shown rather than folded into one of the three.
   */
  _shares() {
    const totals = this._totals();
    const used = totals.energyUsed;
    const share = (field) => totals[field] / used;
    const storedSolar = share("energyFromBatterySolar");
    const generation = share("energyFromGeneration") + storedSolar;
    const battery = share("energyFromBattery") - storedSolar;
    const grid = share("energyFromGrid");
    return {
      generation,
      storedSolar,
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

  /**
   * Each gauge this card draws: its share, its words and its colour.
   *
   * The headline says it includes stored solar only where some was, so a home
   * with panels and no battery is not told about a battery it does not have.
   */
  _gauges() {
    const shares = this._shares();
    const batteryUsed = this._totals().energyFromBattery > 0;
    return [
      {
        key: "generation",
        label: this._labels.from_generation,
        note: shares.storedSolar > ROUNDING ? this._labels.including_stored_solar : "",
        colour: "var(--energy-solar-color, #ff9800)",
      },
      batteryUsed && {
        key: "storedSolar",
        label: this._labels.of_which_stored_solar,
        colour: "var(--energy-solar-color, #ff9800)",
      },
      batteryUsed && {
        key: "battery",
        label: this._labels.from_battery_grid,
        colour: "var(--energy-battery-out-color, #4db6ac)",
      },
      {
        key: "grid",
        label: this._labels.from_grid,
        colour: "var(--energy-grid-consumption-color, #488fc2)",
      },
    ]
      .filter(Boolean)
      .map((gauge) => ({ ...gauge, value: shares[gauge.key] }));
  }

  /**
   * The gauges, under a line saying what they are shares of.
   *
   * Every one is a share of the energy the rows used, in kWh, never of money:
   * shown beside cards that lead with what was paid, a bare percentage was read
   * as a share of the cost (HEA-248, the maintainer on the demo). So the line
   * names the energy, and how much of it.
   */
  _chartMarkup() {
    const locale = localeFrom(this._hass);
    const intro = fill(this._labels.energy_used_came_from, {
      energy: formatEnergy(this._totals().energyUsed, locale),
    });
    const gauges = this._gauges()
      .map(
        ({ key, label, note, colour }) => `
        <div class="gauge">
          <ha-gauge data-gauge="${key}" style="--gauge-color: ${colour}"></ha-gauge>
          <div class="headline">${label}</div>
          ${note ? `<div class="headline">${note}</div>` : ""}
        </div>`,
      )
      .join("");
    return `<div class="intro" data-figure="energy-used">${intro}</div>
      <div class="gauges">${gauges}</div>`;
  }

  /** What no source accounts for, where anything is, and what the headline counts. */
  _breakdown(locale) {
    const { unaccounted } = this._shares();
    // A nought-percent remainder is nothing to report, and a line saying so
    // would read as a fault.
    const shortfall =
      unaccounted > ROUNDING
        ? `<div class="share">${this._labels.unaccounted}
            <span class="value" data-share="unaccounted">${formatPercent(
              unaccounted,
              locale,
            )}</span></div>`
        : "";
    return `${shortfall}<div class="note">${this._labels.self_sufficiency_note}</div>`;
  }

  /**
   * Every gauge, not only the first: `HeaChartCard` hands `_draw` one element.
   *
   * `ha-gauge` renders from properties; an attribute would be a string.
   */
  _afterRender() {
    if (!this._chartReady || this._isEmpty()) return;
    const values = Object.fromEntries(
      this._gauges().map(({ key, value }) => [key, value]),
    );
    for (const gauge of this.shadowRoot.querySelectorAll("ha-gauge")) {
      gauge.hass = this._hass;
      gauge.min = 0;
      gauge.max = 100;
      gauge.value = values[gauge.dataset.gauge] * 100;
      gauge.label = "%";
      gauge.formatOptions = GAUGE_FORMAT;
      gauge.locale = this._hass?.locale;
    }
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
