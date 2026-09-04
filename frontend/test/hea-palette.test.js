/**
 * @vitest-environment happy-dom
 *
 * One colour per device, meaning the device (HEA-101).
 *
 * Reported filtering the testing view to the aircons: one was blue on the
 * device-costs chart and yellow on the Sankey, and another the other way
 * round. Both cards indexed the palette by a device's *position in that card's
 * own list*, and the two lists are ordered differently - one by what was paid,
 * the other by key with zero-valued devices dropped. So position 0 named a
 * different device in each.
 *
 * What is tested here is that a colour follows the device rather than its
 * place: across orderings, across filters, and across the two cards that draw
 * devices at all.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { TAG as COSTS_TAG } from "../hea-device-costs-card.js";
import { TAG as SANKEY_TAG } from "../hea-distribution-card.js";
import { resetFilters, setFilter } from "../hea-filter.js";
import { coloursFor, PALETTE, SECOND_LAP, SLOTS } from "../hea-palette.js";
import {
  aDeviceRow,
  aHass,
  bucketsFor,
  mountCard,
  placed,
  settled,
} from "./doubles.js";

const KITCHEN = { areaId: "a-kitchen", areaName: "Kitchen" };

const AIRCON = placed(aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"), KITCHEN);
const PUMP = placed(aDeviceRow("cloud_polled_pump", "Cloud Polled Pump"), KITCHEN);
const LAMP = placed(aDeviceRow("bright_lamp", "Bright Lamp"), KITCHEN);
const UNTRACKED = aDeviceRow("untracked_energy_devices", "Untracked", true);

/** The pump cost most, so the two cards rank it differently from key order. */
const SPENT = {
  ...bucketsFor("slow_poll_aircon", 10, 1, 2),
  ...bucketsFor("cloud_polled_pump", 20, 9, 11),
  ...bucketsFor("bright_lamp", 5, 3, 4),
  ...bucketsFor("untracked_energy_devices", 5, 1, 1),
};

beforeEach(() => {
  document.body.replaceChildren();
  resetFilters();
  // Both components Home Assistant loads lazily; without them the cards render
  // their "not loaded" message and there is nothing to compare.
  for (const tag of ["ha-chart-base", "ha-sankey-chart"]) {
    if (!customElements.get(tag)) {
      customElements.define(tag, class extends HTMLElement {});
    }
  }
});

describe("assigning the colours", () => {
  it("gives a device the same colour whatever order it arrives in", () => {
    // Given - the two cards walk their devices in different orders, which is
    // the whole cause of the mismatch
    const forwards = coloursFor([AIRCON, PUMP, LAMP]);
    const backwards = coloursFor([LAMP, PUMP, AIRCON]);

    // Then
    for (const key of ["slow_poll_aircon", "cloud_polled_pump", "bright_lamp"]) {
      expect(forwards.get(key)).toBe(backwards.get(key));
    }
  });

  it("answers for the set it is given, which is why callers pass the whole one", () => {
    // Given - this is deliberately *not* filter-invariant on its own: a colour
    // is a position in the household's device set, so handing it a subset
    // renumbers that subset. The stability comes from every caller passing the
    // whole list, which is the contract the cards are tested against below
    const whole = coloursFor([AIRCON, PUMP, LAMP]);
    const subset = coloursFor([PUMP]);

    // Then - a caller who filtered first would get a different answer, and
    // that is the mistake this helper cannot prevent for itself
    expect(subset.get("cloud_polled_pump")).not.toBe(whole.get("cloud_polled_pump"));
  });

  it("leaves the Untracked remainder out of the palette", () => {
    // Given - it is not a device, and colouring it like one invites a reader to
    // hunt for an appliance that does not exist. Counting it would also shift
    // every real device along by one
    const colours = coloursFor([UNTRACKED, AIRCON]);

    // Then
    expect(colours.has("untracked_energy_devices")).toBe(false);
    expect(colours.get("slow_poll_aircon")).toBe(PALETTE[0]);
  });

  it("answers for a card that has no devices yet", () => {
    // Given / When / Then - a card constructed before its first `hass`, or a
    // dashboard placed before the integration is set up. Neither is an error
    // worth failing a whole view over
    expect(coloursFor(undefined).size).toBe(0);
    expect(coloursFor([]).size).toBe(0);
  });

  it("orders by the key itself, not by the reader's language", () => {
    // Given - this ordering is never read; it is what makes a colour the same
    // everywhere. A locale-aware sort would make the assignment depend on the
    // browser's language, so one household could see one set of colours in
    // English and another in Spanish
    const devices = [
      aDeviceRow("a_zebra", "Zebra"),
      aDeviceRow("b_apple", "Apple"),
    ];

    // When / Then - keyed on the slug, so the display names do not decide it
    expect(coloursFor(devices).get("a_zebra")).toBe(PALETTE[0]);
    expect(coloursFor(devices).get("b_apple")).toBe(PALETTE[1]);
  });

  /** As many devices as there are slots across every lap. */
  const manyDevices = (count) =>
    Array.from({ length: count }, (_, index) =>
      aDeviceRow(`device_${String(index).padStart(2, "0")}`, `Device ${index}`),
    );

  it("gives a second lap of devices colours of their own", () => {
    // Given - fourteen tracked devices on the reference instance, and eight
    // hues. Before HEA-105 the ninth device was handed byte-for-byte the hex
    // the first already had, so filtering to one floor drew two pairs that
    // could not be told apart at all
    const colours = coloursFor(manyDevices(SLOTS));

    // Then - every device has a colour, and no two share one
    expect(colours.size).toBe(SLOTS);
    expect(new Set(colours.values()).size).toBe(SLOTS);
  });

  it("leaves the first lap exactly as it was", () => {
    // Given - households have already learned these. A fix for the wrap that
    // repainted the eight devices below it would be a worse change than the
    // bug, and every screenshot and memory of the dashboard would be wrong
    const colours = coloursFor(manyDevices(SLOTS));

    // Then
    PALETTE.forEach((hue, index) => {
      expect(colours.get(`device_${String(index).padStart(2, "0")}`)).toBe(hue);
    });
  });

  it("cycles again once every lap is spent", () => {
    // Given - the palette does not grow without limit. Past sixteen a
    // household has two devices sharing, and cycling keeps that predictable
    // rather than arbitrary, which is the best available answer
    const colours = coloursFor(manyDevices(SLOTS + 1));

    // Then - the seventeenth wears the first one's colour again
    expect(colours.get(`device_${String(SLOTS).padStart(2, "0")}`)).toBe(PALETTE[0]);
    expect(new Set(colours.values()).size).toBe(SLOTS);
  });

  it("never repeats a hue within a lap", () => {
    // Given - the second lap is the first rotated into the gaps beside it, so
    // a rotation that happened to land on a hue already in use would reproduce
    // the defect one lap along instead of fixing it
    expect(new Set([...PALETTE, ...SECOND_LAP]).size).toBe(SLOTS);
  });
});

describe("under the page filter", () => {
  const swatchFor = (card, name) =>
    card.shadowRoot
      .querySelector("ha-chart-base")
      .options.legend.data.find((entry) => entry.name === name).itemStyle.color;

  it("keeps a device's colour when its neighbours are filtered away", async () => {
    // Given - the whole house on the page
    const devices = [AIRCON, PUMP, LAMP, UNTRACKED];
    const whole = mountCard(COSTS_TAG, aHass({ devices, response: SPENT }), {
      layout: "vertical",
    });
    await settled(expect, whole);
    const before = swatchFor(whole, "Cloud Polled Pump");

    // When - the page is narrowed to the kitchen, which the pump is in
    document.body.replaceChildren();
    setFilter("energy_hea-costs", { kind: "area", id: "a-kitchen" });
    const filtered = mountCard(COSTS_TAG, aHass({ devices, response: SPENT }), {
      layout: "vertical",
    });
    await settled(expect, filtered);

    // Then - the same colour. A card colouring by position in what it is
    // drawing would renumber every device the filter left behind
    expect(swatchFor(filtered, "Cloud Polled Pump")).toBe(before);
  });
});

describe("the two cards that draw devices", () => {
  it("agree on what colour a device is", async () => {
    // Given - the reported defect, in one assertion: the cost chart ranks by
    // what was paid, the Sankey walks key order and drops zero-valued rows, so
    // before this they disagreed on every device whose rank differed from its
    // position (HEA-101)
    const devices = [AIRCON, PUMP, LAMP, UNTRACKED];
    const costs = mountCard(COSTS_TAG, aHass({ devices, response: SPENT }), {
      layout: "vertical",
    });
    await settled(expect, costs);
    const sankey = mountCard(
      SANKEY_TAG,
      aHass({ devices, response: SPENT }),
      { metric: "cost" },
    );
    await settled(expect, sankey);

    // When - each card's own idea of a device's colour
    const chart = costs.shadowRoot.querySelector("ha-chart-base");
    const legend = Object.fromEntries(
      chart.options.legend.data
        .filter((entry) => entry.id !== "earlier-period")
        .map((entry) => [entry.name, entry.itemStyle.color]),
    );
    const nodes = sankey.shadowRoot.querySelector("ha-sankey-chart").data.nodes;
    const flows = Object.fromEntries(
      nodes
        .filter((node) => String(node.id).startsWith("device_"))
        .map((node) => [node.label, node.color]),
    );

    // Then - every device the Sankey drew wears the colour the chart gave it
    expect(Object.keys(flows).length).toBeGreaterThan(1);
    for (const [name, colour] of Object.entries(flows)) {
      expect(legend[name], `${name} disagrees between the two cards`).toBe(colour);
    }
  });
});
