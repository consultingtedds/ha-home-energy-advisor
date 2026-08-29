/**
 * @vitest-environment happy-dom
 *
 * Which part of the house the money went to (HEA-90).
 *
 * The arrangement - what sums to what, and where an unfiled device hangs - is
 * `hea-sankey-layout.js`'s and is tested there without a DOM. What is tested
 * here is the card: that it hands Home Assistant's own `ha-sankey-chart` the
 * layout as a property, coaxes that component into existence on a dashboard
 * that has never drawn one, formats its figures as money, and turns sideways on
 * a phone rather than squeezing four columns into a narrow screen.
 */

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { TAG, register } from "../hea-distribution-card.js";
import { DEFAULTS, resetLabels } from "../hea-labels.js";
import {
  aDeviceRow,
  aHass,
  bucketsFor,
  mountCard,
  placed,
  settled,
  sourcesFor,
} from "./doubles.js";

const LOUNGE = { areaId: "a-lounge", areaName: "Lounge", floorId: "f-up", floorName: "Upstairs" };
const GARAGE = { areaId: "a-garage", areaName: "Garage" };

const AIRCON = placed(aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"), LOUNGE);
const PUMP = placed(aDeviceRow("cloud_polled_pump", "Cloud Polled Pump"), GARAGE);

/** Aircon three euros in the lounge, pump one in the garage. */
const SPENT = {
  ...bucketsFor("slow_poll_aircon", 10, 3, 4),
  ...bucketsFor("cloud_polled_pump", 5, 1, 2),
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);
const chartOf = (card) => card.shadowRoot.querySelector("ha-sankey-chart");
const nodeOf = (card, id) => chartOf(card).data.nodes.find((node) => node.id === id);

const aHouse = (extra = {}) =>
  aHass({ devices: [AIRCON, PUMP], response: SPENT, ...extra });

beforeEach(() => {
  document.body.replaceChildren();
  resetLabels();
  // The card waits for a component Home Assistant loads lazily; a test that
  // never defines it would only ever see the "not loaded" message.
  if (!customElements.get("ha-sankey-chart")) {
    customElements.define("ha-sankey-chart", class extends HTMLElement {});
  }
});

afterEach(() => {
  delete globalThis.loadCardHelpers;
  vi.unstubAllGlobals();
});

describe("registration", () => {
  it("is registered, and offers itself in the card picker", () => {
    // Given / When / Then
    expect(customElements.get(TAG)).toBeDefined();
    expect(globalThis.customCards).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: TAG })]),
    );
  });

  it("registering twice does not throw, for a resource listed twice", () => {
    // Given / When / Then
    expect(() => register()).not.toThrow();
  });
});

describe("drawing with Home Assistant's component", () => {
  it("hands the chart the layout as a property, not as markup", async () => {
    // Given
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - an object cannot be expressed as an attribute (ADR-0013)
    expect(chartOf(card).data.nodes.length).toBeGreaterThan(0);
    expect(chartOf(card).data.links.length).toBeGreaterThan(0);
    expect(chartOf(card).hass).toBe(card._hass);
  });

  it("flows each room's cost up to the household", async () => {
    // Given
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then
    expect(nodeOf(card, "area_a-lounge").value).toBe(3);
    expect(nodeOf(card, "area_a-garage").value).toBe(1);
    expect(nodeOf(card, "household").value).toBe(4);
  });

  it("formats its figures as money rather than raw euros to fourteen places", async () => {
    // Given - an allocated share divides into a long recurring decimal
    const card = mount(aHouse());
    await ready(card);

    // When
    const formatted = chartOf(card).valueFormatter(3.14159);

    // Then
    expect(formatted).toMatch(/3\.14/);
    expect(formatted).not.toMatch(/3\.1415/);
  });

  it("asks Home Assistant to load the Sankey component when it is missing", async () => {
    // Given - `ha-sankey-chart` is a different element from `ha-chart-base`,
    // so the statistics-graph nudge would not bring it in
    const createCardElement = vi.fn().mockResolvedValue(document.createElement("div"));
    globalThis.loadCardHelpers = vi.fn().mockResolvedValue({ createCardElement });
    const card = document.createElement(TAG);
    card.setConfig({ type: `custom:${TAG}` });
    card._chartReady = false;

    // When
    document.body.append(card);

    // Then
    await vi.waitFor(() => expect(globalThis.loadCardHelpers).toHaveBeenCalled());
    expect(createCardElement).toHaveBeenCalledWith(
      expect.objectContaining({ type: "energy-sankey" }),
    );
  });

  it("says so when that component never loaded", async () => {
    // Given
    const card = mount(aHouse());
    await ready(card);

    // When
    card._chartReady = false;
    card._render();

    // Then - an empty box would leave the user with nothing to act on
    expect(card.shadowRoot.textContent).toMatch(/chart component is not loaded/i);
    expect(chartOf(card)).toBe(null);
  });
});

describe("three levels on a narrow screen", () => {
  const withScreen = (matches) =>
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches, addEventListener() {}, removeEventListener() {} }),
    );

  it("turns sideways on a phone, as the Energy Dashboard does", async () => {
    // Given
    withScreen(true);

    // When
    const card = mount(aHouse());
    await ready(card);

    // Then
    expect(chartOf(card).vertical).toBe(true);
  });

  it("stays across the page on a wide screen", async () => {
    // Given
    withScreen(false);

    // When
    const card = mount(aHouse());
    await ready(card);

    // Then
    expect(chartOf(card).vertical).toBe(false);
  });

  it("lets a household override the choice either way", async () => {
    // Given - a wide screen, so the override is doing the work
    withScreen(false);

    // When
    const card = mount(aHouse(), { layout: "vertical" });
    await ready(card);

    // Then
    expect(chartOf(card).vertical).toBe(true);
  });

  it("keeps it horizontal when asked to, even on a phone", async () => {
    // Given
    withScreen(true);

    // When
    const card = mount(aHouse(), { layout: "horizontal" });
    await ready(card);

    // Then
    expect(chartOf(card).vertical).toBe(false);
  });

  it("stays horizontal where the browser cannot answer the question", async () => {
    // Given - `matchMedia` is not universally present, and an unreadable
    // screen size is not a reason to refuse to draw
    vi.stubGlobal("matchMedia", undefined);

    // When
    const card = mount(aHouse());
    await ready(card);

    // Then
    expect(chartOf(card).vertical).toBe(false);
  });
});

describe("periods with nothing to draw", () => {
  it("says so when the period cost nothing at all", async () => {
    // Given
    const empty = {
      ...bucketsFor("slow_poll_aircon", 0, 0, 0),
      ...bucketsFor("cloud_polled_pump", 0, 0, 0),
    };

    // When
    const card = mount(aHouse({ response: empty }));
    await ready(card);

    // Then - a lone household node with nothing flowing out of it is worse
    expect(card.shadowRoot.textContent).toMatch(/no cost recorded/i);
    expect(chartOf(card)).toBe(null);
  });
});

describe("measuring by energy instead of cost", () => {
  it("draws energy, and opens with where it came from", async () => {
    // Given - the pump ran hard on free solar, so a cost diagram reduces it to
    // a hairline; energy is the view that shows it
    const hass = aHass({
      devices: [AIRCON, PUMP],
      response: {
        ...SPENT,
        ...sourcesFor("slow_poll_aircon", 4, 6, 0),
        ...sourcesFor("cloud_polled_pump", 0, 5, 0),
      },
    });

    // When
    const card = mount(hass, { metric: "energy" });
    await ready(card);

    // Then
    expect(nodeOf(card, "device_cloud_polled_pump").value).toBe(5);
    expect(nodeOf(card, "source_generation").value).toBe(11);
    expect(nodeOf(card, "source_grid").value).toBe(4);
    expect(nodeOf(card, "household").value).toBe(15);
  });

  it("colours the sources from the household's own theme", async () => {
    // Given - a dashboard that has themed its Energy Dashboard. The layout
    // names Home Assistant's tokens and only the card can read one, so this is
    // the half that would silently keep painting a literal (HEA-93).
    //
    // Set on the card rather than on the document: happy-dom does not resolve
    // an *inherited* custom property through `getComputedStyle`, which is how a
    // real theme would reach it. What is under test is that the card reads the
    // token at all; the inheriting is the browser's job, not ours.
    const hass = aHass({
      devices: [AIRCON, PUMP],
      response: {
        ...SPENT,
        ...sourcesFor("slow_poll_aircon", 4, 6, 2),
        ...sourcesFor("cloud_polled_pump", 0, 5, 0),
      },
    });

    // When
    const card = document.createElement(TAG);
    card.style.setProperty("--energy-battery-out-color", "#123456");
    card.setConfig({
      type: `custom:${TAG}`,
      collection_key: "energy_hea-costs",
      metric: "energy",
    });
    document.body.append(card);
    card.hass = hass;
    await ready(card);

    // Then - the theme's colour, not the fallback it would otherwise take
    expect(nodeOf(card, "source_battery").color).toBe("#123456");
    expect(nodeOf(card, "source_battery").color).not.toBe("#4db6ac");
  });

  it("says no energy was recorded, where the cost view says no cost", async () => {
    // Given - the same card, the same empty period, two different claims. One
    // diagram measuring money and one measuring energy cannot honestly share a
    // sentence about what was missing (HEA-93)
    const empty = {
      ...bucketsFor("slow_poll_aircon", 0, 0, 0),
      ...bucketsFor("cloud_polled_pump", 0, 0, 0),
    };

    // When
    const card = mount(aHouse({ response: empty }), { metric: "energy" });
    await ready(card);

    // Then
    expect(card.shadowRoot.textContent).toMatch(/no energy recorded/i);
    expect(card.shadowRoot.textContent).not.toMatch(/no cost recorded/i);
  });

  it("has no source column on cost, where generation is priced at zero", async () => {
    // Given / When
    const card = mount(aHouse());
    await ready(card);

    // Then
    expect(nodeOf(card, "source_grid")).toBeUndefined();
  });

  it("labels the figures in kWh rather than in money", async () => {
    // Given
    const card = mount(aHouse(), { metric: "energy" });
    await ready(card);

    // When
    const formatted = chartOf(card).valueFormatter(5);

    // Then - a diagram of energy that hovers euros is simply wrong
    expect(formatted).toMatch(/kWh/i);
    expect(formatted).not.toMatch(/€/);
  });

  it("falls back to cost when handed a measure it does not have", async () => {
    // Given - a hand-edited YAML config should not blank the card
    const card = mount(aHouse(), { metric: "bananas" });

    // When
    await ready(card);

    // Then
    expect(nodeOf(card, "household").value).toBe(4);
  });
});

describe("the words around the diagram", () => {
  it("titles itself from the household's own vocabulary", async () => {
    // Given / When
    const card = mount(aHouse());
    await ready(card);

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      DEFAULTS.title_distribution,
    );
  });

  it("does not head a diagram of energy as though it showed cost", async () => {
    // Given / When
    const card = mount(aHouse(), { metric: "energy" });
    await ready(card);

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      DEFAULTS.title_distribution_energy,
    );
  });

  it("takes a configured title over its own", async () => {
    // Given / When
    const card = mount(aHouse(), { title: "Where it went" });
    await ready(card);

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "Where it went",
    );
  });

  it("names the household in the household's language", async () => {
    // Given - Spanish, fetched the way every other card fetches its words
    const hass = aHouse();
    hass.locale = { language: "es" };
    hass.callWS = vi.fn().mockImplementation(({ type }) =>
      type === "frontend/get_translations"
        ? Promise.resolve({
            resources: { "component.home_energy_advisor.common.card_household": "Casa" },
          })
        : Promise.resolve(SPENT),
    );

    // When
    const card = mount(hass);
    await ready(card);

    // Then
    expect(nodeOf(card, "household").label).toBe("Casa");
  });
});
