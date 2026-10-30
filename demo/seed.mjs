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

import {
  BATTERIES,
  BOUND_CONCEPTS,
  DEVICES,
  HOUSE,
  STORED_SOLAR_SHARE,
  TARIFF,
  UNTRACKED,
  WINDOW_DAYS,
} from "./house.mjs";
import { HaSocket, freshAuth } from "./ha-client.mjs";

/**
 * How the devices sensor is found: by the `unique_id` we gave it, never by a
 * composed entity id.
 *
 * The module docstring above already says Home Assistant translates entity ids
 * in the 41 languages that include Spanish. This file then hardcoded the
 * English one, and nothing noticed until the end-to-end run stood a Spanish
 * instance up and the seed insisted the integration was not configured
 * (HEA-116, ADR-0018).
 */
const DEVICES_UNIQUE_ID_SUFFIX = "_devices";
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

/**
 * The cost range, kept out of `CONCEPTS` because it is not required.
 *
 * `CONCEPTS` is what every row must carry before the seed will run - a row short
 * of one would be written past and the card would come up a device short. The
 * bounds cannot join that list: they are opt-in (ADR-0016), the untracked
 * remainder never publishes them at all, and a house configured without them is
 * a house this seed still has to fill.
 *
 * So they are written where they exist and skipped where they do not, and the
 * run says which it did rather than leaving it to be guessed at.
 */
const OPTIONAL_CONCEPTS = BOUND_CONCEPTS;

/**
 * What a device's share of generation could have earned exported, optional for
 * the same reason as the bounds: it exists only where the household has an
 * export price. Written, the devices card shows its Could have earned column
 * beside Saved - the widest the table gets, which is what the full-width layout
 * is there for (ADR-0029).
 */
const FORGONE_CONCEPT = "forgone_export";

/**
 * How much of a device's battery energy was stored sunshine, optional for the
 * same reason again: it is switched off where the household has no battery
 * (ADR-0033). Written, the self-sufficiency headline counts it.
 */
const STORED_SOLAR_CONCEPT = "energy_from_battery_solar";

/**
 * The battery's share of the saving, which only the whole home publishes, and
 * only where there is a battery. Written, the installation card shows its
 * battery part (ADR-0034).
 */
const BATTERY_SAVINGS_CONCEPT = "battery_savings";

/** The whole home's figures this seed writes, and the only ones. */
const WHOLE_HOME_CONCEPTS = ["cost_savings", BATTERY_SAVINGS_CONCEPT];

/** Everything written beyond what every row must carry. */
const WRITTEN_WHERE_PUBLISHED = [
  ...OPTIONAL_CONCEPTS,
  FORGONE_CONCEPT,
  STORED_SOLAR_CONCEPT,
  BATTERY_SAVINGS_CONCEPT,
];

/** Which written concepts are measured in kWh; the rest are money. */
const KWH_CONCEPTS = [...ENERGY_CONCEPTS, STORED_SOLAR_CONCEPT];

async function main() {
  const auth = await freshAuth();
  const socket = await HaSocket.connect(auth.access_token);
  try {
    const { rows, wholeHome } = await readDeviceRows(socket);
    const hours = hourlyWindow();
    const compensation = await exportCompensation(socket);

    // Clear before writing, always. Home Assistant's import does not replace
    // rows that are already there, so a reseed over an existing week keeps the
    // old figures and reports success: nine of ten devices came back identical
    // to the cent after their profiles had been rewritten.
    const targets = [...statisticIds(rows, wholeHome), ...(compensation ? [compensation] : [])];
    await clearAndWait(socket, targets);

    // Per-hour totals for the whole house, accumulated as each device is built.
    const house = {
      used: zeros(hours),
      grid: zeros(hours),
      solar: zeros(hours),
      battery: zeros(hours),
      savings: zeros(hours),
      batterySavings: zeros(hours),
    };

    let written = 0;
    const seriesByKey = new Map();
    for (const row of rows) {
      // A pooled battery is written after the batteries inside it, as their sum.
      if (row.gross) continue;
      const series = profileSeries(row.profile, hours);
      seriesByKey.set(row.key, series);
      // A battery's loss never reached the house, so it is in no house meter.
      if (!row.profile.lost) {
        addInto(house.used, series.energy_used);
        addInto(house.grid, series.energy_from_grid);
        addInto(house.solar, series.energy_from_generation);
        addInto(house.battery, series.energy_from_battery);
        // A loss saves nothing: it is priced at its cost on both sides.
        addInto(house.savings, series.cost_savings);
        addInto(house.batterySavings, series.battery_savings);
      }
      written += await importConcepts(socket, row.statistics, series, hours);
      written += await importSource(socket, row.profile, series, hours);
    }
    for (const pool of rows.filter((row) => row.gross)) {
      const inside = rows
        .filter((row) => row.upstream === pool.key)
        .map((row) => seriesByKey.get(row.key));
      written += await importConcepts(socket, pool.statistics, summed(inside), hours);
    }

    written += await importHouse(socket, house, hours);
    written += await importWholeHome(socket, wholeHome, house, hours);
    written += await importCompensation(socket, compensation, house, hours);

    await confirmReadable(socket, targets, hours);

    console.log(
      `Seeded ${written} statistics across ${rows.length} devices, ` +
        `${WINDOW_DAYS} days to ${hours.at(-1).toISOString().slice(0, 10)}.`,
    );
    // Said out loud, because the alternative is a run that writes no bounds,
    // reports success, and leaves the range column unreachable - which is how
    // this went unnoticed in the first place (HEA-204).
    const bounded = rows.filter((row) =>
      OPTIONAL_CONCEPTS.every((concept) => row.statistics?.[concept]),
    ).length;
    console.log(
      bounded === 0
        ? "  no device publishes a cost range: the option is off, so the range " +
            "column and its rollover cannot appear."
        : `  ${bounded} of them carry a cost range.`,
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
 *
 * The batteries' losses are the exception. Their rows are named in the
 * instance's language around the battery's own name, so each is matched by the
 * name it carries in brackets, and the pool by being published `gross`. They
 * carry only Energy Used and Actual Cost, which is all a battery loss publishes.
 */
async function readDeviceRows(socket) {
  const byName = new Map(DEVICES.map((device) => [device.name, device]));
  // The tracked devices, Untracked, the batteries' pool and each battery in it.
  const wanted = DEVICES.length + 1 + 1 + BATTERIES.length;

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
    const registry = await socket.send({ type: "config/entity_registry/list" });
    const registered = registry.find(
      (entry) =>
        entry.platform === "home_energy_advisor" &&
        entry.unique_id?.endsWith(DEVICES_UNIQUE_ID_SUFFIX),
    );
    if (!registered) {
      throw new Error(
        "The integration's devices sensor is not registered. Configure the " +
          "integration first - `demo/configure.mjs`, or the screenshot run, " +
          "which drives that flow through the browser.",
      );
    }
    const states = await socket.send({ type: "get_states" });
    const sensor = states.find((state) => state.entity_id === registered.entity_id);
    if (!sensor) {
      throw new Error(`${registered.entity_id} is registered but has no state yet.`);
    }
    const published = sensor.attributes.devices ?? [];
    const pool = published.find((row) => row.gross);
    rows = published.map((row) => ({
      ...row,
      profile:
        byName.get(row.name) ??
        (row.upstream && row.upstream === pool?.key ? lossOf(row) : null) ??
        UNTRACKED,
    }));
    const ready = rows.filter((row) => isReady(row, pool));
    if (rows.length >= wanted && ready.length === rows.length) {
      return { rows, wholeHome: sensor.attributes.whole_home };
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  const pool = rows.find((row) => row.gross);
  const missing = rows.filter((row) => !isReady(row, pool)).map((row) => row.name);
  throw new Error(
    `${rows.length - missing.length} of ${wanted} devices are ready` +
      (missing.length ? `; still without entity ids: ${missing.join(", ")}` : "") +
      ". Seeding now would silently leave them out of every card.",
  );
}

/** What a battery loss publishes: the energy it lost, and what that cost. */
const LOSS_CONCEPTS = ["energy_used", "actual_cost"];

/** Whether a row names every statistic it publishes. */
function isReady(row, pool) {
  const isLoss = row.gross || (row.upstream && row.upstream === pool?.key);
  return (isLoss ? LOSS_CONCEPTS : CONCEPTS).every((key) => row.statistics?.[key]);
}

/**
 * A battery's loss as a profile: energy that went in and never came out, spread
 * over the day and priced at what it cost to store.
 */
function lossOf(row) {
  const battery = BATTERIES.find((candidate) => row.name.includes(`(${candidate.name})`));
  if (!battery) return null;
  return {
    weekKwh: battery.lossWeekKwh,
    share: { grid: 0, generation: 0, battery: 1 },
    hours: [0, 24],
    lost: true,
  };
}

/**
 * Several devices' series added hour by hour, concept by concept.
 *
 * Their hours rounded as `runningTotal` rounds them, so the pool's total is
 * exactly the sum of theirs.
 */
function summed(series) {
  return Object.fromEntries(
    Object.keys(series[0]).map((concept) => [
      concept,
      series[0][concept].map((_, hour) =>
        series.reduce((total, one) => total + round(one[concept][hour]), 0),
      ),
    ]),
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

/**
 * For each kWh of its own generation the house used, how much more it exported.
 * Shared by the export meter and what the exports earned, so the two describe
 * the same energy.
 */
const EXPORTED_SHARE = 0.35;

/** The house meters the seed derives, in the order `importHouse` writes them. */
const HOUSE_METERS = [
  HOUSE.gridImportDay,
  HOUSE.gridImportNight,
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
function statisticIds(rows, wholeHome) {
  // The bounds and forgone export are cleared with everything else where they
  // exist. A reseed that left them behind would restart their running totals in
  // front of the old ones, which Home Assistant reads as a week-sized negative
  // hour (HEA-121).
  const concepts = rows.flatMap((row) =>
    [...CONCEPTS, ...WRITTEN_WHERE_PUBLISHED]
      .map((concept) => row.statistics?.[concept])
      .filter(Boolean),
  );
  // Of the whole home's, only the two `importWholeHome` writes: the rest are
  // summed from the rows by the cards, and a figure listed here that is never
  // written is one the readback waits for in vain.
  const wholeHomeIds = WHOLE_HOME_CONCEPTS.map(
    (concept) => wholeHome?.statistics?.[concept],
  ).filter(Boolean);
  const sources = rows.map((row) => row.profile.source).filter(Boolean);
  return [
    ...new Set([...concepts, ...wholeHomeIds, ...sources, ...HOUSE_METERS, HOUSE.dayRate]),
  ];
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
 *
 * Two minutes, raised from forty seconds. The original bound was tuned against
 * an instance that had been sitting idle, and the end-to-end run seeds one that
 * has just created sixty-one native helpers - the recorder is still working
 * through that, and twenty-five statistics were still uncommitted when the old
 * limit expired. Waiting longer costs nothing on a quiet instance, because this
 * returns the moment everything is readable.
 */
const READBACK_ATTEMPTS = 120;

async function confirmReadable(socket, ids, hours) {
  const start = hours[0].toISOString();
  const end = new Date(hours.at(-1).getTime() + 3600_000).toISOString();
  for (let attempt = 0; attempt < READBACK_ATTEMPTS; attempt += 1) {
    const found = await socket.send({
      type: "recorder/statistics_during_period",
      start_time: start,
      end_time: end,
      statistic_ids: ids,
      period: "day",
    });
    const missing = ids.filter((id) => !found[id]?.length);
    if (missing.length === 0) return;
    if (attempt === READBACK_ATTEMPTS - 1) {
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
  const series = Object.fromEntries(
    [...CONCEPTS, ...WRITTEN_WHERE_PUBLISHED].map((concept) => [
      concept,
      [],
    ]),
  );

  for (const start of hours) {
    const hour = start.getHours();
    const used = perDay * shape[hour];

    const solar = used * profile.share.generation * daylight(hour);
    const battery = used * profile.share.battery;
    const grid = used - solar - battery;

    // The part of the battery's energy that was sunshine stored earlier, and
    // the part that was bought.
    const storedSolar = battery * (profile.storedSolar ?? STORED_SOLAR_SHARE);
    const bought = battery - storedSolar;

    const price = priceAt(hour);
    // What the household actually paid: grid at the price of the moment, own
    // generation free whether used at once or stored first, and the battery's
    // bought energy at what it cost to put in.
    const stored = TARIFF.offPeak * (profile.storedCostPremium ?? 1);
    const actual = grid * price + bought * stored;
    // The same energy bought off the meter as it was used.
    const atGridPrice = used * price;

    series.energy_used.push(used);
    series.energy_from_grid.push(grid);
    series.energy_from_generation.push(solar);
    series.energy_from_battery.push(battery);
    series[STORED_SOLAR_CONCEPT].push(storedSolar);
    series.actual_cost.push(actual);
    series.cost_at_grid_price.push(atGridPrice);
    series.cost_savings.push(atGridPrice - actual);
    // The battery's part of that saving, the engine's own split: its energy at
    // the price of the moment, less what the bought part cost to store. No
    // device publishes it; the whole home's is the sum of these (ADR-0034).
    series.battery_savings.push(battery * price - bought * stored);
    // The generation this device used, directly and through the battery,
    // valued at the export rate - the engine's own rule (ADR-0027). One rate
    // all week, so the rate it was stored at is the rate now.
    series.forgone_export.push((solar + storedSolar) * TARIFF.export);

    // The cost range, which must bracket the actual cost rather than merely
    // look like it does. Generation is free whichever way the hour went, stored
    // first or not, so only the energy that came off a meter can be priced
    // differently - and every price it could have carried lies between the
    // cheapest and the dearest the household's tariff and stored energy allow.
    // Pricing all of it at each end therefore contains the real figure by
    // construction, with no fudge factor and nothing to drift out of step with
    // the engine.
    const offMeter = grid + bought;
    const cheapest = Math.min(TARIFF.offPeak, stored);
    const dearest = Math.max(TARIFF.peak, stored);
    series.lowest_possible_cost.push(offMeter * cheapest);
    series.highest_possible_cost.push(offMeter * dearest);
  }
  return series;
}

/**
 * Turn per-hour deltas into the running totals a statistic holds.
 *
 * Each hour is rounded before it is added, not the total after. A rounded
 * total of a sum is not the sum of rounded totals, and the pooled battery is
 * written as the sum of the batteries inside it: rounded the other way, the two
 * disagreed by a thousandth of a kWh, which the cards then drew as a remainder
 * of the pool's own on a Spanish run and not an English one.
 */
function runningTotal(values, hours) {
  let total = 0;
  return values.map((value, index) => {
    total = round(total + round(value));
    return { start: hours[index].toISOString(), state: total, sum: total };
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
  for (const concept of [...CONCEPTS, ...WRITTEN_WHERE_PUBLISHED]) {
    // A device only publishes the concepts it has. The cost bounds are opt-in,
    // forgone export needs an export price and stored solar a battery, so a
    // missing entity id is the ordinary case, not a fault.
    const statisticId = statistics?.[concept];
    if (!statisticId) continue;
    const unit = KWH_CONCEPTS.includes(concept) ? "kWh" : CURRENCY;
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
  const generation = house.solar.map((used) => used * (1 + EXPORTED_SHARE));
  const exported = generation.map((made, index) => made - house.solar[index]);
  // Charging a battery costs more than it gives back.
  const charge = house.battery.map((out) => out * 1.12);

  // A dual-rate meter: the day register carries the import in peak hours and
  // the night register the rest, so each is priced at its own rate.
  const day = house.grid.map((kwh, index) => (isPeak(hours[index].getHours()) ? kwh : 0));
  const night = house.grid.map((kwh, index) => kwh - day[index]);

  // Paired with HOUSE_METERS by position rather than listed again here, so the
  // set that gets cleared and the set that gets written cannot drift apart.
  const series = [day, night, exported, generation, house.battery, charge, house.used];
  for (const [index, statisticId] of HOUSE_METERS.entries()) {
    await importOne(socket, statisticId, "kWh", runningTotal(series[index], hours));
  }

  // The day rate, so the Energy Dashboard can cost the import it has just been
  // given. The night rate is a plain number there, with nothing to record.
  const dayRate = hours.map((start) => ({
    start: start.toISOString(),
    mean: TARIFF.peak,
    min: TARIFF.peak,
    max: TARIFF.peak,
  }));
  await importOne(socket, HOUSE.dayRate, `${CURRENCY}/kWh`, dayRate, { mean: true });

  return HOUSE_METERS.length + 1;
}

/**
 * The whole home's savings and the battery's part of them, as the integration
 * publishes them: the sum of the rows, so the installation card agrees with
 * every other card (ADR-0034).
 *
 * Only these two. Every other whole-home figure the cards read is summed from
 * the rows themselves, and writing it here would only give it a chance to
 * disagree.
 */
async function importWholeHome(socket, wholeHome, house, hours) {
  let written = 0;
  const figures = {
    cost_savings: house.savings,
    [BATTERY_SAVINGS_CONCEPT]: house.batterySavings,
  };
  for (const [concept, values] of Object.entries(figures)) {
    const statisticId = wholeHome?.statistics?.[concept];
    if (!statisticId) continue;
    await importOne(socket, statisticId, CURRENCY, runningTotal(values, hours));
    written += 1;
  }
  return written;
}

/**
 * Where Home Assistant records what the demo's exports earned, if it does.
 *
 * Asked of `energy/info`, as the card asks it, never composed: Home Assistant
 * creates the compensation sensor for an export price itself, named from the
 * export meter, and only once that meter has reported.
 */
async function exportCompensation(socket) {
  const info = await socket.send({ type: "energy/info" });
  const statisticId = info?.cost_sensors?.[HOUSE.gridExport];
  if (!statisticId) {
    console.log(
      "  Home Assistant has no compensation sensor for the export meter yet, " +
        "so the installation card will show no exports.",
    );
  }
  return statisticId;
}

/**
 * What the exports earned: the exported energy `importHouse` derives, at the
 * demo's export rate, written to Home Assistant's own compensation statistic.
 */
async function importCompensation(socket, statisticId, house, hours) {
  if (!statisticId) return 0;
  const earned = house.solar.map((used) => used * EXPORTED_SHARE * TARIFF.export);
  await importOne(socket, statisticId, CURRENCY, runningTotal(earned, hours));
  return 1;
}

const round = (value) => Math.round(value * 1000) / 1000;

await main();
