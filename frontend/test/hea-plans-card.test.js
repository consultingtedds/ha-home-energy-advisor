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

import {
  formatClockTime,
  formatDateTime,
  formatMoney,
  localeFrom,
} from "../hea-format.js";
import { DEFAULTS as LABELS, fill, resetLabels } from "../hea-labels.js";
import { TAG, register } from "../hea-plans-card.js";
import { verdictColour } from "../hea-verdict-scale.js";
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
    // Named for what it prices, which holds for any generation or battery,
    // over two head rows as the groups beside it are (HEA-300)
    expect(heads(card)).toEqual([
      "Plan",
      "Prices",
      "Import cost",
      "Daily charges",
      "Export income",
      "Total",
      "from the grid",
      "vs current plan",
    ]);
    const groups = [...card.shadowRoot.querySelectorAll("thead tr.groups th")].map(
      (cell) => cell.textContent,
    );
    expect(groups).toEqual(["", "What you pay", "What you earn", "", "Buying everything", ""]);
    const night = card.shadowRoot.querySelector('[data-figure="without:night"]');
    // A cost, so -€ in red; what the installation saved, in green (HEA-296),
    // saying whose saving it is so it never reads as a saving without it
    expect(night.firstChild.textContent).toBe("-€61.40");
    expect(night.classList.contains("loss")).toBe(true);
    expect(night.querySelector(".saves").textContent).toBe(
      "your installation saves you €31.62",
    );
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
    expect(flat.querySelector(".saves").textContent).toBe(
      "your installation costs you €2.50 more",
    );
    expect(flat.querySelector(".saves").classList.contains("loss")).toBe(true);
  });

  it("has no such column for a house with neither", async () => {
    // Given / When - the comparison gives no figure, as for a grid-only house
    const card = mountCard(TAG, aHome());
    await settled(expect, card);

    // Then
    expect(heads(card)).not.toContain("from the grid");
    expect(text(card)).not.toContain("Buying everything");
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

  it("names a market plan with no price in the period, and its sensor", async () => {
    // Given - a wholesale plan whose price entity recorded nothing then
    const unpriced = {
      id: "spot",
      name: "Wholesale",
      current: false,
      no_price: true,
      no_price_entities: ["sensor.spot_price"],
    };
    const card = mountCard(TAG, aHome({ ...COMPARED, plans: [unpriced, FLAT] }));
    await settled(expect, card);

    // Then - listed last, said why with the sensor to check, and never ranked
    // (HEA-299)
    expect(order(card)).toEqual(["flat", "spot"]);
    const row = card.shadowRoot.querySelector('[data-plan="spot"]');
    expect(row.textContent).toContain(
      "sensor.spot_price recorded no statistics in this period, so it cannot be " +
        "compared. Check it in Developer Tools > Statistics.",
    );
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
    rates: {
      prices: [],
      export: 0.05,
      daily_charge: 1.1,
      import_market: true,
      export_market: false,
    },
  };
  const JUNE = new Date(2026, 5, 3, 14);
  const JUNE_EVENING = new Date(2026, 5, 3, 20);
  const JULY_MORNING = new Date(2026, 6, 1, 8);
  const JULY_NOON = new Date(2026, 6, 1, 12);
  const locale = (card) => localeFrom(card._hass);
  const stretch = (from, to, source) => ({
    from: from.toISOString(),
    to: to.toISOString(),
    source,
  });
  const leftOut = (card) =>
    [...card.shadowRoot.querySelectorAll(".left-out")].map((line) => line.textContent);

  it("says what every plan left out, naming the price sensor to check", async () => {
    // Given - the market price recorded nothing on two stretches (HEA-299)
    const hass = aHome({
      ...COMPARED,
      left_out: [
        stretch(JUNE, JUNE_EVENING, "sensor.spot_price"),
        stretch(JULY_MORNING, JULY_NOON, "sensor.spot_price"),
      ],
      plans: [FLAT, SPOT],
    });
    hass.states["sensor.spot_price"] = {
      entity_id: "sensor.spot_price",
      state: "0.21",
      attributes: { friendly_name: "Spot price" },
    };
    const card = mountCard(TAG, hass);
    await settled(expect, card);

    // Then - once, above the table, both stretches under the one sensor, named
    // as the household finds it, and each day named once
    const at = (moment) => formatDateTime(moment, locale(card));
    const clock = (moment) => formatClockTime(moment, locale(card));
    expect(leftOut(card)).toEqual([
      `Left out of every plan, daily charges included: ${at(JUNE)} to ${clock(JUNE_EVENING)}, ` +
        `${at(JULY_MORNING)} to ${clock(JULY_NOON)}. Spot price (sensor.spot_price) recorded ` +
        "no statistics then. Check it in Developer Tools > Statistics.",
    ]);
    const row = card.shadowRoot.querySelector('[data-plan="spot"]');
    expect(row.textContent).not.toContain("Left out");
  });

  it("says when it was the grid meters that recorded nothing", async () => {
    // Given
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, left_out: [stretch(JUNE, JUNE_EVENING, "grid")] }),
    );
    await settled(expect, card);

    // Then
    const at = (moment) => formatDateTime(moment, locale(card));
    const clock = (moment) => formatClockTime(moment, locale(card));
    expect(leftOut(card)).toEqual([
      `Left out of every plan, daily charges included: ${at(JUNE)} to ${clock(JUNE_EVENING)}. ` +
        "Your grid meters recorded nothing then.",
    ]);
  });

  it("names a meter that recorded more than a home could use, and how much", async () => {
    // Given - the house meter recorded 11,041 kWh in one hour (HEA-301, ADR-0044)
    const hass = aHome({
      ...COMPARED,
      left_out: [{ ...stretch(JUNE, JUNE_EVENING, "sensor.house"), kwh: 11041 }],
    });
    hass.states["sensor.house"] = {
      entity_id: "sensor.house",
      state: "4120",
      attributes: { friendly_name: "House consumption" },
    };
    const card = mountCard(TAG, hass);
    await settled(expect, card);

    // Then - where to correct it, not "recorded no statistics"
    const at = (moment) => formatDateTime(moment, locale(card));
    const clock = (moment) => formatClockTime(moment, locale(card));
    expect(leftOut(card)).toEqual([
      `Left out of every plan, daily charges included: ${at(JUNE)} to ${clock(JUNE_EVENING)} ` +
        "(11,041 kWh). House consumption (sensor.house) recorded more than a home " +
        "can use in an hour then. Correct it from Settings > Repairs.",
    ]);
  });

  it("names both days when a stretch runs from one day into another", async () => {
    // Given
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, left_out: [stretch(JUNE, JULY_MORNING, "grid")] }),
    );
    await settled(expect, card);

    // Then
    const at = (moment) => formatDateTime(moment, locale(card));
    expect(leftOut(card)).toEqual([
      `Left out of every plan, daily charges included: ${at(JUNE)} to ${at(JULY_MORNING)}. ` +
        "Your grid meters recorded nothing then.",
    ]);
  });

  it("counts the kWh over the hours compared when any were left out", async () => {
    // Given
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, left_out: [stretch(JUNE, JUNE_EVENING, "grid")] }),
    );
    await settled(expect, card);

    // Then - the kWh read against the costs beneath, not the whole period
    expect(card.shadowRoot.querySelector(".flows").textContent).toBe(
      "Imported 134.3 kWh and exported 82 kWh in the hours compared.",
    );
  });

  it("says nothing was left out when nothing was", async () => {
    // Given / When
    const card = mountCard(TAG, aHome({ ...COMPARED, left_out: [] }));
    await settled(expect, card);

    // Then
    expect(leftOut(card)).toEqual([]);
  });

  it("says only that nothing was recorded when the whole period was", async () => {
    // Given - no readings at all, so the whole period is left out
    const card = mountCard(
      TAG,
      aHome({ ...COMPARED, hours: 0, left_out: [stretch(JUNE, JULY_NOON, "grid")] }),
    );
    await settled(expect, card);

    // Then - one note, not the same thing said twice
    expect(leftOut(card)).toEqual([]);
    expect(text(card)).toContain(LABELS.plans_no_readings);
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

describe("each plan's bill (HEA-300)", () => {
  afterEach(() => vi.unstubAllGlobals());

  // Three named periods over 30 days: 675 kWh in, 82 out. 91.58 of energy
  // averages 13.57 c/kWh, a quarter of the way up from Valle to Punta.
  const BILL = {
    id: "bill",
    name: "Three periods",
    current: false,
    energy: 91.58,
    export_credit: 4.1,
    daily_charges: 9,
    total: 96.48,
    breakdown: {
      daily: { rate: 0.3, days: 30, amount: 9 },
      imports: [
        { name: "Punta", rate: 0.245, kwh: 120, amount: 29.4 },
        { name: "Llano", rate: 0.18, kwh: 95, amount: 17.1 },
        { name: "Valle", rate: 0.098, kwh: 460, amount: 45.08 },
      ],
      exports: [{ name: "", rate: 0.05, kwh: 82, amount: 4.1, beyond_allowance: false }],
      average_import_rate: 0.135674,
      cheapest_import_rate: 0.098,
      dearest_import_rate: 0.245,
    },
  };
  const WITH_BILL = { ...COMPARED, plans: [FLAT, BILL] };
  const POSITION = (0.245 - 0.135674) / (0.245 - 0.098);

  const planRow = (card, id) =>
    card.shadowRoot.querySelector(`[data-plan="${id}"] tr.figures`);
  const open = (card, id) => planRow(card, id).click();
  const bill = (card, id) => card.shadowRoot.querySelector(`[data-plan="${id}"] .bill`);
  /** Each of a bill's rows, as the text of each of its cells. */
  const billRows = (card, id) =>
    [...bill(card, id).querySelectorAll("tr")].map((row) =>
      [...row.children].map((cell) => cell.textContent.replaceAll(/\s+/g, " ").trim()),
    );
  const mounted = async (comparison = WITH_BILL) => {
    const card = mountCard(TAG, aHome(comparison));
    await settled(expect, card);
    return card;
  };

  it("is closed until the plan is selected", async () => {
    // Given / When
    const card = await mounted();

    // Then - the table compares plans; a bill is one plan's detail
    expect(bill(card, "bill")).toBeNull();
    expect(text(card)).toContain(LABELS.plans_open);
  });

  it("opens beneath the plan's row, line by line as a bill lists it", async () => {
    // Given
    const card = await mounted();

    // When
    open(card, "bill");

    // Then - the daily charge first, then each price's kWh and cost, the import
    // cost they add up to, the export, and the total, each matching its column
    // in the table above
    expect(billRows(card, "bill")).toEqual([
      ["", "Rate", "Used", "Amount"],
      ["Daily charges", "€0.30/day", "30 days", "-€9.00"],
      ["Punta", "24.5 c/kWh", "120 kWh", "-€29.40"],
      ["Llano", "18.0 c/kWh", "95 kWh", "-€17.10"],
      ["Valle", "9.8 c/kWh", "460 kWh", "-€45.08"],
      ["Import cost", "average 13.57 c/kWh", "675 kWh", "-€91.58"],
      ["Export", "5.0 c/kWh", "82 kWh", "€4.10"],
      ["Total", "", "", "-€96.48"],
    ]);
    expect(text(card)).toContain(LABELS.plans_average_note);
  });

  it("closes when the plan is selected again", async () => {
    // Given
    const card = await mounted();
    open(card, "bill");

    // When
    open(card, "bill");

    // Then
    expect(bill(card, "bill")).toBeNull();
  });

  it("is opened from a button on the plan's name, which says whether it is open", async () => {
    // Given - a keyboard reaches a button, and a screen reader hears its state
    const card = await mounted();
    const button = () =>
      card.shadowRoot.querySelector('[data-plan="bill"] th button.open');
    expect(button().getAttribute("aria-expanded")).toBe("false");

    // When
    button().click();

    // Then
    expect(bill(card, "bill")).not.toBeNull();
    expect(button().getAttribute("aria-expanded")).toBe("true");
  });

  it("colours the average on the device table's scale, from the dearest price to the cheapest", async () => {
    // Given
    const card = await mounted();

    // When
    open(card, "bill");

    // Then - the figure and a band down its row, as a device's verdict is drawn
    const expected = verdictColour(POSITION);
    const average = bill(card, "bill").querySelector("[data-figure='bill-average']");
    expect(average.style.color).toBe(expected.text);
    expect(average.title).toBe(
      "13.57 c/kWh on average: your cheapest price is 9.8 c/kWh and your dearest 24.5 c/kWh.",
    );
    const importRow = average.closest("tr");
    expect(importRow.firstElementChild.style.boxShadow).toContain(expected.edge);
  });

  it("puts the same average under the plan's import cost, with no band on the plan's row", async () => {
    // Given / When
    const card = await mounted();

    // Then - a band down the row would read as a verdict on the whole plan
    const average = card.shadowRoot.querySelector("[data-figure='average:bill']");
    // The figure kept with its unit, so a wrapped line never strands "c/kWh"
    expect(average.textContent).toBe("average 13.57 c/kWh");
    expect(average.style.color).toBe(verdictColour(POSITION).text);
    expect(average.title).toContain("on average");
    expect(planRow(card, "bill").querySelector("th").style.boxShadow).toBe("");
  });

  it("colours nothing for a plan with one price, which has nothing to compare", async () => {
    // Given
    const flat = {
      ...BILL,
      breakdown: {
        ...BILL.breakdown,
        imports: [{ name: "Flat", rate: 0.2, kwh: 675, amount: 135 }],
        average_import_rate: 0.2,
        cheapest_import_rate: 0.2,
        dearest_import_rate: 0.2,
      },
    };

    // When
    const card = await mounted({ ...COMPARED, plans: [FLAT, flat] });

    // Then
    const average = card.shadowRoot.querySelector("[data-figure='average:bill']");
    expect(average.textContent).toBe("average 20.0 c/kWh");
    expect(average.style.color).toBe("");
  });

  it("says what a cap did not pay, so the bill still adds up to the total", async () => {
    // Given - 5.00 earned, 3.00 of it over the cap
    const capped = {
      ...BILL,
      export_credit: 2,
      export_unpaid: 3,
      total: 98.58,
      breakdown: {
        ...BILL.breakdown,
        exports: [{ name: "", rate: 0.1, kwh: 50, amount: 5, beyond_allowance: false }],
      },
    };
    const card = await mounted({ ...COMPARED, plans: [FLAT, capped] });

    // When
    open(card, "bill");

    // Then
    expect(billRows(card, "bill").slice(-3)).toEqual([
      ["Export", "10.0 c/kWh", "50 kWh", "€5.00"],
      ["Not paid under the export cap", "", "", "-€3.00"],
      ["Total", "", "", "-€98.58"],
    ]);
  });

  it("totals export paid at more than one price", async () => {
    // Given - an evening price paying on 15 kWh, the plan's own price, and what
    // it pays beyond its allowance
    const tiered = {
      ...BILL,
      export_credit: 1.7,
      total: 98.88,
      breakdown: {
        ...BILL.breakdown,
        exports: [
          { name: "Evening", rate: 0.1, kwh: 15, amount: 1.5, beyond_allowance: false },
          { name: "", rate: 0.04, kwh: 3, amount: 0.12, beyond_allowance: false },
          { name: "", rate: 0.02, kwh: 4, amount: 0.08, beyond_allowance: true },
        ],
      },
    };
    const card = await mounted({ ...COMPARED, plans: [FLAT, tiered] });

    // When
    open(card, "bill");

    // Then
    expect(billRows(card, "bill").slice(-5)).toEqual([
      ["Evening", "10.0 c/kWh", "15 kWh", "€1.50"],
      ["Export", "4.0 c/kWh", "3 kWh", "€0.12"],
      ["Export beyond its allowance", "2.0 c/kWh", "4 kWh", "€0.08"],
      ["Export income", "", "22 kWh", "€1.70"],
      ["Total", "", "", "-€98.88"],
    ]);
  });

  it("gives a market price one line, at the average it worked out to", async () => {
    // Given - imported at the market's hourly prices, between 6 and 32 c/kWh
    const market = {
      ...BILL,
      rates: { prices: [], export: 0.05, daily_charge: 0.3, import_market: true },
      breakdown: {
        ...BILL.breakdown,
        imports: [{ name: "", rate: null, kwh: 675, amount: 91.58 }],
        cheapest_import_rate: 0.06,
        dearest_import_rate: 0.32,
      },
    };
    const card = await mounted({ ...COMPARED, plans: [FLAT, market] });

    // When
    open(card, "bill");

    // Then
    const rows = billRows(card, "bill");
    expect(rows[2]).toEqual(["Market price", "average 13.57 c/kWh", "675 kWh", "-€91.58"]);
    const average = bill(card, "bill").querySelector("[data-figure='bill-average']");
    expect(average.title).toBe(
      "13.57 c/kWh on average: the cheapest hour you imported in was 6.0 c/kWh, and the dearest 32.0 c/kWh.",
    );
  });

  it("opens on a phone too, where the table leaves the parts out", async () => {
    // Given
    onScreen(true);
    const card = await mounted();

    // When
    open(card, "bill");

    // Then - four narrow columns fit where the table's six do not
    expect(billRows(card, "bill")[5]).toEqual([
      "Import cost",
      "average 13.57 c/kWh",
      "675 kWh",
      "-€91.58",
    ]);
  });

  it("says a single day of charges as one day", async () => {
    // Given - a day's comparison
    const oneDay = {
      ...BILL,
      breakdown: { ...BILL.breakdown, daily: { rate: 0.3, days: 1, amount: 0.3 } },
    };
    const card = await mounted({ ...COMPARED, plans: [FLAT, oneDay] });

    // When
    open(card, "bill");

    // Then
    expect(billRows(card, "bill")[1][2]).toBe("1 day");
  });

  it("stays open when the period's figures are fetched again", async () => {
    // Given
    const card = await mounted();
    open(card, "bill");

    // When - the same plan, priced again
    card._render();

    // Then
    expect(bill(card, "bill")).not.toBeNull();
  });
});
