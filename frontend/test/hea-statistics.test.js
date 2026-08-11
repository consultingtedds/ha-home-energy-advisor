/**
 * The data layer every HEA card sits on: per-device figures for whatever period
 * the user picked (HEA-50). Long-term statistics are the only substrate that
 * can answer an arbitrary range (ADR-0008), and the request and response shapes
 * below were measured against the live instance on 2026-08-09, not assumed.
 */

import { describe, expect, it, vi } from "vitest";

import {
  CONCEPTS,
  bucketPeriodFor,
  fetchDeviceStatistics,
  statisticIdsFor,
} from "../hea-statistics.js";

const MAY = new Date("2026-05-20T00:00:00Z");
const JULY = new Date("2026-07-15T00:00:00Z");
const aPeriod = (start = MAY, end = JULY) => ({ start, end, fallback: false });

const aDevice = (key, name, overrides = {}) => ({
  key,
  name,
  untracked: false,
  ...overrides,
});

const AIRCON = aDevice("slow_poll_aircon", "Slow Poll Aircon");

/** A day of buckets, as the recorder returns them: epoch ms and a delta. */
const aBucket = (start, change) => ({
  start: start.getTime(),
  end: start.getTime() + 86400000,
  change,
});

/**
 * Home Assistant answers on `hass.callWS` — the same tier of the hass object as
 * `states` and `callService`, and deliberately not the frontend internals the
 * energy-collection adapter fronts (ADR-0012 decision 5).
 */
const aHass = (response = {}) => ({
  callWS: vi.fn().mockResolvedValue(response),
});

describe("statisticIdsFor", () => {
  it("builds the three statistic ids a device is accounted by", () => {
    // Given / When / Then — `sensor.<slug>_<concept>`, the slug the HEA-55
    // sensor resolved out of the entity registry rather than one guessed here
    expect(statisticIdsFor([AIRCON])).toEqual([
      "sensor.slow_poll_aircon_energy_used",
      "sensor.slow_poll_aircon_actual_cost",
      "sensor.slow_poll_aircon_cost_at_grid_price",
    ]);
  });

  it("does not ask for Cost Savings, which is a subtraction", () => {
    // Given / When
    const ids = statisticIdsFor([AIRCON]);

    // Then — deriving it is what guarantees the stacked bar's segments sum to
    // the whole (ADR-0012), rather than three numbers that nearly agree
    expect(ids).not.toContain("sensor.slow_poll_aircon_cost_savings");
  });

  it("covers every device, including the Untracked remainder", () => {
    // Given
    const devices = [AIRCON, aDevice("untracked_energy_devices", "Untracked", { untracked: true })];

    // When / Then
    expect(statisticIdsFor(devices)).toHaveLength(6);
  });

  it("asks for nothing when there are no devices", () => {
    // Given / When / Then
    expect(statisticIdsFor([])).toEqual([]);
  });
});

describe("bucketPeriodFor", () => {
  it("buckets a day or two by hour, so a short range still has shape", () => {
    // Given — the picker's "today", part-way through the day
    const period = aPeriod(
      new Date("2026-08-09T00:00:00Z"),
      new Date("2026-08-09T14:30:00Z"),
    );

    // When / Then
    expect(bucketPeriodFor(period)).toBe("hour");
  });

  it("buckets a longer range by day", () => {
    // Given / When / Then
    expect(
      bucketPeriodFor(
        aPeriod(new Date("2026-08-01T00:00:00Z"), new Date("2026-08-09T00:00:00Z")),
      ),
    ).toBe("day");
  });

  it("never buckets by month, however long the range", () => {
    // Given — "20 May to 15 July", the question this ticket exists to answer.
    // Home Assistant's own energy collection would switch to month buckets
    // here; month buckets cannot express a range that starts and ends
    // mid-month, so summing them would quietly bill all of May and all of July.
    // Day buckets align with the picker's local-midnight boundaries at any
    // length, so they stay exact.
    // When / Then
    expect(bucketPeriodFor(aPeriod())).toBe("day");
    expect(
      bucketPeriodFor(
        aPeriod(new Date("2020-01-01T00:00:00Z"), new Date("2026-01-01T00:00:00Z")),
      ),
    ).toBe("day");
  });
});

describe("fetchDeviceStatistics", () => {
  const threeDays = aPeriod(
    new Date("2026-08-04T00:00:00Z"),
    new Date("2026-08-07T00:00:00Z"),
  );
  const DAY_ONE = new Date("2026-08-04T00:00:00Z");
  const DAY_TWO = new Date("2026-08-05T00:00:00Z");

  const airconResponse = {
    "sensor.slow_poll_aircon_energy_used": [
      aBucket(DAY_ONE, 6.2),
      aBucket(DAY_TWO, 8.0),
    ],
    "sensor.slow_poll_aircon_actual_cost": [
      aBucket(DAY_ONE, 0.1),
      aBucket(DAY_TWO, 0.2),
    ],
    "sensor.slow_poll_aircon_cost_at_grid_price": [
      aBucket(DAY_ONE, 1.1),
      aBucket(DAY_TWO, 1.4),
    ],
  };

  it("asks the recorder for the change over the picked period", async () => {
    // Given
    const hass = aHass(airconResponse);

    // When
    await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then — `change` is the per-bucket delta of a cumulative meter; asking for
    // `sum` instead would hand back the meter reading, not the period's cost
    expect(hass.callWS).toHaveBeenCalledWith({
      type: "recorder/statistics_during_period",
      start_time: threeDays.start.toISOString(),
      end_time: threeDays.end.toISOString(),
      statistic_ids: statisticIdsFor([AIRCON]),
      period: "day",
      types: ["change"],
    });
  });

  it("totals each device over the period, and derives what was saved", async () => {
    // Given
    const hass = aHass(airconResponse);

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then — saved is Cost at Grid Price less Actual Cost, so the three
    // reconcile by construction
    expect(result.devices).toEqual([
      expect.objectContaining({
        key: "slow_poll_aircon",
        name: "Slow Poll Aircon",
        energyUsed: 14.2,
        actualCost: expect.closeTo(0.3, 10),
        costAtGridPrice: expect.closeTo(2.5, 10),
        costSavings: expect.closeTo(2.2, 10),
      }),
    ]);
  });

  it("totals the whole house, the Untracked remainder included", async () => {
    // Given — the remainder is part of what the household actually paid, and
    // the invariant is that the allocations sum to the real cost (ADR-0002)
    const untracked = aDevice("untracked_energy_devices", "Untracked", {
      untracked: true,
    });
    const hass = aHass({
      ...airconResponse,
      "sensor.untracked_energy_devices_energy_used": [aBucket(DAY_ONE, 30)],
      "sensor.untracked_energy_devices_actual_cost": [aBucket(DAY_ONE, 4)],
      "sensor.untracked_energy_devices_cost_at_grid_price": [aBucket(DAY_ONE, 5)],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON, untracked], threeDays);

    // Then
    expect(result.totals).toEqual({
      energyUsed: 44.2,
      actualCost: expect.closeTo(4.3, 10),
      costAtGridPrice: expect.closeTo(7.5, 10),
      costSavings: expect.closeTo(3.2, 10),
    });
  });

  it("carries the period through, so a card can say it is a default range", async () => {
    // Given — no picker on the dashboard
    const fallback = { ...threeDays, fallback: true };

    // When
    const result = await fetchDeviceStatistics(aHass(airconResponse), [AIRCON], fallback);

    // Then
    expect(result.period).toEqual(fallback);
  });

  it("ignores a bucket that starts where the period ends", async () => {
    // Given — the recorder returns any bucket *overlapping* the window, so a
    // request ending at midnight comes back with the whole of the next day
    // attached; counting it would bill the user for time they did not ask about
    const hass = aHass({
      ...airconResponse,
      "sensor.slow_poll_aircon_energy_used": [
        aBucket(DAY_ONE, 6.2),
        aBucket(DAY_TWO, 8.0),
        aBucket(threeDays.end, 999),
      ],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then
    expect(result.devices[0].energyUsed).toBe(14.2);
  });

  it("ignores a bucket that starts before the period", async () => {
    // Given
    const hass = aHass({
      ...airconResponse,
      "sensor.slow_poll_aircon_energy_used": [
        aBucket(new Date("2026-08-03T00:00:00Z"), 999),
        aBucket(DAY_ONE, 6.2),
        aBucket(DAY_TWO, 8.0),
      ],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then
    expect(result.devices[0].energyUsed).toBe(14.2);
  });

  it("reads the recorder's older ISO bucket boundaries too", async () => {
    // Given — the recorder moved from ISO strings to epoch milliseconds; a
    // household on an older Home Assistant should still see its costs
    const hass = aHass({
      "sensor.slow_poll_aircon_actual_cost": [
        { start: DAY_ONE.toISOString(), end: DAY_TWO.toISOString(), change: 0.1 },
      ],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then
    expect(result.devices[0].actualCost).toBe(0.1);
  });

  it("reports zero for a device the recorder knows nothing about", async () => {
    // Given — a device added today, over a range that predates it
    const newDevice = aDevice("new_heater", "New Heater");
    const hass = aHass(airconResponse);

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON, newDevice], threeDays);

    // Then — zero, and the devices around it are unaffected
    expect(result.devices[1]).toEqual(
      expect.objectContaining({
        key: "new_heater",
        energyUsed: 0,
        actualCost: 0,
        costAtGridPrice: 0,
        costSavings: 0,
      }),
    );
    expect(result.devices[0].energyUsed).toBe(14.2);
  });

  it("skips a bucket carrying no change rather than counting it as zero-cost", async () => {
    // Given — a gap in the statistics, which the recorder reports as null
    const hass = aHass({
      "sensor.slow_poll_aircon_actual_cost": [
        aBucket(DAY_ONE, 0.1),
        { ...aBucket(DAY_TWO, null), change: null },
      ],
    });

    // When / Then
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);
    expect(result.devices[0].actualCost).toBe(0.1);
  });

  it("asks the recorder nothing when there are no devices", async () => {
    // Given — HEA set up but with no devices tracked yet. An empty
    // statistic_ids list is not a request for nothing; it is a request for
    // every statistic in the database.
    const hass = aHass();

    // When
    const result = await fetchDeviceStatistics(hass, [], threeDays);

    // Then
    expect(hass.callWS).not.toHaveBeenCalled();
    expect(result.devices).toEqual([]);
    expect(result.totals.actualCost).toBe(0);
  });

  it("keeps each device's place in the house, for the views that group by it", async () => {
    // Given — the distribution view groups device → room → floor (HEA-58)
    const located = aDevice("slow_poll_aircon", "Slow Poll Aircon", {
      areaName: "Utility Room",
      floorName: "Ground Floor",
    });

    // When
    const result = await fetchDeviceStatistics(aHass(airconResponse), [located], threeDays);

    // Then
    expect(result.devices[0]).toEqual(
      expect.objectContaining({
        areaName: "Utility Room",
        floorName: "Ground Floor",
        untracked: false,
      }),
    );
  });

  it("returns the period bucket by bucket, for the charts to draw", async () => {
    // Given — the same fetch has to feed a total and a shape over time, or
    // every chart card costs a second round trip for data already in hand
    const hass = aHass(airconResponse);

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then — one row per bucket, oldest first
    expect(result.series).toEqual([
      expect.objectContaining({ start: DAY_ONE, energyUsed: 6.2 }),
      expect.objectContaining({ start: DAY_TWO, energyUsed: 8.0 }),
    ]);
  });

  it("adds the devices together within each bucket", async () => {
    // Given — the chart is of the house, or of whatever the filter selected
    const other = aDevice("fine_meter_aircon", "Fine Meter Aircon");
    const hass = aHass({
      ...airconResponse,
      "sensor.fine_meter_aircon_energy_used": [aBucket(DAY_ONE, 1)],
      "sensor.fine_meter_aircon_actual_cost": [aBucket(DAY_ONE, 0.5)],
      "sensor.fine_meter_aircon_cost_at_grid_price": [aBucket(DAY_ONE, 2.5)],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON, other], threeDays);

    // Then — day one carries both devices, day two only the one that ran
    expect(result.series[0].actualCost).toBeCloseTo(0.6, 10);
    expect(result.series[0].costAtGridPrice).toBeCloseTo(3.6, 10);
    expect(result.series[1].actualCost).toBeCloseTo(0.2, 10);
  });

  it("derives each bucket's saving the same way as the totals", async () => {
    // Given / When
    const result = await fetchDeviceStatistics(aHass(airconResponse), [AIRCON], threeDays);

    // Then — so a stacked bar's segments sum to the bar (ADR-0012)
    expect(result.series[0].costSavings).toBeCloseTo(1.0, 10);
    expect(result.series[1].costSavings).toBeCloseTo(1.2, 10);
  });

  it("leaves a bucket outside the period out of the series too", async () => {
    // Given
    const hass = aHass({
      ...airconResponse,
      "sensor.slow_poll_aircon_actual_cost": [
        aBucket(DAY_ONE, 0.1),
        aBucket(threeDays.end, 999),
      ],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then
    expect(result.series.map((row) => row.start)).toEqual([DAY_ONE, DAY_TWO]);
  });

  it("has no series when there are no devices to ask about", async () => {
    // Given / When
    const result = await fetchDeviceStatistics(aHass(), [], threeDays);

    // Then
    expect(result.series).toEqual([]);
  });

  it("uses the concepts the sensors are actually named for", () => {
    // Given / When / Then — pinned because a typo here shows an empty house
    // rather than an error (ADR-0009 settled the grid-price name)
    expect(CONCEPTS).toEqual({
      energyUsed: "energy_used",
      actualCost: "actual_cost",
      costAtGridPrice: "cost_at_grid_price",
    });
  });
});
