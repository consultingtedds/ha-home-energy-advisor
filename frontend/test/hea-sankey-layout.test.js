/**
 * Arranging cost as a flow: household to floor to room to device (HEA-90).
 *
 * The layout is pure - device rows in, `{nodes, links}` out - so the hierarchy
 * rules are tested here without a DOM, and the card's suite is left to test only
 * that it hands the result to Home Assistant's chart component.
 *
 * The property that matters most is that the tree balances. Device costs sum to
 * their room, rooms to their floor, floors to the household, which is the
 * reconciliation the engine already guarantees. A mismatch here is a grouping
 * bug, never an accounting one - so it is asserted at every level rather than
 * only at the top, where two compensating errors would hide.
 */

import { describe, expect, it } from "vitest";

import {
  HOUSEHOLD_ID,
  COLUMN,
  buildDistribution,
} from "../hea-sankey-layout.js";
import { DEFAULTS } from "../hea-labels.js";

/**
 * Device rows as they reach a card: the HEA-55 row spread with its totals.
 *
 * Written out here rather than pulled through `fetchDeviceStatistics`, because
 * what the layout cares about is a row's cost and its filing, and routing that
 * through the recorder doubles would obscure both.
 */
const aRow = (key, name, actualCost, filing = {}) => ({
  key,
  name,
  untracked: false,
  statistics: { actual_cost: `sensor.${key}_actual_cost` },
  areaId: null,
  areaName: null,
  floorId: null,
  floorName: null,
  actualCost,
  ...filing,
});

/** Upstairs, in a room. The ordinary case: every level present. */
const inLounge = {
  areaId: "a-lounge",
  areaName: "Lounge",
  floorId: "f-up",
  floorName: "Upstairs",
};
const inKitchen = {
  areaId: "a-kitchen",
  areaName: "Kitchen",
  floorId: "f-up",
  floorName: "Upstairs",
};
/** A room belonging to no floor - four devices are filed this way live. */
const inGarage = { areaId: "a-garage", areaName: "Garage" };

const byId = (result) =>
  Object.fromEntries(result.nodes.map((node) => [node.id, node]));

/** What a node's children add up to, read off the links rather than recomputed. */
const flowInto = (result, id) =>
  result.links
    .filter((link) => link.target === id)
    .reduce((total, link) => total + link.value, 0);

const flowOutOf = (result, id) =>
  result.links
    .filter((link) => link.source === id)
    .reduce((total, link) => total + link.value, 0);

const build = (rows) => buildDistribution(rows, DEFAULTS);

describe("the tree balances", () => {
  it("sums devices to their room, rooms to their floor, floors to the household", () => {
    // Given
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      aRow("tv", "TV", 2, inLounge),
      aRow("oven", "Oven", 4, inKitchen),
    ];

    // When
    const result = build(rows);
    const nodes = byId(result);

    // Then
    expect(nodes["area_a-lounge"].value).toBe(3);
    expect(nodes["area_a-kitchen"].value).toBe(4);
    expect(nodes["floor_f-up"].value).toBe(7);
    expect(nodes[HOUSEHOLD_ID].value).toBe(7);
  });

  it("gives every parent exactly the flow its children carry", () => {
    // Given
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      aRow("oven", "Oven", 4, inKitchen),
      aRow("freezer", "Freezer", 2, inGarage),
      aRow("stray", "Stray", 5),
    ];

    // When
    const result = build(rows);

    // Then - every node but the household is fed exactly its own value
    for (const node of result.nodes) {
      if (node.id === HOUSEHOLD_ID) continue;
      expect([node.id, flowInto(result, node.id)]).toEqual([node.id, node.value]);
    }
    // and the household spends exactly what it holds
    expect(flowOutOf(result, HOUSEHOLD_ID)).toBe(byId(result)[HOUSEHOLD_ID].value);
  });
});

describe("devices that are not fully filed", () => {
  it("links a device in no area at all straight to the household", () => {
    // Given - the one tracked device on the reference instance with no area
    const rows = [aRow("lamp", "Lamp", 1, inLounge), aRow("stray", "Stray", 5)];

    // When
    const result = build(rows);

    // Then
    expect(result.links).toContainEqual({
      source: HOUSEHOLD_ID,
      target: "device_stray",
      value: 5,
    });
    expect(byId(result)[HOUSEHOLD_ID].value).toBe(6);
  });

  it("links a room belonging to no floor straight to the household", () => {
    // Given
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      aRow("freezer", "Freezer", 2, inGarage),
    ];

    // When
    const result = build(rows);

    // Then - the garage is a room, so it keeps its own node, fed by the household
    expect(byId(result)["area_a-garage"]).toMatchObject({
      label: "Garage",
      value: 2,
      index: COLUMN.area,
    });
    expect(result.links).toContainEqual({
      source: HOUSEHOLD_ID,
      target: "area_a-garage",
      value: 2,
    });
    expect(byId(result)["floor_f-up"].value).toBe(1);
  });

  it("links a device on a floor but in no room straight to its floor", () => {
    // Given - the other half of Home Assistant's retargeting: a device filed to
    // a floor with no room skips the room column rather than inventing one
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      aRow("boiler", "Boiler", 3, { floorId: "f-up", floorName: "Upstairs" }),
    ];

    // When
    const result = build(rows);

    // Then
    expect(result.links).toContainEqual({
      source: "floor_f-up",
      target: "device_boiler",
      value: 3,
    });
    // and the floor still holds both, so the level above it stays right
    expect(byId(result)["floor_f-up"].value).toBe(4);
    expect(byId(result)["area_a-lounge"].value).toBe(1);
  });

  it("falls back to a room's id when its name has not resolved", () => {
    // Given - a name is resolved from the source device and can be absent; a
    // node labelled "undefined" is worse than one labelled with its id
    const rows = [aRow("lamp", "Lamp", 1, { areaId: "a-lounge", areaName: null })];

    // When
    const result = build(rows);

    // Then
    expect(byId(result)["area_a-lounge"].label).toBe("a-lounge");
  });

  it("keeps the Untracked remainder visible rather than dropping it", () => {
    // Given - the remainder belongs to no room by definition
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      { ...aRow("untracked", "Untracked", 3), untracked: true },
    ];

    // When
    const result = build(rows);

    // Then
    expect(byId(result).device_untracked.value).toBe(3);
    expect(byId(result)[HOUSEHOLD_ID].value).toBe(4);
  });

  it("draws no floor column at all when nothing is filed to a floor", () => {
    // Given
    const rows = [aRow("freezer", "Freezer", 2, inGarage), aRow("stray", "Stray", 5)];

    // When
    const result = build(rows);

    // Then - an absent column is absent, not an empty node the chart must skip
    expect(result.nodes.some((node) => node.index === COLUMN.floor)).toBe(false);
  });
});

describe("what cannot be drawn", () => {
  it("drops a device that cost nothing, which contributes no flow", () => {
    // Given
    const rows = [aRow("lamp", "Lamp", 1, inLounge), aRow("idle", "Idle", 0, inLounge)];

    // When
    const result = build(rows);

    // Then
    expect(byId(result).device_idle).toBeUndefined();
    expect(byId(result)["area_a-lounge"].value).toBe(1);
  });

  it("drops a negative cost, which a flow diagram cannot represent", () => {
    // Given - a correction can leave a period net negative (ADR-0006)
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      aRow("refunded", "Refunded", -2, inLounge),
    ];

    // When
    const result = build(rows);

    // Then - dropped rather than drawn backwards, and the room still balances
    expect(byId(result).device_refunded).toBeUndefined();
    expect(byId(result)["area_a-lounge"].value).toBe(1);
    expect(flowInto(result, "area_a-lounge")).toBe(1);
  });

  it("gives an empty diagram when nothing in the period cost anything", () => {
    // Given
    const rows = [aRow("lamp", "Lamp", 0, inLounge)];

    // When
    const result = build(rows);

    // Then - no lone household node floating with nothing flowing out of it
    expect(result).toEqual({ nodes: [], links: [] });
  });

  it("gives an empty diagram for no devices at all", () => {
    // Given / When
    const result = build([]);

    // Then
    expect(result).toEqual({ nodes: [], links: [] });
  });
});

describe("the shape Home Assistant's chart expects", () => {
  it("puts each level in its own column, household first", () => {
    // Given
    const rows = [aRow("lamp", "Lamp", 1, inLounge)];

    // When
    const nodes = byId(build(rows));

    // Then
    expect(nodes[HOUSEHOLD_ID].index).toBe(COLUMN.household);
    expect(nodes["floor_f-up"].index).toBe(COLUMN.floor);
    expect(nodes["area_a-lounge"].index).toBe(COLUMN.area);
    expect(nodes.device_lamp.index).toBe(COLUMN.device);
    // The columns are ordered, which is what makes the diagram read left to right
    expect(COLUMN.household).toBeLessThan(COLUMN.floor);
    expect(COLUMN.floor).toBeLessThan(COLUMN.area);
    expect(COLUMN.area).toBeLessThan(COLUMN.device);
  });

  it("names the household from the household's own vocabulary", () => {
    // Given - not hardcoded English (ADR-0018)
    const labels = { ...DEFAULTS, household: "Casa" };

    // When
    const result = buildDistribution([aRow("lamp", "Lamp", 1, inLounge)], labels);

    // Then
    expect(byId(result)[HOUSEHOLD_ID].label).toBe("Casa");
  });

  it("labels a room and a floor with their names, never their ids", () => {
    // When
    const nodes = byId(build([aRow("lamp", "Lamp", 1, inLounge)]));

    // Then
    expect(nodes["area_a-lounge"].label).toBe("Lounge");
    expect(nodes["floor_f-up"].label).toBe("Upstairs");
  });

  it("points a device node at its cost sensor, so clicking it opens more-info", () => {
    // When
    const nodes = byId(build([aRow("lamp", "Lamp", 1, inLounge)]));

    // Then - the id the devices sensor published, never one composed from the
    // key: Home Assistant names entities in the household's language (HEA-89)
    expect(nodes.device_lamp.entityId).toBe("sensor.lamp_actual_cost");
  });

  it("leaves a device with no published cost sensor unclickable rather than guessing", () => {
    // Given
    const row = { ...aRow("lamp", "Lamp", 1, inLounge), statistics: {} };

    // When
    const nodes = byId(build([row]));

    // Then
    expect(nodes.device_lamp.entityId).toBeUndefined();
  });

  it("gives each device its own colour and sets the remainder apart", () => {
    // Given
    const rows = [
      aRow("lamp", "Lamp", 1, inLounge),
      aRow("tv", "TV", 2, inLounge),
      { ...aRow("untracked", "Untracked", 3), untracked: true },
    ];

    // When
    const nodes = byId(build(rows));

    // Then
    expect(nodes.device_lamp.color).not.toBe(nodes.device_tv.color);
    // The remainder is not a device; colouring it like one invites a hunt for it
    expect(nodes.device_untracked.color).not.toBe(nodes.device_lamp.color);
    expect(nodes.device_untracked.color).not.toBe(nodes.device_tv.color);
  });

  it("gives a room and a floor no colour of their own", () => {
    // Given - a device's colour is its identity across the dashboard; a
    // container tinted the same way would read as one more device
    const nodes = byId(build([aRow("lamp", "Lamp", 1, inLounge)]));

    // Then
    expect(nodes["area_a-lounge"].color).toBeUndefined();
    expect(nodes["floor_f-up"].color).toBeUndefined();
  });

  it("names two rooms that share a name apart, because ids differ", () => {
    // Given - two households' worth of "Bathroom" is ordinary
    const upstairs = { areaId: "a-bath-1", areaName: "Bathroom", ...{} };
    const downstairs = { areaId: "a-bath-2", areaName: "Bathroom" };

    // When
    const result = build([
      aRow("fan", "Fan", 1, upstairs),
      aRow("heater", "Heater", 2, downstairs),
    ]);

    // Then - two nodes, not one bucket holding three
    expect(byId(result)["area_a-bath-1"].value).toBe(1);
    expect(byId(result)["area_a-bath-2"].value).toBe(2);
  });
});
