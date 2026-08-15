/**
 * Nothing in the dashboard may name a device (HEA-50): every card enumerates
 * the HEA-55 sensor, so adding a device makes every view pick it up. These
 * tests pin the sensor's published shape — the rows as they appear on a real
 * instance — because a card that mis-reads them silently shows an empty house.
 */

import { describe, expect, it } from "vitest";

import { DEVICES_SENSOR, readDevices, readWholeHome } from "../hea-devices.js";

/** A row as the HEA-55 sensor publishes it, in its own snake_case. */
const aRow = (key, name, overrides = {}) => ({
  key,
  name,
  device_id: `device-${key}`,
  untracked: false,
  statistics: { actual_cost: `sensor.${key}_actual_cost` },
  area_id: null,
  area_name: null,
  floor_id: null,
  floor_name: null,
  ...overrides,
});

const aHass = (attributes) => ({
  states: { [DEVICES_SENSOR]: { state: "1", attributes } },
});

describe("readDevices", () => {
  it("reads the devices the sensor publishes, with their place in the house", () => {
    // Given — a tracked device sitting in an area on a floor
    const hass = aHass({
      devices: [
        aRow("slow_poll_aircon", "Slow Poll Aircon", {
          area_id: "utility_room",
          area_name: "Utility Room",
          floor_id: "ground_floor",
          floor_name: "Ground Floor",
        }),
      ],
    });

    // When
    const devices = readDevices(hass);

    // Then — `statistics` matters most: it carries the real entity id per
    // concept, because Home Assistant names entities in the household's own
    // language and a composed `sensor.<key>_<concept>` exists only on an
    // English install (HEA-89, ADR-0018). `key` merely identifies the device.
    expect(devices).toEqual([
      {
        key: "slow_poll_aircon",
        name: "Slow Poll Aircon",
        deviceId: "device-slow_poll_aircon",
        untracked: false,
        statistics: { actual_cost: "sensor.slow_poll_aircon_actual_cost" },
        areaId: "utility_room",
        areaName: "Utility Room",
        floorId: "ground_floor",
        floorName: "Ground Floor",
      },
    ]);
  });

  it("asks for nothing when the integration is too old to publish ids", () => {
    // Given — cards updated ahead of the integration, so rows carry no
    // `statistics`. The old shape invited composing an id from the key; there is
    // nothing to compose from now, and inventing one would resurrect the fault
    const hass = aHass({
      devices: [aRow("slow_poll_aircon", "Slow Poll Aircon", { statistics: undefined })],
    });

    // When / Then — empty, so the card fetches nothing and shows nothing, rather
    // than requesting entity ids that may not exist in this household's language
    expect(readDevices(hass)[0].statistics).toEqual({});
  });

  it("keeps the Untracked remainder, flagged", () => {
    // Given — the remainder is real money, not a placeholder to filter out
    const hass = aHass({
      devices: [
        aRow("untracked_energy_devices", "Untracked Energy Devices", {
          untracked: true,
        }),
      ],
    });

    // When / Then — a card decides how to present it; the data layer keeps it
    expect(readDevices(hass)).toEqual([
      expect.objectContaining({
        key: "untracked_energy_devices",
        untracked: true,
      }),
    ]);
  });

  it("preserves the order the sensor published", () => {
    // Given — the sensor sorts by slug; re-sorting here would fight it
    const hass = aHass({
      devices: [aRow("a_device", "A"), aRow("b_device", "B")],
    });

    // When / Then
    expect(readDevices(hass).map((device) => device.key)).toEqual([
      "a_device",
      "b_device",
    ]);
  });

  it("falls back to the slug when a row carries no name", () => {
    // Given — a device whose name has not resolved from the registry yet
    const hass = aHass({ devices: [aRow("slow_poll_aircon", null)] });

    // When / Then — a card must have something to label the row with
    expect(readDevices(hass)[0].name).toBe("slow_poll_aircon");
  });

  it("skips a row with no slug, since no statistic id can be built from it", () => {
    // Given — a malformed row alongside a good one
    const hass = aHass({
      devices: [{ name: "No key at all" }, aRow("slow_poll_aircon", "Aircon")],
    });

    // When / Then — one bad row must not cost the dashboard the other devices
    expect(readDevices(hass).map((device) => device.key)).toEqual([
      "slow_poll_aircon",
    ]);
  });

  it("is empty when the integration is not loaded", () => {
    // Given / When / Then — a card can be placed before HEA is set up, and is
    // constructed before its first hass update
    expect(readDevices(undefined)).toEqual([]);
    expect(readDevices({})).toEqual([]);
    expect(readDevices({ states: {} })).toEqual([]);
  });

  it("is empty when the sensor is unavailable and carries no device list", () => {
    // Given — an unavailable entity keeps its state but loses its attributes
    // When / Then
    expect(readDevices(aHass({}))).toEqual([]);
    expect(readDevices(aHass({ devices: "not a list" }))).toEqual([]);
  });

  it("reads a sensor that a user renamed", () => {
    // Given — entity ids are the user's to change
    const hass = {
      states: {
        "sensor.hea_devices": {
          state: "1",
          attributes: { devices: [aRow("slow_poll_aircon", "Aircon")] },
        },
      },
    };

    // When / Then
    expect(readDevices(hass, "sensor.hea_devices")).toHaveLength(1);
  });

  it("never returns the whole home as one of the devices", () => {
    // Given — the whole home rides the same sensor, and every card sums this
    // list to get the household total. A row here would double every figure.
    const hass = aHass({
      devices: [aRow("slow_poll_aircon", "Aircon")],
      whole_home: aRow("whole_home", "Whole Home"),
    });

    // When / Then
    expect(readDevices(hass).map((device) => device.key)).toEqual([
      "slow_poll_aircon",
    ]);
  });
});

describe("readWholeHome", () => {
  it("reads the whole-home slug, for figures that belong to no device", () => {
    // Given — the cost range is published for the whole home whether or not the
    // per-device ranges are (ADR-0016), so a card must be able to find it
    const hass = aHass({
      devices: [aRow("slow_poll_aircon", "Aircon")],
      whole_home: aRow("whole_home", "Whole Home"),
    });

    // When / Then — resolved out of the registry, not guessed: a household that
    // renamed the entity would otherwise silently lose the figure
    expect(readWholeHome(hass)).toEqual(
      expect.objectContaining({ key: "whole_home", name: "Whole Home" }),
    );
  });

  it("is null on an integration too old to publish it", () => {
    // Given / When / Then — a dashboard resource can outrun the integration, so
    // the absence has to be a value a card can render nothing for
    expect(readWholeHome(aHass({ devices: [] }))).toBeNull();
    expect(readWholeHome(undefined)).toBeNull();
    expect(readWholeHome(aHass({ whole_home: { name: "no key" } }))).toBeNull();
  });
});
