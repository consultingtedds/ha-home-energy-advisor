/**
 * How well a device did, as a colour (HEA-106).
 *
 * The cards say what each device cost. Nothing said how well each device did: a
 * device costing EUR 0.50 with 60% of its grid-price cost avoided is doing
 * better than one costing EUR 0.10 with 5% avoided, and that comparison was
 * arithmetic the household had to do per row.
 *
 * The trap this has to clear is HEA-75's. `costSavings / costAtGridPrice` has a
 * denominator that goes to nothing constantly - on real data most devices sit at
 * EUR 0.00 - and a percentage over a near-zero base is noise rendered as a
 * verdict. Weighting by the device's share of the household total dissolves it:
 * the devices whose rate is unreliable are exactly the devices that fade out.
 */

import { describe, expect, it } from "vitest";

import { savingRate, verdictScaleFor } from "../hea-verdict-scale.js";

/** A row as the statistics layer publishes one, cut to what the scale reads. */
const aRow = (costAtGridPrice, costSavings) => ({ costAtGridPrice, costSavings });

/** The hue, saturation and lightness of an `hsl()`/`hsla()` string. */
const partsOf = (colour) =>
  [...colour.matchAll(/-?[\d.]+/g)].map((match) => Number(match[0]));

const hueOf = (colour) => partsOf(colour)[0];
const saturationOf = (colour) => partsOf(colour)[1];
const lightnessOf = (colour) => partsOf(colour)[2];
const alphaOf = (colour) => partsOf(colour)[3];

describe("the saving rate", () => {
  it("is the share of the grid-price cost that was avoided", () => {
    // Given / When / Then - paid EUR 4 of a EUR 10 counterfactual, so 60% of it
    // never had to be spent
    expect(savingRate(aRow(10, 6))).toBeCloseTo(0.6);
  });

  it("is nothing at all where there was nothing to avoid", () => {
    // Given - a device that drew no energy has no counterfactual, so there is
    // no rate to report. Zero would claim it did badly, which is a verdict on
    // a device that did not run
    // When / Then
    expect(savingRate(aRow(0, 0))).toBeUndefined();
    expect(savingRate(aRow(undefined, 1))).toBeUndefined();
    expect(savingRate(aRow(10, undefined))).toBeUndefined();
  });

  it("reports a battery-arbitrage loss as the negative it is", () => {
    // Given - storing cheap energy and spending it dearly costs more than the
    // grid would have (HEA-39), so the saving is below zero
    // When / Then - unclamped here; the colour clamps, the number does not
    expect(savingRate(aRow(10, -2))).toBeCloseTo(-0.2);
  });
});

describe("the colour a rate wears", () => {
  /** Two devices of equal weight, so weighting never masks a hue assertion. */
  const evenPair = (rate) => [aRow(10, 10 * rate), aRow(10, 10 * rate)];

  const colourFor = (rate, options) =>
    verdictScaleFor(evenPair(rate), options)(evenPair(rate)[0]);

  it("runs red where nearly all of the grid price was paid anyway", () => {
    // Given / When / Then - hue at the red end of the wheel
    expect(hueOf(colourFor(0).text)).toBeLessThan(20);
  });

  it("runs green where almost none of it was", () => {
    // Given / When / Then
    expect(hueOf(colourFor(1).text)).toBeGreaterThan(100);
  });

  it("passes through amber in between", () => {
    // Given / When / Then - between the two, and nearer red than green, which
    // is what makes the middle read as "some way to go"
    const amber = hueOf(colourFor(0.5).text);
    expect(amber).toBeGreaterThan(20);
    expect(amber).toBeLessThan(70);
  });

  it("clamps a loss to the red end rather than running off the wheel", () => {
    // Given - a negative rate would otherwise compute a negative hue, which is
    // a different colour entirely rather than a worse one
    // When / Then
    expect(hueOf(colourFor(-0.5).text)).toBe(hueOf(colourFor(0).text));
  });

  it("clamps a credit to the green end", () => {
    // Given - a device paid *less* than nothing, on an export credit, rates
    // above 1. There is no better than "avoided all of it"
    // When / Then
    expect(hueOf(colourFor(1.4).text)).toBe(hueOf(colourFor(1).text));
  });

  it("says nothing where there is no rate to say it about", () => {
    // Given - colour is a claim, and a device that never ran supports none
    const rows = [aRow(10, 5), aRow(0, 0)];

    // When
    const verdict = verdictScaleFor(rows)(rows[1]);

    // Then - no colour at all, so the cell renders in the ordinary text colour
    expect(verdict).toBeUndefined();
  });
});

describe("weighting by how much the device matters", () => {
  /** One dominant device and one trivial one, which is the real shape. */
  const LARGE = aRow(20, 10);
  const TINY = aRow(0.02, 0.01);
  const scale = verdictScaleFor([LARGE, TINY]);

  it("drains the colour out of a trivial device, and only the colour", () => {
    // Given - this is HEA-75's failure mode and the whole reason for the
    // weighting: both devices avoided exactly half, but one of them avoided
    // half of two cents. The rate is arithmetically identical and only one of
    // them is worth reading
    // When
    const loud = scale(LARGE);
    const quiet = scale(TINY);

    // Then - the same hue at a fraction of the volume, and the *same
    // lightness*. Weight used to pull lightness back toward the body text as
    // well, which turned every muted red into a brick: dark plus desaturated
    // is how a red stops being one, and the bad end is the end that most needs
    // to be striking (HEA-106, read on 28 Aug).
    expect(hueOf(quiet.text)).toBe(hueOf(loud.text));
    expect(lightnessOf(quiet.text)).toBe(lightnessOf(loud.text));
    expect(saturationOf(quiet.text)).toBeLessThan(saturationOf(loud.text) / 3);
  });

  it("leaves a trivial device with no row edge at all", () => {
    // Given / When - the edge is a block of colour rather than text, so it
    // recedes by going transparent where the text recedes by going neutral.
    // A grey bar on every trivial row is noise; no bar is the absence of a
    // claim, which is the truth about a device that spent two cents
    // Then
    expect(alphaOf(scale(TINY).edge)).toBeLessThan(0.2);
    expect(alphaOf(scale(LARGE).edge)).toBeCloseTo(1);
  });

  it("keeps a mid-sized device as loud as the verdict deserves", () => {
    // Given - a device a quarter the size of the largest. Read on the real
    // instance, `sqrt` put this at half volume and a device at 18% of the
    // largest at 42%, which is where the complaint came from: the poor
    // performers on a given day are usually the smaller devices, so the
    // weighting muted exactly the rows worth looking at (HEA-106).
    //
    // The suppression is meant for rates that are *unreliable* - HEA-75's
    // near-zero denominators - and a real EUR 5 against a real EUR 20 is not
    // unreliable, it is merely smaller. So the curve collapses hard at the
    // very bottom and stays flat through the middle.
    const middling = aRow(5, 2.5);
    const scaleOf = verdictScaleFor([LARGE, middling, TINY]);

    // When
    const quieter = saturationOf(scaleOf(middling).text);
    const loudest = saturationOf(scaleOf(LARGE).text);

    // Then - quieter than the largest, and nowhere near faded out
    expect(quieter).toBeLessThan(loudest);
    expect(quieter).toBeGreaterThan(loudest * 0.7);
  });

  it("still collapses a device whose rate is genuinely noise", () => {
    // Given - the other half of the same curve, and the reason it exists.
    // Two cents of grid-price cost supports no percentage worth colouring
    const scaleOf = verdictScaleFor([LARGE, TINY]);

    // When / Then - a twentieth of the loudest, where a mid-sized device keeps
    // better than seven tenths of it
    expect(saturationOf(scaleOf(TINY).text)).toBeLessThan(
      saturationOf(scaleOf(LARGE).text) * 0.1,
    );
  });

  it("caps a row that outspends every row it is weighed against", () => {
    // Given - a table's totals line is the sum of the devices above it, so it
    // is larger than any of them and would weigh past the top of the scale
    const totals = aRow(20.02, 10.01);

    // When
    const verdict = verdictScaleFor([LARGE, TINY])(totals);

    // Then - the loudest the scale goes, and no louder
    expect(saturationOf(verdict.text)).toBeCloseTo(
      saturationOf(verdictScaleFor([LARGE, TINY])(LARGE).text),
      0,
    );
    expect(alphaOf(verdict.edge)).toBeCloseTo(1);
  });

  it("does not divide by a household that spent nothing", () => {
    // Given - every device at zero, so there is no largest contributor to
    // normalise against
    const rows = [aRow(0, 0), aRow(0, 0)];

    // When / Then - no rate either, so nothing is claimed and nothing throws
    expect(verdictScaleFor(rows)(rows[0])).toBeUndefined();
  });
});

describe("the lightness ramp", () => {
  const evenPair = (rate) => [aRow(10, 10 * rate), aRow(10, 10 * rate)];
  const lightnessAt = (rate, options) =>
    lightnessOf(verdictScaleFor(evenPair(rate), options)(evenPair(rate)[0]).text);

  it("separates the two ends by brightness as well as by hue", () => {
    // Given / When / Then - red and green is the one pairing about 8% of men
    // cannot separate. Once the hue collapses, brightness is what is left to
    // read position by, so the ends must not land on the same lightness
    expect(Math.abs(lightnessAt(0) - lightnessAt(1))).toBeGreaterThan(10);
  });

  it("moves in one direction across the scale", () => {
    // Given / When / Then - monotonic rather than peaking in the middle, so a
    // dichromat reads the ramp as an ordered scale rather than as two ends
    // that meet. See the module docstring: this is a deliberate re-derivation
    // for text, which cannot use the light amber a chart fill can
    const steps = [0, 0.25, 0.5, 0.75, 1].map((rate) => lightnessAt(rate));
    const falling = steps.every(
      (value, index) => index === 0 || value <= steps[index - 1],
    );
    expect(falling).toBe(true);
  });

  it("turns the ramp over on a dark card, so good news stays the loudest", () => {
    // Given - the same ramp on a dark ground would put the strongest verdict
    // in the least contrasting colour. This is where the device palette's
    // yellow was lost, so it is asserted rather than eyeballed
    // When
    const good = lightnessAt(1, { dark: true });
    const bad = lightnessAt(0, { dark: true });

    // Then - light text on a dark card, and the good end the brightest of it
    expect(good).toBeGreaterThan(bad);
    expect(bad).toBeGreaterThan(50);
  });
});
