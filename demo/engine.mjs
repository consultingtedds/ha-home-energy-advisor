/**
 * What the accounting engine itself computed, inside the container (HEA-116).
 *
 * Everything else in the end-to-end run asserts against a *seeded* week -
 * figures the engine never produced, written straight into statistics so that a
 * container minutes old has a dashboard worth photographing. That exercises the
 * whole display path and none of the product's actual claim.
 *
 * This is the other half. In engine mode nothing is seeded, so every figure on
 * the page was computed by the engine from the demo house's meters, in a real
 * Home Assistant, exactly as it would be in somebody's home.
 *
 * ## Why it costs what it does
 *
 * The engine closes an interval only once it is `lateness + BUCKET` behind the
 * clock - fifteen minutes plus five - because a device counter that reports
 * every half hour is still describing energy that arrived earlier. A fresh
 * install therefore publishes nothing for twenty minutes, by design.
 *
 * The cards then read *hourly* statistics, which Home Assistant compiles at the
 * top of each hour. So the engine's figures reach a card somewhere between
 * twenty-five and eighty minutes after the instance comes up, depending where
 * the hour boundary falls.
 *
 * None of that is avoidable without changing what the product does, and a test
 * that changed the product in order to pass would be worth nothing. Hence
 * opt-in: the ten-minute run is the one to reach for after a card change, and
 * this is the one to run before a release.
 */

import { BASE_URL, entityIdForUniqueId } from "./ha-client.mjs";

/**
 * How far the parts may sit from the whole before it is a failure.
 *
 * Each figure is published rounded to four decimal places, and a house of ten
 * devices can therefore drift by half an ulp each. This is an order of
 * magnitude above that bound and still far below a cent, so it catches a real
 * allocation error and never a rounding one - the same reasoning the validation
 * week used against a 0.0008 bound.
 */
export const RECONCILIATION_TOLERANCE = 0.005;

/**
 * How far a card's figure may sit from the engine's.
 *
 * Wider, and deliberately so: a card renders to two decimal places, so a cent
 * of disagreement is the display doing its job. Anything beyond that is the
 * recorder, the statistics compiler or the card's own totalling.
 */
export const CARD_TOLERANCE = 0.02;

/**
 * What the engine currently says, per device and for the house.
 *
 * Read from the entity ids the devices sensor publishes, never composed: on the
 * Spanish pass they are Spanish (ADR-0018, HEA-126).
 */
export async function engineTotals(token) {
  const devicesSensor = await entityIdForUniqueId(token, "_devices");
  if (!devicesSensor) return null;

  const stateOf = async (entityId) => {
    if (!entityId) return 0;
    const state = await fetch(`${BASE_URL}/api/states/${entityId}`, {
      headers: { authorization: `Bearer ${token}` },
    }).then((response) => response.json());
    const value = Number.parseFloat(state?.state);
    return Number.isFinite(value) ? value : 0;
  };

  const sensor = await fetch(`${BASE_URL}/api/states/${devicesSensor}`, {
    headers: { authorization: `Bearer ${token}` },
  }).then((response) => response.json());

  const rows = sensor?.attributes?.devices ?? [];
  const wholeHomeRow = sensor?.attributes?.whole_home;
  if (rows.length === 0 || !wholeHomeRow) return null;

  const read = async (row) => ({
    name: row.name,
    cost: await stateOf(row.statistics?.actual_cost),
    energy: await stateOf(row.statistics?.energy_used),
  });

  return {
    devices: await Promise.all(rows.map(read)),
    wholeHome: await read(wholeHomeRow),
  };
}

/**
 * Wait until the engine has closed an interval and published a figure.
 *
 * Polled on the whole-home cost rather than against a clock, because what is
 * being waited for is the engine's own readiness and not a duration. Twenty
 * minutes is the design minimum; the bound is generous so that a slow container
 * reports what it found rather than a timeout.
 */
export async function waitForEngine(token, { timeoutMs = 2_400_000 } = {}) {
  const started = Date.now();
  const deadline = started + timeoutMs;
  let reported = 0;

  while (Date.now() < deadline) {
    const totals = await engineTotals(token).catch(() => null);
    if (totals && totals.wholeHome.cost > 0) {
      const minutes = Math.round((Date.now() - started) / 60000);
      console.log(`  the engine published its first figures after ${minutes} min`);
      return totals;
    }
    const waited = Math.floor((Date.now() - started) / 60000);
    if (waited > reported) {
      reported = waited;
      console.log(`  warming up, ${waited} min elapsed (20 is the design minimum)`);
    }
    await new Promise((resolve) => setTimeout(resolve, 30000));
  }
  return null;
}

/**
 * Wait until Home Assistant has compiled an hourly statistic for the engine.
 *
 * The cards read hourly buckets, and the recorder writes those at the top of
 * each hour. Until one exists the dashboard is correct to show nothing, so this
 * waits for the boundary rather than treating an empty card as a failure.
 */
export async function waitForHourlyStatistics(socket, statisticId, { timeoutMs = 4_800_000 } = {}) {
  const started = Date.now();
  const deadline = started + timeoutMs;
  let reported = 0;

  while (Date.now() < deadline) {
    const dayAgo = new Date(Date.now() - 24 * 3600_000).toISOString();
    const found = await socket
      .send({
        type: "recorder/statistics_during_period",
        start_time: dayAgo,
        statistic_ids: [statisticId],
        period: "hour",
        types: ["change"],
      })
      .catch(() => ({}));
    const buckets = found?.[statisticId] ?? [];
    if (buckets.some((bucket) => Math.abs(bucket.change ?? 0) > 0)) {
      const minutes = Math.round((Date.now() - started) / 60000);
      console.log(`  an hourly statistic appeared after a further ${minutes} min`);
      return true;
    }
    const waited = Math.floor((Date.now() - started) / 60000);
    if (waited > reported) {
      reported = waited;
      console.log(`  waiting for the hour boundary, ${waited} min elapsed`);
    }
    await new Promise((resolve) => setTimeout(resolve, 60000));
  }
  return false;
}
