/**
 * @vitest-environment happy-dom
 *
 * Every tracked device for the picked period, ordered by what it cost - the
 * "which device costs most" answer, finally sortable (HEA-50).
 *
 * The lifecycle it shares with the totals card is covered by that card's suite;
 * what is tested here is the table: its ordering, its totals row, and the fact
 * that a device name is the household's own text and must be escaped.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULTS as LABELS } from "../hea-labels.js";

const RANGE_COLUMN_LABEL = LABELS.range_column;
import { TAG, register } from "../hea-devices-card.js";
import {
  aDeviceRow,
  aHass,
  anEnergyCollection,
  boundsFor,
  bucketsFor,
  JULY,
  MAY,
  mountCard,
  settled,
  text,
} from "./doubles.js";

/** Three devices whose costs deliberately do not share an order with savings. */
const THREE_DEVICES = [
  aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"),
  aDeviceRow("fine_meter_aircon", "Fine Meter Aircon"),
  aDeviceRow("untracked_energy_devices", "Untracked Energy Devices", true),
];

const THREE_RESPONSE = {
  // energy, actual, at grid price → saved is the difference
  ...bucketsFor("slow_poll_aircon", 38.6, 0.11, 5.78), // saved 5.67
  ...bucketsFor("fine_meter_aircon", 12.0, 3.0, 4.0), // saved 1.00
  ...bucketsFor("untracked_energy_devices", 100, 1.5, 9.5), // saved 8.00
};

/** The window the picker announces as the one to compare against. */
const COMPARE_WINDOW = {
  startCompare: new Date(2026, 2, 20),
  endCompare: new Date(2026, 4, 15),
  compareMode: "previous",
};

/** A date inside that window, so a bucket dated here lands in the earlier one. */
const EARLIER = new Date(2026, 3, 1);

/**
 * The same three devices with an earlier self apiece.
 *
 * The three changes deliberately disagree in sign - -1.20, +2.00, +1.00 - so a
 * total of +1.80 cannot be produced by summing magnitudes, by taking any one
 * row, or by comparing the totals against each other in the wrong order.
 */
const COMPARED_RESPONSE = {
  ...THREE_RESPONSE,
  "sensor.slow_poll_aircon_actual_cost": [
    { start: MAY.getTime(), change: 0.11 },
    { start: EARLIER.getTime(), change: 1.31 },
  ],
  "sensor.fine_meter_aircon_actual_cost": [
    { start: MAY.getTime(), change: 3.0 },
    { start: EARLIER.getTime(), change: 1.0 },
  ],
  "sensor.untracked_energy_devices_actual_cost": [
    { start: MAY.getTime(), change: 1.5 },
    { start: EARLIER.getTime(), change: 0.5 },
  ],
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);

const rows = (card) =>
  [...card.shadowRoot.querySelectorAll("tbody tr")].map((row) =>
    [...row.querySelectorAll("th, td")].map((cell) => cell.textContent.trim()),
  );

const deviceOrder = (card) => rows(card).map(([name]) => name);

/** The totals row's cells as elements, since some of them carry a verdict. */
const totalCells = (card) => [
  ...card.shadowRoot.querySelectorAll("tfoot th, tfoot td"),
];

beforeEach(() => {
  document.body.replaceChildren();
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
});

describe("the card header", () => {
  it("names itself when no title is configured", async () => {
    // Given / When - added from the picker, with nothing filled in
    const card = mount(aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE }));
    await ready(card);

    // Then - so a table of figures beside other cards says what it ranks
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "Cost by device",
    );
  });
});

describe("the table", () => {
  it("lists every device with its energy, costs and saving", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the counterfactual and the saving beside what was actually paid,
    // and the unit price that ties the first two together
    expect(rows(card)).toContainEqual([
      "Slow Poll Aircon",
      "38.6 kWh",
      expect.stringMatching(/0[.,]11/),
      expect.stringMatching(/5[.,]78/),
      expect.stringMatching(/5[.,]67/),
      "0.28",
    ]);
  });

  it("orders devices by what they actually cost, dearest first", async () => {
    // Given - the question is "which device costs most"
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - 3.00, 1.50, 0.11
    expect(deviceOrder(card)).toEqual([
      "Fine Meter Aircon",
      "Untracked Energy Devices",
      "Slow Poll Aircon",
    ]);
  });

  it("orders by another figure when one is configured", async () => {
    // Given - "which device saved me most" is the same table, sorted differently
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass, { sort_by: "cost_savings" });
    await ready(card);

    // Then - 8.00, 5.67, 1.00
    expect(deviceOrder(card)).toEqual([
      "Untracked Energy Devices",
      "Slow Poll Aircon",
      "Fine Meter Aircon",
    ]);
  });

  it("rejects a sort nobody can satisfy", () => {
    // Given - a hand-edited dashboard yaml
    const card = document.createElement(TAG);

    // When / Then - the message names the options, since the editor shows it
    expect(() => card.setConfig({ type: `custom:${TAG}`, sort_by: "vibes" })).toThrow(
      /sort_by/,
    );
  });

  it("totals the devices it lists", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - 0.11 + 3.00 + 1.50 actual, against 5.78 + 4.00 + 9.50 at grid price
    const total = [...card.shadowRoot.querySelectorAll("tfoot th, tfoot td")].map(
      (cell) => cell.textContent.trim(),
    );
    expect(total[2]).toMatch(/4[.,]61/);
    expect(total[3]).toMatch(/19[.,]28/);
    expect(total[4]).toMatch(/14[.,]67/);
  });

  it("shows that there is more table to the right", async () => {
    // Given - too wide for a phone, the table scrolls sideways and said so
    // nowhere, so Saved and Rate did not exist as far as the reader was
    // concerned (HEA-103)
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - edge shadows, drawn by the scroll container itself so a table
    // that fits shows none and one scrolled to its end hides that end's
    const styles = card.shadowRoot.querySelector("style").textContent;
    expect(styles).toMatch(/\.scroll\s*\{[^}]*overflow-x:\s*auto/);
    expect(styles).toContain("radial-gradient");
  });

  it("names the rate's unit in the header, not on every row", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the unit is stated once. Repeated on eleven rows it made this the
    // widest column in the table and said nothing new after the first row.
    const headers = [...card.shadowRoot.querySelectorAll("thead th")].map(
      (cell) => cell.textContent.trim(),
    );
    expect(headers.at(-1)).toMatch(/c\/kWh/);
    expect(rows(card)[0][5]).not.toMatch(/kWh|€/);
  });

  it("keeps the unit out of the header's uppercasing", async () => {
    // Given - the header row is uppercased in CSS, which would turn c/kWh into
    // C/KWH and make a unit symbol wrong rather than merely shouty
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the unit is carried in its own element the stylesheet exempts
    const unit = card.shadowRoot.querySelector("thead .unit");
    expect(unit.textContent).toBe("c/kWh");
    expect(card.constructor.cardStyle).toMatch(/\.unit[^}]*text-transform:\s*none/);
  });

  it("shows what each device actually paid per kWh", async () => {
    // Given - three devices whose unit prices differ by two orders of magnitude
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the rate is cost over energy, per device. This is the figure that
    // exposed HEA-74: a device priced far under the tariff on a night when
    // every kWh came off the grid is visible here and nowhere else.
    const rates = Object.fromEntries(
      rows(card).map((row) => [row[0], row[5]]),
    );
    expect(rates["Fine Meter Aircon"]).toBe("25.0"); // 3.00 / 12.0 = 25c
    expect(rates["Slow Poll Aircon"]).toBe("0.28"); // 0.11 / 38.6 = 0.28c
    expect(rates["Untracked Energy Devices"]).toBe("1.5"); // 1.50 / 100 = 1.5c
  });

  it("totals the rate as the period's blended price, not a sum of rates", async () => {
    // Given - the same three devices
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - 4.61 over 150.6 kWh is 3.06 c/kWh. Adding the three rates would
    // give 26.78, which is not a price anything was bought at: a rate is a
    // ratio, and ratios do not sum.
    const total = [
      ...card.shadowRoot.querySelectorAll("tfoot th, tfoot td"),
    ].map((cell) => cell.textContent.trim());
    expect(total[5]).toBe("3.06");
    expect(total[5]).not.toBe("26.78");
  });

  it("shows no rate for a device that used no energy", async () => {
    // Given - a device that reported nothing over the period
    const hass = aHass({
      devices: [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")],
      response: bucketsFor("slow_poll_aircon", 0, 0, 0),
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - a dash, not a zero. Dividing by no energy yields no price, and
    // "free" is a different claim from "we cannot say"
    expect(rows(card)[0][5]).toBe("-");
  });

  it("marks a device whose saving is really a loss", async () => {
    // Given - battery arbitrage cost more than the grid would have (HEA-39)
    const hass = aHass({
      devices: [aDeviceRow("slow_poll_aircon", "Slow Poll Aircon")],
      response: bucketsFor("slow_poll_aircon", 10, 5, 3),
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then
    const saving = card.shadowRoot.querySelector("tbody tr .loss");
    expect(saving.textContent).toMatch(/-/);
  });

  it("escapes a device name, which is the household's own text", async () => {
    // Given - a device a user named awkwardly
    const hass = aHass({
      devices: [aDeviceRow("slow_poll_aircon", "<img src=x onerror=alert(1)>")],
      response: bucketsFor("slow_poll_aircon", 1, 1, 1),
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - shown as text, never parsed as markup
    expect(card.shadowRoot.querySelector("tbody img")).toBe(null);
    expect(text(card)).toContain("<img src=x onerror=alert(1)>");
  });

  it("counts only the devices a filter names", async () => {
    // Given
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass, { devices: ["fine_meter_aircon"] });
    await ready(card);

    // Then
    expect(deviceOrder(card)).toEqual(["Fine Meter Aircon"]);
  });

  it("shows what each device's cost could honestly have been", async () => {
    // Given - a household that opted into per-device ranges. A counter reporting
    // every 30-90 minutes used that energy somewhere inside the span and nothing
    // says where, so the cost is knowable only to a range (ADR-0016).
    const hass = aHass({
      devices: THREE_DEVICES,
      response: {
        ...THREE_RESPONSE,
        ...boundsFor("slow_poll_aircon", 0.02, 0.4),
        ...boundsFor("fine_meter_aircon", 2.8, 3.1),
        ...boundsFor("untracked_energy_devices", 1.5, 1.5),
      },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - money, never a percentage: 0.02 to 0.40 on a cost of 0.11 is
    // +345 %, a number that says only that division happened (HEA-75)
    const ranges = Object.fromEntries(rows(card).map((row) => [row[0], row[3]]));
    expect(ranges["Slow Poll Aircon"]).toMatch(/0[.,]02.+0[.,]40/);
    expect(ranges["Fine Meter Aircon"]).toMatch(/2[.,]80.+3[.,]10/);
  });

  it("shows a single figure where there is no span to be uncertain about", async () => {
    // Given - the Untracked remainder is derived per interval from meters that
    // reported for it, so its floor and ceiling are its cost
    const hass = aHass({
      devices: THREE_DEVICES,
      response: {
        ...THREE_RESPONSE,
        ...boundsFor("slow_poll_aircon", 0.02, 0.4),
        ...boundsFor("fine_meter_aircon", 2.8, 3.1),
        ...boundsFor("untracked_energy_devices", 1.5, 1.5),
      },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - one amount, not "~€1.50" and not "€1.50 - €1.50"
    const ranges = Object.fromEntries(rows(card).map((row) => [row[0], row[3]]));
    expect(ranges["Untracked Energy Devices"]).toMatch(/^\D*1[.,]50$/);
  });

  it("drops the range column rather than half-filling it", async () => {
    // Given - one device bounded and two not, which is what a household sees
    // mid-rollout or with the per-device option off for some period of the range
    const hass = aHass({
      devices: THREE_DEVICES,
      response: { ...THREE_RESPONSE, ...boundsFor("slow_poll_aircon", 0.02, 0.4) },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - no column of dashes, and no invitation to compare a bounded device
    // with an unbounded one
    const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
      cell.textContent.trim(),
    );
    expect(headers).not.toContain(RANGE_COLUMN_LABEL);
  });

  it("adds a change column only when a comparison is asked for", async () => {
    // Given - comparison is off by default, which is the normal case
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the table is exactly as it was
    const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
      cell.textContent.trim(),
    );
    expect(headers).not.toContain(LABELS.change);
  });

  it("shows each device's change against the earlier period", async () => {
    // Given - the picker comparing against an earlier window. One bucket lands
    // in each, so the data layer separates them by which period it asked for
    const collection = anEnergyCollection();
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE, collection });
    const card = mount(hass);
    await ready(card);

    const may = new Date(2026, 4, 20);
    const april = new Date(2026, 3, 1);
    hass.callWS = vi.fn().mockResolvedValue({
      ...bucketsFor("slow_poll_aircon", 38.6, 0.11, 5.78, may),
      ...bucketsFor("fine_meter_aircon", 12.0, 3.0, 4.0, may),
      ...bucketsFor("untracked_energy_devices", 100, 1.5, 9.5, may),
      "sensor.slow_poll_aircon_actual_cost": [
        { start: may.getTime(), change: 0.11 },
        { start: april.getTime(), change: 1.31 },
      ],
    });

    // When
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });

    // Then - the aircon cost EUR 1.20 less than it did before, signed so the
    // direction needs no working out
    await vi.waitFor(() => {
      const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
        cell.textContent.trim(),
      );
      expect(headers).toContain(LABELS.change);
    });
    const byName = Object.fromEntries(rows(card).map((row) => [row[0], row]));
    expect(byName["Slow Poll Aircon"].join(" ")).toMatch(/[-−]\D*1[.,]20/);
  });

  it("colours a device's change by whether it is good news", async () => {
    // Given - the Change column derives from Paid, where down is good. The
    // column carries no `field`, so the table's existing loss rule - which
    // tests one - could never have reached it (HEA-99).
    const collection = anEnergyCollection();
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE, collection });
    const card = mount(hass);
    await ready(card);

    const may = new Date(2026, 4, 20);
    const april = new Date(2026, 3, 1);
    hass.callWS = vi.fn().mockResolvedValue({
      ...bucketsFor("slow_poll_aircon", 38.6, 0.11, 5.78, may),
      ...bucketsFor("fine_meter_aircon", 12.0, 3.0, 4.0, may),
      ...bucketsFor("untracked_energy_devices", 100, 1.5, 9.5, may),
      // The aircon spent less than before; the pump spent more.
      "sensor.slow_poll_aircon_actual_cost": [
        { start: may.getTime(), change: 0.11 },
        { start: april.getTime(), change: 1.31 },
      ],
      "sensor.fine_meter_aircon_actual_cost": [
        { start: may.getTime(), change: 3.0 },
        { start: april.getTime(), change: 1.0 },
      ],
    });

    // When
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });
    // Waiting on the Change column itself, not on the first green cell
    // anywhere: an absolute saving is green too now (HEA-102), so "something
    // is green" stopped meaning "the comparison has arrived" and this raced
    // ahead to assert against a table that had no Change column yet.
    await vi.waitFor(() => {
      const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
        cell.textContent.trim(),
      );
      expect(headers).toContain(LABELS.change);
    });

    // Then - the two rows disagree, in one column, on the same day
    const toneOf = (name) => {
      const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
        cell.textContent.trim(),
      );
      // Named rather than "the first cell carrying a verdict", for the same
      // reason. The leading device name is a `th`, so the `td` list is one short.
      const column = headers.indexOf(LABELS.change) - 1;
      const row = [...card.shadowRoot.querySelectorAll("tbody tr")].find((tr) =>
        tr.textContent.includes(name),
      );
      return [...row.querySelectorAll("td")][column].className;
    };
    expect(toneOf("Slow Poll Aircon")).toContain("gain");
    expect(toneOf("Fine Meter Aircon")).toContain("loss");
  });

  it("totals the change column instead of leaving it blank", async () => {
    // Given - the picker comparing against an earlier window, every device
    // carrying an earlier self
    const collection = anEnergyCollection();
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE, collection });
    const card = mount(hass);
    await ready(card);

    hass.callWS = vi.fn().mockResolvedValue(COMPARED_RESPONSE);

    // When
    collection.announce(MAY, JULY, COMPARE_WINDOW);

    // Then - 4.61 paid now against 2.81 then, so +1.80, which is exactly the
    // sum of the column above it. The totals card eight centimetres away has
    // always shown this figure; the table said "-", so one of the two was
    // wrong about whether a total change means anything (HEA-99)
    await vi.waitFor(() => {
      const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
        cell.textContent.trim(),
      );
      expect(headers).toContain(LABELS.change);
    });
    expect(totalCells(card)[3].textContent.trim()).toMatch(/\+\D*1[.,]80/);
  });

  it("colours the total change by whether it is good news", async () => {
    // Given - the same three devices, whose changes sum to more spent
    const collection = anEnergyCollection();
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE, collection });
    const card = mount(hass);
    await ready(card);

    hass.callWS = vi.fn().mockResolvedValue(COMPARED_RESPONSE);

    // When
    collection.announce(MAY, JULY, COMPARE_WINDOW);

    // Then - the totals row reads like the column above it rather than being
    // the one uncoloured figure in it. Spending more is bad news, whatever the
    // individual rows did
    await vi.waitFor(() =>
      expect(card.shadowRoot.querySelector("tfoot td.loss")).not.toBeNull(),
    );
    expect(totalCells(card)[3].className).toContain("loss");
  });

  it("colours a real saving as good news, row and total alike", async () => {
    // Given - the table marked a negative saving red and said nothing about a
    // positive one, so the absence of red meant either "fine" or "no rule
    // here" (HEA-102). THREE_RESPONSE saves on every device
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - 5.67 + 1.00 + 8.00 saved, green on the rows and on the total.
    // The device name is a `th`, so Saved is the fourth `td` of five
    const saved = [...card.shadowRoot.querySelectorAll("tbody tr")].map(
      (row) => [...row.querySelectorAll("td")][3],
    );
    expect(saved.every((cell) => cell.classList.contains("gain"))).toBe(true);
    expect(totalCells(card)[4].className).toContain("gain");
  });

  it("leaves the energy and the money uncoloured", async () => {
    // Given - only the saving has an honest direction. Using energy is neither
    // good nor bad, and spending is the bill rather than bad news
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - energy, paid and would-have-paid carry no verdict
    const [firstRow] = [...card.shadowRoot.querySelectorAll("tbody tr")];
    const cells = [...firstRow.querySelectorAll("td")];
    for (const index of [0, 1, 2]) {
      expect(cells[index].className, `column ${index}`).toBe("");
    }
  });

  it("colours a total saving below zero as the loss it is", async () => {
    // Given - a period the battery lost money on, so every device paid more
    // than the grid alone would have cost (HEA-39). The rule already reached
    // each row; the totals row was rendered with no class at all
    const hass = aHass({
      devices: THREE_DEVICES,
      response: {
        ...bucketsFor("slow_poll_aircon", 38.6, 5.78, 0.11),
        ...bucketsFor("fine_meter_aircon", 12.0, 4.0, 3.0),
        ...bucketsFor("untracked_energy_devices", 100, 9.5, 1.5),
      },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - 19.28 paid against 4.61 at grid price is a saving of -14.67, and
    // a negative saving must never read as a gain
    const saved = totalCells(card)[4];
    expect(saved.textContent.trim()).toMatch(/[-−]\D*14[.,]67/);
    expect(saved.className).toContain("loss");
  });

  it("reports a device with nothing in the earlier window as all increase", async () => {
    // Given - the comparison window holds no buckets at all for these devices,
    // because every bucket in the response is dated inside the current period
    const collection = anEnergyCollection();
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE, collection });
    const card = mount(hass);
    await ready(card);

    const may = new Date(2026, 4, 20);
    hass.callWS = vi.fn().mockResolvedValue(THREE_RESPONSE);

    // When
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });

    // Then - the whole of this period's figure, as an increase against zero.
    //
    // Statistics cannot tell "the device did not run" from "the device was not
    // tracked yet", and the first is far the commoner - a seasonal heater, an
    // aircon in a cool month. Reporting the increase is right for that case and
    // overstates only for a device genuinely added since, which the household
    // is in a position to know
    await vi.waitFor(() => {
      const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
        cell.textContent.trim(),
      );
      expect(headers).toContain(LABELS.change);
    });
    const byName = Object.fromEntries(rows(card).map((row) => [row[0], row]));
    expect(byName["Slow Poll Aircon"].join(" ")).toMatch(/\+\D*0[.,]11/);
  });

  it("names the range column for the figure it brackets", async () => {
    // Given - a household with every device bounded, so the column is shown
    const hass = aHass({
      devices: THREE_DEVICES,
      response: {
        ...THREE_RESPONSE,
        ...boundsFor("slow_poll_aircon", 0.02, 0.4),
        ...boundsFor("fine_meter_aircon", 0.1, 0.9),
        ...boundsFor("untracked_energy_devices", 0.3, 1.1),
      },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the header says which of the three figures it is a range of. The
    // bounds bracket what was paid and nothing else, and a column headed simply
    // "Range" sitting between Paid and Would have paid could be read as either
    // (HEA-88)
    const headers = [...card.shadowRoot.querySelectorAll("thead th")].map((cell) =>
      cell.textContent.trim(),
    );
    expect(headers).toContain(RANGE_COLUMN_LABEL);
    expect(RANGE_COLUMN_LABEL).toContain(LABELS.paid);
    expect(headers).not.toContain("Range");
  });

  it("still states the household's range when no device carries one", async () => {
    // Given - per-device ranges are opt-in, but the whole-home range never is:
    // every install is honest by default (ADR-0016)
    const hass = aHass({
      devices: THREE_DEVICES,
      response: { ...THREE_RESPONSE, ...boundsFor("whole_home", 4.2, 5.9) },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - the disclosure survives the column being dropped, so a household is
    // never told nothing, and it says which figure it qualifies rather than
    // leaving "these figures" to cover all three (HEA-88)
    expect(text(card)).toMatch(/4[.,]20.+5[.,]90/);
    expect(text(card)).toMatch(/not a typical error/);
    expect(text(card)).toMatch(/What you paid could honestly sit between/);
    expect(text(card)).not.toMatch(/These figures could/);
  });

  it("says what the range is, so it is not read as an error bar", async () => {
    // Given - summing each delta's worst case assumes every device's energy
    // landed in its own dearest slice at once. That is an outer bound, not a
    // confidence interval, and must never read as "the error is 28 %"
    // (ADR-0016 decision 4).
    const hass = aHass({
      devices: THREE_DEVICES,
      response: {
        ...THREE_RESPONSE,
        ...boundsFor("slow_poll_aircon", 0.02, 0.4),
        ...boundsFor("fine_meter_aircon", 2.8, 3.1),
        ...boundsFor("untracked_energy_devices", 1.5, 1.5),
      },
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - and it names the column it explains, so the two are read together
    expect(text(card)).toMatch(/not a typical error/);
    expect(text(card)).toContain(LABELS.range_column);
  });

  it("says nothing about ranges on an integration too old to publish any", async () => {
    // Given - a dashboard resource can outrun the integration
    const hass = aHass({
      devices: THREE_DEVICES,
      response: THREE_RESPONSE,
      wholeHome: null,
    });

    // When
    const card = mount(hass);
    await ready(card);

    // Then - silence beats a range of zero, which would claim exactness
    expect(text(card)).not.toMatch(/typical error/);
  });

  it("grows its card size with the number of devices it shows", async () => {
    // Given - masonry lays out from this estimate, and a 15-device table is
    // nothing like the height of a one-device one
    const hass = aHass({ devices: THREE_DEVICES, response: THREE_RESPONSE });

    // When
    const card = mount(hass);
    await ready(card);

    // Then
    expect(card.getCardSize()).toBeGreaterThan(3);
  });
});
