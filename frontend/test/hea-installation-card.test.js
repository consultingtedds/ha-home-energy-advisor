/**
 * @vitest-environment happy-dom
 *
 * What the installation earned, as a card (HEA-241, ADR-0034).
 *
 * The arithmetic is `hea-installation.test.js`'s. What is tested here is what
 * the card makes of it: the three parts and their total for the period, each
 * part only where it applies, the Energy Dashboard asked for its export
 * statistic, and the whole home shown whatever the page is filtered to.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetFilters, setFilter } from "../hea-filter.js";
import { DEFAULTS as LABELS, resetLabels } from "../hea-labels.js";
import { TAG, register } from "../hea-installation-card.js";
import { MAY, aDeviceRow, aHass, mountCard, settled, text } from "./doubles.js";

const WHOLE_HOME = aDeviceRow("whole_home", "Whole Home", false, {
  cost_savings: "sensor.whole_home_cost_savings",
  battery_savings: "sensor.whole_home_battery_savings",
});
const PANELS_ONLY = aDeviceRow("whole_home", "Whole Home", false, {
  cost_savings: "sensor.whole_home_cost_savings",
});
const LOSSES = aDeviceRow("battery_losses", "Battery Losses", false, {
  actual_cost: "sensor.battery_losses_actual_cost",
});
const AIRCON = {
  ...aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"),
  area_id: "a7f3",
  area_name: "Office",
};

const day = (change) => [{ start: MAY.getTime(), change }];

/** The reference home's 28 October: 4.04 saved, 1.124 by the battery, 0.225 exported. */
const MEASURED_DAY = {
  "sensor.whole_home_cost_savings": day(4.04),
  "sensor.whole_home_battery_savings": day(1.124),
  "sensor.battery_losses_actual_cost": day(0),
  "sensor.grid_export_compensation": day(0.225),
};

const EXPORTING = {
  energy_sources: [
    {
      type: "grid",
      stat_energy_from: "sensor.grid_import",
      stat_energy_to: "sensor.grid_export",
      stat_compensation: null,
      entity_energy_price_export: "sensor.export_price",
    },
  ],
};
const CREATED = {
  cost_sensors: { "sensor.grid_export": "sensor.grid_export_compensation" },
};

/** Answers each request the card makes the way Home Assistant does. */
const answering = ({ buckets = MEASURED_DAY, prefs = EXPORTING, info = CREATED } = {}) =>
  vi.fn(async ({ type }) => {
    if (type === "energy/get_prefs") {
      if (prefs instanceof Error) throw prefs;
      return prefs;
    }
    if (type === "energy/info") return info;
    if (type === "recorder/statistics_during_period") return buckets;
    if (type === "frontend/get_translations") return { resources: {} };
    throw new Error(`unexpected ${type}`);
  });

/** A home whose figures are enabled: a disabled sensor has no state at all. */
const aHome = ({ wholeHome = WHOLE_HOME, devices = [AIRCON, LOSSES], ...answers } = {}) => {
  const hass = aHass({ devices, wholeHome, callWS: answering(answers) });
  for (const id of Object.values(wholeHome.statistics)) {
    hass.states[id] = { state: "1.0", attributes: {} };
  }
  return hass;
};

const figure = (card, key) =>
  card.shadowRoot.querySelector(`[data-figure="${key}"]`)?.textContent;

beforeEach(() => {
  resetLabels();
  register();
});

afterEach(() => {
  document.body.innerHTML = "";
  resetFilters();
});

describe("registration", () => {
  it("is registered, and offers itself in the card picker", () => {
    expect(customElements.get(TAG)).toBeDefined();
    expect(globalThis.customCards.some((card) => card.type === TAG)).toBe(true);
  });
});

describe("the three parts", () => {
  it("shows a measured day's parts and their total", async () => {
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    expect(figure(card, "generationSaved")).toBe("€2.92");
    expect(figure(card, "batterySaved")).toBe("€1.12");
    expect(figure(card, "exportsEarned")).toBe("€0.23");
    expect(figure(card, "total")).toBe("€4.27");
  });

  it("names each part, and says what the figures cover", async () => {
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    expect(text(card)).toContain(LABELS.generation_saved);
    expect(text(card)).toContain(LABELS.battery_saved);
    expect(text(card)).toContain(LABELS.exports_earned);
    expect(text(card)).toContain(LABELS.installation_note);
  });

  it("asks the Energy Dashboard where its exports are recorded", async () => {
    const hass = aHome();
    const card = mountCard(TAG, hass);
    await settled(expect, card);

    const request = hass.callWS.mock.calls
      .map(([message]) => message)
      .find((message) => message.type === "recorder/statistics_during_period");
    expect(request.statistic_ids).toEqual([
      "sensor.whole_home_cost_savings",
      "sensor.whole_home_battery_savings",
      "sensor.battery_losses_actual_cost",
      "sensor.grid_export_compensation",
    ]);
  });

  it("marks a battery that cost more than it saved", async () => {
    const card = mountCard(
      TAG,
      aHome({
        buckets: {
          ...MEASURED_DAY,
          "sensor.whole_home_battery_savings": day(0.1),
          "sensor.battery_losses_actual_cost": day(0.35),
        },
      }),
    );
    await settled(expect, card);

    const battery = card.shadowRoot.querySelector('[data-figure="batterySaved"]');
    expect(battery.textContent).toBe("-€0.25");
    expect(battery.classList.contains("loss")).toBe(true);
  });
});

describe("only what applies", () => {
  it("has no battery part for a home with panels and no battery", async () => {
    const card = mountCard(TAG, aHome({ wholeHome: PANELS_ONLY, devices: [AIRCON] }));
    await settled(expect, card);

    expect(figure(card, "batterySaved")).toBeUndefined();
    expect(figure(card, "generationSaved")).toBe("€4.04");
    expect(text(card)).not.toContain(LABELS.battery_saved);
  });

  it("has no exports part where the Energy Dashboard records none", async () => {
    const card = mountCard(TAG, aHome({ info: { cost_sensors: {} } }));
    await settled(expect, card);

    expect(figure(card, "exportsEarned")).toBeUndefined();
    expect(figure(card, "total")).toBe("€4.04");
  });

  it("still shows the rest when the Energy Dashboard cannot be read", async () => {
    const card = mountCard(TAG, aHome({ prefs: new Error("no energy dashboard") }));
    await settled(expect, card);

    expect(figure(card, "exportsEarned")).toBeUndefined();
    expect(figure(card, "generationSaved")).toBe("€2.92");
  });

  it("says there is nothing to show for a home on the grid alone", async () => {
    // Its savings figure is created disabled, so it has no state (HEA-175)
    const hass = aHass({
      devices: [AIRCON],
      wholeHome: PANELS_ONLY,
      callWS: answering(),
    });
    const card = mountCard(TAG, hass);
    await settled(expect, card, "empty");

    expect(text(card)).toContain(LABELS.no_installation);
  });
});

describe("the whole home", () => {
  it("is shown whatever the page is narrowed to", async () => {
    setFilter("energy_hea-costs", { kind: "area", id: "a7f3" });
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    expect(figure(card, "generationSaved")).toBe("€2.92");
  });
});
