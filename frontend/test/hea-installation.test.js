/**
 * What the installation earned, as arithmetic and as lookups (HEA-241, ADR-0034).
 *
 * The figures are the whole home's Cost Savings and Battery Savings, Battery
 * Losses' Paid, and the Energy Dashboard's own export compensation. Each part is
 * tested against a day measured on the reference home rather than numbers chosen
 * to come out round: 4.04 saved, 1.124 of it by the battery, nothing lost, and
 * 0.225 earned by exports, which is 4.265 altogether.
 */

import { describe, expect, it } from "vitest";

import {
  compensationStatistics,
  installationReturn,
  installationStatistics,
} from "../hea-installation.js";
import { MAY, aDeviceRow } from "./doubles.js";

const PERIOD = { start: new Date(2026, 4, 1), end: new Date(2026, 5, 1) };

const WHOLE_HOME = aDeviceRow("whole_home", "Whole Home", false, {
  cost_savings: "sensor.whole_home_cost_savings",
  battery_savings: "sensor.whole_home_battery_savings",
});
// Battery Losses publishes no Would have paid: its energy was bought and is gone.
const LOSSES = aDeviceRow("battery_losses", "Battery Losses", false, {
  actual_cost: "sensor.battery_losses_actual_cost",
  energy_used: "sensor.battery_losses_energy_used",
});
const AIRCON = aDeviceRow("slow_poll_aircon", "Slow Poll Aircon");

const day = (change, at = MAY) => [{ start: at.getTime(), change }];

const MEASURED_DAY = {
  "sensor.whole_home_cost_savings": day(4.04),
  "sensor.whole_home_battery_savings": day(1.124),
  "sensor.battery_losses_actual_cost": day(0),
  "sensor.grid_export_compensation": day(0.225),
};

const ALL_PARTS = {
  costSavings: "sensor.whole_home_cost_savings",
  batterySavings: "sensor.whole_home_battery_savings",
  lossesPaid: ["sensor.battery_losses_actual_cost"],
  exportsEarned: ["sensor.grid_export_compensation"],
};

describe("the three parts", () => {
  it("adds a measured day up the way the household would", () => {
    const earned = installationReturn(MEASURED_DAY, ALL_PARTS, PERIOD);

    // Generation saved is what the savings were less the battery's share of them
    expect(earned.generationSaved).toBeCloseTo(2.916, 10);
    expect(earned.batterySaved).toBeCloseTo(1.124, 10);
    expect(earned.exportsEarned).toBeCloseTo(0.225, 10);
    expect(earned.total).toBeCloseTo(4.265, 10);
  });

  it("takes what the battery lost off the battery's part, not off the total's others", () => {
    const lossy = {
      ...MEASURED_DAY,
      "sensor.battery_losses_actual_cost": day(0.4),
    };

    const earned = installationReturn(lossy, ALL_PARTS, PERIOD);

    // The generation and the exports did not lose anything to the battery
    expect(earned.generationSaved).toBeCloseTo(2.916, 10);
    expect(earned.exportsEarned).toBeCloseTo(0.225, 10);
    expect(earned.batterySaved).toBeCloseTo(0.724, 10);
    expect(earned.total).toBeCloseTo(3.865, 10);
  });

  it("lets the battery's part go below zero rather than flattering it", () => {
    // A battery charged dear, discharged cheap and losing a lot in between
    const losing = {
      ...MEASURED_DAY,
      "sensor.whole_home_battery_savings": day(0.1),
      "sensor.battery_losses_actual_cost": day(0.35),
    };

    const earned = installationReturn(losing, ALL_PARTS, PERIOD);

    expect(earned.batterySaved).toBeCloseTo(-0.25, 10);
    expect(earned.generationSaved).toBeCloseTo(3.94, 10);
  });

  it("sums every grid source's exports and every top-level loss", () => {
    const parts = {
      ...ALL_PARTS,
      lossesPaid: ["sensor.battery_losses_actual_cost", "sensor.second_battery_losses"],
      exportsEarned: ["sensor.grid_export_compensation", "sensor.night_export_compensation"],
    };
    const buckets = {
      ...MEASURED_DAY,
      "sensor.battery_losses_actual_cost": day(0.1),
      "sensor.second_battery_losses": day(0.05),
      "sensor.night_export_compensation": day(0.075),
    };

    const earned = installationReturn(buckets, parts, PERIOD);

    expect(earned.batterySaved).toBeCloseTo(0.974, 10);
    expect(earned.exportsEarned).toBeCloseTo(0.3, 10);
  });

  it("counts only what was recorded inside the period", () => {
    // The recorder hands back every bucket overlapping the window, so the day
    // after the period ends arrives attached to it
    const after = new Date(2026, 5, 1);
    const buckets = {
      ...MEASURED_DAY,
      "sensor.grid_export_compensation": [
        { start: MAY.getTime(), change: 0.225 },
        { start: after.getTime(), change: 9 },
      ],
    };

    expect(installationReturn(buckets, ALL_PARTS, PERIOD).exportsEarned).toBeCloseTo(
      0.225,
      10,
    );
  });
});

describe("a part that does not apply", () => {
  it("leaves out the battery's part for a home with no battery", () => {
    const panelsOnly = { ...ALL_PARTS, batterySavings: undefined, lossesPaid: [] };

    const earned = installationReturn(MEASURED_DAY, panelsOnly, PERIOD);

    // All the savings were the generation's, with no battery to share them
    expect(earned.batterySaved).toBeUndefined();
    expect(earned.generationSaved).toBeCloseTo(4.04, 10);
    expect(earned.total).toBeCloseTo(4.265, 10);
  });

  it("leaves out the exports for a home whose Energy Dashboard records none", () => {
    const noExports = { ...ALL_PARTS, exportsEarned: [] };

    const earned = installationReturn(MEASURED_DAY, noExports, PERIOD);

    expect(earned.exportsEarned).toBeUndefined();
    expect(earned.total).toBeCloseTo(4.04, 10);
  });
});

describe("which statistics", () => {
  it("reads the whole home's savings and every top-level battery loss", () => {
    // A pooled battery publishes its losses gross, each battery's share inside it
    const share = { ...aDeviceRow("garage_battery_losses", "Garage Battery Losses", false, {
      actual_cost: "sensor.garage_battery_losses_actual_cost",
    }), upstream: "battery_losses" };

    expect(installationStatistics(WHOLE_HOME, [AIRCON, LOSSES, share])).toEqual({
      costSavings: "sensor.whole_home_cost_savings",
      batterySavings: "sensor.whole_home_battery_savings",
      lossesPaid: ["sensor.battery_losses_actual_cost"],
    });
  });

  it("has no battery part for a home with no battery savings figure", () => {
    const panelsOnly = aDeviceRow("whole_home", "Whole Home", false, {
      cost_savings: "sensor.whole_home_cost_savings",
    });

    expect(installationStatistics(panelsOnly, [AIRCON])).toEqual({
      costSavings: "sensor.whole_home_cost_savings",
      batterySavings: undefined,
      lossesPaid: [],
    });
  });
});

describe("where the exports are recorded", () => {
  it("uses the compensation Home Assistant created for an export price", () => {
    // The newer shape, as the reference home holds it: an export price and no
    // compensation statistic of the household's own
    const prefs = {
      energy_sources: [
        {
          type: "grid",
          stat_energy_from: "sensor.grid_import",
          stat_energy_to: "sensor.grid_export",
          stat_compensation: null,
          entity_energy_price_export: "sensor.export_price",
        },
      ],
    };
    const info = {
      cost_sensors: {
        "sensor.grid_import": "sensor.grid_import_cost",
        "sensor.grid_export": "sensor.grid_export_compensation",
      },
    };

    expect(compensationStatistics(prefs, info)).toEqual([
      "sensor.grid_export_compensation",
    ]);
  });

  it("prefers a compensation statistic the household provides", () => {
    const prefs = {
      energy_sources: [
        {
          type: "grid",
          stat_energy_to: "sensor.grid_export",
          stat_compensation: "sensor.retailer_export_credit",
        },
      ],
    };
    const info = { cost_sensors: { "sensor.grid_export": "sensor.grid_export_compensation" } };

    expect(compensationStatistics(prefs, info)).toEqual(["sensor.retailer_export_credit"]);
  });

  it("reads the older flow lists just the same", () => {
    const prefs = {
      energy_sources: [
        {
          type: "grid",
          flow_from: [{ stat_energy_from: "sensor.grid_import" }],
          flow_to: [
            { stat_energy_to: "sensor.grid_export" },
            { stat_energy_to: "sensor.second_export", stat_compensation: "sensor.second_credit" },
          ],
        },
      ],
    };
    const info = { cost_sensors: { "sensor.grid_export": "sensor.grid_export_compensation" } };

    expect(compensationStatistics(prefs, info)).toEqual([
      "sensor.grid_export_compensation",
      "sensor.second_credit",
    ]);
  });

  it("finds nothing for an export meter with no price, and for no export meter", () => {
    const prefs = {
      energy_sources: [
        { type: "solar", stat_energy_from: "sensor.panels" },
        { type: "grid", stat_energy_from: "sensor.grid_import", stat_energy_to: "sensor.grid_export" },
        { type: "grid", stat_energy_from: "sensor.daily_standing_charge", stat_energy_to: null },
      ],
    };

    // Home Assistant creates no compensation sensor without an export price
    expect(compensationStatistics(prefs, { cost_sensors: {} })).toEqual([]);
    expect(compensationStatistics(undefined, undefined)).toEqual([]);
  });

  it("names one statistic once, however many sources lead to it", () => {
    const prefs = {
      energy_sources: [
        { type: "grid", stat_energy_to: "sensor.grid_export", stat_compensation: "sensor.credit" },
        { type: "grid", stat_energy_to: "sensor.other_export", stat_compensation: "sensor.credit" },
      ],
    };

    expect(compensationStatistics(prefs, {})).toEqual(["sensor.credit"]);
  });
});
