/**
 * @vitest-environment happy-dom
 *
 * The control that narrows the whole page (HEA-95).
 *
 * The period picker's shape one layer down (ADR-0012): this card owns the
 * selection and every other card follows it, so "what did the aircon cost this
 * week" is asked once rather than configured five times.
 *
 * It draws its options from the device rows the HEA-55 sensor publishes, so a
 * household that adds a room gets it in the list without touching a dashboard.
 * Nothing here names a room, a floor or a label.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { EVERYTHING, filterFor, resetFilters, setFilter } from "../hea-filter.js";
import { TAG, register } from "../hea-filter-card.js";
import { DEFAULTS as LABELS, resetLabels } from "../hea-labels.js";
import { aDeviceRow, aHass, mountCard, placed } from "./doubles.js";

const KEY = "energy_hea-costs";

const LOUNGE = { areaId: "a-lounge", areaName: "Lounge", floorId: "f-up", floorName: "Upstairs" };
const KITCHEN = { areaId: "a-kitchen", areaName: "Kitchen", floorId: "f-up", floorName: "Upstairs" };
const GARAGE = { areaId: "a-garage", areaName: "Garage" };

const AIRCON = placed(aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"), LOUNGE);
const KETTLE = placed(aDeviceRow("fine_meter_kettle", "Fine Meter Kettle"), KITCHEN);
const PUMP = placed(aDeviceRow("cloud_polled_pump", "Cloud Polled Pump"), GARAGE);
const UNTRACKED = aDeviceRow("untracked_energy_devices", "Untracked", true);

const HOUSE = [AIRCON, KETTLE, PUMP, UNTRACKED];

const mount = (hass, config) => mountCard(TAG, hass, config);
const selectOf = (card) => card.shadowRoot.querySelector("select");
const valuesOf = (card) =>
  [...selectOf(card).querySelectorAll("option")].map((o) => o.value);
const groupsOf = (card) =>
  [...selectOf(card).querySelectorAll("optgroup")].map((g) => g.label);
const namesIn = (card, group) =>
  [...selectOf(card).querySelectorAll("optgroup")]
    .filter((g) => g.label === group)
    .flatMap((g) => [...g.querySelectorAll("option")].map((o) => o.textContent));

/** Act as the browser does when the household picks something. */
const choose = (card, value) => {
  const select = selectOf(card);
  select.value = value;
  select.dispatchEvent(new Event("change"));
};

beforeEach(() => {
  document.body.replaceChildren();
  resetFilters();
  resetLabels();
});

describe("registration", () => {
  it("is registered, and offers itself in the card picker", () => {
    // Given / When / Then
    expect(customElements.get(TAG)).toBeDefined();
    expect(globalThis.customCards).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: TAG })]),
    );
  });

  it("survives the resource being added to a dashboard twice", () => {
    // Given / When / Then
    expect(() => register()).not.toThrow();
  });

  it("offers an editor and a height, so it behaves in a Lovelace view", () => {
    // Given / When
    const card = mount(aHass({ devices: HOUSE }));

    // Then - one row of control, unlike the cards it filters, and an editor so
    // Home Assistant does not drop the user into raw yaml (HEA-73)
    expect(customElements.get(TAG).getConfigElement()).toBeInstanceOf(HTMLElement);
    expect(card.getCardSize()).toBe(1);
  });
});

describe("the options it offers", () => {
  it("builds them from the devices sensor, naming nothing itself", async () => {
    // Given - a household that adds a room should get it in the list without
    // touching a dashboard, which is the rule every card here follows
    const card = mount(aHass({ devices: HOUSE }));

    // Then - groupings first, then the individual devices to drill into
    expect(groupsOf(card)).toEqual([
      LABELS.filter_rooms,
      LABELS.filter_floors,
      LABELS.filter_devices,
    ]);
    // Alphabetical, and no unfiled bucket: every *tracked* device here has a
    // room, and the Untracked remainder is not counted when building the list
    expect(namesIn(card, LABELS.filter_rooms)).toEqual([
      "Garage",
      "Kitchen",
      "Lounge",
    ]);
    // The garage is in no floor, so that group does have one
    expect(namesIn(card, LABELS.filter_floors)).toEqual([
      "Upstairs",
      LABELS.filter_unfiled,
    ]);
  });

  it("opens on everything, which is what an untouched page shows", async () => {
    // Given / When
    const card = mount(aHass({ devices: HOUSE }));

    // Then
    expect(valuesOf(card)[0]).toBe("all:");
    expect(selectOf(card).value).toBe("all:");
  });

  it("names a room once, however many devices are in it", async () => {
    // Given - two devices in the lounge
    const second = placed(aDeviceRow("lounge_lamp", "Lounge Lamp"), LOUNGE);

    // When
    const card = mount(aHass({ devices: [AIRCON, second, PUMP] }));

    // Then
    expect(namesIn(card, LABELS.filter_rooms)).toEqual(["Garage", "Lounge"]);
  });

  it("offers the unfiled bucket only where something is unfiled", async () => {
    // Given - the garage is in no floor, but every device is in a room
    const card = mount(aHass({ devices: [AIRCON, KETTLE, PUMP] }));

    // Then - a floor bucket, because the garage has none; no room bucket,
    // because nothing is roomless. An always-present empty bucket would read
    // as a house with unfiled devices it does not have
    expect(namesIn(card, LABELS.filter_floors)).toContain(LABELS.filter_unfiled);
    expect(namesIn(card, LABELS.filter_rooms)).not.toContain(LABELS.filter_unfiled);
  });

  it("ignores the Untracked remainder when building the list", async () => {
    // Given - it is in no room and carries no label by definition, so counting
    // it would put an unfiled bucket on every household's card
    const card = mount(aHass({ devices: [AIRCON, KETTLE, UNTRACKED] }));

    // Then
    expect(namesIn(card, LABELS.filter_rooms)).not.toContain(LABELS.filter_unfiled);
  });

  it("offers every device by name, last, once a ranking has named one", async () => {
    // Given - the drill-down HEA-98 asks for: the chart already draws one
    // device correctly when it is the only one shown, and what was missing was
    // a way to say which. Last in the list, because it is the step *after* the
    // groupings rather than a peer of them
    const card = mount(aHass({ devices: HOUSE }));

    // Then - alphabetical, and the Untracked remainder is among them. It is
    // frequently the largest line in the house, and a device list naming every
    // device except that one would be a strange thing to offer
    expect(groupsOf(card).at(-1)).toBe(LABELS.filter_devices);
    expect(namesIn(card, LABELS.filter_devices)).toEqual([
      "Cloud Polled Pump",
      "Fine Meter Kettle",
      "Slow Poll Aircon",
      "Untracked",
    ]);
  });

  it("keeps the remainder out of the groupings while offering it as a device", async () => {
    // Given - naming it is unambiguous; filing it under a room is a claim
    // nobody can make for it
    const card = mount(aHass({ devices: [AIRCON, UNTRACKED] }));

    // Then
    expect(namesIn(card, LABELS.filter_rooms)).not.toContain(LABELS.filter_unfiled);
    expect(namesIn(card, LABELS.filter_devices)).toContain("Untracked");
  });

  it("offers no labels until the integration publishes them", async () => {
    // Given - labels arrive in a later integration version, and a card may run
    // against an instance that has not been updated. An empty Labels group
    // would read as a household with no labels rather than as a feature that
    // has not arrived
    const card = mount(aHass({ devices: HOUSE }));

    // Then
    expect(groupsOf(card)).not.toContain(LABELS.filter_labels);
  });

  it("offers the labels a household has actually used", async () => {
    // Given - one label on two devices, none on the third
    const labelled = [
      { ...AIRCON, labels: ["aircon"] },
      { ...KETTLE, labels: ["aircon", "kitchen_gear"] },
      PUMP,
    ];

    // When
    const card = mount(
      aHass({
        devices: labelled,
        labels: { aircon: "aircon", kitchen_gear: "kitchen gear" },
      }),
    );

    // Then - each named once, and no unfiled bucket: a device without labels
    // is not "unlabelled", it simply is not in any of them
    expect(namesIn(card, LABELS.filter_labels)).toEqual(["aircon", "kitchen gear"]);
  });

  it("shows what a label is called, not its id", async () => {
    // Given - a label whose id is not its name, which the reference instance
    // has: `lifetime_counter_plug` is called "high draw". Showing the id would put
    // an underscore in front of the household (HEA-95)
    const card = mount(
      aHass({
        devices: [{ ...AIRCON, labels: ["lifetime_counter_plug"] }, PUMP],
        labels: { lifetime_counter_plug: "high draw" },
      }),
    );

    // Then - the name is shown, and the id is what gets selected
    expect(namesIn(card, LABELS.filter_labels)).toEqual(["high draw"]);
    choose(card, "label:lifetime_counter_plug");
    expect(filterFor(KEY)).toEqual({ kind: "label", id: "lifetime_counter_plug" });
  });

  it("falls back to the id where the integration names no labels", async () => {
    // Given - a card newer than the instance it runs against, publishing rows
    // with labels but no names beside them. A blank option would be worse than
    // a slug
    const card = mount(aHass({ devices: [{ ...AIRCON, labels: ["aircon"] }, PUMP] }));

    // Then
    expect(namesIn(card, LABELS.filter_labels)).toEqual(["aircon"]);
  });
});

describe("leaving the control alone", () => {
  it("survives Home Assistant setting hass over and over", async () => {
    // Given - `hass` is set on every state change, many times a second on a
    // busy instance. Rebuilding the markup each time destroys the dropdown
    // underneath the household mid-selection, which made the card unusable
    // (HEA-95)
    const card = mount(aHass({ devices: HOUSE }));
    const select = selectOf(card);

    // When - nothing it shows has changed
    card.hass = aHass({ devices: HOUSE });
    card.hass = aHass({ devices: HOUSE });

    // Then - the very same element, so an open dropdown is still open
    expect(selectOf(card)).toBe(select);
  });

  it("rebuilds when a device arrives", async () => {
    // Given - a household that adds a device should see its room appear
    const card = mount(aHass({ devices: [AIRCON, PUMP] }));
    const select = selectOf(card);

    // When
    card.hass = aHass({ devices: HOUSE });

    // Then
    expect(selectOf(card)).not.toBe(select);
    expect(namesIn(card, LABELS.filter_rooms)).toContain("Kitchen");
  });

  it("rebuilds when a room is renamed", async () => {
    // Given - the name is the household's own text and may change without any
    // device arriving or leaving
    const card = mount(aHass({ devices: HOUSE }));

    // When
    const renamed = placed(aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"), {
      ...LOUNGE,
      areaName: "Snug",
    });
    card.hass = aHass({ devices: [renamed, KETTLE, PUMP, UNTRACKED] });

    // Then
    expect(namesIn(card, LABELS.filter_rooms)).toContain("Snug");
  });

  it("rebuilds when a device is renamed", async () => {
    // Given - a device's own name is now an option's text, so the control has
    // to notice it moving as well as its room's (HEA-98)
    const card = mount(aHass({ devices: HOUSE }));

    // When
    const renamed = placed(aDeviceRow("slow_poll_aircon", "one device's Aircon"), LOUNGE);
    card.hass = aHass({ devices: [renamed, KETTLE, PUMP, UNTRACKED] });

    // Then
    expect(namesIn(card, LABELS.filter_devices)).toContain("one device's Aircon");
  });
});

describe("choosing one", () => {
  it("narrows the page to a single device", async () => {
    // Given - the question asked once a ranking has said which device to look
    // at, answered by every card on the page rather than by a second control
    const card = mount(aHass({ devices: HOUSE }));

    // When
    choose(card, "device:slow_poll_aircon");

    // Then - the key, never the name: a household may rename a device
    expect(filterFor(KEY)).toEqual({ kind: "device", id: "slow_poll_aircon" });
  });

  it("narrows the page, not just itself", async () => {
    // Given
    const card = mount(aHass({ devices: HOUSE }));

    // When
    choose(card, "area:a-lounge");

    // Then - the selection lives on the page's shared store, which every card
    // sharing the collection key follows
    expect(filterFor(KEY)).toEqual({ kind: "area", id: "a-lounge" });
  });

  it("goes back to everything", async () => {
    // Given
    const card = mount(aHass({ devices: HOUSE }));
    choose(card, "area:a-lounge");

    // When
    choose(card, "all:");

    // Then
    expect(filterFor(KEY)).toEqual(EVERYTHING);
  });

  it("selects the unfiled bucket as a real choice, not as nothing", async () => {
    // Given - "devices in no room" is a question a household can ask, and it
    // has to be distinguishable from having asked nothing
    const card = mount(aHass({ devices: [AIRCON, aDeviceRow("odd", "Odd One")] }));

    // When
    choose(card, "area:");

    // Then
    expect(filterFor(KEY)).toEqual({ kind: "area", id: null });
  });

  it("follows a selection made somewhere else", async () => {
    // Given - two filter cards on one page, or a page restored with a
    // selection already made
    const card = mount(aHass({ devices: HOUSE }));

    // When
    setFilter(KEY, { kind: "area", id: "a-kitchen" });

    // Then
    await vi.waitFor(() => expect(selectOf(card).value).toBe("area:a-kitchen"));
  });

  it("keeps two dashboards apart", async () => {
    // Given - a card on another dashboard, with its own collection
    const card = mount(aHass({ devices: HOUSE }), {
      collection_key: "energy_other",
    });

    // When
    choose(card, "area:a-lounge");

    // Then
    expect(filterFor("energy_other")).toEqual({ kind: "area", id: "a-lounge" });
    expect(filterFor(KEY)).toEqual(EVERYTHING);
  });
});

describe("when there is nothing to filter", () => {
  it("says so rather than offering an empty control", async () => {
    // Given - HEA installed but no devices tracked yet
    const card = mount(aHass({ devices: [] }));

    // Then
    expect(selectOf(card)).toBe(null);
    expect(card.shadowRoot.textContent).toContain(LABELS.no_devices);
  });
});
