/**
 * HEA-193: the harness said "still moving" while nothing moved, and counted the
 * missing devices instead of naming them. Both are message defects, so these
 * assert the message.
 */

import { describe, expect, it } from "vitest";

import {
  giveUpReport,
  hasFigures,
  humanMs,
  noted,
  readiness,
  signalLine,
  stillnessMs,
} from "../demo/progress.mjs";

const withFigures = (name) => ({ name, statistics: { energy_used: `sensor.${name}` } });
const listedOnly = (name) => ({ name, statistics: {} });

describe("noted", () => {
  it("keeps the moment a value became what it is, not when it was last read", () => {
    const first = noted(null, 3, 1000);
    const again = noted(first, 3, 9000);
    expect(again.since).toBe(1000);
    expect(stillnessMs(again, 16000)).toBe(15000);
  });

  it("restarts the clock when the value changes", () => {
    const moved = noted(noted(null, 3, 1000), 4, 9000);
    expect(moved).toEqual({ value: 4, since: 9000 });
  });
});

describe("hasFigures", () => {
  it("is false for a row that exists and names no statistics", () => {
    expect(hasFigures(listedOnly("Dishwasher"))).toBe(false);
    expect(hasFigures(withFigures("Dishwasher"))).toBe(true);
  });
});

describe("readiness", () => {
  const expected = ["Dishwasher", "Tumble Dryer", "Car Charger"];

  it("separates a device listed without figures from one not listed at all", () => {
    const state = readiness(expected, [
      withFigures("Dishwasher"),
      listedOnly("Tumble Dryer"),
    ]);
    expect(state.withoutFigures).toEqual(["Tumble Dryer"]);
    expect(state.absent).toEqual(["Car Charger"]);
    expect(state.ready).toBe(1);
    expect(state.wanted).toBe(4);
  });

  it("counts the remainder in what it wants, and names it only by absence", () => {
    const state = readiness(expected, expected.map(withFigures));
    expect(state.absent).toEqual([]);
    expect(state.withoutFigures).toEqual([]);
    expect(state.ready).toBe(3);
    expect(state.remainderMissing).toBe(true);
  });

  it("is satisfied once the remainder arrives too", () => {
    const rows = [...expected.map(withFigures), withFigures("Untracked Energy Devices")];
    const state = readiness(expected, rows);
    expect(state.ready).toBe(4);
    expect(state.remainderMissing).toBe(false);
  });
});

describe("humanMs", () => {
  it("reads as minutes and seconds past a minute", () => {
    expect(humanMs(9000)).toBe("9s");
    expect(humanMs(165000)).toBe("2m 45s");
  });
});

describe("signalLine", () => {
  it("says still arriving only when the value moved recently", () => {
    const line = signalLine("devices", { value: 8, since: 1000 }, 4000);
    expect(line).toContain("still arriving");
    expect(line).toContain("last moved 3s ago");
  });

  it("does not say moving when nothing has moved - the HEA-193 defect", () => {
    const line = signalLine("devices", { value: 3, since: 0 }, 900000);
    expect(line).not.toContain("moving");
    expect(line).not.toContain("arriving");
    expect(line).toBe("  devices: 3 - unchanged for 15m 0s");
  });
});

describe("giveUpReport", () => {
  const base = {
    expectedNames: ["Dishwasher", "Tumble Dryer", "Car Charger"],
    now: 900000,
    waitedMs: 180000,
  };

  it("names both classes of missing device and points at HEA-192", () => {
    const report = giveUpReport({
      ...base,
      rows: [withFigures("Dishwasher"), listedOnly("Tumble Dryer")],
      devices: { value: 1, since: 0 },
      helpers: { value: 1, since: 0 },
    });
    expect(report).toContain("published but carrying no figures: Tumble Dryer");
    expect(report).toContain("HEA-192");
    expect(report).toContain("not published at all: Car Charger");
    expect(report).toContain("devices with figures (of 4): 1 - unchanged for 15m 0s");
  });

  it("reports a stalled house without ever claiming progress", () => {
    const report = giveUpReport({
      ...base,
      rows: [withFigures("Dishwasher")],
      devices: { value: 1, since: 0 },
      helpers: { value: 1, since: 0 },
    });
    expect(report).not.toContain("still");
    expect(report).toContain("unchanged for 15m 0s");
  });

  it("says so when only the remainder is outstanding", () => {
    const report = giveUpReport({
      ...base,
      rows: base.expectedNames.map(withFigures),
      // Within the moving threshold, so this house is genuinely still arriving
      // and the report is allowed to say so.
      devices: { value: 3, since: 895000 },
      helpers: { value: 60, since: 895000 },
    });
    expect(report).toContain("the Untracked remainder has not");
    expect(report).not.toContain("not published at all");
    expect(report).toContain("still arriving");
  });
});
