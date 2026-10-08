/**
 * Set the integration up on the demo instance, through Home Assistant's own
 * config flow API (HEA-116).
 *
 * `screenshots.mjs` drives the same flow through the browser, because four of
 * the README images *are* those screens. Nothing else should: a picker is a
 * search dialog with an overlay and an async filter, and automating it cost an
 * afternoon to get right once. The end-to-end suite needs a configured instance
 * rather than a photographed one, so it asks the API for the same thing and
 * spends its browser time on what only a browser can answer.
 *
 * This is the API the frontend itself calls. A flow driven here is the flow a
 * household walks through, minus the widgets.
 *
 *   import { configureIntegration } from "./configure.mjs";
 *
 * Idempotent: an instance that already has the integration is left alone, so a
 * rerun against a half-built house finishes it rather than failing.
 */

import { BOUND_CONCEPTS, DEVICES, HOUSE } from "./house.mjs";
import { BASE_URL, entityIdForUniqueId } from "./ha-client.mjs";
import { describeHouse } from "./diagnose.mjs";
import { giveUpReport, hasFigures, noted } from "./progress.mjs";

const DOMAIN = "home_energy_advisor";

/** The currency the seeded week is priced in, matching `house.mjs`'s tariff. */
const CURRENCY = "EUR";

async function api(path, token, { method = "GET", body } = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      ...(body ? { "content-type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    throw new Error(`${method} ${path} failed: ${response.status} ${await response.text()}`);
  }
  return response.status === 204 ? null : response.json();
}

/** The integration's config entry, or null if it has not been set up. */
export async function existingEntry(token) {
  const entries = await api(`/api/config/config_entries/entry?domain=${DOMAIN}`, token);
  return entries[0] ?? null;
}

/**
 * A flow result that should have created something, or an error naming why not.
 *
 * A flow that ends in `form` has rejected the input and is showing the reason,
 * and a flow that ends in `abort` has declined to start. Both come back as a
 * perfectly successful HTTP response, so a caller that only checks the status
 * code reports a house it never built - the failure this harness has already
 * made once, in the device loop that cheerfully added nine devices and created
 * none.
 */
function created(result, what) {
  if (result.type === "create_entry") return result;
  const reason = result.errors
    ? JSON.stringify(result.errors)
    : (result.reason ?? result.type);
  throw new Error(`Setting up ${what} did not create anything: ${reason}`);
}

/**
 * Take the house-level step: the meters, the price and the currency.
 *
 * Every field is supplied rather than left to the Energy Dashboard prefill,
 * even though the prefill would answer most of them (HEA-117, HEA-118). The
 * suite is asserting what the integration *produces*, and a setup that depends
 * on a second feature working is a setup that fails for two different reasons.
 */
async function createEntry(token) {
  const started = await api("/api/config/config_entries/flow", token, {
    method: "POST",
    body: { handler: DOMAIN, show_advanced_options: false },
  });
  const result = await api(`/api/config/config_entries/flow/${started.flow_id}`, token, {
    method: "POST",
    body: {
      price_entity: HOUSE.importPrice,
      currency: CURRENCY,
      grid_import_entity: HOUSE.gridImport,
      grid_export_entity: HOUSE.gridExport,
      generation_entity: HOUSE.generation,
      battery_charge_entity: HOUSE.batteryCharge,
      battery_discharge_entity: HOUSE.batteryDischarge,
      house_consumption_entity: HOUSE.houseConsumption,
    },
  });
  return created(result, "the household");
}

/**
 * Add one tracked device as a config subentry.
 *
 * A power-only device goes in under `power_entity`, which is what makes the
 * integration create an Integral helper for it - the demo keeps one on purpose,
 * so that path is exercised rather than described.
 */
async function addDevice(token, entryId, device) {
  const started = await api("/api/config/config_entries/subentries/flow", token, {
    method: "POST",
    body: { handler: [entryId, "device"] },
  });
  const field = device.kind === "power" ? "power_entity" : "energy_entity";
  const result = await api(
    `/api/config/config_entries/subentries/flow/${started.flow_id}`,
    token,
    { method: "POST", body: { name: device.name, [field]: device.source } },
  );
  return created(result, device.name);
}

/**
 * Wait for one device's figures to exist before the next device is added.
 *
 * Carrying statistics is the test, not merely appearing in the list: a row is
 * published as soon as the subentry exists, while the entities behind it are
 * still being registered, and a row naming no statistics is one the seed would
 * write nothing for.
 *
 * **Four minutes, which sounds absurd and is measured.** The first device on
 * this instance took over a minute to publish its figures - a container on a
 * bind-mounted Windows filesystem, reloading the entry and registering sixty-odd
 * entities. Waiting for the answer costs minutes once; guessing short costs a
 * whole run, and every failure this harness produced in a day was a budget that
 * had been guessed rather than measured.
 */
async function waitForOneDevice(token, name, { timeoutMs = 240000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let listed = false;
  while (Date.now() < deadline) {
    const rows = await publishedDevices(token);
    const row = rows.find((candidate) => candidate.name === name);
    listed = row !== undefined;
    if (row && hasFigures(row)) return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  // Which of the two it is decides where to look, so say it rather than leaving
  // both open (HEA-193).
  throw new Error(
    listed
      ? `Gave up waiting for ${name}: it is published in the device list and ` +
        "carries no statistics, so its entities were never registered " +
        "(HEA-192). The seed would write nothing for it."
      : `Gave up waiting for ${name}: it never reached the device list at all. ` +
        "The entry may still be reloading from the device added before it.",
  );
}

/** Every device row the integration is publishing, or `[]` before it does. */
async function publishedDevices(token) {
  const sensor = await entityIdForUniqueId(token, "_devices").catch(() => null);
  if (!sensor) return [];
  const state = await api(`/api/states/${sensor}`, token).catch(() => null);
  return state?.attributes?.devices ?? [];
}

/**
 * Wait until the integration has caught up with the devices just added.
 *
 * Adding a device reloads the config entry, and the sensor that names every
 * device republishes on its own refresh rather than on the reload - measured at
 * over half a minute behind on this instance. The browser flow never noticed,
 * because clicking through nine pickers takes longer than that.
 *
 * Driving the API is fast enough to outrun it, and the failure is ugly: the
 * seed reads the rows, imports statistics against them, and finds a dozen of
 * them unreadable because the entry reloaded underneath the import. So this
 * waits for the answer rather than for a duration, and waits for the *last*
 * device rather than for any.
 */
async function waitForDevices(token, expected, { timeoutMs = 180000 } = {}) {
  const started = Date.now();
  const deadline = started + timeoutMs;
  // Tracked with the moment each count last *changed*, not just its value, so
  // giving up can say how long a thing has been stuck rather than implying it is
  // nearly there. Saying "still moving" while the device count had not moved for
  // a quarter of an hour is the defect this fixes (HEA-193).
  let devices = noted(null, 0, started);
  let helpers = noted(null, -1, started);
  let rows = [];
  let stableHelpers = 0;
  let previousHelpers = -1;

  while (Date.now() < deadline) {
    // Resolved rather than composed, every time round: the id is translated on
    // a Spanish instance, and it does not exist at all until the platform has
    // registered it (ADR-0018).
    const devicesSensor = await entityIdForUniqueId(token, "_devices").catch(() => null);
    const sensor = devicesSensor
      ? await api(`/api/states/${devicesSensor}`, token).catch(() => null)
      : null;
    rows = sensor?.attributes?.devices ?? [];
    // Every row must carry its statistic ids too. A row that exists but names
    // no statistics is one the seed would write nothing for, and the card would
    // come up a device short with nothing on the page to say why.
    const listed = rows.filter(hasFigures).length;
    devices = noted(devices, listed, Date.now());

    // The devices sensor is necessary and nowhere near sufficient. It publishes
    // while the integration is still creating the native helpers that carry the
    // period totals - sixty utility_meters and an Integral on this house, each
    // one a config entry of its own. That work keeps the recorder busy, and a
    // seed that lands in the middle of it imports statistics the recorder never
    // finishes committing: fifty-two of them, in the run that found this.
    //
    // So wait for the helper count to stop moving. Stability is the honest
    // signal; a fixed number would encode today's device list and cycle options
    // into the harness and go quietly wrong the day either changes.
    const count = await countHelpers(token);
    helpers = noted(helpers, count, Date.now());
    stableHelpers = count === previousHelpers ? stableHelpers + 1 : 0;
    previousHelpers = count;

    // The devices plus the Untracked remainder the integration derives itself.
    if (devices.value >= expected + 1 && stableHelpers >= 3) {
      console.log(`  ${count} native helpers created, and the count has settled`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  // Everything a diagnosis needs, before the throw rather than after it: this
  // failure used to be re-investigated from scratch every time it happened.
  const report = giveUpReport({
    expectedNames: DEVICES.map((device) => device.name),
    rows,
    devices,
    helpers,
    now: Date.now(),
    waitedMs: Date.now() - started,
  });
  console.log(report);
  await describeHouse(token);
  throw new Error(report.split("\n")[0]);
}

/**
 * Turn the per-device cost range on, through the options flow a household uses.
 *
 * The range is opt-in (ADR-0016), so a demo house left alone publishes no bound
 * statistics and the column and its rollover cannot appear at all. That is how
 * the reveal reached a release laying the whole table out again on hover: no
 * screenshot and none of the checks here had ever rendered one (HEA-203,
 * HEA-204).
 *
 * On in both passes, English and Spanish. The bound sensors carry translated
 * entity ids like every other concept, and a translated id nothing reads is the
 * fault that rendered every card empty on a Spanish install (ADR-0018) - so the
 * Spanish pass is the only thing that would catch it.
 *
 * The house still exercises the other path: the untracked remainder is derived
 * rather than priced from a device's own energy, so it publishes no bounds and
 * sits in the same table as a row without a range.
 */
async function enableCostBounds(token, entryId) {
  const started = await api("/api/config/config_entries/options/flow", token, {
    method: "POST",
    body: { handler: entryId },
  });
  const menu = await api(
    `/api/config/config_entries/options/flow/${started.flow_id}`,
    token,
    { method: "POST", body: { next_step_id: "cost_bounds" } },
  );
  if (menu.step_id !== "cost_bounds") {
    throw new Error(
      `Expected the cost_bounds form, got ${menu.step_id ?? menu.type}. The ` +
        "options menu has changed shape and this is pointing at the wrong step.",
    );
  }
  created(
    await api(`/api/config/config_entries/options/flow/${started.flow_id}`, token, {
      method: "POST",
      body: { device_cost_bounds: true },
    }),
    "the cost range",
  );
}

/**
 * Wait until every row that can carry bounds names both of them.
 *
 * Enabling the option reloads the entry and registers two more sensors per
 * device, and the devices sensor republishes on its own refresh rather than on
 * the reload. Seeding before that lands writes no bound statistics and reports
 * success, which is the shape of failure this harness keeps producing.
 *
 * Every row *except* the untracked remainder, which publishes no bounds by
 * design - the card agrees, filtering to the rows that offer a range before
 * asking whether all of them are complete.
 */
async function waitForBounds(token, expected, { timeoutMs = 180000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let ready = 0;
  while (Date.now() < deadline) {
    const rows = await publishedDevices(token);
    ready = rows.filter((row) =>
      BOUND_CONCEPTS.every((concept) => row.statistics?.[concept]),
    ).length;
    if (ready >= expected) {
      console.log(`  cost range on, and ${ready} rows name both bounds`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(
    `Gave up waiting for the cost bounds: ${ready} of ${expected} rows name ` +
      "both. Seeding now would leave the range column empty and the rollover " +
      "unreachable, which is the gap HEA-204 exists to close.",
  );
}

/** How many native helpers the integration has created so far. */
async function countHelpers(token) {
  const entries = await api("/api/config/config_entries/entry", token).catch(() => null);
  if (!entries) return -1;
  return entries.filter((entry) => ["utility_meter", "integration"].includes(entry.domain))
    .length;
}

/**
 * Set the integration up, and return its config entry id.
 *
 * Devices are added one at a time rather than in parallel. Each one reloads the
 * config entry as the platform picks it up, and Home Assistant will refuse a
 * flow against an entry that is mid-reload.
 */
export async function configureIntegration(token) {
  const already = await existingEntry(token);
  if (already) {
    console.log(`  integration already set up (${already.entry_id})`);
    await waitForDevices(token, DEVICES.length);
    // Rerun against a house configured before this existed, or by a run that
    // stopped between the two steps. Skipped where it is already on, because
    // submitting the form reloads the entry for nothing.
    if (!already.options?.device_cost_bounds) {
      await enableCostBounds(token, already.entry_id);
    }
    await waitForBounds(token, DEVICES.length);
    return already.entry_id;
  }

  const entry = await createEntry(token);
  const entryId = entry.result.entry_id;
  console.log(`  household configured (${entryId})`);

  // One at a time, and **waiting for each to arrive before adding the next**.
  //
  // Adding a subentry reloads the entry, and a reload on a real instance takes
  // seconds - restoring the snapshot, re-reading every meter, creating helpers.
  // Driving the API is fast enough that the next add lands while the last reload
  // is still running, and on this instance that left seven devices of nine with
  // no entities at all: configured, published in the device list, and carrying
  // nothing (HEA-192). Nine stacked reloads is not a shape a household can
  // produce by clicking, and it is not what this harness is here to test.
  for (const device of DEVICES) {
    await addDevice(token, entryId, device);
    await waitForOneDevice(token, device.name);
    console.log(`  + ${device.name}`);
  }

  await waitForDevices(token, DEVICES.length);
  console.log(`  all ${DEVICES.length + 1} devices published, including Untracked`);

  // Last, once every device exists. Enabling it reloads the entry and registers
  // two more sensors per device, so doing it first would mean doing that work
  // again for each device added afterwards.
  await enableCostBounds(token, entryId);
  await waitForBounds(token, DEVICES.length);
  return entryId;
}
