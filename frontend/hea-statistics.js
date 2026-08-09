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
});

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
  return { period, devices: rows, totals: sumRows(rows) };
};

const totalsFor = (device, buckets, period) => {
  const changeIn = (concept) =>
    changeWithin(buckets?.[statisticIdFor(device.key, concept)], period);
  const actualCost = changeIn(CONCEPTS.actualCost);
  const costAtGridPrice = changeIn(CONCEPTS.costAtGridPrice);
  return {
    ...device,
    energyUsed: changeIn(CONCEPTS.energyUsed),
    actualCost,
    costAtGridPrice,
    costSavings: costAtGridPrice - actualCost,
  };
};

/**
 * The change a statistic recorded inside the period.
 *
 * The recorder returns every bucket *overlapping* the window, so a request
 * ending at midnight comes back with the following day attached; counting it
 * would bill the user for time they did not ask about. Bucket boundaries are
 * epoch milliseconds on current Home Assistant and ISO strings on older ones —
 * both are accepted, since a household on an older release should still see
 * its costs.
 */
const changeWithin = (statistic, { start, end }) => {
  if (!Array.isArray(statistic)) return 0;
  let total = 0;
  for (const bucket of statistic) {
    const bucketStart = new Date(bucket.start).getTime();
    if (bucketStart < start.getTime() || bucketStart >= end.getTime()) continue;
    // A gap in the statistics is reported as null; it is unknown, not zero.
    if (typeof bucket.change === "number") total += bucket.change;
  }
  return total;
};

/**
 * The whole house, the Untracked remainder included — that remainder is part of
 * what the household actually paid, and the allocations sum to the real cost
 * (ADR-0002). Deriving the total from the parts also keeps a card's header
 * agreeing with the table beneath it.
 */
const sumRows = (rows) =>
  rows.reduce(
    (totals, row) => ({
      energyUsed: totals.energyUsed + row.energyUsed,
      actualCost: totals.actualCost + row.actualCost,
      costAtGridPrice: totals.costAtGridPrice + row.costAtGridPrice,
      costSavings: totals.costSavings + row.costSavings,
    }),
    { energyUsed: 0, actualCost: 0, costAtGridPrice: 0, costSavings: 0 },
  );
