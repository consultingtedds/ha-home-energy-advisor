/**
 * Cost arranged as a flow: household to floor to room to device (HEA-90).
 *
 * Every other card answers "which device cost most". This one answers "which
 * part of the house did", which is a different question and the only one in the
 * family that needs the hierarchy HEA-58 publishes on each device row.
 *
 * Kept apart from the card and free of the DOM, because the interesting part is
 * arithmetic rather than rendering: the tree has to balance, and that is worth
 * testing without mounting anything.
 *
 * ## Following Home Assistant's own layout
 *
 * ADR-0017 says reuse before build, and ADR-0013 draws with Home Assistant's
 * bundled chart component. `ha-sankey-chart` takes `{nodes, links}` and nothing
 * else - no energy preferences - so the drawing is entirely HA's and this file
 * only decides the arrangement. Where it had already decided something, its
 * decision is taken rather than re-derived (`energy/common/sankey.ts`):
 *
 * - **A missing level retargets; it does not pass through.** HA points the link
 *   at the nearest ancestor that exists - `no_floor` links the room to the root,
 *   `no_area` links the device to the floor - and lets a link span two columns.
 *   That is the whole answer to unfiled devices, which must stay visible or the
 *   total stops matching the card beside it.
 * - **Columns are `index`, and gaps close themselves.** The chart maps the
 *   sorted distinct indexes onto consecutive depths, so a household with no
 *   floors set simply gets one column fewer with no special case here.
 *
 * The numbering starts at 1 because HA's energy Sankey spends 0 on the sources
 * feeding the home. Ours starts at the household, and leaving 0 free keeps the
 * two diagrams numbered alike should a source column ever be wanted.
 */

import { residualOf } from "./hea-hierarchy.js";
import { coloursFor, PALETTE, UNTRACKED_COLOUR } from "./hea-palette.js";

/** The root: everything the household spent, or used, in the period. */
export const HOUSEHOLD_ID = "household";

/** Which column each level is drawn in. Ordered, so the diagram reads across. */
export const COLUMN = Object.freeze({
  source: 0,
  household: 1,
  floor: 2,
  area: 3,
  device: 4,
});

/**
 * What a device is measured by, and whether that has sources worth drawing.
 *
 * **Cost has no source column, and cannot have one.** Generation is priced at
 * zero (ADR-0009), so a solar band on a cost diagram is zero width - and the
 * solar band is the most interesting thing on Home Assistant's own. Worse, the
 * integration publishes energy by source but no *cost* by source, and the two
 * cannot be recovered from each other: `actual_cost` is grid plus battery, and
 * splitting them needs the prices each interval was charged at, which only the
 * engine holds. Approximating it from a period-average price would put a made-up
 * number on screen, and this file does not do arithmetic the engine has not
 * already done.
 *
 * Energy has all three, they reconcile with the device totals, and the story a
 * cost diagram cannot tell - a device that ran hard and cost nothing - is
 * exactly the one it tells best.
 */
const METRICS = Object.freeze({
  cost: { field: "actualCost", sources: null },
  energy: {
    field: "energyUsed",
    sources: [
      // Named for the vocabulary key each takes, so the words stay the
      // household's own (ADR-0018) and match the sources card beside it.
      //
      // Coloured from Home Assistant's own energy tokens rather than from
      // literals, so a household that themes its Energy Dashboard gets a
      // diagram that agrees with it. Two of these were already HA's default
      // hexes copied by hand, which is how a themed instance came to be shown
      // the wrong colours while looking right on a default one (HEA-93). The
      // fallbacks are those defaults, for a context that defines no theme.
      {
        id: "grid",
        field: "energyFromGrid",
        variable: "--energy-grid-consumption-color",
        fallback: "#488fc2",
      },
      {
        id: "generation",
        field: "energyFromGeneration",
        variable: "--energy-solar-color",
        fallback: "#ff9800",
      },
      {
        id: "battery",
        field: "energyFromBattery",
        variable: "--energy-battery-out-color",
        fallback: "#4db6ac",
      },
    ],
  },
});

/**
 * What a device is coloured when the caller names no scheme.
 *
 * The palette is shared with the device-costs chart so a household reading both
 * sees one vocabulary of colour - but it used to be *copied* here, and each card
 * indexed it by a device's position in its own list. The two lists are ordered
 * differently, so the same device came out blue on one card and yellow on the
 * other (HEA-101). A colour is keyed on the device now, and the card resolves it
 * from the household's whole device set, which is knowledge this file does not
 * have.
 *
 * The fallback keys on whatever it was given, which is right for a caller
 * holding every device and wrong for one holding a filtered subset - so a card
 * passes its own resolver rather than relying on this.
 */
const fallbackDeviceColour = (devices) => {
  const colours = coloursFor(devices);
  return (device) =>
    device.untracked
      ? UNTRACKED_COLOUR.fallback
      : (colours.get(device.key) ?? PALETTE[0]);
};

/**
 * What a source is coloured when nothing can resolve a theme.
 *
 * This file is deliberately free of the DOM - the arrangement is arithmetic and
 * is tested without one - so it cannot read a CSS variable itself. The card
 * passes a resolver; without one every source takes Home Assistant's own
 * default for its token, which is what an unthemed instance renders anyway.
 */
const fallbackColour = ({ fallback }) => fallback;

/**
 * Arrange the period as nodes and links for `ha-sankey-chart`.
 *
 * Parent values are accumulated from their children and never computed
 * independently, so each level sums to the one above it by construction. The
 * engine already guarantees that reconciliation; re-deriving it here would only
 * introduce a way for the screen to disagree with it.
 *
 * A device inside another is drawn under it, as Home Assistant's own energy
 * Sankey draws `included_in_stat` (HEA-191). Floors and rooms then group only
 * what is left at the top, which is also theirs: a light on the kitchen circuit
 * is part of that circuit wherever it hangs, and crediting its room too would
 * draw the same energy twice.
 *
 * @param devices rows as a card holds them - the HEA-55 row and its totals
 * @param labels this household's vocabulary (ADR-0018)
 * @param options `{metric, groupByFloor, groupByArea}` - `"cost"` (the default)
 *   or `"energy"`; both groupings on unless turned off, as Home Assistant's are
 * @returns {{nodes: Array<object>, links: Array<object>}}
 */
export const buildDistribution = (
  devices,
  labels,
  {
    metric = "cost",
    colour = fallbackColour,
    deviceColour = fallbackDeviceColour(devices),
    groupByFloor = true,
    groupByArea = true,
  } = {},
) => {
  const { field, sources } = METRICS[metric] ?? METRICS.cost;

  const top = treesOf(devices, field).filter((tree) => tree.value > 0);
  if (top.length === 0) return { nodes: [], links: [] };

  const household = top.reduce((total, tree) => total + tree.value, 0);
  const grouping = groupedByPlace(top, { groupByFloor, groupByArea });
  const circuits = drawnTrees(top, labels, deviceColour);

  // Summed over what each device used itself, never over every row: a source
  // counting energy for a device the diagram dropped would make the first
  // column heavier than everything to the right of it.
  const inflow = sourceNodes(
    sources,
    devices.filter((device) => device[field] > 0),
    labels,
    colour,
  );

  return {
    nodes: [
      ...inflow,
      { id: HOUSEHOLD_ID, label: labels.household, value: household, index: COLUMN.household },
      ...grouping.nodes,
      ...circuits.nodes,
    ],
    links: [
      ...inflow.map((node) => ({
        source: node.id,
        target: HOUSEHOLD_ID,
        value: node.value,
      })),
      ...grouping.links,
      ...circuits.links,
    ],
  };
};

/**
 * Each top-level device with everything inside it, valued as the whole.
 *
 * A row carries what the device used *itself* - the engine nets a circuit of
 * what is metered inside it - so a circuit's value is rebuilt as its own share
 * plus its children's. Only what can be drawn counts: a flow diagram cannot
 * draw a quantity of nothing nor one backwards, and a correction can leave a
 * figure net negative over a period (ADR-0006). So a node is exactly what flows
 * out of it, and the tree balances whatever the rows say.
 */
const treesOf = (devices, field) => {
  const byKey = new Map(devices.map((device) => [device.key, device]));
  const children = new Map();
  const roots = [];
  for (const device of devices) {
    const container = containerOf(device, byKey);
    if (!container) roots.push(device);
    else if (children.has(container.key)) children.get(container.key).push(device);
    else children.set(container.key, [device]);
  }

  const treeOf = (device) => {
    const own = Math.max(device[field] ?? 0, 0);
    const inside = (children.get(device.key) ?? [])
      .map(treeOf)
      .filter((tree) => tree.value > 0);
    return {
      device,
      own,
      inside,
      value: inside.reduce((total, tree) => total + tree.value, own),
    };
  };
  return roots.map(treeOf);
};

/**
 * The device this one sits inside, or nothing if it is at the top.
 *
 * A container missing from the rows - removed from the integration while the
 * Energy Dashboard still names it - leaves the device at the top rather than
 * hanging it from nothing. So does a loop back to the device itself, which a
 * hand-edited configuration can make: Home Assistant bounds the same walk for
 * the same reason, and a loop has no top to hang from.
 */
const containerOf = (device, byKey) => {
  const container = byKey.get(device.upstream);
  if (!container) return null;
  const seen = new Set();
  for (let current = container; current; current = byKey.get(current.upstream)) {
    if (current.key === device.key) return null;
    if (seen.has(current.key)) break;
    seen.add(current.key);
  }
  return container;
};

/**
 * Floors and rooms, holding only the top-level devices.
 *
 * Each grouping is optional, under Home Assistant's own option names. Where one
 * is off, or a device is filed to neither, the link goes to the nearest level
 * that is drawn - their retargeting, which keeps every device visible.
 */
const groupedByPlace = (top, { groupByFloor, groupByArea }) => {
  const floors = new Map();
  const areas = new Map();
  const links = [];

  top.forEach(({ device, value }) => {
    const floor =
      groupByFloor && device.floorId ? track(floors, device.floorId, device.floorName) : null;
    const area =
      groupByArea && device.areaId ? track(areas, device.areaId, device.areaName) : null;
    if (floor) floor.value += value;
    if (area) {
      area.value += value;
      // Recorded on the area rather than per device: a room belongs to one
      // floor, and the first device filed there settles which.
      area.floorId ??= floor?.id ?? null;
    }
    links.push({ source: placeOf(area, floor), target: nodeIdOf(device), value });
  });

  return {
    nodes: [
      ...nodesFrom(floors, "floor_", COLUMN.floor),
      ...nodesFrom(areas, "area_", COLUMN.area),
    ],
    links: [...containerLinks(floors, areas), ...links],
  };
};

/**
 * Every device node, and the links from each circuit to what is inside it.
 *
 * Columns follow Home Assistant's sections: a circuit sits one column further
 * right for each circuit above it, and every leaf - an ordinary device, an
 * appliance, a circuit's own untracked share - lines up in the column after the
 * deepest circuit. A household with no nesting has no circuits, so every device
 * lands in the one device column, exactly as before.
 */
const drawnTrees = (top, labels, deviceColour) => {
  const leafColumn = COLUMN.device + circuitDepth(top);
  const nodes = [];
  const links = [];

  const draw = (tree, depth) => {
    const { device, own, inside, value } = tree;
    const isCircuit = inside.length > 0;
    nodes.push({
      id: nodeIdOf(device),
      label: device.name,
      value,
      index: isCircuit ? COLUMN.device + depth : leafColumn,
      color: deviceColour(device),
      // The id the devices sensor published, so a click opens that device's cost
      // sensor. Never composed from the key: Home Assistant names entities in
      // the household's own language (HEA-89, ADR-0018).
      ...entityIdOf(device),
    });
    if (!isCircuit) return;
    inside.forEach((child) => {
      links.push({ source: nodeIdOf(device), target: nodeIdOf(child.device), value: child.value });
      draw(child, depth + 1);
    });
    if (own > 0) {
      const leftover = residualOf(device, labels);
      nodes.push({
        id: nodeIdOf(leftover),
        label: leftover.name,
        value: own,
        index: leafColumn,
        // The circuit's colour, as on the bars: it is part of that circuit. The
        // figure is exactly what the circuit's own sensor publishes, so a click
        // opens that.
        color: deviceColour(device),
        ...entityIdOf(device),
      });
      links.push({ source: nodeIdOf(device), target: nodeIdOf(leftover), value: own });
    }
  };

  top.forEach((tree) => draw(tree, 0));
  return { nodes, links };
};

/** How many levels of circuit the deepest branch holds: none for a flat house. */
const circuitDepth = (trees) =>
  trees.reduce(
    (deepest, tree) =>
      tree.inside.length > 0 ? Math.max(deepest, 1 + circuitDepth(tree.inside)) : deepest,
    0,
  );

const nodeIdOf = (device) => `device_${device.key}`;

/**
 * Where the household's energy came from, as the column feeding it.
 *
 * A source the household did not draw on is left out rather than drawn at
 * zero: a band labelled "Battery" on a house with no battery invites a hunt
 * for hardware that is not there.
 */
const sourceNodes = (sources, drawn, labels, colour) =>
  (sources ?? [])
    .map((source) => ({
      id: `source_${source.id}`,
      label: labels[source.id],
      value: drawn.reduce(
        (total, device) => total + (device[source.field] ?? 0),
        0,
      ),
      index: COLUMN.source,
      color: colour(source),
    }))
    .filter((node) => node.value > 0);

/** The running total for a container, created on first sight of it. */
const track = (containers, id, name) => {
  if (!containers.has(id)) {
    // A container whose name has not resolved yet still has to label its node.
    containers.set(id, { id, name: name || id, value: 0 });
  }
  return containers.get(id);
};

/**
 * Where a top-level device's flow comes from: its room, else its floor, else
 * the household directly. Retargeting rather than inventing an empty level,
 * which is how Home Assistant's own layout handles the same gap.
 */
const placeOf = (area, floor) => {
  if (area) return `area_${area.id}`;
  if (floor) return `floor_${floor.id}`;
  return HOUSEHOLD_ID;
};

/** Absent where the integration published no such entity, never a guessed id. */
const entityIdOf = (device) => {
  const entityId = device.statistics?.actual_cost;
  return entityId ? { entityId } : {};
};

/** Containers carry no colour: only a device's colour identifies it. */
const nodesFrom = (containers, prefix, index) =>
  [...containers.values()].map((container) => ({
    id: `${prefix}${container.id}`,
    label: container.name,
    value: container.value,
    index,
  }));

/** Household to floor, and floor to room - or household to room where there is no floor. */
const containerLinks = (floors, areas) => [
  ...[...floors.values()].map((floor) => ({
    source: HOUSEHOLD_ID,
    target: `floor_${floor.id}`,
    value: floor.value,
  })),
  ...[...areas.values()].map((area) => ({
    source: area.floorId ? `floor_${area.floorId}` : HOUSEHOLD_ID,
    target: `area_${area.id}`,
    value: area.value,
  })),
];
