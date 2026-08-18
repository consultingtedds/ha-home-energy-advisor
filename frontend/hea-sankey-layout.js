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

/** The root: everything the household spent in the period. */
export const HOUSEHOLD_ID = "household";

/** Which column each level is drawn in. Ordered, so the diagram reads across. */
export const COLUMN = Object.freeze({
  household: 1,
  floor: 2,
  area: 3,
  device: 4,
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
 * Arrange the period's costs as nodes and links for `ha-sankey-chart`.
 *
 * Parent values are accumulated from their children and never computed
 * independently, so each level sums to the one above it by construction. The
 * engine already guarantees that reconciliation; re-deriving it here would only
 * introduce a way for the screen to disagree with it.
 *
 * @param devices rows as a card holds them - the HEA-55 row and its totals
 * @param labels this household's vocabulary (ADR-0018)
 * @returns {{nodes: Array<object>, links: Array<object>}}
 */
export const buildDistribution = (devices, labels) => {
  // A flow diagram cannot draw a cost of nothing and cannot draw one backwards.
  // A correction can leave a device net negative over a period (ADR-0006), and
  // a device that simply did not run is the ordinary case.
  const spending = devices.filter((device) => device.actualCost > 0);
  if (spending.length === 0) return { nodes: [], links: [] };

  const floors = new Map();
  const areas = new Map();
  const deviceNodes = [];
  const links = [];
  let household = 0;

  spending.forEach((device, position) => {
    const cost = device.actualCost;
    household += cost;

    // The nearest container that exists, which is what decides the link's
    // source as well as which intermediate nodes are worth creating at all.
    const floor = device.floorId ? track(floors, device.floorId, device.floorName) : null;
    const area = device.areaId ? track(areas, device.areaId, device.areaName) : null;
    if (floor) floor.value += cost;
    if (area) {
      area.value += cost;
      // Recorded on the area rather than per device: a room belongs to one
      // floor, and the first device filed there settles which.
      area.floorId ??= device.floorId ?? null;
    }

    const id = `device_${device.key}`;
    deviceNodes.push({
      id,
      label: device.name,
      value: cost,
      index: COLUMN.device,
      color: device.untracked ? UNTRACKED_COLOUR : PALETTE[position % PALETTE.length],
      // The id the devices sensor published, so a click opens that device's cost
      // sensor. Never composed from the key: Home Assistant names entities in
      // the household's own language (HEA-89, ADR-0018).
      ...entityIdOf(device),
    });
    links.push({ source: parentOf(device), target: id, value: cost });
  });

  return {
    nodes: [
      { id: HOUSEHOLD_ID, label: labels.household, value: household, index: COLUMN.household },
      ...nodesFrom(floors, "floor_", COLUMN.floor),
      ...nodesFrom(areas, "area_", COLUMN.area),
      ...deviceNodes,
    ],
    links: [...containerLinks(floors, areas), ...links],
  };
};

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
