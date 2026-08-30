/**
 * The device set every HEA card enumerates.
 *
 * Nothing in the dashboard names a device (HEA-50). The integration publishes
 * the authoritative list on `sensor.home_energy_advisor_devices` (HEA-55), so
 * adding or removing a device is picked up by every view with no dashboard
 * edit - the specific failure of the earlier hand-listed WIP.
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

/** Where the list lives, unless a user renamed the entity. */
export const DEVICES_SENSOR = "sensor.home_energy_advisor_devices";

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
export const readDevices = (hass, entityId = DEVICES_SENSOR) => {
  const rows = hass?.states?.[entityId]?.attributes?.devices;
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
export const readWholeHome = (hass, entityId = DEVICES_SENSOR) => {
  const row = hass?.states?.[entityId]?.attributes?.whole_home;
  return row?.key ? toDevice(row) : null;
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
