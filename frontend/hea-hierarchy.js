/**
 * Devices arranged by what contains what, for the cards that show both (HEA-153).
 *
 * A household who clamps a circuit and also meters appliances on it has told the
 * Energy Dashboard so, and the integration publishes each device at what it used
 * **itself** - the circuit less whatever is metered inside it. Those figures are
 * right and they are not the whole story: the circuit's own meter reads the lot,
 * and a household looking at the breaker wants the number on the breaker.
 *
 * So one list of rows becomes two shapes:
 *
 * - **leaves**, which are what sum to the household. Every device with nothing
 *   inside it, plus one row per container for the part of it nothing else
 *   accounts for. Exactly the energy of the original list, redistributed.
 * - **groups**, the same leaves with each container above its own as a subtotal
 *   carrying the whole subtree - the figure the clamp shows.
 *
 * A subtotal is safe to show and unsafe to add up: it contains the rows beneath
 * it. Anything summing these has to sum the leaves, which is why they are a
 * separate function rather than a flag on the rows.
 *
 * Figures are added here rather than published per container, because a gross
 * figure has no entity and should not get one: a device's sensors are permanent
 * once statistics exist behind them (ADR-0003), and a roll-up a card can compute
 * is not worth that. Home Assistant reaches the same conclusion - their device
 * chart computes gross and net and publishes neither.
 */

import { BOUNDS, CONCEPTS } from "./hea-statistics.js";

/** The figures that add up. A rate does not, and is derived from these. */
const ADDS = Object.keys(CONCEPTS);
const MAY_ADD = Object.keys(BOUNDS);

/** Which devices sit inside each container, by key, in the order given. */
const childrenByParent = (devices) => {
  const children = new Map();
  for (const device of devices) {
    if (!device.upstream) continue;
    const found = children.get(device.upstream);
    if (found) found.push(device);
    else children.set(device.upstream, [device]);
  }
  return children;
};

/**
 * The part of a container nothing else accounts for, as a row of its own.
 *
 * The container's published figures are already exactly this - the engine nets
 * it - so nothing is recomputed. What changes is the name and the key: it is a
 * leaf beside the devices inside it rather than the circuit itself, and a card
 * colouring or filtering by key must not confuse the two.
 */
const residualOf = (device, labels) => ({
  ...device,
  key: `${device.key}${RESIDUAL_SUFFIX}`,
  name: `${device.name} ${labels.device_untracked}`,
  upstream: device.key,
  // Not the household's Untracked remainder, which is a different row and a
  // different claim. This is one circuit's.
  untracked: false,
  residualOf: device.key,
});

/** How a residual row's key is built, so a reader can recognise one. */
export const RESIDUAL_SUFFIX = "__untracked";

/** Those figures summed across rows, with the derived ones derived again. */
const added = (rows) => {
  const total = Object.fromEntries(ADDS.map((field) => [field, 0]));
  for (const row of rows) {
    for (const field of ADDS) total[field] += row[field] ?? 0;
  }
  for (const field of MAY_ADD) {
    // Absent is not zero: the per-device range is opt-in, and a range of zero
    // would claim an exactness the absence denies (ADR-0016). So a subtotal has
    // a range only where every row under it does.
    total[field] = rows.every((row) => typeof row[field] === "number")
      ? rows.reduce((sum, row) => sum + row[field], 0)
      : undefined;
  }
  total.costSavings = total.costAtGridPrice - total.actualCost;
  return total;
};

/**
 * Every row that counts once, with each container replaced by its own residual.
 *
 * The set a chart draws and anything summing to the household reads. A household
 * who has declared no hierarchy gets their own list back, untouched.
 */
export const leavesOf = (devices, labels) => {
  const children = childrenByParent(devices);
  if (children.size === 0) return devices;
  return devices.flatMap((device) =>
    children.has(device.key) ? [residualOf(device, labels)] : [device],
  );
};

/**
 * Containers as subtotals, each immediately above the rows inside it.
 *
 * Grouping is the point, not the indent. Indenting a child while leaving it in a
 * cost-ranked list puts it under whichever row happened to rank above it, which
 * says something false rather than nothing - a reader sees a tumble dryer inside
 * an air conditioner.
 *
 * `rank` orders both the top level and each group's children, so a table's own
 * sort still decides what comes first; only containment decides where.
 */
export const groupedOf = (devices, labels, rank = (rows) => rows) => {
  const children = childrenByParent(devices);
  if (children.size === 0) return rank(devices).map((device) => ({ device, depth: 0 }));

  const containers = new Set(children.keys());
  const top = devices.filter((device) => !device.upstream);
  return rank(top).flatMap((device) => {
    if (!containers.has(device.key)) return [{ device, depth: 0 }];
    // No fallback: `containers` is this map's own key set, so a container always
    // has children to look up. A `?? []` here would be a branch nothing could
    // reach, which reads as a guarded case and is really a dead one.
    const inside = rank([...children.get(device.key), residualOf(device, labels)]);
    return [
      { device: { ...device, ...added(inside), subtotal: true }, depth: 0 },
      ...inside.map((child) => ({ device: child, depth: 1 })),
    ];
  });
};
