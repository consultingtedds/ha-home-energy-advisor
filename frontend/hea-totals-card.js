/**
 * What the picked period cost, what it would have cost at grid price, and the
 * difference — the first card on the shared data layer (HEA-50).
 *
 * It owns no date range. Home Assistant's own `energy-date-selection` card is
 * the period control (ADR-0012); this card follows whatever that picker
 * announces, and falls back to a default range rather than rendering empty when
 * a dashboard has no picker on it.
 *
 * Plain `HTMLElement`, not LitElement: reaching Lit from a custom card means
 * pulling it out of Home Assistant's frontend internals, and ADR-0012 keeps
 * those behind one adapter. The chrome is `<ha-card>`, which is a documented
 * element rather than an internal.
 */

import { subscribeToPeriod } from "./ha-energy-collection.js";
import { readDevices } from "./hea-devices.js";
import { formatMoney, formatPeriod, localeFrom } from "./hea-format.js";
import { fetchDeviceStatistics } from "./hea-statistics.js";

export const TAG = "hea-totals-card";

/**
 * The three figures, in the order they answer the question: what it cost, what
 * it would have cost, and the difference. Names settled in ADR-0009 — "Cost at
 * Grid Price", never "Cost Without Solar".
 */
const FIGURES = [
  { key: "actualCost", label: "Actual Cost" },
  { key: "costAtGridPrice", label: "Cost at Grid Price" },
  { key: "costSavings", label: "Saved" },
];

const STYLE = `
  .body { padding: 16px; }
  .figures { display: flex; flex-wrap: wrap; gap: 16px; }
  .figure { flex: 1 1 8em; display: flex; flex-direction: column; gap: 4px; }
  .label {
    color: var(--secondary-text-color);
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .value {
    color: var(--primary-text-color);
    font-size: 1.6em;
    font-weight: 500;
    white-space: nowrap;
  }
  .value.loss { color: var(--error-color, #db4437); }
  .period {
    margin-top: 16px;
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .hint { margin-top: 4px; color: var(--secondary-text-color); font-size: 0.8em; }
  .message { margin: 0; color: var(--secondary-text-color); }
`;

class HeaTotalsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._state = "loading";
    // Every fetch carries a number so a slow answer that lands after a newer
    // one can be recognised and dropped.
    this._request = 0;
  }

  setConfig(config) {
    if (config.devices !== undefined && !Array.isArray(config.devices)) {
      throw new Error("`devices` must be a list of device keys");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._subscription) {
      // The picker may only have created its collection after this card's
      // first update, so keep offering it a chance to attach.
      this._subscription.retry(hass);
    } else {
      this._subscribe();
    }
    this._refetchIfDevicesChanged();
  }

  connectedCallback() {
    this._render();
    if (this._hass && !this._subscription) this._subscribe();
  }

  disconnectedCallback() {
    this._subscription?.unsubscribe();
    this._subscription = null;
  }

  /** Masonry needs a height estimate; three figures and a caption is about 3. */
  getCardSize() {
    return 3;
  }

  _subscribe() {
    this._subscription = subscribeToPeriod(
      this._hass,
      this._config?.collection_key,
      (period) => {
        this._period = period;
        this._scheduleFetch();
      },
    );
  }

  /**
   * Coalesce a burst of period announcements into one fetch.
   *
   * Subscribing emits the fallback period and then, immediately, the picker's
   * real one. Fetching on each would ask the recorder twice on every load and
   * put two answers in flight for no reason.
   */
  _scheduleFetch() {
    if (this._fetchPending) return;
    this._fetchPending = true;
    queueMicrotask(() => {
      this._fetchPending = false;
      this._fetch();
    });
  }

  _refetchIfDevicesChanged() {
    const keys = this._devices()
      .map((device) => device.key)
      .join(",");
    if (keys === this._deviceKeys) return;
    this._deviceKeys = keys;
    if (this._period) this._scheduleFetch();
  }

  /** The devices this card covers: the whole house unless a filter names some. */
  _devices() {
    const devices = readDevices(this._hass);
    const wanted = this._config?.devices;
    return wanted ? devices.filter((device) => wanted.includes(device.key)) : devices;
  }

  async _fetch() {
    if (!this._hass || !this._period) return;
    const devices = this._devices();
    const request = ++this._request;

    if (devices.length === 0) {
      // An empty statistic_ids list would ask the recorder for every statistic
      // in the database, so stop here and say why the card is blank.
      this._state = "empty";
      this._render();
      return;
    }

    try {
      const result = await fetchDeviceStatistics(this._hass, devices, this._period);
      if (request !== this._request) return; // a newer period has overtaken this
      this._totals = result.totals;
      this._state = "ready";
    } catch (error) {
      if (request !== this._request) return;
      // Zeroes would read as a week that cost nothing, which is worse than
      // admitting the figures could not be loaded.
      this._state = "error";
      console.error(`${TAG}: could not load statistics`, error);
    }
    this._render();
  }

  _render() {
    const locale = localeFrom(this._hass);
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._body(locale)}</div>
      </ha-card>
    `;
    // Set as a property rather than interpolated, so a title containing a quote
    // cannot break out of the markup.
    const title = this._config?.title;
    if (title) this.shadowRoot.querySelector("ha-card").setAttribute("header", title);
  }

  _body(locale) {
    if (this._state === "empty") {
      return `<p class="message">No devices are being tracked yet.</p>`;
    }
    if (this._state === "error") {
      return `<p class="message">Statistics could not be loaded.</p>`;
    }
    return `<div class="figures">${this._figures(locale)}</div>${this._caption(locale)}`;
  }

  _figures(locale) {
    return FIGURES.map(({ key, label }) => {
      const value = this._totals?.[key];
      // A negative saving is a battery arbitrage loss (HEA-39); it keeps its
      // sign and is marked so it reads as the loss it is.
      const loss = key === "costSavings" && value < 0 ? " loss" : "";
      return `
        <div class="figure">
          <span class="label">${label}</span>
          <span class="value${loss}" data-figure="${key}">${formatMoney(value, locale)}</span>
        </div>`;
    }).join("");
  }

  _caption(locale) {
    const hint = this._period?.fallback
      ? `<div class="hint">Add an Energy date picker card to choose the range.</div>`
      : "";
    return `<div class="period">${formatPeriod(this._period, locale)}</div>${hint}`;
  }
}

/**
 * Register the card, tolerating a dashboard that lists the resource twice — a
 * second `customElements.define` throws, and would take the whole view with it.
 */
export const register = () => {
  if (!customElements.get(TAG)) customElements.define(TAG, HeaTotalsCard);
  // Home Assistant documents this list as `window.customCards`; in a browser
  // `globalThis` is that same object, and it is the one Sonar prefers.
  globalThis.customCards = globalThis.customCards ?? [];
  if (!globalThis.customCards.some((card) => card.type === TAG)) {
    globalThis.customCards.push({
      type: TAG,
      name: "Home Energy Advisor: Totals",
      description:
        "What the selected period cost, what it would have cost at grid price, and the difference.",
    });
  }
};

register();
