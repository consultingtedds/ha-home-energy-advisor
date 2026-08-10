/**
 * @vitest-environment happy-dom
 *
 * The visual editors (HEA-73). Without one, a custom card drops the user into
 * raw YAML and expects them to know that a device is called
 * `kitchen_aircon` — a slug that appears nowhere in the interface.
 *
 * `ha-form` belongs to Home Assistant and is never defined in these tests, so
 * what is asserted is the contract we hand it: the schema, the data, and the
 * `config-changed` event we raise from what it reports back.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { TAG as DEVICES_TAG } from "../hea-devices-card.js";
import { TAG as TOTALS_TAG } from "../hea-totals-card.js";
import { aDeviceRow, aHass } from "./doubles.js";

const TWO_DEVICES = [
  aDeviceRow("kitchen_aircon", "Kitchen Aircon"),
  aDeviceRow("living_room_aircon", "Living Room Aircon"),
];

/** The editor Home Assistant would obtain and set up for a card. */
const anEditorFor = (tag, config = {}, hass = aHass({ devices: TWO_DEVICES })) => {
  const editor = customElements.get(tag).getConfigElement();
  document.body.append(editor);
  editor.setConfig({ type: `custom:${tag}`, ...config });
  editor.hass = hass;
  return editor;
};

const formOf = (editor) => editor.shadowRoot.querySelector("ha-form");
const fieldOf = (editor, name) =>
  formOf(editor).schema.find((field) => field.name === name);

/** Act as `ha-form` does when the user changes something. */
const userEdits = (editor, value) =>
  formOf(editor).dispatchEvent(
    new CustomEvent("value-changed", { detail: { value } }),
  );

beforeEach(() => {
  document.body.replaceChildren();
});

describe("a card's editor", () => {
  it("is offered by the card, so Home Assistant stops showing raw yaml", () => {
    // Given / When / Then
    for (const tag of [TOTALS_TAG, DEVICES_TAG]) {
      expect(customElements.get(tag).getConfigElement()).toBeInstanceOf(HTMLElement);
    }
  });

  it("shows the configuration the card actually has", () => {
    // Given / When
    const editor = anEditorFor(TOTALS_TAG, { title: "Running costs" });

    // Then — ha-form renders from this, so it is what the user sees pre-filled
    expect(formOf(editor).data).toEqual(
      expect.objectContaining({ title: "Running costs" }),
    );
  });

  it("labels its fields in words, not in config keys", () => {
    // Given — ha-form asks the editor what to call each field, and
    // "collection_key" means nothing to a household
    const editor = anEditorFor(TOTALS_TAG);

    // When / Then
    const label = (name) => formOf(editor).computeLabel({ name });
    expect(label("devices")).toMatch(/device/i);
    expect(label("collection_key")).toMatch(/period/i);
    expect(label("something_new")).toBe("something_new");
  });

  it("waits for its configuration when hass arrives first", () => {
    // Given — Home Assistant sets hass and setConfig in whichever order suits
    // it, and an editor that rendered without a config would crash the panel
    const editor = customElements.get(TOTALS_TAG).getConfigElement();
    document.body.append(editor);

    // When
    editor.hass = aHass({ devices: TWO_DEVICES });
    expect(formOf(editor)).toBe(null);
    editor.setConfig({ type: `custom:${TOTALS_TAG}` });

    // Then
    expect(fieldOf(editor, "devices").selector.select.options).toHaveLength(2);
  });

  it("offers the title and the energy period", () => {
    // Given / When
    const editor = anEditorFor(TOTALS_TAG);

    // Then
    expect(fieldOf(editor, "title")).toBeDefined();
    expect(fieldOf(editor, "collection_key")).toBeDefined();
  });
});

describe("choosing devices", () => {
  it("lists devices by the name the household gave them", () => {
    // Given — the whole point: `kitchen_aircon` appears nowhere in the
    // interface, so nobody should have to type it
    const editor = anEditorFor(TOTALS_TAG);

    // When
    const options = fieldOf(editor, "devices").selector.select.options;

    // Then — the name is shown, the key is what gets written
    expect(options).toEqual([
      { value: "kitchen_aircon", label: "Kitchen Aircon" },
      { value: "living_room_aircon", label: "Living Room Aircon" },
    ]);
  });

  it("lets more than one be chosen", () => {
    // Given / When / Then — "this device, or these devices, cost x"
    expect(fieldOf(anEditorFor(TOTALS_TAG), "devices").selector.select.multiple).toBe(
      true,
    );
  });

  it("offers nothing rather than breaking when the integration is absent", () => {
    // Given — a card being configured before HEA is set up
    const editor = anEditorFor(TOTALS_TAG, {}, aHass({ devices: null }));

    // When / Then
    expect(fieldOf(editor, "devices").selector.select.options).toEqual([]);
  });

  it("follows the device list as it changes", () => {
    // Given — a device added while the editor is open
    const editor = anEditorFor(TOTALS_TAG, {}, aHass({ devices: [TWO_DEVICES[0]] }));
    expect(fieldOf(editor, "devices").selector.select.options).toHaveLength(1);

    // When
    editor.hass = aHass({ devices: TWO_DEVICES });

    // Then
    expect(fieldOf(editor, "devices").selector.select.options).toHaveLength(2);
  });
});

describe("the devices card's own options", () => {
  it("offers the orderings the card supports, and no others", () => {
    // Given / When
    const sort = fieldOf(anEditorFor(DEVICES_TAG), "sort_by");

    // Then — the same four the card validates, so the editor cannot produce a
    // config the card would reject
    expect(sort.selector.select.options.map((option) => option.value)).toEqual([
      "actual_cost",
      "cost_at_grid_price",
      "cost_savings",
      "energy_used",
    ]);
  });

  it("is not offered on the totals card, which has nothing to sort", () => {
    // Given / When / Then
    expect(fieldOf(anEditorFor(TOTALS_TAG), "sort_by")).toBeUndefined();
  });
});

describe("reporting a change", () => {
  it("tells Home Assistant the new configuration", () => {
    // Given
    const editor = anEditorFor(TOTALS_TAG, { title: "Running costs" });
    const changed = vi.fn();
    editor.addEventListener("config-changed", changed);

    // When — the user picks two devices
    userEdits(editor, {
      title: "Running costs",
      devices: ["living_room_aircon", "kitchen_aircon"],
    });

    // Then
    expect(changed).toHaveBeenCalledTimes(1);
    expect(changed.mock.calls[0][0].detail.config).toEqual({
      type: `custom:${TOTALS_TAG}`,
      title: "Running costs",
      devices: ["living_room_aircon", "kitchen_aircon"],
    });
  });

  it("crosses the shadow boundary, or the dashboard never hears it", () => {
    // Given — Home Assistant listens on an ancestor, not on the editor
    const editor = anEditorFor(TOTALS_TAG);
    const heard = vi.fn();
    document.body.addEventListener("config-changed", heard);

    // When
    userEdits(editor, { title: "Costs" });

    // Then
    expect(heard).toHaveBeenCalledTimes(1);
  });

  it("drops a field the user cleared instead of writing an empty one", () => {
    // Given — a card whose title the user has just deleted
    const editor = anEditorFor(TOTALS_TAG, { title: "Running costs" });
    const changed = vi.fn();
    editor.addEventListener("config-changed", changed);

    // When
    userEdits(editor, { title: "" });

    // Then — the yaml stays as small as what was actually chosen
    expect(changed.mock.calls[0][0].detail.config).toEqual({
      type: `custom:${TOTALS_TAG}`,
    });
  });

  it("treats choosing no devices as the whole house, not as an empty filter", () => {
    // Given — a card filtered to one device
    const editor = anEditorFor(TOTALS_TAG, { devices: ["living_room_aircon"] });
    const changed = vi.fn();
    editor.addEventListener("config-changed", changed);

    // When — the user unticks it
    userEdits(editor, { devices: [] });

    // Then — an empty list would show an empty card; absent means everything
    expect(changed.mock.calls[0][0].detail.config).toEqual({
      type: `custom:${TOTALS_TAG}`,
    });
  });
});
