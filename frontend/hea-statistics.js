/**
 * Per-device figures for the period the user picked — the data layer under
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
 * The sensor suffixes a device is accounted by, keyed by the field each becomes
 * on a row — the two are named alike deliberately, so a row's `costAtGridPrice`
 * is visibly `sensor.<key>_cost_at_grid_price` and nothing has to be translated
 * in the reader's head. Names settled in ADR-0009.
 */
export const CONCEPTS = Object.freeze({
  energyUsed: "energy_used",
  actualCost: "actual_cost",
  costAtGridPrice: "cost_at_grid_price",
  energyFromGrid: "energy_from_grid",
  energyFromGeneration: "energy_from_generation",
  energyFromBattery: "energy_from_battery",
});

/** Every concept at zero — the starting point for any accumulation. */
const zeroed = () =>
  Object.fromEntries(Object.keys(CONCEPTS).map((field) => [field, 0]));

const DAY_MS = 24 * 60 * 60 * 1000;

/** Up to this many days, buckets are hourly so a short range still has shape. */
const HOURLY_DAYS = 2;

/**
 * The statistic recording a device's concept.
 *
 * Written once because the request and the read of the response must agree
 * exactly: a divergence between them is not an error but an empty house.
 */
const statisticIdFor = (deviceKey, concept) => `sensor.${deviceKey}_${concept}`;

/** Every statistic the given devices need, in a stable order. */
export const statisticIdsFor = (devices) =>
  devices.flatMap((device) =>
    Object.values(CONCEPTS).map((concept) => statisticIdFor(device.key, concept)),
  );

/**
 * How finely to bucket a period.
 *
 * Home Assistant's own energy collection switches to month buckets for long
 * ranges. We never do: a month bucket cannot express a range that starts or
 * ends mid-month, so summing them would quietly bill the user for all of May
 * and all of July when they asked for 20 May to 15 July — precisely the
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
export const fetchDeviceStatistics = async (hass, devices, period) => {
  const statisticIds = statisticIdsFor(devices);
  // An empty `statistic_ids` is not a request for nothing — it is a request for
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
    series: seriesFrom(devices, buckets, period),
  };
};

/**
 * The period bucket by bucket, added up across the devices asked for.
 *
 * The same fetch has to answer both "what did this cost" and "what did it look
 * like over time", or every chart card costs a second round trip for data
 * already in hand. Rows are oldest first, and a bucket is present if any device
 * recorded one — devices need not share bucket boundaries.
 */
const seriesFrom = (devices, buckets, period) => {
  const byStart = new Map();
  for (const device of devices) {
    for (const [field, concept] of Object.entries(CONCEPTS)) {
      const statistic = buckets?.[statisticIdFor(device.key, concept)];
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
      changeWithin(buckets?.[statisticIdFor(device.key, concept)], period),
    ]),
  );
  return {
    ...device,
    ...totals,
    costSavings: totals.costAtGridPrice - totals.actualCost,
  };
};

/**
 * The buckets a statistic recorded inside the period, as `{start, change}`.
 *
 * The recorder returns every bucket *overlapping* the window, so a request
 * ending at midnight comes back with the following day attached; counting it
 * would bill the user for time they did not ask about. Bucket boundaries are
 * epoch milliseconds on current Home Assistant and ISO strings on older ones —
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
 * The whole house, the Untracked remainder included — that remainder is part of
 * what the household actually paid, and the allocations sum to the real cost
 * (ADR-0002). Deriving the total from the parts also keeps a card's header
 * agreeing with the table beneath it.
 */
const sumRows = (rows) =>
  rows.reduce(
    (totals, row) => {
      for (const field of Object.keys(totals)) totals[field] += row[field];
      return totals;
    },
    { ...zeroed(), costSavings: 0 },
  );
