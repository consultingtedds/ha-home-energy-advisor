/**
 * What every HEA card does the same way (HEA-50).
 *
 * A card follows Home Assistant's own period picker (ADR-0012), reads the
 * device set from the HEA-55 sensor, fetches statistics for the period, and
 * renders one of four states: loading, empty, error, or the figures. Only that
 * last part differs between cards, so only that part is left to them.
 *
 * Subclasses implement `_body(locale)` and set `static cardStyle`; everything
 * below - the subscription and its teardown, coalescing a burst of period
 * announcements, dropping a response that has been overtaken, and the states -
 * is shared, and is where the bugs would otherwise be duplicated.
 */

import { subscribeToPeriod } from "./ha-energy-collection.js";
import { readDevices, readWholeHome } from "./hea-devices.js";
import { formatPeriod, localeFrom } from "./hea-format.js";
import { fill, labelsFor, loadLabels } from "./hea-labels.js";
import { fetchDeviceStatistics, withComparison } from "./hea-statistics.js";

const BASE_STYLE = `
  .body { padding: 16px; }
  .period {
    margin-top: 16px;
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .hint { margin-top: 4px; color: var(--secondary-text-color); font-size: 0.8em; }
  .message { margin: 0; color: var(--secondary-text-color); }
`;

/**
 * Good news and bad news, and why these are the last rules in the sheet.
 *
 * A tone is a verdict on a figure, so it has to beat whatever colour the card
 * gives that figure ordinarily. `.loss` used to sit in `BASE_STYLE`, which is
 * concatenated *before* a card's own styles - equal specificity, later wins -
 * so the totals card's `.value { color: var(--primary-text-color) }` quietly
 * overrode it and HEA-39's colour was applied as a class and never painted.
 * The suite could not see it either: with no theme loaded that variable
 * resolves to nothing, the declaration collapses and the tone comes through,
 * so only a test that stands up a theme can tell the two apart (HEA-99).
 *
 * Appending them last is the whole fix, and it holds for any card added later
 * without that card having to know about it.
 */
const TONE_STYLE = `
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`;

export class HeaCard extends HTMLElement {
  /** Extra CSS for the subclass's own markup. */
  static cardStyle = "";

  /** The `cards` translation key naming this card when no title is configured. */
  static titleKey = "";

  /**
   * That key, for a card whose default name depends on what it is showing -
   * a diagram of energy should not head itself "Where the cost went" (HEA-90).
   */
  _titleKey() {
    return this.constructor.titleKey;
  }

  /**
   * This household's words, for the synchronous render path.
   *
   * English until `loadLabels` has answered, which is before any paint that
   * shows figures. A card is never blocked on its vocabulary (ADR-0018).
   */
  get _labels() {
    return labelsFor(this._hass);
  }

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

    // Before the empty check rather than after it: that branch renders and
    // returns, so a household with nothing tracked yet would be shown the
    // fallback English for good, with no later paint to correct it. A failed
    // fetch resolves to English rather than rejecting, so this can never be
    // what stops a card rendering (ADR-0018).
    //
    // Still alongside the figures rather than before them for every other
    // card: the words and the numbers are wanted at the same moment, and the
    // statistics request below is not held up by it.
    await loadLabels(this._hass);

    if (devices.length === 0) {
      // An empty statistic_ids list would ask the recorder for every statistic
      // in the database, so stop here and say why the card is blank.
      this._state = "empty";
      this._render();
      return;
    }

    // Only meaningful for the whole house: a card filtered to three devices is
    // not bounded by the household's range, and offering it there would invite
    // a comparison between a subset and its whole.
    const wholeHome = this._config?.devices ? undefined : readWholeHome(this._hass);

    try {
      // Both windows at once. The comparison is a second call rather than a new
      // mechanism, and asking for them together means one render rather than a
      // card that shows this period and then shifts when the other lands.
      const [result, comparison] = await Promise.all([
        fetchDeviceStatistics(this._hass, devices, this._period, wholeHome),
        this._period.compare
          ? fetchDeviceStatistics(
              this._hass,
              devices,
              this._period.compare,
              wholeHome,
            )
          : undefined,
      ]);
      if (request !== this._request) return; // a newer period has overtaken this
      this._result = withComparison(result, comparison);
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
      <style>${BASE_STYLE}${this.constructor.cardStyle}${TONE_STYLE}</style>
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
    // header, for a user stacking cards under a heading of their own - so the
    // two cases are distinguished rather than both treated as "unset".
    const title = this._config?.title ?? this._labels[this._titleKey()];
    if (title) this.shadowRoot.querySelector("ha-card").setAttribute("header", title);
    this._afterRender();
  }

  /**
   * A hook for cards whose markup needs properties set rather than attributes -
   * `ha-chart-base` takes its data and options as properties (ADR-0013), and
   * markup alone cannot express an object.
   */
  _afterRender() {
    // Deliberately empty: most cards are fully described by their markup.
  }

  _content(locale) {
    if (this._state === "empty") {
      return `<p class="message">${this._labels.no_devices}</p>`;
    }
    if (this._state === "error") {
      return `<p class="message">${this._labels.statistics_failed}</p>`;
    }
    return `${this._body(locale)}${this._caption(locale)}`;
  }

  _caption(locale) {
    const hint = this._period?.fallback
      ? `<div class="hint">${this._labels.no_picker}</div>`
      : "";
    return `<div class="period">${this._periodLabel(locale)}</div>${hint}`;
  }

  /**
   * The range the figures cover, and the one they are measured against.
   *
   * Comparison shipped in HEA-96 rendering "-EUR 0.77 vs EUR 1.87" under a
   * caption that said only "18 Aug 2026" - so the reader was given a baseline
   * figure and never told which window it came from. The picker knows, and it
   * arrives on `period.compare` already; it simply was not drawn (HEA-99).
   *
   * Joined with the same "vs" the figures themselves use, so the caption reads
   * as their baseline rather than as a second unrelated date. The dates are
   * Home Assistant's own, never derived from `compare.mode`: computing what
   * "the previous period" means risks disagreeing with the window actually
   * fetched, and a caption naming the wrong baseline is worse than none.
   *
   * Done here rather than in each card because all four wear this caption, and
   * building it four times is how the comparison came to read four ways.
   */
  _periodLabel(locale) {
    const period = formatPeriod(this._period, locale);
    const compare = this._period?.compare;
    if (!compare) return period;
    return fill(this._labels.compared_period, {
      period,
      compared: formatPeriod(compare, locale),
    });
  }
}

/**
 * Register a card and offer it in the card picker.
 *
 * Tolerates a dashboard that lists the resource twice - a second
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
