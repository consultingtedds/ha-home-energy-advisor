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

import { formatDateTime, formatMoney, localeFrom } from "../hea-format.js";
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
  rates: {
    prices: [
      { name: "Peak", import: 0.31, export: null },
      { name: "Off-peak", import: 0.09, export: null },
    ],
    export: 0.04,
    daily_charge: 0.3,
    import_market: false,
    export_market: false,
  },
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
  card.shadowRoot.querySelector(`[data-figure="${key}"]`)?.firstChild?.textContent;

/** Whose favour a figure is shown in: "gain", "loss", or neither. */
const tone = (card, key) => {
  const cell = card.shadowRoot.querySelector(`[data-figure="${key}"]`);
  return ["gain", "loss"].find((name) => cell?.classList.contains(name));
};

const order = (card) =>
  [...card.shadowRoot.querySelectorAll("[data-plan]")].map((row) => row.dataset.plan);

/** The column heads, in order: the last head row, under the group headings. */
const heads = (card) =>
  [...card.shadowRoot.querySelectorAll("thead tr:last-child th")].map(
    (cell) => cell.textContent,
  );

/** Each line of a plan's Prices cell. */
const priceLines = (card, id) =>
  [...card.shadowRoot.querySelectorAll(`[data-plan="${id}"] td.prices > div`)].map(
    (line) => line.textContent.replaceAll(/\s+/g, " ").trim(),
  );

/** A screen of the width asked for, as the cards ask `matchMedia` for it. */
const onScreen = (narrow) =>
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: narrow,
      addEventListener() {},
      removeEventListener() {},
    }),
  );

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

    // Then - each a cost to the household, so each -€ in red (HEA-296)
    expect(order(card)).toEqual(["night", "flat", "peaky"]);
    expect(figure(card, "total:night")).toBe("-€29.78");
    expect(figure(card, "total:flat")).toBe("-€40.82");
    expect(figure(card, "total:peaky")).toBe("-€45.98");
    expect(tone(card, "total:night")).toBe("loss");
  });

  it("shows a plan in credit as money in the household's favour", async () => {
    // Given - export income beat the import cost and the daily charges
    const credit = { ...NIGHT, total: -0.03 };

    // When
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, credit] }));
    await settled(expect, card);

    // Then - "-€0.03" read as a loss, and it was the opposite (HEA-296)
    expect(figure(card, "total:night")).toBe("€0.03");
    expect(tone(card, "total:night")).toBe("gain");
  });

  it("marks the household's own plan and the cheapest, each in a colour of its own", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    const row = (id) => card.shadowRoot.querySelector(`[data-plan="${id}"]`);
    expect(row("flat").textContent).toContain(LABELS.plans_your_plan);
    expect(row("night").textContent).toContain(LABELS.plans_cheapest);
    expect(row("peaky").textContent).not.toContain(LABELS.plans_cheapest);
    expect(row("flat").querySelector(".tag.current")).not.toBeNull();
    expect(row("night").querySelector(".tag.cheapest")).not.toBeNull();
  });

  it("says by how much every other plan is cheaper or dearer, signed by whose favour", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - cheaper is in the household's favour, €, green; dearer -€, red;
    // the head says what it is against, so no word doubles the sign
    expect(figure(card, "difference:night")).toBe("€11.04");
    expect(tone(card, "difference:night")).toBe("gain");
    expect(figure(card, "difference:peaky")).toBe("-€5.16");
    expect(tone(card, "difference:peaky")).toBe("loss");
    expect(figure(card, "difference:flat")).toBeUndefined();
  });

  it("shows what each total is made of, what is paid against what is earned", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - what the household pays -€ in red, the export income € in green;
    // the total still takes the income off (HEA-277, HEA-296)
    expect(figure(card, "energy:night")).toBe("-€24.06");
    expect(tone(card, "energy:night")).toBe("loss");
    expect(figure(card, "export:night")).toBe("€3.28");
    expect(tone(card, "export:night")).toBe("gain");
    expect(figure(card, "daily:night")).toBe("-€9.00");
    expect(tone(card, "daily:night")).toBe("loss");
  });

  it("leaves a figure of nothing plain, in nobody's favour", async () => {
    // Given - a plan that pays nothing for export
    const unpaid = { ...NIGHT, export_credit: 0 };

    // When
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, unpaid] }));
    await settled(expect, card);

    // Then
    expect(figure(card, "export:night")).toBe("€0.00");
    expect(tone(card, "export:night")).toBeUndefined();
  });

  it("is a table whose heads say what each column is, like a bill", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - each part named for the money it is (HEA-277), in the order a bill
    // reads: what is paid, then what is earned, then the total (HEA-280)
    expect(heads(card)).toEqual([
      "Plan",
      "Prices",
      "Import cost",
      "Daily charges",
      "Export income",
      "Total",
      "vs current plan",
    ]);
    const flat = card.shadowRoot.querySelector('[data-plan="flat"]');
    expect(flat.textContent).toContain("Current plan");
  });

  it("puts what is paid and what is earned under a heading each, the earned one tinted", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - told apart by heading and tint, never by a minus or a coloured
    // figure: "Export income" read as a loss with one (HEA-280)
    const groups = [...card.shadowRoot.querySelectorAll("thead tr.groups th")].map(
      (cell) => [cell.textContent, cell.colSpan],
    );
    expect(groups).toEqual([
      ["", 2],
      ["What you pay", 2],
      ["What you earn", 1],
      ["", 2],
    ]);
    const exported = card.shadowRoot.querySelector('[data-figure="export:night"]');
    expect(exported.classList.contains("earn")).toBe(true);
    const imported = card.shadowRoot.querySelector('[data-figure="energy:night"]');
    expect(imported.classList.contains("earn")).toBe(false);
  });

  it("says what the comparison assumes", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(text(card)).toContain(LABELS.plans_note);
  });
});

describe("each plan's own prices", () => {
  it("lists each named price, then what export pays and the daily charge", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - one to a line, as an offer lists its periods, in the minor unit a
    // tariff is quoted in
    expect(priceLines(card, "night")).toEqual([
      "Peak 31.0 c/kWh",
      "Off-peak 9.0 c/kWh",
      "Export 4.0 c/kWh",
      "Daily €0.30/day",
    ]);
  });

  it("says a plan at the market is at the market, rather than naming a price", async () => {
    // Given - a plan importing and exporting at market price entities
    const market = {
      ...NIGHT,
      id: "market",
      name: "Wholesale",
      rates: { ...NIGHT.rates, prices: [], import_market: true, export_market: true },
    };

    // When
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, market] }));
    await settled(expect, card);

    // Then
    expect(priceLines(card, "market")).toEqual([
      "Market price",
      "Export Market price",
      "Daily €0.30/day",
    ]);
  });
});

describe("each plan without solar or battery", () => {
  // The same plans, as the comparison gives them for a house with an
  // installation: what each would have cost buying everything it used.
  const WITH_SOLAR = {
    ...COMPARED,
    plans: [
      { ...FLAT, without_installation: 70.15 },
      { ...NIGHT, without_installation: 61.4 },
      { ...PEAKY, without_installation: 79.2 },
    ],
  };

  it("adds a column beside Total, with what the installation saved on that plan", async () => {
    // Given / When
    const card = mountCard(TAG, aHome(WITH_SOLAR));
    await settled(expect, card);

    // Then - the figure a household weighs its panels and battery by, on every
    // plan (HEA-293, discussion 58)
    expect(heads(card)).toEqual([
      "Plan",
      "Prices",
      "Import cost",
      "Daily charges",
      "Export income",
      "Total",
      "Without solar or battery",
      "vs current plan",
    ]);
    const night = card.shadowRoot.querySelector('[data-figure="without:night"]');
    // A cost, so -€ in red; what the installation saved, in green (HEA-296)
    expect(night.firstChild.textContent).toBe("-€61.40");
    expect(night.classList.contains("loss")).toBe(true);
    expect(night.querySelector(".saves").textContent).toBe("saves €31.62");
    expect(night.querySelector(".saves").classList.contains("gain")).toBe(true);
  });

  it("says so where the installation cost more than it saved on a plan", async () => {
    // Given - a battery charged dear and discharged cheap can cost money
    const dearer = { ...COMPARED, plans: [{ ...FLAT, without_installation: 38.32 }] };

    // When
    const card = mountCard(TAG, aHome(dearer));
    await settled(expect, card);

    // Then - never a saving below nothing
    const flat = card.shadowRoot.querySelector('[data-figure="without:flat"]');
    expect(flat.querySelector(".saves").textContent).toBe("€2.50 more");
    expect(flat.querySelector(".saves").classList.contains("loss")).toBe(true);
  });

  it("has no such column for a house with neither", async () => {
    // Given / When - the comparison gives no figure, as for a grid-only house
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(heads(card)).not.toContain("Without solar or battery");
  });

  it("leaves it out on a phone, with the breakdown", async () => {
    // Given / When
    onScreen(true);
    const card = mountCard(TAG, aHome(WITH_SOLAR));
    await settled(expect, card);

    // Then
    expect(heads(card)).toEqual(["Plan", "Total", "vs current plan"]);
    vi.unstubAllGlobals();
  });
});

describe("the period's energy", () => {
  it("says once what the meters recorded, since it is the same for every plan", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - the kWh are the household's; only the prices are the plan's
    expect(card.shadowRoot.querySelector(".flows").textContent).toBe(
      "Imported 134.3 kWh and exported 82 kWh in this period.",
    );
  });

  it("says nothing of it where the meters recorded nothing", async () => {
    // Given / When
    const card = mountCard(TAG, aHome({ ...COMPARED, hours: 0 }));
    await settled(expect, card);

    // Then - the note saying there were no readings is the whole story
    expect(card.shadowRoot.querySelector(".flows")).toBeNull();
  });
});

describe("on a phone", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the plan, its total and the difference, and says where the rest went", async () => {
    // Given / When
    onScreen(true);
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then - six columns do not fit a phone; the breakdown is on a wider screen
    expect(heads(card)).toEqual(["Plan", "Total", "vs current plan"]);
    expect(card.shadowRoot.querySelector("thead tr.groups")).toBeNull();
    expect(text(card)).toContain(
      "Import cost, export income and daily charges are shown on a wider screen.",
    );
  });

  it("says nothing of a hidden breakdown on a wide screen", async () => {
    // Given / When
    onScreen(false);
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(text(card)).not.toContain("shown on a wider screen");
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

  it("names a market plan with no price in the period, without a figure", async () => {
    // Given - a wholesale plan whose price entity recorded nothing then
    const unpriced = { id: "spot", name: "Wholesale", current: false, no_price: true };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [unpriced, FLAT] }));
    await settled(expect, card);

    // Then - listed last, said why, and never ranked
    expect(order(card)).toEqual(["flat", "spot"]);
    const row = card.shadowRoot.querySelector('[data-plan="spot"]');
    expect(row.textContent).toContain(LABELS.plans_no_price);
    expect(figure(card, "total:spot")).toBeUndefined();
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

describe("plans priced from the market (HEA-260)", () => {
  // A wholesale plan: import at whatever the market charged.
  const SPOT = {
    id: "spot",
    name: "Wholesale",
    current: false,
    energy: 21.5,
    export_credit: 4.1,
    daily_charges: 33,
    total: 50.4,
    carried_hours: 0,
  };
  const JUNE = new Date(2026, 5, 3, 14);
  const locale = (card) => localeFrom(card._hass);

  it("says from when every plan is compared, and which plan's prices set it", async () => {
    // Given - the market plan's prices start partway through, so every plan is
    // compared from then (HEA-294)
    const card = mountCard(
      TAG,
      aHome({
        ...COMPARED,
        compared_from: JUNE.toISOString(),
        compared_from_plan: "Wholesale",
        plans: [FLAT, SPOT],
      }),
    );
    await settled(expect, card);

    // Then - once, above the table, not under the one plan
    const date = formatDateTime(JUNE, locale(card));
    expect(card.shadowRoot.querySelector(".span").textContent).toBe(
      `Compared from ${date}, when Wholesale's prices start, so every plan covers the same days.`,
    );
    const row = card.shadowRoot.querySelector('[data-plan="spot"]');
    expect(row.textContent).not.toContain("Compared from");
  });

  it("says when it is the grid meters' readings that set the start", async () => {
    // Given
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, compared_from: JUNE.toISOString(), compared_from_plan: null }),
    );
    await settled(expect, card);

    // Then
    const date = formatDateTime(JUNE, locale(card));
    expect(card.shadowRoot.querySelector(".span").textContent).toBe(
      `Compared from ${date}, when your grid meters' readings start, so every plan covers the same days.`,
    );
  });

  it("says nothing of a start when the whole period is compared", async () => {
    // Given / When
    const card = mountCard(TAG, aHome({ ...COMPARED, compared_from: null }));
    await settled(expect, card);

    // Then
    expect(card.shadowRoot.querySelector(".span")).toBeNull();
  });

  it("says how long was priced at a price carried over a gap", async () => {
    // Given
    const gappy = { ...SPOT, carried_hours: 2.5 };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, gappy] }));
    await settled(expect, card);

    // Then
    const row = card.shadowRoot.querySelector('[data-plan="spot"]');
    expect(row.textContent).toContain(fill(LABELS.plans_carried, { hours: "2.5" }));
  });

  it("says nothing of carried prices where there are none", async () => {
    // Given / When
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, SPOT] }));
    await settled(expect, card);

    // Then
    const row = card.shadowRoot.querySelector('[data-plan="spot"]').textContent;
    expect(row).not.toContain(fill(LABELS.plans_carried, { hours: "0" }));
  });

  it("says from when market prices were applied five minutes at a time", async () => {
    // Given - 5-minute statistics kept from partway through the period
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, five_minute_from: JUNE.toISOString(), plans: [FLAT, SPOT] }),
    );
    await settled(expect, card);

    // Then
    expect(text(card)).toContain(
      fill(LABELS.plans_market_from, { date: formatDateTime(JUNE, locale(card)) }),
    );
  });

  it("says market prices were applied hour by hour where nothing finer was kept", async () => {
    // Given / When
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, five_minute_from: null, plans: [FLAT, SPOT] }),
    );
    await settled(expect, card);

    // Then
    expect(text(card)).toContain(LABELS.plans_market_hourly);
  });

  it("says market prices were applied five minutes at a time throughout", async () => {
    // Given - 5-minute statistics kept from before the period began
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, five_minute_from: MAY.toISOString(), plans: [FLAT, SPOT] }),
    );
    await settled(expect, card);

    // Then
    expect(text(card)).toContain(LABELS.plans_market_five_minutes);
  });

  it("says nothing of resolution where no plan follows the market", async () => {
    // Given / When
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(text(card)).not.toContain(LABELS.plans_market_hourly);
  });
});

describe("export a capped plan did not pay (HEA-258)", () => {
  const row = (card, id) => card.shadowRoot.querySelector(`[data-plan="${id}"]`);
  const money = (card, amount) => formatMoney(amount, localeFrom(card._hass));

  it("says how much export the cap left unpaid", async () => {
    // Given - a generous feed-in price capped at the month's energy cost
    const capped = { ...NIGHT, export_unpaid: 6.4, export_carried: 0 };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, capped] }));
    await settled(expect, card);

    // Then
    expect(figure(card, "export-unpaid:night")).toBe(
      fill(LABELS.plans_export_unpaid, { amount: money(card, 6.4) }),
    );
  });

  it("says how much was carried forward and is not yet used", async () => {
    // Given
    const carried = { ...NIGHT, export_unpaid: 0, export_carried: 2.15 };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, carried] }));
    await settled(expect, card);

    // Then
    expect(figure(card, "export-carried:night")).toBe(
      fill(LABELS.plans_export_carried, { amount: money(card, 2.15) }),
    );
  });

  it("says nothing where the cap never bit, or the plan has none", async () => {
    // Given - one plan capped but within its cap, and one from an older
    // integration that sends neither figure
    const within = { ...NIGHT, export_unpaid: 0, export_carried: 0 };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [FLAT, within] }));
    await settled(expect, card);

    // Then
    for (const id of ["flat", "night"]) {
      expect(row(card, id).querySelector('[data-figure^="export-"]')).toBe(null);
    }
  });
});
