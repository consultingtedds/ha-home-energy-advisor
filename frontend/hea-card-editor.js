/**
 * The visual editor behind every HEA card (HEA-73).
 *
 * Without one, Home Assistant tells the user the card "cannot be edited from
 * the UI" and hands them raw YAML - in which they are expected to know that a
 * device is called `fine_meter_aircon`, a slug that appears nowhere in the
 * interface. The device list is already published (HEA-55), so the editor shows
 * it: names to choose from, keys written for them.
 *
 * Built on Home Assistant's `ha-form`, so it looks and behaves like every
 * built-in card editor. That is a frontend *element*, like `<ha-card>`, not the
 * energy-collection internals ADR-0012 decision 5 isolates: a break there is
 * visible and cosmetic rather than a silently wrong number, and it is confined
 * to the editor, so the card itself keeps working.
 */

import { readDevices } from "./hea-devices.js";
import { labelsFor, loadLabels } from "./hea-labels.js";

/** Each editor field's key in the shared vocabulary (ADR-0018). */
const FIELD_LABELS = {
  title: "editor_title",
  collection_key: "editor_collection_key",
  devices: "editor_devices",
  sort_by: "editor_sort_by",
  layout: "editor_layout",
  metric: "editor_metric",
};

export class HeaCardEditor extends HTMLElement {
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
    this._render();
    // The editor is opened long after a card has painted, so the vocabulary is
    // usually already loaded; fetch anyway, in case the editor is the first
    // thing on the page. Re-render on arrival rather than block on it.
    loadLabels(hass).then(() => this._render());
  }

  /** Fields the card being edited adds to the shared ones. */
  _extraSchema() {
    return [];
  }

  _render() {
    if (!this._config) return;
    let form = this.shadowRoot.querySelector("ha-form");
    if (!form) {
      form = document.createElement("ha-form");
      form.computeLabel = (field) =>
        labelsFor(this._hass)[FIELD_LABELS[field.name]] ?? field.name;
      form.addEventListener("value-changed", (event) =>
        this._report(event.detail.value),
      );
      this.shadowRoot.append(form);
    }
    form.hass = this._hass;
    form.data = this._config;
    form.schema = this._schema();
  }

  _schema() {
    return [
      { name: "title", selector: { text: {} } },
      { name: "collection_key", selector: { text: {} } },
      {
        name: "devices",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            // Names to choose from, keys written for them. Never a hardcoded
            // list: a device added to the integration appears here by itself.
            options: readDevices(this._hass).map((device) => ({
              value: device.key,
              label: device.name,
            })),
          },
        },
      },
      ...this._extraSchema(),
    ];
  }

  _report(value) {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: pruned({ ...this._config, ...value }) },
        // Home Assistant listens on an ancestor, and the editor is inside a
        // shadow root: without both of these the dashboard never hears it.
        bubbles: true,
        composed: true,
      }),
    );
  }
}

/**
 * The configuration with nothing empty left in it.
 *
 * A cleared field means "not set", not "set to nothing" - and an empty device
 * list would filter the card down to no devices at all, where the user meant
 * the whole house.
 */
const pruned = (config) =>
  Object.fromEntries(
    Object.entries(config).filter(
      ([, value]) =>
        value !== "" &&
        value !== undefined &&
        value !== null &&
        !(Array.isArray(value) && value.length === 0),
    ),
  );

/** Register an editor, tolerating a resource listed twice on one dashboard. */
export const registerEditor = (tag, editorClass) => {
  if (!customElements.get(tag)) customElements.define(tag, editorClass);
};
