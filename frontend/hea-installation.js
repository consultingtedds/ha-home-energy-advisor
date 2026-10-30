/**
 * What the household's installation earned, from figures already recorded
 * (HEA-241, ADR-0034).
 *
 * Three parts, each read from a long-term statistic that already exists:
 *
 * - **Generation saved** is the whole home's Cost Savings less its Battery
 *   Savings. Cost Savings is, per slice, generation used at the import price
 *   plus battery energy used at the import price less what it cost to store,
 *   and Battery Savings is exactly the second term, so the difference is the
 *   generation's own share by construction rather than by estimate.
 * - **Battery saved** is Battery Savings less what the battery's losses cost.
 *   Against no installation at all that energy would never have been bought, so
 *   the battery is charged for it, and the part may be negative.
 * - **Exports earned** is the Energy Dashboard's own compensation statistic for
 *   each grid source, read where the Energy Dashboard reads it. It is priced by
 *   the same export price this integration reads (ADR-0026), so the two cannot
 *   disagree.
 *
 * Every figure is the whole home's. None of them can be narrowed to a device,
 * a room or a label, which is why they have a card of their own.
 */

import { hasACounterfactual } from "./hea-statistics.js";

/**
 * Whether this home has an installation to have earned anything.
 *
 * Its whole-home Cost Savings is created disabled on a home with neither
 * generation nor a battery (HEA-175), and a disabled entity has no state. So
 * the card and the dashboard ask the same question the integration already
 * answered, rather than each deciding afresh.
 */
export const hasAnInstallation = (hass, wholeHome) => {
  const savings = wholeHome?.statistics?.cost_savings;
  return Boolean(savings && hass?.states?.[savings]);
};

/**
 * The statistics this integration publishes that the return is built from.
 *
 * Losses are the battery rows with no Would have paid of their own, top level
 * only: a pooled battery publishes its losses gross, each battery's share inside
 * it (ADR-0031), so counting the shares as well would charge every loss twice.
 */
export const installationStatistics = (wholeHome, devices) => ({
  costSavings: wholeHome?.statistics?.cost_savings,
  batterySavings: wholeHome?.statistics?.battery_savings,
  lossesPaid: (devices ?? [])
    .filter((device) => !device.untracked && !device.upstream)
    .filter((device) => !hasACounterfactual(device))
    .map((device) => device.statistics?.actual_cost)
    .filter(Boolean),
});

/**
 * Each grid source's export compensation statistic, as the Energy Dashboard
 * finds it.
 *
 * A household's own `stat_compensation` first, and otherwise the sensor Home
 * Assistant created for an export price, which `energy/info` reports under
 * `cost_sensors`, keyed by the export meter. Never guessed from an entity's
 * name: a reconfigured Energy Dashboard leaves the old compensation sensor
 * behind under a similar name, still recording.
 *
 * Read in both shapes Home Assistant stores a grid source in: the flows on the
 * source itself, and the `flow_to` lists before it (HEA-117, HEA-209). Both name
 * these two keys the same.
 */
export const compensationStatistics = (prefs, info) => {
  const created = info?.cost_sensors ?? {};
  const found = [];
  for (const source of prefs?.energy_sources ?? []) {
    if (source?.type !== "grid") continue;
    const exports = Array.isArray(source.flow_to) ? source.flow_to : [source];
    for (const flow of exports) {
      const statistic =
        flow?.stat_compensation || (flow?.stat_energy_to && created[flow.stat_energy_to]);
      if (statistic && !found.includes(statistic)) found.push(statistic);
    }
  }
  return found;
};

/** Every statistic the return needs, for one recorder request. */
export const statisticIdsOf = (parts) =>
  [
    parts.costSavings,
    parts.batterySavings,
    ...(parts.lossesPaid ?? []),
    ...(parts.exportsEarned ?? []),
  ].filter(Boolean);

/**
 * The three parts over the period, and their total.
 *
 * A part that does not apply is `undefined`, not zero: a home with no battery
 * has no battery part to show, which is a different statement from a battery
 * that saved nothing.
 */
export const installationReturn = (buckets, parts, period) => {
  const within = (statistic) => changeWithin(buckets?.[statistic], period);
  const savings = within(parts.costSavings);
  const hasBattery = Boolean(parts.batterySavings);
  const batterySavings = hasBattery ? within(parts.batterySavings) : 0;
  const lossesPaid = (parts.lossesPaid ?? []).reduce((sum, id) => sum + within(id), 0);
  const exports = parts.exportsEarned ?? [];

  const generationSaved = savings - batterySavings;
  const batterySaved = hasBattery ? batterySavings - lossesPaid : undefined;
  const exportsEarned = exports.length
    ? exports.reduce((sum, id) => sum + within(id), 0)
    : undefined;
  return {
    generationSaved,
    batterySaved,
    exportsEarned,
    total: generationSaved + (batterySaved ?? 0) + (exportsEarned ?? 0),
  };
};

/**
 * What a statistic changed by inside the period.
 *
 * The recorder returns every bucket *overlapping* the window, so one ending at
 * midnight comes back with the next day attached, and a gap arrives as a null
 * change: both are left out, as the other cards leave them out.
 */
const changeWithin = (statistic, { start, end }) => {
  if (!Array.isArray(statistic)) return 0;
  let total = 0;
  for (const bucket of statistic) {
    const at = new Date(bucket.start).getTime();
    if (at < start.getTime() || at >= end.getTime()) continue;
    if (typeof bucket.change === "number") total += bucket.change;
  }
  return total;
};
