/**
 * What the household's installation earned over the period (HEA-241, ADR-0034).
 *
 * Generation saved, battery saved and exports earned, and their total, for the
 * whole home. Unlike every other card it is never narrowed by the page filter:
 * none of its figures can be split by device, room or label, so it says it
 * covers the whole home rather than ignoring a filter on a card that otherwise
 * honours it.
 *
 * It does not lead with Paid, which ADR-0029 asks of the cost cards: this one
 * answers a question about the installation rather than about what a device's
 * use cost. None of its figures is ever merged into Paid.
 */

import { HeaCard, registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { readDevices, readWholeHome } from "./hea-devices.js";
import { formatMoney, savingTone } from "./hea-format.js";
import {
  compensationStatistics,
  hasAnInstallation,
  installationReturn,
  installationStatistics,
  statisticIdsOf,
} from "./hea-installation.js";
import { loadLabels } from "./hea-labels.js";
import { bucketPeriodFor } from "./hea-statistics.js";

export const TAG = "hea-installation-card";
const EDITOR_TAG = `${TAG}-editor`;

/** The parts, in the order the total is built from them. */
const PARTS = [
  { key: "generationSaved", label: "generation_saved" },
  { key: "batterySaved", label: "battery_saved" },
  { key: "exportsEarned", label: "exports_earned" },
];

class HeaInstallationCard extends HeaCard {
  static titleKey = "title_installation";

  static cardStyle = `
    .parts { display: flex; flex-direction: column; gap: var(--hea-space-s); }
    .part, .total {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: var(--hea-space-m);
    }
    .label { color: var(--secondary-text-color); }
    .value { color: var(--primary-text-color); white-space: nowrap; }
    .total {
      margin-top: var(--hea-space-s);
      padding-top: var(--hea-space-s);
      border-top: 1px solid var(--divider-color);
      font-weight: 500;
    }
    .total .value { font-size: 1.4em; }
  `;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /** Three parts, a total and a note. */
  getCardSize() {
    return 4;
  }

  /**
   * The whole home, never the filtered subset: these figures have no devices.
   *
   * Asks the Energy Dashboard where its exports are recorded, and goes on
   * without them if it cannot say - a household with no Energy Dashboard still
   * has its generation and battery to show.
   */
  async _fetch() {
    if (!this._hass || !this._period) return;
    const request = ++this._request;
    await loadLabels(this._hass);

    const wholeHome = readWholeHome(this._hass);
    if (!hasAnInstallation(this._hass, wholeHome)) {
      this._state = "empty";
      this._render();
      return;
    }

    try {
      const parts = {
        ...installationStatistics(wholeHome, readDevices(this._hass)),
        exportsEarned: await this._exportStatistics(),
      };
      const buckets = await this._hass.callWS({
        type: "recorder/statistics_during_period",
        start_time: this._period.start.toISOString(),
        end_time: this._period.end.toISOString(),
        statistic_ids: statisticIdsOf(parts),
        period: bucketPeriodFor(this._period),
        types: ["change"],
      });
      if (request !== this._request) return;
      this._earned = installationReturn(buckets, parts, this._period);
      this._state = "ready";
    } catch (error) {
      if (request !== this._request) return;
      this._state = "error";
      console.error(`${this.localName}: could not load statistics`, error);
    }
    this._render();
  }

  async _exportStatistics() {
    try {
      const [prefs, info] = await Promise.all([
        this._hass.callWS({ type: "energy/get_prefs" }),
        this._hass.callWS({ type: "energy/info" }),
      ]);
      return compensationStatistics(prefs, info);
    } catch {
      // No Energy Dashboard is an ordinary configuration, not a fault.
      return [];
    }
  }

  _content(locale) {
    if (this._state === "empty") {
      return `<p class="message">${this._labels.no_installation}</p>`;
    }
    return super._content(locale);
  }

  _body(locale) {
    const earned = this._earned;
    const parts = PARTS.filter(({ key }) => earned?.[key] !== undefined)
      .map(({ key, label }) => this._line("part", key, this._labels[label], locale))
      .join("");
    return `
      <div class="parts">
        ${parts}
        ${this._line("total", "total", this._labels.total, locale)}
      </div>
      <div class="hint">${this._labels.installation_note}</div>`;
  }

  /** One labelled figure, marked as a gain or a loss as Saved is (HEA-102). */
  _line(kind, key, label, locale) {
    const value = this._earned?.[key];
    const tone = savingTone(value, locale);
    return `
      <div class="${kind}">
        <span class="label">${label}</span>
        <span class="value${tone ? ` ${tone}` : ""}" data-figure="${key}">${formatMoney(
          value,
          locale,
        )}</span>
      </div>`;
  }
}

/** Nothing beyond the shared fields, but it needs a tag of its own. */
class HeaInstallationCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaInstallationCardEditor);
  registerCard(TAG, HeaInstallationCard, {
    name: "Home Energy Advisor: What your installation earned",
    description:
      "What your generation, battery and exports earned over the selected period, for the whole home.",
  });
};

register();
