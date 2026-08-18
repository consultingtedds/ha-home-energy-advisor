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

/**
 * A row carrying energy and its source split, for the energy metric.
 *
 * The three sources sum to the energy used - the invariant the engine
 * guarantees and the sources card checks - so a diagram built from them
 * balances for the same reason the cost one does.
 */
const anEnergyRow = (key, name, { grid = 0, generation = 0, battery = 0 }, filing = {}) => ({
  ...aRow(key, name, 0, filing),
  energyUsed: grid + generation + battery,
  energyFromGrid: grid,
  energyFromGeneration: generation,
  energyFromBattery: battery,
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

  it("measures by cost when asked for a metric that does not exist", () => {
    // Given - the card guards its own config, but this is exported and a
    // caller with a typo should get the default view rather than an empty one
    const rows = [aRow("lamp", "Lamp", 1, inLounge)];

    // When
    const result = buildDistribution(rows, DEFAULTS, { metric: "bananas" });

    // Then
    expect(byId(result)[HOUSEHOLD_ID].value).toBe(1);
  });

  it("draws no source column on the cost metric", () => {
    // Given - generation is priced at zero (ADR-0009), so a solar ribbon on a
    // cost diagram would be zero width. An invisible band that is really the
    // whole point of the view is worse than no column at all.
    const nodes = byId(build([aRow("lamp", "Lamp", 1, inLounge)]));

    // Then
    expect(Object.keys(nodes).some((id) => id.startsWith("source_"))).toBe(false);
  });
});

describe("the energy metric", () => {
  const energy = (rows, labels = DEFAULTS) =>
    buildDistribution(rows, labels, { metric: "energy" });

  it("measures each device by energy rather than by what it cost", () => {
    // Given - the cloud-polled pump ran hard and cost nothing, which is exactly the
    // device a cost diagram draws as a hairline
    const rows = [anEnergyRow("pump", "Pump", { generation: 6.6 }, inLounge)];

    // When
    const nodes = byId(energy(rows));

    // Then
    expect(nodes.device_pump.value).toBe(6.6);
    expect(nodes[HOUSEHOLD_ID].value).toBe(6.6);
  });

  it("opens with where the energy came from", () => {
    // Given
    const rows = [
      anEnergyRow("pump", "Pump", { grid: 1, generation: 4 }, inLounge),
      anEnergyRow("lamp", "Lamp", { grid: 2, battery: 3 }, inKitchen),
    ];

    // When
    const result = energy(rows);
    const nodes = byId(result);

    // Then - one column before the household, as Home Assistant's own does
    expect(nodes.source_grid).toMatchObject({ value: 3, index: COLUMN.source });
    expect(nodes.source_generation).toMatchObject({ value: 4, index: COLUMN.source });
    expect(nodes.source_battery).toMatchObject({ value: 3, index: COLUMN.source });
    expect(COLUMN.source).toBeLessThan(COLUMN.household);
  });

  it("feeds the household exactly what the sources carry", () => {
    // Given
    const rows = [
      anEnergyRow("pump", "Pump", { grid: 1, generation: 4 }, inLounge),
      anEnergyRow("lamp", "Lamp", { grid: 2, battery: 3 }, inKitchen),
    ];

    // When
    const result = energy(rows);

    // Then - the sources reconcile with the devices, so the diagram balances
    // end to end rather than only from the household rightwards
    expect(flowInto(result, HOUSEHOLD_ID)).toBe(10);
    expect(byId(result)[HOUSEHOLD_ID].value).toBe(10);
    expect(flowOutOf(result, HOUSEHOLD_ID)).toBe(10);
  });

  it("leaves out a source the household did not draw on", () => {
    // Given - a house with no battery, which is most houses
    const rows = [anEnergyRow("lamp", "Lamp", { grid: 2, generation: 1 }, inLounge)];

    // When
    const nodes = byId(energy(rows));

    // Then - a zero-width band labelled "Battery" invites a hunt for a
    // battery that is not there
    expect(nodes.source_battery).toBeUndefined();
    expect(nodes.source_grid.value).toBe(2);
  });

  it("counts sources only for the devices it draws", () => {
    // Given - a device with no energy is dropped, so its sources must go too
    // or the first column would outweigh everything right of it
    const rows = [
      anEnergyRow("lamp", "Lamp", { grid: 2 }, inLounge),
      anEnergyRow("idle", "Idle", { grid: 0 }, inLounge),
    ];

    // When
    const result = energy(rows);

    // Then
    expect(byId(result).device_idle).toBeUndefined();
    expect(flowInto(result, HOUSEHOLD_ID)).toBe(2);
  });

  it("names the sources from the household's own vocabulary", () => {
    // Given
    const labels = { ...DEFAULTS, grid: "Red", generation: "Generación", battery: "Batería" };

    // When
    const nodes = byId(energy([anEnergyRow("lamp", "Lamp", { grid: 1, generation: 1, battery: 1 })], labels));

    // Then
    expect(nodes.source_grid.label).toBe("Red");
    expect(nodes.source_generation.label).toBe("Generación");
    expect(nodes.source_battery.label).toBe("Batería");
  });

  it("gives each source its own colour, apart from the devices'", () => {
    // When
    const nodes = byId(energy([anEnergyRow("lamp", "Lamp", { grid: 1, generation: 1 }, inLounge)]));

    // Then
    expect(nodes.source_grid.color).toBeDefined();
    expect(nodes.source_generation.color).not.toBe(nodes.source_grid.color);
    expect(nodes.source_grid.color).not.toBe(nodes.device_lamp.color);
  });

  it("treats a source the row does not carry as none of it", () => {
    // Given - a row from an integration too old to publish one of the three.
    // Absent must read as zero rather than poison the sum with NaN, which
    // would take the whole diagram down rather than one band.
    const row = anEnergyRow("lamp", "Lamp", { grid: 2 }, inLounge);
    delete row.energyFromBattery;

    // When
    const result = energy([row]);

    // Then
    expect(byId(result).source_battery).toBeUndefined();
    expect(flowInto(result, HOUSEHOLD_ID)).toBe(2);
  });

  it("gives an empty diagram when no energy was used at all", () => {
    // Given / When
    const result = energy([anEnergyRow("lamp", "Lamp", { grid: 0 }, inLounge)]);

    // Then
    expect(result).toEqual({ nodes: [], links: [] });
  });
});

describe("more of the shape Home Assistant's chart expects", () => {
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
