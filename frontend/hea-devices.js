/**
 * The device set every HEA card enumerates.
 *
 * Nothing in the dashboard names a device (HEA-50). The integration publishes
 * the authoritative list on one sensor (HEA-55), so adding or removing a device
 * is picked up by every view with no dashboard edit - the specific failure of
 * the earlier hand-listed WIP. Which entity that sensor is depends on the
 * instance's language, so it is resolved rather than named; see
 * `resolveSensor`.
 *
 * The `key` on each row identifies a device - for a colour, a series, a sort. It
 * is *not* half of an entity id: `statistics` carries the real id per concept,
 * because Home Assistant names entities in the household's own language and
 * `sensor.<key>_<concept>` therefore exists only on an English install
 * (HEA-89, ADR-0018).
 *
 * Rows arrive in the sensor's snake_case and are normalised here, so a change
 * to that attribute schema is a one-file fix rather than a hunt through cards.
 */

/** The entity id on an English instance that has not renamed it. */
export const DEVICES_SENSOR = "sensor.home_energy_advisor_devices";

/** The integration that owns the sensor, as the entity registry records it. */
const PLATFORM = "home_energy_advisor";

/**
 * Where the list actually lives on this instance.
 *
 * The id above is a starting guess and nothing more. Home Assistant builds an
 * entity id from the entity's *translated* name, so on the Spanish install this
 * integration ships translations for, the sensor is
 * `sensor.home_energy_advisor_dispositivos` and the English id does not exist
 * (ADR-0018). A household that renamed the entity moves it too.
 *
 * This file already said all of that, in its own header, directly above a
 * constant that assumed otherwise. Every card therefore rendered "No devices
 * are being tracked yet." on a Spanish instance with nine tracked devices, and
 * the dashboard strategy laid out that message instead of the whole dashboard.
 * The unit tests could not see it because they build `hass` themselves and put
 * the sensor where the code expects it; the end-to-end run against a real
 * Spanish instance is what found it (HEA-116).
 *
 * Resolved through the entity registry the frontend already holds, matching on
 * the platform that owns the entity rather than on how the attributes look.
 * Another integration publishing a `devices` attribute is not far-fetched, and
 * adopting it would be worse than finding nothing.
 */
const resolveSensor = (hass) => {
  if (hass?.states?.[DEVICES_SENSOR]) return DEVICES_SENSOR;
  const entities = hass?.entities;
  if (!entities) return DEVICES_SENSOR;
  for (const [entityId, entry] of Object.entries(entities)) {
    if (entry?.platform !== PLATFORM) continue;
    if (Array.isArray(hass?.states?.[entityId]?.attributes?.devices)) return entityId;
  }
  return DEVICES_SENSOR;
};

/**
 * The tracked devices plus the Untracked remainder, or `[]` if unavailable.
 *
 * Empty covers a card constructed before its first `hass`, a dashboard placed
 * before the integration is set up, and an unavailable sensor - none of which
 * is an error worth failing a whole view over.
 *
 * @returns {Array<{key: string, name: string, deviceId: string|null,
 *   untracked: boolean, areaId: string|null, areaName: string|null,
 *   floorId: string|null, floorName: string|null}>}
 */
export const readDevices = (hass, entityId = undefined) => {
  const rows = hass?.states?.[entityId ?? resolveSensor(hass)]?.attributes?.devices;
  if (!Array.isArray(rows)) return [];
  return rows.filter((row) => row?.key).map(toDevice);
};

/**
 * The whole-home aggregate, or `null` where the integration publishes none.
 *
 * Deliberately not one of `readDevices`' rows: cards sum that list to get the
 * household total, so a whole-home row there would double every figure. It is
 * here for the figures that belong to no device - the cost range published for
 * the whole home whether or not the per-device ranges are (ADR-0016).
 *
 * @returns {{key: string, name: string, deviceId: string|null}|null}
 */
export const readWholeHome = (hass, entityId = undefined) => {
  const row = hass?.states?.[entityId ?? resolveSensor(hass)]?.attributes?.whole_home;
  return row?.key ? toDevice(row) : null;
};

/**
 * What each label a device carries is called, keyed by its id.
 *
 * The rows carry ids, which is what a filter matches on and what survives a
 * rename; an id is not presentable, though - a label of two words has an id
 * joining them with an underscore - so the names travel beside the list and are resolved
 * once rather than repeated on every row.
 *
 * Empty where the integration is older than labels, which is the case a card
 * must survive: it simply offers no labels to filter by (HEA-95).
 *
 * @returns {Record<string, string>}
 */
export const readLabelNames = (hass, entityId = undefined) => {
  const names = hass?.states?.[entityId ?? resolveSensor(hass)]?.attributes?.labels;
  return names && typeof names === "object" ? names : {};
};

const toDevice = (row) => ({
  key: row.key,
  // A device whose name has not resolved yet still has to label its row.
  name: row.name || row.key,
  deviceId: row.device_id ?? null,
  untracked: Boolean(row.untracked),
  // Passed through as published. An absent concept means the integration has no
  // such entity - the cost bounds are opt-in - and must stay absent rather than
  // become a guessed id (ADR-0018).
  statistics: row.statistics ?? {},
  areaId: row.area_id ?? null,
  areaName: row.area_name ?? null,
  floorId: row.floor_id ?? null,
  floorName: row.floor_name ?? null,
  // Empty rather than absent on an integration published before labels
  // existed: a card may be newer than the instance it is running against, and
  // every reader wants a set to test membership against either way (HEA-95).
  labels: Array.isArray(row.labels) ? row.labels : [],
});
