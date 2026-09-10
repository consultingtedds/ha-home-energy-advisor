/**
 * Take a fresh container from nothing to a house that is ready to photograph.
 *
 * Onboarding, floors, rooms, which sensor sits in which room, and the Energy
 * Dashboard preferences. Everything except the integration itself, which is set
 * up through the browser by `screenshots.mjs` because driving that flow by hand
 * is what produces four of the eleven images (HEA-80).
 *
 * Safe to rerun. Each step checks for what it would create and reuses it, so a
 * rebuild does not end up with two Kitchens.
 *
 *   node demo/setup.mjs
 */

import {
  AREAS,
  DEVICES,
  FLOORS,
  HOUSE,
  UNTRACKED_SOURCES,
} from "./house.mjs";
import {
  HaSocket,
  onboard,
  readSession,
  waitForHomeAssistant,
  writeSession,
} from "./ha-client.mjs";

async function main() {
  await waitForHomeAssistant();

  const existing = readSession();
  const auth = (await onboard()) ?? existing?.auth;
  const token = auth?.access_token;
  if (!token) {
    throw new Error(
      "This instance is already onboarded but the session file is gone. " +
        "Delete demo/config and start again - the demo is meant to be rebuilt.",
    );
  }
  // Written before anything else can throw. Onboarding can only be done once,
  // so a token lost to a later failure costs a rebuild of the whole instance.
  writeSession({ ...existing, token, auth });

  const socket = await HaSocket.connect(token);
  try {
    await assertSourcesExist(socket);
    const floors = await createFloors(socket);
    const areas = await createAreas(socket, floors);
    await placeDevices(socket, areas);
    await setEnergyPreferences(socket);
    writeSession({ token, auth, areas, floors });
  } finally {
    socket.close();
  }

  console.log(`Demo house ready: ${DEVICES.length} devices across ${AREAS.length} rooms.`);
}

/**
 * Fail here rather than in a screenshot.
 *
 * A renamed template sensor otherwise surfaces as a card with nothing in it,
 * three steps later, which reads exactly like a broken card.
 */
async function assertSourcesExist(socket) {
  const states = await socket.send({ type: "get_states" });
  const present = new Set(states.map((state) => state.entity_id));
  const wanted = [
    ...Object.values(HOUSE),
    ...DEVICES.map((device) => device.source),
    ...UNTRACKED_SOURCES,
  ];
  const missing = wanted.filter((entityId) => !present.has(entityId));
  if (missing.length > 0) {
    throw new Error(
      `configuration.yaml does not define: ${missing.join(", ")}. ` +
        "house.mjs and config/configuration.yaml have drifted apart.",
    );
  }
}

async function createFloors(socket) {
  const existing = await socket.send({ type: "config/floor_registry/list" });
  const byName = new Map(existing.map((floor) => [floor.name, floor.floor_id]));
  const floors = {};
  for (const floor of FLOORS) {
    floors[floor.key] =
      byName.get(floor.name) ??
      (
        await socket.send({
          type: "config/floor_registry/create",
          name: floor.name,
          level: floor.level,
        })
      ).floor_id;
  }
  return floors;
}

async function createAreas(socket, floors) {
  const existing = await socket.send({ type: "config/area_registry/list" });
  const byName = new Map(existing.map((area) => [area.name, area.area_id]));
  const areas = {};
  for (const area of AREAS) {
    areas[area.key] =
      byName.get(area.name) ??
      (
        await socket.send({
          type: "config/area_registry/create",
          name: area.name,
          floor_id: floors[area.floor],
        })
      ).area_id;
  }
  return areas;
}

/**
 * Put each source sensor in its room.
 *
 * The integration reads a source's own area before falling back to the area of
 * the device behind it, which is what makes this work at all: a template sensor
 * declared in YAML has no device entry to inherit from. Without this step the
 * cost distribution card has no floors and no rooms to break anything down by.
 */
async function placeDevices(socket, areas) {
  for (const device of DEVICES) {
    await socket.send({
      type: "config/entity_registry/update",
      entity_id: device.source,
      area_id: areas[device.area],
    });
  }
}

/**
 * Fill in the Energy Dashboard, so the integration's first setup screen arrives
 * already answered.
 *
 * The README tells a household that most of the house step is filled in for
 * them if they have set the Energy Dashboard up. That claim only photographs if
 * the demo instance has actually done it.
 */
function setEnergyPreferences(socket) {
  return socket.send({
    type: "energy/save_prefs",
    energy_sources: [
      // Home Assistant 2026.9 replaced the grid source's `flow_from` and
      // `flow_to` arrays with one flat import/export pair, and migrates stored
      // preferences on load. New preferences have to be written in the new
      // shape - the old one is refused outright.
      {
        type: "grid",
        stat_energy_from: HOUSE.gridImport,
        stat_energy_to: HOUSE.gridExport,
        stat_cost: null,
        entity_energy_price: HOUSE.importPrice,
        number_energy_price: null,
        stat_compensation: null,
        entity_energy_price_export: HOUSE.exportPrice,
        number_energy_price_export: null,
        // Required, even though a demo has no billing day to adjust for.
        cost_adjustment_day: 0,
      },
      {
        type: "solar",
        stat_energy_from: HOUSE.generation,
        config_entry_solar_forecast: null,
      },
      {
        type: "battery",
        stat_energy_from: HOUSE.batteryDischarge,
        stat_energy_to: HOUSE.batteryCharge,
      },
    ],
    device_consumption: [],
  });
}

await main();
