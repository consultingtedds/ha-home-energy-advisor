/**
 * @vitest-environment happy-dom
 */

import { beforeEach, describe, expect, it } from "vitest";

import {
  DASHBOARD_TAG,
  STRATEGY_TYPE,
  VIEW_TAG,
} from "../hea-dashboard-strategy.js";
import { aDeviceRow, aHass } from "./doubles.js";

/** Every card in a generated view, however deeply a section nests it. */
const cardTypes = (view) =>
  (view.sections ?? []).flatMap((section) =>
    (section.cards ?? []).map((card) => card.type),
  );

const footerCards = (view) => view.footer?.card?.cards?.map((c) => c.type) ?? [];

const generateDashboard = (hass) =>
  customElements.get(DASHBOARD_TAG).generate({ type: "custom:hea" }, hass);

const generateView = (hass) =>
  customElements.get(VIEW_TAG).generate({ type: "custom:hea" }, hass);

describe("the dashboard strategy", () => {
  let hass;

  beforeEach(() => {
    hass = aHass({
      devices: [
        aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"),
        aDeviceRow("cloud_polled_pump", "Cloud Polled Pump"),
        aDeviceRow("untracked_energy_devices", "Untracked Energy Devices", true),
      ],
    });
  });

  it("registers as both a dashboard and a view strategy", () => {
    // Given / When / Then - the dashboard is what Add dashboard offers; the view
    // is what goes onto a dashboard the household already has
    expect(customElements.get(DASHBOARD_TAG)).toBeDefined();
    expect(customElements.get(VIEW_TAG)).toBeDefined();
  });

  it("offers itself in Home Assistant's Add dashboard dialog", () => {
    // Given / When - the registry that dialog reads
    const entry = globalThis.customStrategies.find(
      (candidate) => candidate.type === STRATEGY_TYPE,
    );

    // Then - only `strategyType: "dashboard"` is listed there, and the dialog
    // renders `name` and `description` with no thumbnail of its own
    expect(entry).toMatchObject({
      type: STRATEGY_TYPE,
      strategyType: "dashboard",
    });
    expect(entry.name).toBeTruthy();
    expect(entry.description).toBeTruthy();
  });

  it("builds one view carrying the whole card family", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);

    // Then - every card the family ships, so a household that picks this gets
    // the dashboard the cards were built for rather than a starting point
    expect(views).toHaveLength(1);
    expect(cardTypes(views[0])).toEqual(
      expect.arrayContaining([
        "custom:hea-totals-card",
        "custom:hea-devices-card",
        "custom:hea-device-costs-card",
        "custom:hea-cost-over-time-card",
        "custom:hea-sources-card",
        "custom:hea-distribution-card",
        "custom:hea-self-sufficiency-card",
      ]),
    );
  });

  it("pins the period picker and the filter in the view footer", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);

    // Then - both are controls for the whole page, so they stay put while it
    // scrolls; the picker is Home Assistant's own, which is what every card
    // subscribes to rather than owning a date range
    expect(footerCards(views[0])).toEqual([
      "energy-date-selection",
      "custom:hea-filter-card",
    ]);
  });

  it("names no device anywhere in what it generates", async () => {
    // Given / When - a household whose devices have names the cards could have
    // been made to hardcode
    const generated = JSON.stringify(await generateDashboard(hass));

    // Then - the cards enumerate the devices registry themselves, so adding a
    // device needs no dashboard edit. This is the whole reason a generated
    // dashboard is safe where the hand-listed one was not
    expect(generated).not.toContain("slow_poll_aircon");
    expect(generated).not.toContain("Slow Poll Aircon");
  });

  it("sets no card titles, so each card names itself in the household's language", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);
    const cards = views[0].sections.flatMap((section) => section.cards);

    // Then - a title written here would be English on a Spanish install, where
    // an absent one falls back to the card's own translated default
    for (const card of cards.filter((c) => c.type.startsWith("custom:hea"))) {
      expect(card).not.toHaveProperty("title");
    }
  });

  it("tells a household tracking nothing yet, rather than drawing empty cards", async () => {
    // Given - a fresh install: the integration is set up but no device is tracked
    const { views } = await generateDashboard(aHass({ devices: [] }));

    // When / Then - eight cards all saying "no data" reads as a fault; one
    // sentence reads as the instruction it is
    expect(cardTypes(views[0])).toEqual(["markdown"]);
    expect(views[0].sections[0].cards[0].content).toMatch(/tracked/i);
  });

  it("fills in the create dialog, so nothing is left for the household to name", async () => {
    // Given / When - what Home Assistant asks a dashboard strategy for before
    // it opens the title/icon/url dialog
    const suggestions = await customElements
      .get(DASHBOARD_TAG)
      .getCreateSuggestions(hass);

    // Then - both fields the dialog offers. Without these it opens empty and a
    // household has to invent a name and a url for something we already named
    expect(suggestions.title).toBe("Home Energy Advisor");
    expect(suggestions.icon).toMatch(/^mdi:/);
  });

  it("suggests a title Home Assistant can turn into a valid url", async () => {
    // Given - the dialog derives the url path by slugifying the suggested title
    const { title } = await customElements
      .get(DASHBOARD_TAG)
      .getCreateSuggestions(hass);

    // When / Then - Home Assistant rejects a single-word url path, so a
    // one-word title would be prefixed "dashboard-" behind the household's back
    expect(title.trim().split(/\s+/).length).toBeGreaterThan(1);
  });

  it("offers no config editor, having nothing to configure", () => {
    // Given / When / Then - the strategy takes no options; without this Home
    // Assistant offers a YAML editor for a config that is two lines and fixed
    expect(customElements.get(DASHBOARD_TAG).noEditor).toBe(true);
  });

  it("leaves regeneration on Home Assistant's default registries", () => {
    // Given / When / Then - the built-in strategies set this to [], which means
    // never regenerating. The layout depends on the device list, so a household
    // adding their first device would be left looking at the empty state until
    // they reloaded. The default already watches entities, devices, areas and
    // floors, which is exactly what this reads
    const strategy = customElements.get(DASHBOARD_TAG);
    expect(strategy.registryDependencies).toBeUndefined();
  });

  it("generates the same view standalone, for a dashboard already in use", async () => {
    // Given / When - the view strategy, which has no picker in Home Assistant's
    // UI but resolves fine when written into a view by hand
    const view = await generateView(hass);
    const { views } = await generateDashboard(hass);

    // Then - one definition of what an HEA page is, not two that drift
    expect(view).toEqual(views[0]);
  });
});
