import { describe, expect, it } from "vitest";

import { withRoundedCaps } from "../hea-bars.js";

/** The radius Home Assistant uses, as the helper applies it to an outer end. */
const TOP = [4, 4, 0, 0];
const BOTTOM = [0, 0, 4, 4];

const radiusOf = (point) => point?.itemStyle?.borderRadius;
const widthOf = (point) => point?.itemStyle?.borderWidth;

describe("withRoundedCaps", () => {
  it("rounds the top of a single stack and leaves the segment beneath square", () => {
    // Given - the cost-over-time chart's shape: paid, with the saving stacked
    // above it, as [when, amount] pairs
    const [paid, saved] = withRoundedCaps([
      { stack: "cost", data: [[0, 1.2]] },
      { stack: "cost", data: [[0, 0.3]] },
    ]);

    // Then - only the saving is capped. It is the top of the bar; the paid
    // segment meets it and a radius there would draw a lozenge mid-column
    expect(radiusOf(saved.data[0])).toEqual(TOP);
    expect(radiusOf(paid.data[0])).toBeUndefined();
  });

  it("caps every device's bar, not just the last one declared", () => {
    // Given - "What each device cost": one stack per device, two segments each,
    // and the points are bare amounts rather than pairs because the axis is
    // categories. Three devices, so a helper treating the lot as one column
    // would cap the aircon and leave the other two squared off
    const series = withRoundedCaps([
      { stack: "aircon", data: [0.9] },
      { stack: "aircon", data: [0.2] },
      { stack: "oven", data: [0.5] },
      { stack: "oven", data: [0.1] },
      { stack: "fridge", data: [0.3] },
      { stack: "fridge", data: [0.05] },
    ]);

    // Then - each device's upper segment is the end of its own bar
    const [airconPaid, airconSaved, ovenPaid, ovenSaved, fridgePaid, fridgeSaved] =
      series;
    expect(radiusOf(airconSaved.data[0])).toEqual(TOP);
    expect(radiusOf(ovenSaved.data[0])).toEqual(TOP);
    expect(radiusOf(fridgeSaved.data[0])).toEqual(TOP);

    // ...and no segment that something sits on top of is rounded
    expect(radiusOf(airconPaid.data[0])).toBeUndefined();
    expect(radiusOf(ovenPaid.data[0])).toBeUndefined();
    expect(radiusOf(fridgePaid.data[0])).toBeUndefined();
  });

  it("keeps a bare amount rather than spreading it into nothing", () => {
    // Given - a category chart's bare points, where the capped one has to be
    // wrapped into an object to carry a style
    const [only] = withRoundedCaps([{ stack: "oven", data: [0.5] }]);

    // Then - the amount survives being wrapped. Spreading a number gives an
    // empty object, which draws no bar at all and says nothing about why
    expect(only.data[0].value).toBe(0.5);
    expect(radiusOf(only.data[0])).toEqual(TOP);
  });

  it("strips the border from a segment of no height", () => {
    // Given - a device that cost something and saved nothing, which is most of
    // them on most days
    const [paid, saved] = withRoundedCaps([
      { stack: "oven", data: [0.5] },
      { stack: "oven", data: [0] },
    ]);

    // Then - the empty segment carries no border, or it draws a hairline along
    // the axis that reads as a bar which is not there...
    expect(widthOf(saved.data[0])).toBe(0);
    // ...and the cap moves down to the segment that does have height
    expect(radiusOf(paid.data[0])).toEqual(TOP);
  });

  it("caps a bar that falls below the axis in its own direction", () => {
    // Given - a device that cost more than the grid would have: the saving is a
    // loss, so it hangs below zero while the spend stands above it
    const [paid, lost] = withRoundedCaps([
      { stack: "oven", data: [0.5] },
      { stack: "oven", data: [-0.08] },
    ]);

    // Then - two outer ends, each rounded away from the axis
    expect(radiusOf(paid.data[0])).toEqual(TOP);
    expect(radiusOf(lost.data[0])).toEqual(BOTTOM);
  });

  it("gives an unstacked series its own ends", () => {
    // Given - two series with no stack between them, which ECharts draws as two
    // separate bars rather than one column
    const [first, second] = withRoundedCaps([{ data: [0.4] }, { data: [0.7] }]);

    // Then - both are capped. Keyed by position they would have been read as one
    // stack, and the first bar would have been left square
    expect(radiusOf(first.data[0])).toEqual(TOP);
    expect(radiusOf(second.data[0])).toEqual(TOP);
  });

  it("caps each bucket independently along a time axis", () => {
    // Given - two buckets, where the second has no saving to sit on top
    const [paid, saved] = withRoundedCaps([
      {
        stack: "cost",
        data: [
          [0, 1.2],
          [1, 0.8],
        ],
      },
      {
        stack: "cost",
        data: [
          [0, 0.3],
          [1, 0],
        ],
      },
    ]);

    // Then - the first bucket is capped at the saving, the second at the spend
    expect(radiusOf(saved.data[0])).toEqual(TOP);
    expect(radiusOf(paid.data[0])).toBeUndefined();
    expect(radiusOf(paid.data[1])).toEqual(TOP);
    expect(widthOf(saved.data[1])).toBe(0);
  });
});
