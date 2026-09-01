/**
 * The control that narrows the whole page (HEA-95).
 *
 * The period picker's shape one layer down (ADR-0012): this card owns the
 * selection and every other card follows it, so "what did the aircon cost this
 * week" is asked once on the page rather than configured five times. The
 * selection lives in `hea-filter.js`, keyed by the same `collection_key` the
 * cards already agree on.
 *
 * The options come from the device rows the HEA-55 sensor publishes, so a
 * household that adds a room finds it in the list without touching a dashboard.
 * Nothing here names a room, a floor, a label or a device.
 *
 * Individual devices are offered too (HEA-98), which is what answers "show me
 * this one device across the period": the charts already draw a single device
 * correctly when it is the only one on them - `_devices()` narrows, and the
 * series are built from whatever list they are handed - so what was missing was
 * never a chart but a way to say which device.
 *
 * A plain `<select>` rather than one of Home Assistant's own form components.
 * ADR-0012 confines internals to one adapter, and this card needs none of them:
 * a select is a native control the browser makes accessible and searchable for
 * free, it needs no lazy-loaded component and so has no "not loaded" state to
 * fall into, and grouped options are exactly the shape of rooms-then-floors.
 *
 * This card does not extend `HeaCard`. It wants the device list and nothing
 * else - no period, no statistics - and inheriting the fetch would have it
 * asking the recorder for figures it never draws.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { readDevices, readLabelNames } from "./hea-devices.js";
import { filterFor, setFilter, subscribeToFilter } from "./hea-filter.js";
import { escapeText } from "./hea-format.js";
import { labelsFor, loadLabels } from "./hea-labels.js";

export const TAG = "hea-filter-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * The groups offered, in the order a household thinks in.
 *
 * Rooms first: it is the question most often asked and the one every instance
 * can answer. Labels after them, because they exist only where a household has
 * made them, and an empty group would read as "you have no labels" rather than
 * as a grouping nobody has set up.
 *
 * Individual devices last of all. Naming one is the step *after* a grouping -
 * the question asked once a ranking has said which device to look at (HEA-98) -
 * and it is also the longest list, so it belongs past the groups rather than
 * between them.
 */
const GROUPS = [
  { kind: "area", label: "filter_rooms", id: "areaId", name: "areaName" },
  { kind: "floor", label: "filter_floors", id: "floorId", name: "floorName" },
];

/** A selection, as one string, because that is what an option's value is. */
const encode = ({ kind, id }) => `${kind}:${id ?? ""}`;
const decode = (value) => {
  const [kind, id] = [value.slice(0, value.indexOf(":")), value.slice(value.indexOf(":") + 1)];
  return { kind, id: id === "" ? null : id };
};

class HeaFilterCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // The words and the rooms arrive together; neither blocks the other, and a
    // failed vocabulary fetch resolves to English rather than rejecting.
    loadLabels(hass).then(() => this._renderIfChanged());
    this._renderIfChanged();
  }

  /** One row: a label and a control. */
  getCardSize() {
    return 1;
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  connectedCallback() {
    this._render();
    this._unfilter ??= subscribeToFilter(this._config?.collection_key, () =>
      this._renderIfChanged(),
    );
  }

  /**
   * Everything this card draws, as one string.
   *
   * Home Assistant sets `hass` on every state change - many times a second on
   * a busy instance - and this card's markup is a `<select>`. Rewriting it on
   * each one destroys the dropdown underneath the household while they are
   * choosing from it, which is what made the first version unusable (HEA-95).
   *
   * So the card redraws only when what it *shows* has moved: the rooms, floors
   * and labels in use, their names, the devices and *their* names, the current
   * selection, and the vocabulary once it arrives. A device's cost changes
   * constantly and is not in here, because this card never draws one.
   */
  _signature() {
    return JSON.stringify([
      this._allDevices().map((device) => [
        device.key,
        device.name,
        device.areaId,
        device.areaName,
        device.floorId,
        device.floorName,
        device.labels,
      ]),
      encode(filterFor(this._config?.collection_key)),
      this._labels.filter_rooms,
    ]);
  }

  _renderIfChanged() {
    if (this._signature() === this._drawn) return;
    this._render();
  }

  disconnectedCallback() {
    this._unfilter?.();
    this._unfilter = null;
  }

  get _labels() {
    return labelsFor(this._hass);
  }

  /**
   * The devices the *groupings* are built from.
   *
   * The Untracked remainder is left out: it is in no room and carries no label
   * by definition, so counting it would put an "unfiled" bucket on every
   * household's card whether or not they had anything unfiled. It is offered
   * by name in the Devices group instead, where nothing has to be claimed
   * about where it lives (HEA-98).
   */
  _devices() {
    return readDevices(this._hass).filter((device) => !device.untracked);
  }

  /** Everything nameable, remainder included. */
  _allDevices() {
    return readDevices(this._hass);
  }

  /**
   * One entry per room or floor in use, and a bucket for the unfiled.
   *
   * The bucket appears only where something is actually unfiled. Measured on
   * the reference instance, one tracked device has no room and five have no
   * floor, so it is not a theoretical case - but an always-present empty bucket
   * would describe a house that does not exist.
   */
  _optionsFor({ kind, id, name }, devices) {
    const named = new Map();
    let unfiled = false;
    for (const device of devices) {
      if (device[id]) named.set(device[id], device[name] ?? device[id]);
      else unfiled = true;
    }
    const options = [...named.entries()]
      .map(([value, text]) => ({ value: encode({ kind, id: value }), text }))
      .sort((left, right) => left.text.localeCompare(right.text));
    if (unfiled) {
      options.push({ value: encode({ kind, id: null }), text: this._labels.filter_unfiled });
    }
    return options;
  }

  /**
   * The labels a household has actually used, or none.
   *
   * No unfiled bucket here: a device carrying no labels is not "unlabelled" in
   * the way a device in no room is unfiled - it simply is not in any of them,
   * and a bucket would invite a household to read it as a group.
   */
  _labelOptions(devices) {
    const names = readLabelNames(this._hass);
    const used = new Set(devices.flatMap((device) => device.labels ?? []));
    return [...used]
      .map((label) => ({
        value: encode({ kind: "label", id: label }),
        // The id is what a filter matches on and what survives a rename; the
        // name is what a household reads. A label of two words has an id
        // joining them with an underscore, and showing that would put the
        // underscore in front of them.
        text: names[label] ?? label,
      }))
      .sort((left, right) => left.text.localeCompare(right.text));
  }

  /**
   * Every device by name, the remainder among them.
   *
   * No unfiled bucket and no omissions: a device is either in the house or it
   * is not, and the remainder is a real line with a real cost.
   */
  _deviceOptions() {
    return this._allDevices()
      .map((device) => ({
        value: encode({ kind: "device", id: device.key }),
        text: device.name,
      }))
      .sort((left, right) => left.text.localeCompare(right.text));
  }

  _groups() {
    const devices = this._devices();
    const groups = GROUPS.map((group) => ({
      label: this._labels[group.label],
      options: this._optionsFor(group, devices),
    }));
    const labels = this._labelOptions(devices);
    if (labels.length) {
      groups.push({ label: this._labels.filter_labels, options: labels });
    }
    groups.push({ label: this._labels.filter_devices, options: this._deviceOptions() });
    return groups.filter((group) => group.options.length > 0);
  }

  _render() {
    const labels = this._labels;
    const devices = this._devices();
    this._drawn = this._signature();
    const body = devices.length
      ? this._control(labels)
      : `<p class="message">${labels.no_devices}</p>`;
    this.shadowRoot.innerHTML = `
      <style>
        /*
         * Matching Home Assistant's own energy-date-selection card, which this
         * is meant to stand beside: it fills its grid cell and centres its one
         * row, so a card of a different height next to it leaves the two
         * controls sitting on different lines (HEA-95).
         */
        ha-card {
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: center;
        }
        .body { padding: 16px; display: flex; align-items: center; gap: 12px; }
        .label {
          color: var(--secondary-text-color);
          font-size: 0.85em;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        select {
          flex: 1 1 auto;
          min-width: 0;
          padding: 8px;
          color: var(--primary-text-color);
          background: var(--card-background-color, transparent);
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: var(--ha-border-radius-small, 4px);
          font: inherit;
        }
        .message { margin: 0; padding: 16px; color: var(--secondary-text-color); }
      </style>
      <ha-card>${body}</ha-card>
    `;
    const select = this.shadowRoot.querySelector("select");
    if (!select) return;
    select.value = encode(filterFor(this._config?.collection_key));
    select.addEventListener("change", () =>
      setFilter(this._config?.collection_key, decode(select.value)),
    );
  }

  /**
   * The control itself.
   *
   * A room's name is the household's own text and is escaped; so are a label,
   * which a household types into Home Assistant's label registry, and a device
   * name, which comes from the device registry.
   */
  _control(labels) {
    const groups = this._groups()
      .map(
        (group) => `<optgroup label="${escapeText(group.label)}">${group.options
          .map(
            (option) =>
              `<option value="${escapeText(option.value)}">${escapeText(option.text)}</option>`,
          )
          .join("")}</optgroup>`,
      )
      .join("");
    return `<div class="body">
      <span class="label">${labels.title_filter}</span>
      <select>
        <option value="${encode({ kind: "all", id: null })}">${escapeText(
          labels.filter_everything,
        )}</option>
        ${groups}
      </select>
    </div>`;
  }
}

/** Only the shared fields; what it filters is the household's to choose live. */
class HeaFilterCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaFilterCardEditor);
  registerCard(TAG, HeaFilterCard, {
    name: "Home Energy Advisor: Filter",
    description:
      "Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device.",
  });
};

register();
