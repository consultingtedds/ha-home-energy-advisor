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
 * Hues that stay apart from each other, and apart on either theme.
 *
 * The same palette the device-costs chart uses, so a household reading both
 * sees one vocabulary of colour rather than two. Cycled rather than exhausted.
 */
const PALETTE = [
  "#0072b2",
  "#e69f00",
  "#009e73",
  "#cc79a7",
  "#56b4e9",
  "#d55e00",
  "#8c6bb1",
  "#3d9970",
];

/** The remainder is not a device; colouring it like one invites a hunt for it. */
const UNTRACKED_COLOUR = "#8a8a8a";

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
 * @param devices rows as a card holds them - the HEA-55 row and its totals
 * @param labels this household's vocabulary (ADR-0018)
 * @param options `{metric}` - `"cost"` (the default) or `"energy"`
 * @returns {{nodes: Array<object>, links: Array<object>}}
 */
export const buildDistribution = (
  devices,
  labels,
  { metric = "cost", colour = fallbackColour } = {},
) => {
  const { field, sources } = METRICS[metric] ?? METRICS.cost;

  // A flow diagram cannot draw a quantity of nothing and cannot draw one
  // backwards. A correction can leave a device net negative over a period
  // (ADR-0006), and a device that simply did not run is the ordinary case.
  const drawn = devices.filter((device) => device[field] > 0);
  if (drawn.length === 0) return { nodes: [], links: [] };

  const floors = new Map();
  const areas = new Map();
  const deviceNodes = [];
  const links = [];
  let household = 0;

  drawn.forEach((device, position) => {
    const value = device[field];
    household += value;

    // The nearest container that exists, which is what decides the link's
    // source as well as which intermediate nodes are worth creating at all.
    const floor = device.floorId ? track(floors, device.floorId, device.floorName) : null;
    const area = device.areaId ? track(areas, device.areaId, device.areaName) : null;
    if (floor) floor.value += value;
    if (area) {
      area.value += value;
      // Recorded on the area rather than per device: a room belongs to one
      // floor, and the first device filed there settles which.
      area.floorId ??= device.floorId ?? null;
    }

    const id = `device_${device.key}`;
    deviceNodes.push({
      id,
      label: device.name,
      value,
      index: COLUMN.device,
      color: device.untracked ? UNTRACKED_COLOUR : PALETTE[position % PALETTE.length],
      // The id the devices sensor published, so a click opens that device's cost
      // sensor. Never composed from the key: Home Assistant names entities in
      // the household's own language (HEA-89, ADR-0018).
      ...entityIdOf(device),
    });
    links.push({ source: parentOf(device), target: id, value });
  });

  // Summed over the devices actually drawn, never over every row: a source
  // counting energy for a device the diagram dropped would make the first
  // column heavier than everything to the right of it.
  const inflow = sourceNodes(sources, drawn, labels, colour);

  return {
    nodes: [
      ...inflow,
      { id: HOUSEHOLD_ID, label: labels.household, value: household, index: COLUMN.household },
      ...nodesFrom(floors, "floor_", COLUMN.floor),
      ...nodesFrom(areas, "area_", COLUMN.area),
      ...deviceNodes,
    ],
    links: [
      ...inflow.map((node) => ({
        source: node.id,
        target: HOUSEHOLD_ID,
        value: node.value,
      })),
      ...containerLinks(floors, areas),
      ...links,
    ],
  };
};

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
 * Where a device's flow comes from: its room, else its floor, else the
 * household directly. Retargeting rather than inventing an empty level, which
 * is how Home Assistant's own layout handles the same gap.
 */
const parentOf = (device) => {
  if (device.areaId) return `area_${device.areaId}`;
  if (device.floorId) return `floor_${device.floorId}`;
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
