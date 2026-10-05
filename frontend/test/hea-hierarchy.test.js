import { describe, expect, it } from "vitest";

import { groupedOf, leavesOf, RESIDUAL_SUFFIX } from "../hea-hierarchy.js";

const LABELS = { device_untracked: "Untracked" };

/**
 * A device as the cards hold one: published figures, already netted.
 *
 * The circuit's own row is 13 kWh because that is what the engine publishes for
 * it - the clamp's 20 less the 7 metered inside it. Nothing here recomputes that;
 * the arithmetic under test is what a card adds back up.
 */
const aDevice = (key, name, energy, actual, atGrid, overrides = {}) => ({
  key,
  name,
  upstream: null,
  untracked: false,
  energyUsed: energy,
  actualCost: actual,
  costAtGridPrice: atGrid,
  costSavings: atGrid - actual,
  energyFromGrid: energy,
  energyFromGeneration: 0,
  energyFromBattery: 0,
  ...overrides,
});

/** A circuit of 20 kWh: a dishwasher, a washing machine, and 13 of its own. */
const circuit = () => [
  aDevice("kitchen_circuit", "Kitchen Circuit", 13, 1, 4),
  aDevice("dishwasher", "Dishwasher", 5, 2, 3, { upstream: "kitchen_circuit" }),
  aDevice("washing_machine", "Washing Machine", 2, 2, 3, {
    upstream: "kitchen_circuit",
  }),
  aDevice("oven", "Oven", 9, 3, 3),
];

describe("leavesOf", () => {
  it("replaces a container with the part of it nothing else accounts for", () => {
    // Given / When
    const leaves = leavesOf(circuit(), LABELS);

    // Then - the circuit is gone and its residual stands in its place, named so
    // a household can tell it from the circuit and from the household's own
    // Untracked remainder
    expect(leaves.map((row) => row.name)).toEqual([
      "Kitchen Circuit Untracked",
      "Dishwasher",
      "Washing Machine",
      "Oven",
    ]);
    expect(leaves[0].key).toBe(`kitchen_circuit${RESIDUAL_SUFFIX}`);
    expect(leaves[0].energyUsed).toBe(13);
  });

  it("keeps the household's total intact, which is the whole point", () => {
    // Given - the published rows sum to what the house used
    const devices = circuit();
    const published = devices.reduce((sum, row) => sum + row.energyUsed, 0);

    // When
    const leaves = leavesOf(devices, LABELS);

    // Then - exactly the same energy, redistributed. A chart summing these is
    // summing the household, which is what makes them safe to draw
    expect(leaves.reduce((sum, row) => sum + row.energyUsed, 0)).toBe(published);
    expect(published).toBe(29);
  });

  it("hands back the same list when nothing contains anything", () => {
    // Given / When - every household that has declared no hierarchy
    const devices = [aDevice("oven", "Oven", 9, 3, 3)];

    // Then - the identical array, not a rebuilt copy of it: no hierarchy means
    // no work and nothing to get wrong
    expect(leavesOf(devices, LABELS)).toBe(devices);
  });
});

describe("groupedOf", () => {
  it("puts a container above the rows inside it, carrying the whole subtree", () => {
    // Given / When - ranked by cost, which would otherwise scatter the children
    const rank = (rows) => [...rows].sort((a, b) => b.actualCost - a.actualCost);
    const grouped = groupedOf(circuit(), LABELS, rank);

    // Then - the circuit's subtotal is the clamp's own reading, 5 + 2 + 13, and
    // the rows inside it follow it immediately rather than ranking against the
    // rest of the house
    expect(
      grouped.map(({ device, depth }) => [device.name, device.energyUsed, depth]),
    ).toEqual([
      ["Oven", 9, 0],
      ["Kitchen Circuit", 20, 0],
      ["Dishwasher", 5, 1],
      ["Washing Machine", 2, 1],
      ["Kitchen Circuit Untracked", 13, 1],
    ]);
  });

  it("adds up the money as well as the energy, and derives the saving again", () => {
    // Given / When
    const grouped = groupedOf(circuit(), LABELS);
    const subtotal = grouped.find(({ device }) => device.subtotal).device;

    // Then - paid 2 + 2 + 1, would have paid 3 + 3 + 4, and the saving is the
    // difference of the sums rather than a sum of differences
    expect(subtotal.actualCost).toBe(5);
    expect(subtotal.costAtGridPrice).toBe(10);
    expect(subtotal.costSavings).toBe(5);
  });

  it("treats a figure that has not arrived as nothing, not as a broken sum", () => {
    // Given - a row the statistics have not decorated yet, which a card holds
    // for the moment between rendering and its first response
    const devices = [
      aDevice("circuit", "Circuit", 4, 2, 5),
      { key: "plug", name: "Plug", upstream: "circuit", untracked: false },
    ];

    // When
    const [{ device: subtotal }] = groupedOf(devices, LABELS);

    // Then - the circuit's own figures, and no `NaN`. One absent number would
    // otherwise poison every total on the card, and a reader cannot tell a
    // missing figure from a wrong one once it reads "NaN"
    expect(subtotal.energyUsed).toBe(4);
    expect(subtotal.actualCost).toBe(2);
    expect(subtotal.costSavings).toBe(3);
  });

  it("marks the subtotal, because nothing may add it to the rows beneath it", () => {
    // Given / When
    const grouped = groupedOf(circuit(), LABELS);

    // Then - exactly one row is flagged, and it is the container. A totals line
    // summing the column would otherwise count the circuit twice (ADR-0002)
    expect(
      grouped.filter(({ device }) => device.subtotal).map(({ device }) => device.name),
    ).toEqual(["Kitchen Circuit"]);
  });

  it("adds up the cost range where every row inside carries one", () => {
    // Given - a household who opted into the per-device range (ADR-0016), so the
    // circuit and the plug on it both have one
    const devices = [
      aDevice("circuit", "Circuit", 4, 2, 5, { costFloor: 1.8, costCeiling: 2.4 }),
      aDevice("plug", "Plug", 1, 1, 2, {
        upstream: "circuit",
        costFloor: 0.9,
        costCeiling: 1.2,
      }),
    ];

    // When
    const [{ device: subtotal }] = groupedOf(devices, LABELS);

    // Then - the bounds add, because what the whole circuit could have cost is
    // what each part could have cost. The figure a household reads as "between"
    expect(subtotal.costFloor).toBeCloseTo(2.7);
    expect(subtotal.costCeiling).toBeCloseTo(3.6);
  });

  it("gives a subtotal a cost range only where every row inside has one", () => {
    // Given - the range is opt-in, so one device may carry it and another not
    const devices = [
      aDevice("circuit", "Circuit", 1, 1, 2, { costFloor: 0.5, costCeiling: 1.5 }),
      aDevice("plug", "Plug", 1, 1, 2, { upstream: "circuit" }),
    ];

    // When
    const [{ device: subtotal }] = groupedOf(devices, LABELS);

    // Then - absent, not a partial sum. A range is a claim about what is
    // knowable, and one built from half the rows would understate the doubt
    expect(subtotal.costFloor).toBeUndefined();
    expect(subtotal.costCeiling).toBeUndefined();
  });

  it("leaves a flat household as a flat list at depth zero", () => {
    // Given / When
    const grouped = groupedOf([aDevice("oven", "Oven", 9, 3, 3)], LABELS);

    // Then
    expect(grouped).toEqual([
      { device: expect.objectContaining({ name: "Oven" }), depth: 0 },
    ]);
  });
});
