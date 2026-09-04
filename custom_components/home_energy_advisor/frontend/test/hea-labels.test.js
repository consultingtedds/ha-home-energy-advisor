/**
 * The card vocabulary, and the two places it is written down.
 *
 * `strings.json` and `translations/en.json` are canonical; `DEFAULTS` is the
 * fallback a card paints with before the fetch resolves. Two copies of the same
 * English will drift unless something holds them together, and a drifted
 * fallback is the worst kind: it renders perfectly on the developer's machine
 * and shows different words to a household whose fetch was slow.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import enJson from "../../translations/en.json" with { type: "json" };
import esJson from "../../translations/es.json" with { type: "json" };
import stringsJson from "../../strings.json" with { type: "json" };
import { DEFAULTS, fill, labelsFor, loadLabels, resetLabels } from "../hea-labels.js";

const aHass = (language, resources) => ({
  locale: { language },
  callWS: vi.fn().mockResolvedValue({ resources }),
});

const qualified = (bare) =>
  Object.fromEntries(
    Object.entries(bare).map(([key, value]) => [
      `component.home_energy_advisor.common.card_${key}`,
      value,
    ]),
  );

/**
 * The card strings out of a translation file's `common` section.
 *
 * They share it with the backend's own - hassfest allows no section of our own
 * (ADR-0018 update) - so the prefix is what separates them.
 */
const cardsIn = (file) =>
  Object.fromEntries(
    Object.entries(file.common)
      .filter(([key]) => key.startsWith("card_"))
      .map(([key, value]) => [key.slice("card_".length), value]),
  );

beforeEach(() => {
  resetLabels();
});

describe("the vocabulary", () => {
  it("says the same English as the translation files", () => {
    // Given / When / Then - the fallback is a copy, so it is pinned to the
    // original rather than trusted to stay in step
    expect(DEFAULTS).toEqual(cardsIn(enJson));
    expect(cardsIn(stringsJson)).toEqual(cardsIn(enJson));
  });

  it("is fully translated into every language the integration ships", () => {
    // Given - Spanish is a day-one commitment, not a later nicety
    // When / Then - a missing key falls back to English silently, so a card
    // would show half a sentence in each language and nothing would fail
    const [english, spanish] = [cardsIn(enJson), cardsIn(esJson)];
    expect(Object.keys(spanish).sort()).toEqual(Object.keys(english).sort());
    for (const [key, value] of Object.entries(spanish)) {
      expect(value, `es.json card_${key}`).toBeTruthy();
    }
  });

  it("keeps every placeholder its English carries", () => {
    // Given - a translation that drops `{range}` silently loses the figures the
    // sentence exists to state, leaving a confident claim about nothing
    const spanish = cardsIn(esJson);
    for (const [key, english] of Object.entries(cardsIn(enJson))) {
      const placeholders = (english.match(/\{\w+\}/g) ?? []).sort();
      const translated = (spanish[key].match(/\{\w+\}/g) ?? []).sort();
      expect(translated, `es.json card_${key}`).toEqual(placeholders);
    }
  });

  it("names the range column after the figure it brackets", () => {
    // Given - the bounds bracket what was paid and nothing else, so a column
    // headed "Range" between Paid and Would have paid could be read as either
    // (HEA-88). True in translation too, or the point is lost where it is needed
    const spanish = cardsIn(esJson);
    expect(DEFAULTS.range_column).toContain(DEFAULTS.paid);
    expect(spanish.range_column).toContain(spanish.paid);
  });

  it("lives where hassfest allows, since CI and HACS both run it", () => {
    // Given - a `cards` section of our own was the obvious shape and is
    // rejected: `gen_strings_schema` is a plain vol.Schema, so any top-level key
    // it does not name fails validation (ADR-0018 update). Caught by running
    // hassfest, not by reading it
    expect(stringsJson.cards).toBeUndefined();
    expect(Object.keys(stringsJson.common).length).toBeGreaterThan(
      Object.keys(DEFAULTS).length,
    );
  });
});

describe("loadLabels", () => {
  it("asks Home Assistant for this household's language", async () => {
    // Given
    const hass = aHass("es", qualified({ paid: "Pagado" }));

    // When
    const labels = await loadLabels(hass);

    // Then - the integration's own files, over the standard websocket command
    expect(hass.callWS).toHaveBeenCalledWith({
      type: "frontend/get_translations",
      language: "es",
      category: "common",
      integration: ["home_energy_advisor"],
    });
    expect(labels.paid).toBe("Pagado");
  });

  it("falls back to English for a key the language has not translated", async () => {
    // Given - a partial translation, which is the normal state of any language
    // that is not the one the strings were written in
    const hass = aHass("es", qualified({ paid: "Pagado" }));

    // When
    const labels = await loadLabels(hass);

    // Then - English rather than a bare key: "would_have_paid" in a column
    // header is worse than the wrong language
    expect(labels.would_have_paid).toBe(DEFAULTS.would_have_paid);
  });

  it("gives the household English when the fetch fails", async () => {
    // Given - an older core, a dropped connection, a category that resolves to
    // nothing. None of it is worth failing a card over
    const hass = { locale: { language: "es" }, callWS: vi.fn().mockRejectedValue(new Error("nope")) };

    // When
    const labels = await loadLabels(hass);

    // Then - what the cards showed before any of this existed
    expect(labels).toEqual(DEFAULTS);
  });

  it("fetches once per language, however many cards a dashboard holds", async () => {
    // Given - a dashboard of five cards is five instances of this call
    const hass = aHass("es", qualified({ paid: "Pagado" }));

    // When
    await Promise.all([loadLabels(hass), loadLabels(hass)]);
    await loadLabels(hass);

    // Then
    expect(hass.callWS).toHaveBeenCalledTimes(1);
  });

  it("is readable synchronously once loaded, for the render path", async () => {
    // Given - `_render` cannot await, so it reads what has been banked
    const hass = aHass("es", qualified({ paid: "Pagado" }));
    expect(labelsFor(hass)).toEqual(DEFAULTS);

    // When
    await loadLabels(hass);

    // Then
    expect(labelsFor(hass).paid).toBe("Pagado");
  });
});

describe("fill", () => {
  it("substitutes a placeholder", () => {
    // Given / When / Then
    expect(fill(DEFAULTS.range_device, { range: "€3.61 - €4.72" })).toBe(
      "What you paid could be between €3.61 - €4.72.",
    );
  });
});
