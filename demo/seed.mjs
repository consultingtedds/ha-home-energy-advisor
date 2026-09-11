/**
 * Write a fabricated week straight into the recorder.
 *
 * This is the step that makes the harness cheap. The cards read long-term
 * statistics, so the demo never has to run long enough for the engine to
 * accumulate anything: the figures are imported at the shape we want them, and
 * the integration only has to have existed long enough to create the entities
 * they attach to (HEA-80).
 *
 * Two sets of statistics are written, and both are needed. The integration's
 * own sensors are what the cards draw. The demo's *source* sensors are what
 * everything else in Home Assistant draws - the Energy Dashboard, a history
 * page, the chart in any entity's dialog - and without them the house is a
 * facade that falls over the moment a reader clicks anything.
 *
 * The house totals are derived from the devices rather than invented separately,
 * so the demo reconciles: what the meters say the house drew is what the devices
 * plus the untracked remainder actually used.
 *
 *   node demo/seed.mjs
 *
 * Run it after the integration is configured, because it reads entity ids from
 * the devices sensor rather than composing them. Composing one would assume the
 * English name, and Home Assistant builds entity ids from the translated name in
 * the 41 languages that include Spanish, which this integration ships
 * (ADR-0018).
 */

import { DEVICES, HOUSE, TARIFF, UNTRACKED, WINDOW_DAYS } from "./house.mjs";
import { HaSocket, freshAuth } from "./ha-client.mjs";

const DEVICES_SENSOR = "sensor.home_energy_advisor_devices";
const CURRENCY = "EUR";
const HOURS_PER_DAY = 24;

/** Which concepts are measured in kWh; the rest of what we write is money. */
const ENERGY_CONCEPTS = [
  "energy_used",
  "energy_from_grid",
  "energy_from_generation",
  "energy_from_battery",
];

const CONCEPTS = [
  ...ENERGY_CONCEPTS,
  "actual_cost",
  "cost_at_grid_price",
  "cost_savings",
];

async function main() {
  const auth = await freshAuth();
  const socket = await HaSocket.connect(auth.access_token);
  try {
    const rows = await readDeviceRows(socket);
    const hours = hourlyWindow();

    // Clear before writing, always. Home Assistant's import does not replace
    // rows that are already there, so a reseed over an existing week keeps the
    // old figures and reports success: nine of ten devices came back identical
    // to the cent after their profiles had been rewritten.
    const targets = statisticIds(rows);
    await clearAndWait(socket, targets);

    // Per-hour totals for the whole house, accumulated as each device is built.
    const house = { used: zeros(hours), grid: zeros(hours), solar: zeros(hours), battery: zeros(hours) };

    let written = 0;
    for (const row of rows) {
      const series = profileSeries(row.profile, hours);
      addInto(house.used, series.energy_used);
      addInto(house.grid, series.energy_from_grid);
      addInto(house.solar, series.energy_from_generation);
      addInto(house.battery, series.energy_from_battery);
      written += await importConcepts(socket, row.statistics, series, hours);
      written += await importSource(socket, row.profile, series, hours);
    }

    written += await importHouse(socket, house, hours);

    await confirmReadable(socket, targets, hours);

    console.log(
      `Seeded ${written} statistics across ${rows.length} devices, ` +
        `${WINDOW_DAYS} days to ${hours.at(-1).toISOString().slice(0, 10)}.`,
    );
  } finally {
    socket.close();
  }
}

/**
 * The device rows the integration publishes, each carrying its own entity ids.
 *
 * Profiles are matched to rows by name. A row with no profile is the untracked
 * remainder, which the integration creates itself and which is what makes the
 * shares add up to the whole bill.
 */
async function readDeviceRows(socket) {
  const byName = new Map(DEVICES.map((device) => [device.name, device]));
  const wanted = DEVICES.length + 1; // the tracked devices, plus Untracked

  // Polled, because a device added a moment ago is not finished. The sensors
  // behind a power source are derived through an Integral helper, which appears
  // a beat after the device does, and a row without its entity ids is written
  // straight past: the seed then reports a number that looks fine and is seven
  // statistics short.
  // Ninety seconds, because the wait is for the devices sensor to republish
  // rather than for the entities to exist. The entities of the device added
  // last are in the registry within a second; the sensor that names them
  // catches up on its own refresh, which took over half a minute here.
  let rows = [];
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const states = await socket.send({ type: "get_states" });
    const sensor = states.find((state) => state.entity_id === DEVICES_SENSOR);
    if (!sensor) {
      throw new Error(
        `${DEVICES_SENSOR} does not exist. Configure the integration first - ` +
          "the screenshot run drives that flow through the browser.",
      );
    }
    rows = (sensor.attributes.devices ?? []).map((row) => ({
      ...row,
      profile: byName.get(row.name) ?? UNTRACKED,
    }));
    const ready = rows.filter((row) => CONCEPTS.every((key) => row.statistics?.[key]));
    if (rows.length >= wanted && ready.length === rows.length) return rows;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  const missing = rows
    .filter((row) => !CONCEPTS.every((key) => row.statistics?.[key]))
    .map((row) => row.name);
  throw new Error(
    `${rows.length - missing.length} of ${wanted} devices are ready` +
      (missing.length ? `; still without entity ids: ${missing.join(", ")}` : "") +
      ". Seeding now would silently leave them out of every card.",
  );
}

/**
 * Whole hours over the window, ending at the hour just gone.
 *
 * Not through the end of today, which was tried: Home Assistant rejects an
 * imported statistic dated in the future, and rejects the whole series rather
 * than the offending rows, so every device whose window falls later in the day
 * ended up with nothing at all.
 *
 * That leaves today part-finished, which is exactly what a real day looks like
 * part-way through. The screenshot run moves the picker back to a complete day
 * rather than photographing a morning.
 */
function hourlyWindow() {
  const end = new Date();
  end.setMinutes(0, 0, 0);
  const hours = [];
  for (let index = WINDOW_DAYS * HOURS_PER_DAY; index > 0; index -= 1) {
    hours.push(new Date(end.getTime() - index * 3600_000));
  }
  return hours;
}

/** The house meters the seed derives, in the order `importHouse` writes them. */
const HOUSE_METERS = [
  HOUSE.gridImport,
  HOUSE.gridExport,
  HOUSE.generation,
  HOUSE.batteryDischarge,
  HOUSE.batteryCharge,
  HOUSE.houseConsumption,
];

/**
 * Every statistic this seed is responsible for: the integration's own sensors,
 * the demo's source sensors, and the house meters.
 */
function statisticIds(rows) {
  const concepts = rows.flatMap((row) =>
    CONCEPTS.map((concept) => row.statistics?.[concept]).filter(Boolean),
  );
  const sources = rows.map((row) => row.profile.source).filter(Boolean);
  return [...new Set([...concepts, ...sources, ...HOUSE_METERS, HOUSE.importPrice])];
}

/**
 * Clear the statistics, and wait until they are actually gone.
 *
 * The wait is the point. `clear_statistics` returns before the recorder has
 * committed it, so importing straight afterwards leaves rows from the previous
 * seeding sitting in front of the new ones. The new series restarts its running
 * total at zero, so the sum goes *backwards* at the join, and Home Assistant
 * correctly reports that hour as a large negative change - about minus a week's
 * worth. Every card then adds it up and shows negative money and negative
 * energy, which looks like a product defect and is not (HEA-121).
 *
 * A real sensor cannot do this. Its statistics come from Home Assistant's own
 * engine, which handles a counter reset and never writes a decreasing sum. Only
 * imported statistics can go backwards, so only this seed can cause it.
 */
async function clearAndWait(socket, ids) {
  await socket.send({ type: "recorder/clear_statistics", statistic_ids: ids });
  const wide = { start_time: new Date(0).toISOString(), statistic_ids: ids, period: "month" };
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const found = await socket.send({
      type: "recorder/statistics_during_period",
      ...wide,
    });
    if (Object.keys(found).length === 0) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(
    "The old statistics are still there after thirty seconds. Seeding over " +
      "them would make the running totals go backwards and every card negative.",
  );
}

/**
 * Read every statistic back before claiming the seed worked.
 *
 * The recorder commits on its own schedule, so counting the calls that were made
 * says nothing about what is readable. Whatever runs next - the screenshot pass,
 * most obviously - would otherwise photograph a card with a device missing from
 * it, and nothing on the page would say why.
 */
async function confirmReadable(socket, ids, hours) {
  const start = hours[0].toISOString();
  const end = new Date(hours.at(-1).getTime() + 3600_000).toISOString();
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const found = await socket.send({
      type: "recorder/statistics_during_period",
      start_time: start,
      end_time: end,
      statistic_ids: ids,
      period: "day",
    });
    const missing = ids.filter((id) => !found[id]?.length);
    if (missing.length === 0) return;
    if (attempt === 39) {
      throw new Error(
        `${missing.length} statistics never became readable, including ` +
          `${missing.slice(0, 4).join(", ")}. The cards would be short of them.`,
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

const zeros = (hours) => hours.map(() => 0);
const isPeak = (hour) => hour >= TARIFF.peakFrom && hour < TARIFF.peakUntil;
const priceAt = (hour) => (isPeak(hour) ? TARIFF.peak : TARIFF.offPeak);

function addInto(target, values) {
  values.forEach((value, index) => {
    target[index] += value;
  });
}

/**
 * A device's day, as twenty-four fractions that sum to one.
 *
 * Each device runs in a window rather than being spread across the tariff,
 * because *when* it runs is what decides what it saves. Generation is worth
 * something only while the sun is up, and an hour either side of noon is worth
 * far more than one at eight in the evening. Smearing a device across the whole
 * fourteen-hour peak window caps its saving at the average of that window, which
 * is why nothing could reach the ninety per cent a timer really achieves.
 *
 * `baseline` is the share that never stops, for the things that tick over all
 * day whatever else is happening.
 */
function dailyShape(profile) {
  const [from, to] = profile.hours;
  const running = (hour) =>
    from < to ? hour >= from && hour < to : hour >= from || hour < to;
  const baseline = profile.baseline ?? 0;
  // A gentle hump, so no two hours are identical and the charts have life.
  const raw = Array.from({ length: HOURS_PER_DAY }, (_, hour) => {
    const hump = 1 + 0.25 * Math.sin(((hour + 1) / HOURS_PER_DAY) * 2 * Math.PI);
    return ((running(hour) ? 1 - baseline : 0) + baseline / HOURS_PER_DAY) * hump;
  });
  const total = raw.reduce((sum, value) => sum + value, 0);
  return raw.map((value) => value / total);
}

/**
 * Generation is worth nothing at night, so a device's own share of it has to
 * follow the sun rather than its own draw. Whatever it would have taken from
 * generation after dark is bought from the grid instead.
 */
function daylight(hour) {
  if (hour < 7 || hour >= 21) return 0;
  return Math.sin(((hour - 7) / 14) * Math.PI);
}

/** Per-hour figures for one device, by concept. Deltas, not running totals. */
function profileSeries(profile, hours) {
  const perDay = profile.weekKwh / WINDOW_DAYS;
  const shape = dailyShape(profile);
  const series = Object.fromEntries(CONCEPTS.map((concept) => [concept, []]));

  for (const start of hours) {
    const hour = start.getHours();
    const used = perDay * shape[hour];

    const solar = used * profile.share.generation * daylight(hour);
    const battery = used * profile.share.battery;
    const grid = used - solar - battery;

    const price = priceAt(hour);
    // What the household actually paid: grid at the price of the moment, own
    // generation free, battery at what its stored energy cost to put in.
    const stored = TARIFF.offPeak * (profile.storedCostPremium ?? 1);
    const actual = grid * price + battery * stored;
    // The same energy bought off the meter as it was used.
    const atGridPrice = used * price;

    series.energy_used.push(used);
    series.energy_from_grid.push(grid);
    series.energy_from_generation.push(solar);
    series.energy_from_battery.push(battery);
    series.actual_cost.push(actual);
    series.cost_at_grid_price.push(atGridPrice);
    series.cost_savings.push(atGridPrice - actual);
  }
  return series;
}

/** Turn per-hour deltas into the running totals a statistic holds. */
function runningTotal(values, hours) {
  let total = 0;
  return values.map((value, index) => {
    total += value;
    return { start: hours[index].toISOString(), state: round(total), sum: round(total) };
  });
}

/** Import one statistic, either a running total or an hourly average. */
function importOne(socket, statisticId, unit, stats, { mean = false } = {}) {
  return socket.send({
    type: "recorder/import_statistics",
    metadata: {
      has_mean: mean,
      has_sum: !mean,
      name: null,
      source: "recorder",
      statistic_id: statisticId,
      unit_of_measurement: unit,
    },
    stats,
  });
}

/** The integration's own sensors: what the cards draw. */
async function importConcepts(socket, statistics, series, hours) {
  let written = 0;
  for (const concept of CONCEPTS) {
    // A device only publishes the concepts it has. The cost bounds are opt-in,
    // so a missing entity id is the ordinary case, not a fault.
    const statisticId = statistics?.[concept];
    if (!statisticId) continue;
    const unit = ENERGY_CONCEPTS.includes(concept) ? "kWh" : CURRENCY;
    await importOne(socket, statisticId, unit, runningTotal(series[concept], hours));
    written += 1;
  }
  return written;
}

/**
 * The demo's own source sensor, so the rest of Home Assistant has something to
 * show for it. Without this a source's history is however long the container
 * has been up, which is minutes.
 *
 * The untracked remainder has no source sensor, by definition: it is the energy
 * nobody metered.
 */
async function importSource(socket, profile, series, hours) {
  if (!profile.source) return 0;
  if (profile.kind === "power") {
    // A power sensor holds an average in watts, not a total in kWh.
    const watts = series.energy_used.map((kwh, index) => ({
      start: hours[index].toISOString(),
      mean: round(kwh * 1000),
      min: round(kwh * 1000 * 0.6),
      max: round(kwh * 1000 * 1.4),
    }));
    await importOne(socket, profile.source, "W", watts, { mean: true });
    return 1;
  }
  await importOne(socket, profile.source, "kWh", runningTotal(series.energy_used, hours));
  return 1;
}

/**
 * The house meters, derived from what the devices did rather than invented.
 *
 * This is the demo's version of the invariant the product itself has to hold:
 * the meters and the devices describe the same week, so a reader who adds the
 * cards up against the Energy Dashboard finds them agreeing.
 */
async function importHouse(socket, house, hours) {
  // Generation covers what was used from it plus what went to the grid.
  const generation = house.solar.map((used) => used * 1.35);
  const exported = generation.map((made, index) => made - house.solar[index]);
  // Charging a battery costs more than it gives back.
  const charge = house.battery.map((out) => out * 1.12);

  // Paired with HOUSE_METERS by position rather than listed again here, so the
  // set that gets cleared and the set that gets written cannot drift apart.
  const series = [house.grid, exported, generation, house.battery, charge, house.used];
  for (const [index, statisticId] of HOUSE_METERS.entries()) {
    await importOne(socket, statisticId, "kWh", runningTotal(series[index], hours));
  }

  // The tariff itself, so a price chart has a shape and the Energy Dashboard
  // can cost the import it has just been given.
  const importPrice = hours.map((start) => ({
    start: start.toISOString(),
    mean: priceAt(start.getHours()),
    min: TARIFF.offPeak,
    max: TARIFF.peak,
  }));
  await importOne(socket, HOUSE.importPrice, `${CURRENCY}/kWh`, importPrice, { mean: true });

  return HOUSE_METERS.length + 1;
}

const round = (value) => Math.round(value * 1000) / 1000;

await main();
