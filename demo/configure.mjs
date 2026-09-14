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

import { DEVICES, HOUSE } from "./house.mjs";
import { BASE_URL, entityIdForUniqueId } from "./ha-client.mjs";

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
  const deadline = Date.now() + timeoutMs;
  let listed = 0;
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
    const rows = sensor?.attributes?.devices ?? [];
    // Every row must carry its statistic ids too. A row that exists but names
    // no statistics is one the seed would write nothing for, and the card would
    // come up a device short with nothing on the page to say why.
    const ready = rows.filter((row) => Object.keys(row.statistics ?? {}).length > 0);
    listed = ready.length;

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
    const helpers = await countHelpers(token);
    stableHelpers = helpers === previousHelpers ? stableHelpers + 1 : 0;
    previousHelpers = helpers;

    // The devices plus the Untracked remainder the integration derives itself.
    if (listed >= expected + 1 && stableHelpers >= 3) {
      console.log(`  ${helpers} native helpers created, and the count has settled`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(
    `Gave up waiting: ${listed} of ${expected + 1} devices on the devices ` +
      `sensor, ${previousHelpers} helpers and still moving. Seeding against ` +
      "this would produce cards with devices missing.",
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
    return already.entry_id;
  }

  const entry = await createEntry(token);
  const entryId = entry.result.entry_id;
  console.log(`  household configured (${entryId})`);

  for (const device of DEVICES) {
    await addDevice(token, entryId, device);
    console.log(`  + ${device.name}`);
  }

  await waitForDevices(token, DEVICES.length);
  console.log(`  all ${DEVICES.length + 1} devices published, including Untracked`);
  return entryId;
}
