/**
 * @vitest-environment happy-dom
 *
 * Every tariff plan, priced against what the meters recorded (HEA-255, ADR-0036).
 *
 * The pricing is the integration's (`plan_comparison.py`); what is tested here is
 * what the card makes of it: each plan's total, cheapest first, the household's
 * own plan marked, and how much more or less every other would have cost.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULTS as LABELS, fill, resetLabels } from "../hea-labels.js";
import { TAG, register } from "../hea-plans-card.js";
import { JULY, MAY, aHass, mountCard, settled, text } from "./doubles.js";

const FLAT = {
  id: "flat",
  name: "Flat rate",
  current: true,
  energy: 31.42,
  export_credit: 4.1,
  daily_charges: 13.5,
  total: 40.82,
};
const NIGHT = {
  id: "night",
  name: "Night saver",
  current: false,
  energy: 24.06,
  export_credit: 3.28,
  daily_charges: 9,
  total: 29.78,
};
const PEAKY = {
  id: "peaky",
  name: "Peak and off-peak",
  current: false,
  energy: 38.9,
  export_credit: 4.92,
  daily_charges: 12,
  total: 45.98,
};

const COMPARED = {
  hours: 720,
  days: 30,
  imported_kwh: 134.27,
  exported_kwh: 82,
  plans: [FLAT, NIGHT, PEAKY],
};

/** Answers the card's requests as the integration does. */
const answering = (comparison = COMPARED) =>
  vi.fn(async ({ type }) => {
    if (type === "home_energy_advisor/compare_plans") return comparison;
    if (type === "frontend/get_translations") return { resources: {} };
    throw new Error(`unexpected ${type}`);
  });

const aHome = (comparison) => aHass({ callWS: answering(comparison) });

const figure = (card, key) =>
  card.shadowRoot.querySelector(`[data-figure="${key}"]`)?.textContent;

const order = (card) =>
  [...card.shadowRoot.querySelectorAll("[data-plan]")].map((row) => row.dataset.plan);

beforeEach(() => {
  resetLabels();
  register();
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("registration", () => {
  it("is registered, and offers itself in the card picker", () => {
    expect(customElements.get(TAG)).toBeDefined();
    expect(globalThis.customCards.some((card) => card.type === TAG)).toBe(true);
  });
});

describe("the comparison", () => {
  it("asks the integration to price every plan over the period shown", async () => {
    // Given / When
    const hass = aHome();
    const card = mountCard(TAG, hass);
    await settled(expect, card);

    // Then
    expect(hass.callWS).toHaveBeenCalledWith({
      type: "home_energy_advisor/compare_plans",
      start_time: MAY.toISOString(),
      end_time: JULY.toISOString(),
    });
  });

  it("lists every plan, cheapest first, with its total", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(order(card)).toEqual(["night", "flat", "peaky"]);
    expect(figure(card, "total:night")).toBe("€29.78");
    expect(figure(card, "total:flat")).toBe("€40.82");
    expect(figure(card, "total:peaky")).toBe("€45.98");
  });

  it("marks the household's own plan and the cheapest", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    const row = (id) => card.shadowRoot.querySelector(`[data-plan="${id}"]`);
    expect(row("flat").textContent).toContain(LABELS.plans_your_plan);
    expect(row("night").textContent).toContain(LABELS.plans_cheapest);
    expect(row("peaky").textContent).not.toContain(LABELS.plans_cheapest);
  });

  it("says how much less or more every other plan would have cost", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - a saving reads as good news, a dearer plan as bad
    const night = card.shadowRoot.querySelector('[data-figure="difference:night"]');
    expect(night.textContent).toBe(fill(LABELS.plans_less, { amount: "€11.04" }));
    expect(night.classList.contains("gain")).toBe(true);
    const peaky = card.shadowRoot.querySelector('[data-figure="difference:peaky"]');
    expect(peaky.textContent).toBe(fill(LABELS.plans_more, { amount: "€5.16" }));
    expect(peaky.classList.contains("loss")).toBe(true);
    expect(figure(card, "difference:flat")).toBeUndefined();
  });

  it("shows what each total is made of", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - export credited against the energy, and the daily charges added
    expect(figure(card, "energy:night")).toBe("€24.06");
    expect(figure(card, "export:night")).toBe("-€3.28");
    expect(figure(card, "daily:night")).toBe("€9.00");
  });

  it("says what the comparison assumes", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(text(card)).toContain(LABELS.plans_note);
  });
});

describe("what it cannot compare", () => {
  it("tells a household with no plans how to add one", async () => {
    // Given / When
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [] }));
    await settled(expect, card, "empty");

    // Then
    expect(text(card)).toContain(LABELS.no_plans);
  });

  it("says when the meters recorded nothing in the period", async () => {
    // Given / When - a period before the meters were recorded
    const card = mountCard(TAG, aHome({ ...COMPARED, hours: 0 }));
    await settled(expect, card);

    // Then - the daily charges alone would otherwise read as a real comparison
    expect(text(card)).toContain(LABELS.plans_no_readings);
  });

  it("names a plan that does not price every hour, without a figure", async () => {
    // Given - only an entry edited outside its form can hold one
    const gappy = { id: "gappy", name: "Half a plan", current: false, incomplete: true };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, gappy] }));
    await settled(expect, card);

    // Then - listed last, said why, and never ranked
    expect(order(card)).toEqual(["flat", "gappy"]);
    const row = card.shadowRoot.querySelector('[data-plan="gappy"]');
    expect(row.textContent).toContain(LABELS.plans_incomplete);
    expect(figure(card, "total:gappy")).toBeUndefined();
  });

  it("asks for the household's own plan when none is marked", async () => {
    // Given - no plan marked as the one the household is on
    const unmarked = [FLAT, NIGHT].map((plan) => ({ ...plan, current: false }));
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: unmarked }));
    await settled(expect, card);

    // Then - ranked, but compared with nothing
    expect(order(card)).toEqual(["night", "flat"]);
    expect(figure(card, "difference:night")).toBeUndefined();
    expect(text(card)).toContain(LABELS.plans_no_current);
  });

  it("says so when the comparison cannot be loaded", async () => {
    // Given - an integration too old to have the comparison
    const hass = aHass({
      callWS: vi.fn(async ({ type }) => {
        if (type === "frontend/get_translations") return { resources: {} };
        throw new Error("Unknown command.");
      }),
    });

    // When
    const card = mountCard(TAG, hass);

    // Then
    await settled(expect, card, "error");
  });
});
