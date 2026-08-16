/**
 * Money and dates as the household reads them (HEA-50).
 *
 * Home Assistant knows the currency and the language already, so a card must
 * never hardcode a symbol or a date order - a euro household and a dollar one
 * see their own, and 20/05 does not become 05/20.
 */

import { describe, expect, it } from "vitest";

import {
  escapeText,
  formatEnergy,
  formatMoney,
  formatMoneyRange,
  formatPeriod,
  formatRate,
  localeFrom,
  rateUnit,
} from "../hea-format.js";

const EURO = { language: "en-GB", currency: "EUR" };

describe("localeFrom", () => {
  it("takes the language and currency Home Assistant already knows", () => {
    // Given - a euro household with the frontend in Spanish
    const hass = { locale: { language: "es" }, config: { currency: "EUR" } };

    // When / Then
    expect(localeFrom(hass)).toEqual({ language: "es", currency: "EUR" });
  });

  it("falls back to the browser's own defaults when either is missing", () => {
    // Given - a card constructed before hass, or an instance with no currency
    // set. Undefined lets Intl choose, which is better than guessing dollars.
    // When / Then
    expect(localeFrom(undefined)).toEqual({
      language: undefined,
      currency: undefined,
    });
    expect(localeFrom({ config: {} })).toEqual({
      language: undefined,
      currency: undefined,
    });
  });
});

describe("formatMoney", () => {
  it("shows an amount in the household's currency", () => {
    // Given / When
    const formatted = formatMoney(12.345, EURO);

    // Then - rounded to the cent, and carrying the symbol Home Assistant knows
    expect(formatted).toMatch(/12[.,]35/);
    expect(formatted).toMatch(/€/);
  });

  it("keeps the minus sign on a loss", () => {
    // Given - battery arbitrage can make Cost Savings negative (HEA-39), and
    // hiding that would be a lie in the user's favour
    // When / Then
    expect(formatMoney(-3.5, EURO)).toMatch(/-/);
  });

  it("still formats when the instance has no currency configured", () => {
    // Given / When
    const formatted = formatMoney(12.345, { language: "en-GB" });

    // Then - a bare number beats a wrong symbol
    expect(formatted).toMatch(/12[.,]35/);
  });

  it("shows a dash rather than NaN when there is no figure yet", () => {
    // Given / When / Then - the first render happens before any fetch resolves
    expect(formatMoney(undefined, EURO)).toBe("-");
    expect(formatMoney(Number.NaN, EURO)).toBe("-");
  });
});

describe("formatMoneyRange", () => {
  it("shows the range a cost could honestly sit in", () => {
    // Given / When
    const formatted = formatMoneyRange([3.609, 4.7241], EURO);

    // Then - in money. The percentage form of this is +31 %, and of a device
    // that cost under a cent it is +1252 %: a number that says only that
    // division happened (ADR-0016, HEA-75)
    expect(formatted).toMatch(/3[.,]61/);
    expect(formatted).toMatch(/4[.,]72/);
    expect(formatted).toMatch(/€/);
  });

  it("shows one figure where the floor and ceiling meet", () => {
    // Given - the Untracked remainder is derived per interval from meters that
    // reported for it, so it has no span to be uncertain about. `Intl`'s own
    // formatRange writes an equal pair as "~€1.50", putting an approximation
    // sign on the one figure that is exact.
    // When / Then
    expect(formatMoneyRange([1.5, 1.5], EURO)).toBe(formatMoney(1.5, EURO));
  });

  it("reads as a range even if handed its bounds backwards", () => {
    // Given / When / Then - a caller that swaps them gets a range, not a
    // backwards one that reads as nonsense
    expect(formatMoneyRange([4.72, 3.61], EURO)).toBe(
      formatMoneyRange([3.61, 4.72], EURO),
    );
  });

  it("shows a dash where there is no range to show", () => {
    // Given - per-device ranges are opt-in, so a household may publish none;
    // that must not render as "€0.00 - €0.00", which claims exactness
    // When / Then
    expect(formatMoneyRange(undefined, EURO)).toBe("-");
    expect(formatMoneyRange([undefined, 4.72], EURO)).toBe("-");
    expect(formatMoneyRange([Number.NaN, Number.NaN], EURO)).toBe("-");
  });
});

describe("formatEnergy", () => {
  it("shows kilowatt-hours, rounded to something readable", () => {
    // Given / When / Then - the sensors record six decimal places; a table of
    // them would be unreadable and none of it is meaningful
    expect(formatEnergy(38.650095, EURO)).toBe("38.7 kWh");
  });

  it("shows a dash rather than NaN when there is no figure yet", () => {
    // Given / When / Then
    expect(formatEnergy(undefined, EURO)).toBe("-");
  });
});

describe("escapeText", () => {
  it("leaves an ordinary device name alone to the eye", () => {
    // Given / When / Then - an apostrophe is escaped but still reads correctly
    // once the browser parses it back
    expect(escapeText("Slow Poll Aircon")).toBe("Slow Poll Aircon");
  });

  it("defuses markup in a name a user chose", () => {
    // Given - device names come from the household's own registry, and cards
    // build their rows as strings
    // When / Then
    expect(escapeText("<img src=x onerror=alert(1)>")).not.toContain("<");
  });
});

describe("formatPeriod", () => {
  it("reads as the range the user picked", () => {
    // Given - "from 20 May to 15 July", the question the ticket exists for
    const period = {
      start: new Date(2026, 4, 20),
      end: new Date(2026, 6, 15),
      fallback: false,
    };

    // When
    const label = formatPeriod(period, EURO);

    // Then - day before month, because the locale says so
    expect(label).toMatch(/20/);
    expect(label).toMatch(/May/);
    expect(label).toMatch(/15/);
    expect(label).toMatch(/Jul/);
  });

  it("collapses a single day to one date", () => {
    // Given - the picker's "today", which ends part-way through the day
    const period = {
      start: new Date(2026, 7, 9, 0, 0),
      end: new Date(2026, 7, 9, 14, 30),
      fallback: false,
    };

    // When / Then - "9 Aug 2026", not "9 Aug 2026 - 9 Aug 2026"
    expect(formatPeriod(period, EURO)).toBe("9 Aug 2026");
  });

  it("is empty when there is no period yet", () => {
    // Given / When / Then
    expect(formatPeriod(undefined, EURO)).toBe("");
  });
});

describe("formatRate", () => {
  it("quotes a unit price the way a tariff is quoted - in minor units", () => {
    // Given - the off-peak import rate
    // When / Then - 9.3, not 0.093. A €/kWh figure is always a small fraction
    // of a euro, so a column of them reads as leading zeroes; cents is the
    // unit tariffs are actually advertised in
    expect(formatRate(0.093, EURO)).toBe("9.3");
  });

  it("keeps a rate far below the tariff legible", () => {
    // Given - a device that ran almost entirely on surplus generation
    // When / Then - the point of the column is that this is visibly not a
    // tariff, so it must not collapse to zero
    expect(formatRate(0.003, EURO)).toBe("0.3");
    expect(formatRate(0.0004, EURO)).toBe("0.04");
  });

  it("carries no symbol, because the header carries it once", () => {
    // Given / When / Then - the cell is a bare number: this column is the only
    // one that would otherwise hold both a currency prefix and a unit suffix,
    // which is what made it twice the width of every other column
    expect(formatRate(0.093, EURO)).not.toMatch(/€|c|kWh/);
  });

  it("is a dash when there is no rate to show", () => {
    // Given - a device that used no energy, so no rate can be derived
    // When / Then - a dash, never a zero: they mean different things
    expect(formatRate(undefined, EURO)).toBe("-");
    expect(formatRate(null, EURO)).toBe("-");
  });

  it("stays in major units for a currency with no minor unit we know", () => {
    // Given - a currency whose subunit symbol Intl cannot supply
    // When / Then - better a correct major-unit figure than an invented symbol
    expect(formatRate(30, { language: "ja", currency: "JPY" })).toBe("30");
  });
});

describe("rateUnit", () => {
  it("names the minor unit where the currency has a conventional one", () => {
    // Given / When / Then - the header carries this once, so every cell below
    // it can be a bare number
    expect(rateUnit(EURO)).toBe("c/kWh");
    expect(rateUnit({ language: "en-US", currency: "USD" })).toBe("¢/kWh");
    expect(rateUnit({ language: "en-GB", currency: "GBP" })).toBe("p/kWh");
  });

  it("falls back to the currency's own symbol, taken from Intl", () => {
    // Given - a currency outside the small table of known minor units. Intl
    // has no notion of a subunit symbol, so inventing one would be guessing;
    // the major-unit symbol it does know is correct
    // The Japanese locale writes yen fullwidth (￥, U+FFE5) rather than ¥
    // (U+00A5) - which is the point of asking Intl instead of guessing
    expect(rateUnit({ language: "ja", currency: "JPY" })).toMatch(/\/kWh$/);
    expect(rateUnit({ language: "ja", currency: "JPY" })).toMatch(/[¥￥]/);
  });

  it("names only the energy unit when no currency is configured", () => {
    // Given / When / Then - the same rule formatMoney follows: no symbol beats
    // a wrong one
    expect(rateUnit({ language: "en-GB" })).toBe("/kWh");
  });
});
