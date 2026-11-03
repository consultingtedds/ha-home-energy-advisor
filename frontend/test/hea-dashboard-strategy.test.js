/**
 * @vitest-environment happy-dom
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  DASHBOARD_TAG,
  STRATEGY_TYPE,
  VIEW_TAG,
} from "../hea-dashboard-strategy.js";
import { DEFAULTS as LABELS } from "../hea-labels.js";
import { aDeviceRow, aGridOnlyRow, aHass } from "./doubles.js";

/** Every card in a generated view, however deeply a section nests it. */
const cardTypes = (view) =>
  (view.sections ?? []).flatMap((section) =>
    (section.cards ?? []).map((card) => card.type),
  );

/** Each section's cards, by type, in order. */
const layout = (view) =>
  view.sections.map((section) => section.cards.map((card) => card.type));

const footerCards = (view) => view.footer?.card?.cards?.map((c) => c.type) ?? [];

const generateDashboard = (hass) =>
  customElements.get(DASHBOARD_TAG).generate({ type: "custom:hea" }, hass);

const generateView = (hass) =>
  customElements.get(VIEW_TAG).generate({ type: "custom:hea" }, hass);

/** A household that has entered one tariff plan. */
const withAPlan = (hass) => {
  hass.callWS = vi.fn(async ({ type }) => {
    if (type === "home_energy_advisor/list_plans") {
      return { plans: [{ id: "flat", name: "Flat rate", current: true }] };
    }
    return { resources: {} };
  });
  return hass;
};

const aHomeOnTheGridAlone = () =>
  aHass({
    devices: [
      aGridOnlyRow("slow_poll_aircon", "Slow Poll Aircon"),
      aGridOnlyRow("untracked_energy_devices", "Untracked Energy Devices", true),
    ],
    wholeHome: aGridOnlyRow("whole_home", "Whole Home"),
  });

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

describe("registration", () => {
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
});

describe("the dashboard's tabs", () => {
  it("opens on a summary, with the devices behind it", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);

    // Then - the whole-home answers first, the per-device detail on a tab of
    // its own (HEA-257), each named in the household's language
    expect(views.map(({ path, title }) => [path, title])).toEqual([
      ["summary", LABELS.tab_summary],
      ["devices", LABELS.tab_devices],
    ]);
    for (const view of views) expect(view.icon).toMatch(/^mdi:/);
  });

  it("puts the totals across the summary, then when and where the cost went", async () => {
    // Given - a home with generation, so its installation card applies
    hass.states["sensor.whole_home_cost_savings"] = { state: "4.04", attributes: {} };

    // When
    const { views } = await generateDashboard(hass);
    const summary = views[0];

    // Then - the headline full width, the charts in two columns beneath it
    expect(layout(summary)).toEqual([
      ["custom:hea-totals-card"],
      ["custom:hea-cost-over-time-card", "custom:hea-installation-card"],
      ["custom:hea-distribution-card", "custom:hea-self-sufficiency-card"],
    ]);
    expect(summary.sections.map((section) => section.column_span)).toEqual([
      summary.max_columns,
      summary.max_columns / 2,
      summary.max_columns / 2,
    ]);
  });

  it("puts the device table across the devices tab, with its charts beneath", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);
    const devices = views[1];

    // Then - the table has the width Paid and its add-ons need (ADR-0029)
    expect(layout(devices)).toEqual([
      ["custom:hea-devices-card"],
      ["custom:hea-device-costs-card"],
      ["custom:hea-sources-card"],
    ]);
    expect(devices.sections[0].column_span).toBe(devices.max_columns);
  });

  it("adds a tariffs tab once a plan is entered", async () => {
    // Given / When
    const { views } = await generateDashboard(withAPlan(hass));

    // Then - the comparison on a tab of its own, after the others (HEA-255)
    const tariffs = views.at(-1);
    expect([tariffs.path, tariffs.title]).toEqual(["tariffs", LABELS.tab_tariffs]);
    expect(layout(tariffs)).toEqual([["custom:hea-plans-card"]]);
  });

  it("has no tariffs tab where no plan is entered", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);

    // Then - a tab that could only say there is nothing to compare is not offered
    expect(views.map((view) => view.path)).not.toContain("tariffs");
  });

  it("has no tariffs tab where the integration cannot say which plans there are", async () => {
    // Given - an integration from before plans existed
    hass.callWS = vi.fn(async ({ type }) => {
      if (type === "home_energy_advisor/list_plans") throw new Error("Unknown command.");
      return { resources: {} };
    });

    // When
    const { views } = await generateDashboard(hass);

    // Then - the rest as before, rather than no dashboard at all
    expect(views.map((view) => view.path)).toEqual(["summary", "devices"]);
  });

  it("leaves out the cards about sources on both tabs, for a home on the grid alone", async () => {
    // Given / When
    const { views } = await generateDashboard(aHomeOnTheGridAlone());

    // Then - a gauge that can only read nought and a breakdown that is all grid
    // say nothing the devices table does not (HEA-253)
    expect(views.map(layout)).toEqual([
      [["custom:hea-totals-card"], ["custom:hea-cost-over-time-card"], ["custom:hea-distribution-card"]],
      [["custom:hea-devices-card"], ["custom:hea-device-costs-card"]],
    ]);
  });

  it("pins the period picker and the filter on every tab", async () => {
    // Given / When
    const { views } = await generateDashboard(withAPlan(hass));

    // Then - the picker keys its period to the dashboard, not the tab, so a
    // period picked on one tab is still picked on the next
    for (const view of views) {
      expect(footerCards(view)).toEqual(["energy-date-selection", "custom:hea-filter-card"]);
    }
  });

  it("asks the picker to open its calendar upwards", async () => {
    // Given / When
    const { views } = await generateDashboard(hass);
    const picker = views[0].footer.card.cards.find(
      (card) => card.type === "energy-date-selection",
    );

    // Then - the card's own option, which it passes to the period selector.
    // Left at its default the calendar is drawn downwards from a control
    // already pinned to the bottom of the viewport, past the edge of a sticky
    // footer that never scrolls to reach it (HEA-115).
    expect(picker.vertical_opening_direction).toBe("up");
  });

  it("names no device anywhere in what it generates", async () => {
    // Given / When - a household whose devices have names the cards could have
    // been made to hardcode
    const generated = JSON.stringify(await generateDashboard(withAPlan(hass)));

    // Then - the cards enumerate the devices registry themselves, so adding a
    // device needs no dashboard edit. This is the whole reason a generated
    // dashboard is safe where the hand-listed one was not
    expect(generated).not.toContain("slow_poll_aircon");
    expect(generated).not.toContain("Slow Poll Aircon");
  });

  it("sets no card titles, so each card names itself in the household's language", async () => {
    // Given / When
    const { views } = await generateDashboard(withAPlan(hass));
    const cards = views.flatMap((view) => view.sections.flatMap((s) => s.cards));

    // Then - a title written here would be English on a Spanish install, where
    // an absent one falls back to the card's own translated default
    for (const card of cards.filter((c) => c.type.startsWith("custom:hea"))) {
      expect(card).not.toHaveProperty("title");
    }
  });

  it("tells a household tracking nothing yet, rather than drawing empty tabs", async () => {
    // Given - a fresh install: the integration is set up but no device is tracked
    const { views } = await generateDashboard(aHass({ devices: [] }));

    // When / Then - eight cards all saying "no data" reads as a fault; one
    // sentence reads as the instruction it is
    expect(views).toHaveLength(1);
    expect(cardTypes(views[0])).toEqual(["markdown"]);
    expect(views[0].sections[0].cards[0].content).toMatch(/tracked/i);
  });
});

describe("the single page, for a dashboard already in use", () => {
  it("carries every card the tabs do, on one page", async () => {
    // Given - the view strategy, which a household adds to a dashboard of their
    // own and which cannot hold tabs (HEA-257)
    hass.states["sensor.whole_home_cost_savings"] = { state: "4.04", attributes: {} };
    withAPlan(hass);

    // When
    const view = await generateView(hass);
    const { views } = await generateDashboard(hass);

    // Then - nothing a household had on that page goes missing on upgrade
    expect(new Set(cardTypes(view))).toEqual(new Set(views.flatMap(cardTypes)));
  });

  it("gives the summary and the device table the full width, first", async () => {
    // Given / When
    const view = await generateView(hass);

    // Then - the figures a household came for lead the page, and the table has
    // room for Paid and every add-on beside it on a large screen (ADR-0029).
    // Home Assistant stacks sections on a narrow one, so a phone is unchanged
    const [first, ...rest] = view.sections;
    expect(first.column_span).toBe(view.max_columns);
    expect(first.cards.map((card) => card.type)).toEqual([
      "custom:hea-totals-card",
      "custom:hea-devices-card",
    ]);
    expect(rest.map((section) => section.column_span)).toEqual([2, 2]);
    expect(layout({ sections: rest })).toEqual([
      ["custom:hea-cost-over-time-card", "custom:hea-sources-card"],
      [
        "custom:hea-device-costs-card",
        "custom:hea-distribution-card",
        "custom:hea-self-sufficiency-card",
      ],
    ]);
  });

  it("adds what the installation earned beside the gauge, for a home with one", async () => {
    // Given - a home with generation: its whole-home savings figure is enabled
    hass.states["sensor.whole_home_cost_savings"] = { state: "4.04", attributes: {} };

    // When
    const view = await generateView(hass);

    // Then - after the self-sufficiency gauge, the other whole-home answer
    expect(view.sections[2].cards.map((card) => card.type)).toEqual([
      "custom:hea-device-costs-card",
      "custom:hea-distribution-card",
      "custom:hea-self-sufficiency-card",
      "custom:hea-installation-card",
    ]);
  });

  it("leaves it out for a home on the grid alone", async () => {
    // Given - the default household: its savings figure was created disabled,
    // so it has no state (HEA-175)
    // When
    const view = await generateView(hass);

    // Then - a card that could only say there is nothing to show is not offered
    expect(cardTypes(view)).not.toContain("custom:hea-installation-card");
  });

  it("leaves out the cards about sources, for a home on the grid alone", async () => {
    // Given / When
    const view = await generateView(aHomeOnTheGridAlone());

    // Then
    expect(layout(view)).toEqual([
      ["custom:hea-totals-card", "custom:hea-devices-card"],
      ["custom:hea-cost-over-time-card"],
      ["custom:hea-device-costs-card", "custom:hea-distribution-card"],
    ]);
  });

  it("puts them back once the household has a second source", async () => {
    // Given - a battery added: its rows publish where their energy came from
    const withABattery = aHass({
      devices: [
        aDeviceRow("slow_poll_aircon", "Slow Poll Aircon", false, {
          energy_used: "sensor.slow_poll_aircon_energy_used",
          actual_cost: "sensor.slow_poll_aircon_actual_cost",
          energy_from_grid: "sensor.slow_poll_aircon_energy_from_grid",
          energy_from_battery: "sensor.slow_poll_aircon_energy_from_battery",
        }),
        aGridOnlyRow("battery_losses", "Battery Losses"),
      ],
    });

    // When
    const view = await generateView(withABattery);

    // Then - Battery Losses publishes no split of its own, and is not what
    // decides this
    expect(cardTypes(view)).toEqual(
      expect.arrayContaining(["custom:hea-sources-card", "custom:hea-self-sufficiency-card"]),
    );
  });

  it("adds the plan comparison at the end, full width, once a plan is entered", async () => {
    // Given / When
    const view = await generateView(withAPlan(hass));

    // Then - a section of its own after everything else (HEA-255)
    const last = view.sections.at(-1);
    expect(last.cards.map((card) => card.type)).toEqual(["custom:hea-plans-card"]);
    expect(last.column_span).toBe(view.max_columns);
  });

  it("pins the period picker and the filter in the view footer", async () => {
    // Given / When
    const view = await generateView(hass);

    // Then
    expect(footerCards(view)).toEqual(["energy-date-selection", "custom:hea-filter-card"]);
  });

  it("tells a household tracking nothing yet, rather than drawing empty cards", async () => {
    // Given / When
    const view = await generateView(aHass({ devices: [] }));

    // Then
    expect(cardTypes(view)).toEqual(["markdown"]);
  });
});
