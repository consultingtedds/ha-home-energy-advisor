/**
 * Money and dates as the household reads them (HEA-50).
 *
 * Home Assistant knows the currency and the language already, so a card must
 * never hardcode a symbol or a date order — a euro household and a dollar one
 * see their own, and 20/05 does not become 05/20.
 */

import { describe, expect, it } from "vitest";

import { formatMoney, formatPeriod, localeFrom } from "../hea-format.js";

const EURO = { language: "en-GB", currency: "EUR" };

describe("localeFrom", () => {
  it("takes the language and currency Home Assistant already knows", () => {
    // Given — a euro household with the frontend in Spanish
    const hass = { locale: { language: "es" }, config: { currency: "EUR" } };

    // When / Then
    expect(localeFrom(hass)).toEqual({ language: "es", currency: "EUR" });
  });

  it("falls back to the browser's own defaults when either is missing", () => {
    // Given — a card constructed before hass, or an instance with no currency
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

    // Then — rounded to the cent, and carrying the symbol Home Assistant knows
    expect(formatted).toMatch(/12[.,]35/);
    expect(formatted).toMatch(/€/);
  });

  it("keeps the minus sign on a loss", () => {
    // Given — battery arbitrage can make Cost Savings negative (HEA-39), and
    // hiding that would be a lie in the user's favour
    // When / Then
    expect(formatMoney(-3.5, EURO)).toMatch(/-/);
  });

  it("still formats when the instance has no currency configured", () => {
    // Given / When
    const formatted = formatMoney(12.345, { language: "en-GB" });

    // Then — a bare number beats a wrong symbol
    expect(formatted).toMatch(/12[.,]35/);
  });

  it("shows a dash rather than NaN when there is no figure yet", () => {
    // Given / When / Then — the first render happens before any fetch resolves
    expect(formatMoney(undefined, EURO)).toBe("—");
    expect(formatMoney(Number.NaN, EURO)).toBe("—");
  });
});

describe("formatPeriod", () => {
  it("reads as the range the user picked", () => {
    // Given — "from 20 May to 15 July", the question the ticket exists for
    const period = {
      start: new Date(2026, 4, 20),
      end: new Date(2026, 6, 15),
      fallback: false,
    };

    // When
    const label = formatPeriod(period, EURO);

    // Then — day before month, because the locale says so
    expect(label).toMatch(/20/);
    expect(label).toMatch(/May/);
    expect(label).toMatch(/15/);
    expect(label).toMatch(/Jul/);
  });

  it("collapses a single day to one date", () => {
    // Given — the picker's "today", which ends part-way through the day
    const period = {
      start: new Date(2026, 7, 9, 0, 0),
      end: new Date(2026, 7, 9, 14, 30),
      fallback: false,
    };

    // When / Then — "9 Aug 2026", not "9 Aug 2026 – 9 Aug 2026"
    expect(formatPeriod(period, EURO)).toBe("9 Aug 2026");
  });

  it("is empty when there is no period yet", () => {
    // Given / When / Then
    expect(formatPeriod(undefined, EURO)).toBe("");
  });
});
