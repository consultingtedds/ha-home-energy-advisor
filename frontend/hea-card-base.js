/**
 * What every HEA card does the same way (HEA-50).
 *
 * A card follows Home Assistant's own period picker (ADR-0012), reads the
 * device set from the HEA-55 sensor, fetches statistics for the period, and
 * renders one of four states: loading, empty, error, or the figures. Only that
 * last part differs between cards, so only that part is left to them.
 *
 * Subclasses implement `_body(locale)` and set `static cardStyle`; everything
 * below — the subscription and its teardown, coalescing a burst of period
 * announcements, dropping a response that has been overtaken, and the states —
 * is shared, and is where the bugs would otherwise be duplicated.
 */

import { subscribeToPeriod } from "./ha-energy-collection.js";
import { readDevices } from "./hea-devices.js";
import { formatPeriod, localeFrom } from "./hea-format.js";
import { fetchDeviceStatistics } from "./hea-statistics.js";

const BASE_STYLE = `
  .body { padding: 16px; }
  .period {
    margin-top: 16px;
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .hint { margin-top: 4px; color: var(--secondary-text-color); font-size: 0.8em; }
  .message { margin: 0; color: var(--secondary-text-color); }
  .loss { color: var(--error-color, #db4437); }
`;

export class HeaCard extends HTMLElement {
  /** Extra CSS for the subclass's own markup. */
  static cardStyle = "";

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
      this._result = result;
      this._state = "ready";
    } catch (error) {
      if (request !== this._request) return;
      // Zeroes would read as a period that cost nothing, which is worse than
      // admitting the figures could not be loaded.
      this._state = "error";
      console.error(`${this.localName}: could not load statistics`, error);
    }
    this._render();
  }

  _render() {
    const locale = localeFrom(this._hass);
    this.shadowRoot.innerHTML = `
      <style>${BASE_STYLE}${this.constructor.cardStyle}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(locale)}</div>
      </ha-card>
    `;
    // Set as a property rather than interpolated, so a title containing a quote
    // cannot break out of the markup.
    //
    // An absent title takes the card's own default: a card added from the
    // picker should say what it shows, and a chart of coloured bars says
    // nothing on its own. An *empty* title is a deliberate request for no
    // header, for a user stacking cards under a heading of their own — so the
    // two cases are distinguished rather than both treated as "unset".
    const title = this._config?.title ?? this.constructor.defaultTitle;
    if (title) this.shadowRoot.querySelector("ha-card").setAttribute("header", title);
    this._afterRender();
  }

  /**
   * A hook for cards whose markup needs properties set rather than attributes —
   * `ha-chart-base` takes its data and options as properties (ADR-0013), and
   * markup alone cannot express an object.
   */
  _afterRender() {
    // Deliberately empty: most cards are fully described by their markup.
  }

  _content(locale) {
    if (this._state === "empty") {
      return `<p class="message">No devices are being tracked yet.</p>`;
    }
    if (this._state === "error") {
      return `<p class="message">Statistics could not be loaded.</p>`;
    }
    return `${this._body(locale)}${this._caption(locale)}`;
  }

  _caption(locale) {
    const hint = this._period?.fallback
      ? `<div class="hint">Add an Energy date picker card to choose the range.</div>`
      : "";
    return `<div class="period">${formatPeriod(this._period, locale)}</div>${hint}`;
  }
}

/**
 * Register a card and offer it in the card picker.
 *
 * Tolerates a dashboard that lists the resource twice — a second
 * `customElements.define` throws, and would take the whole view with it.
 */
export const registerCard = (tag, cardClass, { name, description }) => {
  if (!customElements.get(tag)) customElements.define(tag, cardClass);
  // Home Assistant documents this list as `window.customCards`; in a browser
  // `globalThis` is that same object, and it is the one Sonar prefers.
  globalThis.customCards = globalThis.customCards ?? [];
  if (!globalThis.customCards.some((card) => card.type === tag)) {
    globalThis.customCards.push({ type: tag, name, description });
  }
};
