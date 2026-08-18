/**
 * Per-device figures for the period the user picked - the data layer under
 * every HEA card (HEA-50).
 *
 * A `utility_meter` is a fixed-period accumulator and cannot answer "20 May to
 * 15 July"; long-term statistics can, and HEA's sensors already record them
 * (ADR-0008). Each cost sensor is a cumulative meter, so the period's figure is
 * the *change* across it, which the recorder computes per bucket.
 *
 * Home Assistant answers on `hass.callWS`, part of the `hass` object handed to
 * every custom card alongside `states` and `callService`. That is deliberately
 * not a frontend internal, so nothing here belongs behind the energy-collection
 * adapter (ADR-0012 decision 5); the request and response shapes below were
 * measured against a live 2026.8 instance.
 *
 * Cost Savings is derived, never fetched: the stacked bar's segments have to
 * sum to Cost at Grid Price (ADR-0012), and a subtraction guarantees that where
 * a fourth statistic would merely tend to agree.
 */

/**
 * The concepts a device is accounted by, keyed by the field each becomes on a
 * row - the two are named alike deliberately, so a row's `costAtGridPrice` is
 * visibly the `cost_at_grid_price` concept and nothing has to be translated in
 * the reader's head. Names settled in ADR-0009.
 *
 * These are keys into the `statistics` map the devices sensor publishes, not
 * suffixes to append to anything: the entity id itself is translated, so it is
 * looked up rather than built (ADR-0018).
 */
export const CONCEPTS = Object.freeze({
  energyUsed: "energy_used",
  actualCost: "actual_cost",
  costAtGridPrice: "cost_at_grid_price",
  energyFromGrid: "energy_from_grid",
  energyFromGeneration: "energy_from_generation",
  energyFromBattery: "energy_from_battery",
});

/**
 * What a cost is knowable to, given how rarely a device's counter reports.
 *
 * Kept apart from `CONCEPTS` because these are the only figures that may not
 * exist: the per-device range is opt-in (ADR-0016), and a household that has not
 * asked for it has no such statistic. Absent is not zero - a range of zero would
 * claim perfect precision, which is the opposite of what the absence means - so
 * these accumulate to `undefined` rather than joining `zeroed()`.
 *
 * The values are the integration's own concept keys - `description.key` on each
 * sensor - which are never translated, and are what the published `statistics`
 * map is keyed by. They read "lowest/highest possible cost" rather than
 * "floor/ceiling" because HEA-84 first shipped `cost_floor` here against a sensor
 * whose key was `lowest_possible_cost`, so every card asked for a statistic that
 * could not exist. The row *field* names stay floor/ceiling because they are ours.
 *
 * That fix corrected the key half of the trap and left the language half: the
 * value was still concatenated into an entity id, which HA names in the
 * household's own language (HEA-89, ADR-0018). Knowing a rule and applying it
 * turned out to be different things, one comment apart.
 */
export const BOUNDS = Object.freeze({
  costFloor: "lowest_possible_cost",
  costCeiling: "highest_possible_cost",
});

/** Every concept at zero - the starting point for any accumulation. */
const zeroed = () =>
  Object.fromEntries(Object.keys(CONCEPTS).map((field) => [field, 0]));

const DAY_MS = 24 * 60 * 60 * 1000;

/** Up to this many days, buckets are hourly so a short range still has shape. */
const HOURLY_DAYS = 2;

/**
 * The statistic recording a device's concept, as the integration published it.
 *
 * Read, never composed. Home Assistant derives an entity id from the entity's
 * *translated* name whenever the instance language is one of the 41 in
 * `NATIVE_ENTITY_IDS` - `es` among them, and this integration ships Spanish - so
 * `sensor.${key}_actual_cost` names an entity that exists only on an English
 * install. Every card rendered empty on a Spanish one, and a household renaming
 * an entity broke the same guess (HEA-89, ADR-0018).
 *
 * The devices sensor knows each id exactly, because the integration owns the
 * entities. `undefined` means it published none - a concept the household did
 * not opt into - and is passed through rather than filled in.
 */
const statisticIdFor = (device, concept) => device?.statistics?.[concept];

/**
 * Every statistic the given devices need, in a stable order.
 *
 * The bounds are requested unconditionally. A card cannot ask whether the
 * household opted into per-device ranges, and an absent key in the response
 * answers that for free; a config lookup would cost a round trip and could go
 * stale between the two.
 *
 * `wholeHome`, where given, contributes only its bounds: its energy and costs
 * are the sum of the rows already fetched (the allocations are exhaustive,
 * ADR-0002), and the range is the one household figure not derivable from them.
 */
export const statisticIdsFor = (devices, wholeHome) => {
  const ids = devices.flatMap((device) =>
    [...Object.values(CONCEPTS), ...Object.values(BOUNDS)]
      .map((concept) => statisticIdFor(device, concept))
      .filter(Boolean),
  );
  if (!wholeHome?.statistics || devices.length === 0) return ids;
  return [
    ...ids,
    ...Object.values(BOUNDS)
      .map((concept) => statisticIdFor(wholeHome, concept))
      .filter(Boolean),
  ];
};

/**
 * Attach what each figure was over the comparison window (HEA-96).
 *
 * Done here rather than in each card so a card reads one result rather than
 * juggling two, and so a row's earlier self travels with the row - a table
 * column deriving a change gets it from the row it is already rendering.
 *
 * A device present now but absent then gets `undefined`, never a zero. Zero
 * would render as "all of it more than before" and invent a window in which
 * the device cost nothing, when the truth is it was not tracked at all.
 *
 * Returns the result untouched when there is nothing to compare, which is the
 * default: comparison must cost the normal path nothing.
 */
export const withComparison = (result, comparison) => {
  if (!comparison) return result;
  const before = new Map(comparison.devices.map((device) => [device.key, device]));
  return {
    ...result,
    totals: { ...result.totals, before: comparison.totals },
    devices: result.devices.map((device) => ({
      ...device,
      before: before.get(device.key),
    })),
    seriesBefore: alignedTo(comparison.series, result.period, comparison.period),
  };
};

/**
 * The earlier period's buckets, moved onto the current period's axis.
 *
 * A chart plots against time, so an unshifted earlier series would draw off to
 * the left of everything else - two months ago is simply not on the axis. The
 * offset is between the two windows' starts, which is what makes "last month"
 * lie over "this month" the way a reader expects.
 *
 * The shift is presentational and nothing downstream should treat these as real
 * instants. Where the two windows differ in length the line runs short or long,
 * which is visible and honest: a comparison against a shorter month should look
 * like one.
 */
const alignedTo = (series, period, comparisonPeriod) => {
  if (!series?.length) return undefined;
  const offset = period.start.getTime() - comparisonPeriod.start.getTime();
  return series.map((row) => ({
    ...row,
    start: new Date(row.start.getTime() + offset),
    actualStart: row.start,
  }));
};

/**
 * How finely to bucket a period.
 *
 * Home Assistant's own energy collection switches to month buckets for long
 * ranges. We never do: a month bucket cannot express a range that starts or
 * ends mid-month, so summing them would quietly bill the user for all of May
 * and all of July when they asked for 20 May to 15 July - precisely the
 * question this work exists to answer. Day buckets align with the picker's
 * local-midnight boundaries at any length, so they stay exact.
 */
export const bucketPeriodFor = ({ start, end }) =>
  end - start > HOURLY_DAYS * DAY_MS ? "day" : "hour";

/**
 * Fetch and total each device's energy and cost over the period.
 *
 * @param hass the Home Assistant object handed to the card
 * @param devices as read from `sensor.home_energy_advisor_devices`
 * @param period `{start, end, fallback}` from the energy-collection adapter
 * @returns {Promise<{period: object, devices: Array<object>, totals: object}>}
 */
export const fetchDeviceStatistics = async (hass, devices, period, wholeHome) => {
  const statisticIds = statisticIdsFor(devices, wholeHome);
  // An empty `statistic_ids` is not a request for nothing - it is a request for
  // every statistic in the database.
  const buckets = statisticIds.length
    ? await hass.callWS({
        type: "recorder/statistics_during_period",
        start_time: period.start.toISOString(),
        end_time: period.end.toISOString(),
        statistic_ids: statisticIds,
        period: bucketPeriodFor(period),
        types: ["change"],
      })
    : {};

  const rows = devices.map((device) => totalsFor(device, buckets, period));
  return {
    period,
    devices: rows,
    totals: sumRows(rows),
    wholeHome: boundsFor(wholeHome, buckets, period),
    series: seriesFrom(devices, buckets, period),
  };
};

/**
 * A key's cost range over the period, or `undefined` if it publishes none.
 *
 * The distinction is the whole point: a household that has not opted in, and one
 * whose figures are exact, must not read the same. Only a statistic the recorder
 * actually holds produces a range.
 */
const boundsFor = (device, buckets, period) => {
  if (!device) return undefined;
  const bounds = {};
  for (const [field, concept] of Object.entries(BOUNDS)) {
    const statistic = buckets?.[statisticIdFor(device, concept)];
    if (!Array.isArray(statistic)) return undefined;
    bounds[field] = changeWithin(statistic, period);
  }
  return bounds;
};

/**
 * The period bucket by bucket, added up across the devices asked for.
 *
 * The same fetch has to answer both "what did this cost" and "what did it look
 * like over time", or every chart card costs a second round trip for data
 * already in hand. Rows are oldest first, and a bucket is present if any device
 * recorded one - devices need not share bucket boundaries.
 */
const seriesFrom = (devices, buckets, period) => {
  const byStart = new Map();
  for (const device of devices) {
    for (const [field, concept] of Object.entries(CONCEPTS)) {
      const statistic = buckets?.[statisticIdFor(device, concept)];
      for (const bucket of bucketsWithin(statistic, period)) {
        const row = byStart.get(bucket.start) ?? zeroed();
        row[field] += bucket.change;
        byStart.set(bucket.start, row);
      }
    }
  }
  return [...byStart.entries()]
    .sort(([left], [right]) => left - right)
    .map(([start, row]) => ({
      ...row,
      start: new Date(start),
      costSavings: row.costAtGridPrice - row.actualCost,
    }));
};

const totalsFor = (device, buckets, period) => {
  const totals = Object.fromEntries(
    Object.entries(CONCEPTS).map(([field, concept]) => [
      field,
      changeWithin(buckets?.[statisticIdFor(device, concept)], period),
    ]),
  );
  return {
    ...device,
    ...totals,
    ...boundsFor(device, buckets, period),
    costSavings: totals.costAtGridPrice - totals.actualCost,
  };
};

/**
 * The buckets a statistic recorded inside the period, as `{start, change}`.
 *
 * The recorder returns every bucket *overlapping* the window, so a request
 * ending at midnight comes back with the following day attached; counting it
 * would bill the user for time they did not ask about. Bucket boundaries are
 * epoch milliseconds on current Home Assistant and ISO strings on older ones -
 * both are accepted, since a household on an older release should still see
 * its costs.
 *
 * A gap is reported as a null change; it is unknown rather than zero, so it is
 * dropped here and never reaches a total or a chart.
 */
const bucketsWithin = (statistic, { start, end }) => {
  if (!Array.isArray(statistic)) return [];
  const within = [];
  for (const bucket of statistic) {
    const bucketStart = new Date(bucket.start).getTime();
    if (bucketStart < start.getTime() || bucketStart >= end.getTime()) continue;
    if (typeof bucket.change === "number") {
      within.push({ start: bucketStart, change: bucket.change });
    }
  }
  return within;
};

/** The total change a statistic recorded inside the period. */
const changeWithin = (statistic, period) =>
  bucketsWithin(statistic, period).reduce(
    (total, bucket) => total + bucket.change,
    0,
  );

/**
 * The whole house, the Untracked remainder included - that remainder is part of
 * what the household actually paid, and the allocations sum to the real cost
 * (ADR-0002). Deriving the total from the parts also keeps a card's header
 * agreeing with the table beneath it.
 */
const sumRows = (rows) => {
  const totals = rows.reduce(
    (running, row) => {
      for (const field of Object.keys(running)) running[field] += row[field];
      return running;
    },
    { ...zeroed(), costSavings: 0 },
  );
  return { ...totals, ...summedBounds(rows) };
};

/**
 * The household's range as the sum of its rows - but only if every row has one.
 *
 * Summing across a gap would bound the household by a subset of itself and read
 * as a *narrower* range than the truth, which is the one direction a disclosure
 * figure must never err in.
 */
const summedBounds = (rows) => {
  const fields = Object.keys(BOUNDS);
  if (!rows.length || !rows.every((row) => fields.every((f) => f in row))) {
    return {};
  }
  return Object.fromEntries(
    fields.map((field) => [
      field,
      rows.reduce((total, row) => total + row[field], 0),
    ]),
  );
};
