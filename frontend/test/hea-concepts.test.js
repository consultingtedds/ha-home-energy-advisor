/**
 * The one vocabulary the cost concepts wear, wherever they are named (HEA-104).
 *
 * A household reading the stacked bar learns that blue means Paid; the cards
 * either say that everywhere or the colour is a coincidence. What is asserted
 * here is the contract - which concepts carry a mark, which carry none, and
 * that Would have paid is drawn as a container rather than as a third fill.
 * Whether the mark actually paints is asserted where there is a shadow root to
 * paint into, in the card suites.
 */

import { describe, expect, it } from "vitest";

import { CONCEPT_STYLE, PAID, SAVED, swatch } from "../hea-concepts.js";

/** The declarations for one class, from the stylesheet the cards concatenate. */
const ruleFor = (selector) => {
  const match = new RegExp(`\\.swatch\\.${selector}\\s*\\{([^}]*)\\}`).exec(
    CONCEPT_STYLE,
  );
  return match ? match[1] : "";
};

describe("the chart colours", () => {
  it("keeps Paid on the primary colour and Saved on the success colour", () => {
    // Given / When / Then - both have been live in the over-time chart for
    // weeks, so this names a vocabulary households already read rather than
    // changing one. Saved stays green because a saving genuinely is good news:
    // the identity and the verdict agree rather than compete
    expect(PAID.variable).toBe("--primary-color");
    expect(SAVED.variable).toBe("--success-color");
  });

  it("carries a fallback for each, for a theme that defines neither", () => {
    // Given / When / Then - a chart resolves these in JavaScript, where an
    // unset variable comes back as an empty string and would draw nothing
    expect(PAID.fallback).toMatch(/^#[\da-f]{6}$/i);
    expect(SAVED.fallback).toMatch(/^#[\da-f]{6}$/i);
  });
});

describe("the mark a concept wears in text", () => {
  it("marks each of the three cost concepts", () => {
    // Given / When / Then - keyed by the label the concept wears, so a card
    // that already names the concept needs no second way to say which it is
    for (const concept of ["paid", "would_have_paid", "saved"]) {
      expect(swatch(concept), concept).toMatch(/class="swatch /);
    }
  });

  it("fills Paid and Saved from their own variables", () => {
    // Given / When / Then
    expect(ruleFor("paid")).toContain("--primary-color");
    expect(ruleFor("saved")).toContain("--success-color");
  });

  it("gives Would have paid no fill of its own", () => {
    // Given - it is Paid plus Saved by construction, so it is the container
    // rather than a third quantity beside them. A third fill would have a
    // container contradicting its own contents
    // When
    const rule = ruleFor("would-have-paid");

    // Then - an outline, and nothing painted inside it
    expect(rule).toContain("border");
    expect(rule).not.toContain("background");
  });

  it("outlines it in the text colour, not the earlier period's grey", () => {
    // Given / When / Then - `--secondary-text-color` is already the earlier
    // period, in the over-time legend and the device-costs key both. A grey
    // mark beside two coloured ones would read as "last week" or as "no
    // figure" before it read as "the whole bar"
    expect(ruleFor("would-have-paid")).toContain("--primary-text-color");
    expect(ruleFor("would-have-paid")).not.toContain("--secondary-text-color");
  });

  it("says nothing for a column that is not a cost concept", () => {
    // Given / When / Then - a device name, an amount of energy and a rate are
    // not concepts in this vocabulary, and a mark against them would invent a
    // meaning the reader would then look for
    for (const other of ["device", "energy", "range_column", "change", "rate"]) {
      expect(swatch(other), other).toBe("");
    }
  });

  it("says nothing for a label that builds itself", () => {
    // Given - the rate column's label is a function of the locale, because its
    // unit follows the household's currency (`hea-devices-card`)
    // When / Then - an object used as a key must not resolve to a mark
    expect(swatch((locale, labels) => labels.rate)).toBe("");
    expect(swatch(undefined)).toBe("");
  });

  it("keeps the mark out of the accessible name", () => {
    // Given / When / Then - colour is reinforcement and never the only cue, so
    // the label beside it is already the whole meaning. An empty span announced
    // as anything would be noise
    expect(swatch("paid")).toContain('aria-hidden="true"');
  });
});
