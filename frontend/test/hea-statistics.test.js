/**
 * The data layer every HEA card sits on: per-device figures for whatever period
 * the user picked (HEA-50). Long-term statistics are the only substrate that
 * can answer an arbitrary range (ADR-0008), and the request and response shapes
 * below were measured against the live instance on 2026-08-09, not assumed.
 */

import { describe, expect, it, vi } from "vitest";

import {
  BOUNDS,
  CONCEPTS,
  bucketPeriodFor,
  fetchDeviceStatistics,
  statisticIdsFor,
  withComparison,
} from "../hea-statistics.js";

const MAY = new Date("2026-05-20T00:00:00Z");
const JULY = new Date("2026-07-15T00:00:00Z");
const aPeriod = (start = MAY, end = JULY) => ({ start, end, fallback: false });

const aDevice = (key, name, overrides = {}) => ({
  key,
  name,
  untracked: false,
  statistics: Object.fromEntries(
    [...Object.values(CONCEPTS), ...Object.values(BOUNDS), "cost_savings"].map(
      (concept) => [concept, `sensor.${key}_${concept}`],
    ),
  ),
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
 * Home Assistant answers on `hass.callWS` - the same tier of the hass object as
 * `states` and `callService`, and deliberately not the frontend internals the
 * energy-collection adapter fronts (ADR-0012 decision 5).
 */
const aHass = (response = {}) => ({
  callWS: vi.fn().mockResolvedValue(response),
});

describe("statisticIdsFor", () => {
  it("builds the statistic ids a device is accounted by", () => {
    // Given / When / Then - the ids the HEA-55 sensor published for it, in a
    // stable order. They look composed because an English install is where the
    // two agree; the Spanish case below is what tells them apart
    expect(statisticIdsFor([AIRCON])).toEqual([
      "sensor.slow_poll_aircon_energy_used",
      "sensor.slow_poll_aircon_actual_cost",
      "sensor.slow_poll_aircon_cost_at_grid_price",
      "sensor.slow_poll_aircon_energy_from_grid",
      "sensor.slow_poll_aircon_energy_from_generation",
      "sensor.slow_poll_aircon_energy_from_battery",
      "sensor.slow_poll_aircon_lowest_possible_cost",
      "sensor.slow_poll_aircon_highest_possible_cost",
    ]);
  });

  it("asks for the bounds whether or not the household publishes them", () => {
    // Given / When - the per-device range is opt-in (ADR-0016), and a card has
    // no way to ask whether it is on. Requesting a statistic that does not exist
    // costs one absent key in the response; a config lookup would cost a second
    // round trip and could go stale between them.
    const ids = statisticIdsFor([AIRCON]);

    // Then - absence in the answer is what tells the card, so the request is
    // unconditional and the *response* is where availability is decided
    expect(ids).toContain("sensor.slow_poll_aircon_lowest_possible_cost");
  });

  it("asks for the whole home's range, which is published either way", () => {
    // Given - the household band is always on, so a card can show it even when
    // no device carries one
    const wholeHome = aDevice("whole_home", "Whole Home");

    // When / Then - its energy and costs are already the sum of the rows, so
    // only the bounds are fetched: they are the one figure not derivable
    expect(statisticIdsFor([AIRCON], wholeHome)).toEqual([
      ...statisticIdsFor([AIRCON]),
      "sensor.whole_home_lowest_possible_cost",
      "sensor.whole_home_highest_possible_cost",
    ]);
  });

  it("does not ask for Cost Savings, which is a subtraction", () => {
    // Given / When
    const ids = statisticIdsFor([AIRCON]);

    // Then - deriving it is what guarantees the stacked bar's segments sum to
    // the whole (ADR-0012), rather than three numbers that nearly agree
    expect(ids).not.toContain("sensor.slow_poll_aircon_cost_savings");
  });

  it("covers every device, including the Untracked remainder", () => {
    // Given
    const devices = [AIRCON, aDevice("untracked_energy_devices", "Untracked", { untracked: true })];

    // When / Then
    expect(statisticIdsFor(devices)).toHaveLength(
      2 * (Object.keys(CONCEPTS).length + Object.keys(BOUNDS).length),
    );
  });

  it("asks for nothing when there are no devices", () => {
    // Given / When / Then
    expect(statisticIdsFor([])).toEqual([]);
  });

  it("uses the ids the integration published, not ones built from the key", () => {
    // Given - a device on a Spanish instance. Home Assistant derives an entity
    // id from the entity's *translated* name for the 41 languages in
    // NATIVE_ENTITY_IDS, `es` among them, and this integration ships Spanish -
    // so the ids share no suffix with the English ones (HEA-89, ADR-0018)
    const spanish = aDevice("aire_acondicionado", "Aire Acondicionado", {
      statistics: {
        energy_used: "sensor.aire_acondicionado_energia_usada",
        actual_cost: "sensor.aire_acondicionado_coste_real",
        cost_at_grid_price: "sensor.aire_acondicionado_coste_a_precio_de_red",
        energy_from_grid: "sensor.aire_acondicionado_energia_de_la_red",
        energy_from_generation: "sensor.aire_acondicionado_energia_de_generacion",
        energy_from_battery: "sensor.aire_acondicionado_energia_de_la_bateria",
        lowest_possible_cost: "sensor.aire_acondicionado_coste_minimo_posible",
        highest_possible_cost: "sensor.aire_acondicionado_coste_maximo_posible",
      },
    });

    // When / Then - every requested id is one the integration said exists. This
    // is the only shape of device that can tell reading from composing apart:
    // on an English install the two agree, which is why the fault shipped
    expect(statisticIdsFor([spanish])).toEqual(Object.values(spanish.statistics));
    expect(statisticIdsFor([spanish]).join()).not.toMatch(/actual_cost/);
  });

  it("skips a concept the integration published no id for", () => {
    // Given - the cost bounds are opt-in (ADR-0016), so a household that never
    // asked has no such entity and the payload simply omits it
    const unbounded = aDevice("slow_poll_aircon", "Slow Poll Aircon", {
      statistics: {
        energy_used: "sensor.slow_poll_aircon_energy_used",
        actual_cost: "sensor.slow_poll_aircon_actual_cost",
      },
    });

    // When / Then - nothing invented to fill the gap. Asking for a statistic
    // that cannot exist was harmless when ids were guessed; now an absent id is
    // the integration saying so, and inventing one would discard that
    expect(statisticIdsFor([unbounded])).toEqual([
      "sensor.slow_poll_aircon_energy_used",
      "sensor.slow_poll_aircon_actual_cost",
    ]);
  });
});

describe("withComparison", () => {
  const aResult = (devices, totals) => ({ period: aPeriod(), devices, totals });
  const aRow = (key, actualCost) => ({ key, name: key, actualCost });

  it("hands every row what it was, and the totals too", () => {
    // Given - the same fetch run over two windows
    const now = aResult([aRow("slow_poll_aircon", 3)], { actualCost: 3 });
    const then = aResult([aRow("slow_poll_aircon", 5)], { actualCost: 5 });

    // When
    const merged = withComparison(now, then);

    // Then - each row carries its earlier self, so a column can show the change
    // without a card reaching into a second result set of its own
    expect(merged.devices[0].before.actualCost).toBe(5);
    expect(merged.totals.before.actualCost).toBe(5);
    expect(merged.devices[0].actualCost).toBe(3);
  });

  it("leaves a device that did not exist in the earlier window unmatched", () => {
    // Given - a device added since, so the comparison window has no row for it
    const now = aResult([aRow("new_device", 3)], { actualCost: 3 });
    const then = aResult([aRow("slow_poll_aircon", 5)], { actualCost: 5 });

    // When / Then - `undefined`, never zero. Zero would render as "3 more than
    // before" and invent a period in which the device cost nothing, when the
    // truth is that it was not being tracked at all
    expect(withComparison(now, then).devices[0].before).toBeUndefined();
  });

  it("moves the earlier buckets onto the current period's axis", () => {
    // Given - a chart plots against time, so the earlier period's own instants
    // sit off to the left of everything drawn and would never be seen
    const now = {
      period: { start: new Date("2026-05-01T00:00:00Z"), end: new Date("2026-06-01T00:00:00Z") },
      devices: [],
      totals: {},
    };
    const then = {
      period: { start: new Date("2026-04-01T00:00:00Z"), end: new Date("2026-05-01T00:00:00Z") },
      devices: [],
      totals: {},
      series: [{ start: new Date("2026-04-03T00:00:00Z"), actualCost: 2 }],
    };

    // When
    const [row] = withComparison(now, then).seriesBefore;

    // Then - shifted by the gap between the two starts, so the third of April
    // lies over the third of May. Its real instant is kept, because a shifted
    // date is for drawing and nothing else should mistake it for a fact
    expect(row.start.toISOString()).toBe("2026-05-03T00:00:00.000Z");
    expect(row.actualStart.toISOString()).toBe("2026-04-03T00:00:00.000Z");
    expect(row.actualCost).toBe(2);
  });

  it("changes nothing when there is no comparison", () => {
    // Given / When / Then - the untouched result, not a copy carrying empty
    // fields: comparison is off by default and must cost the normal path nothing
    const now = aResult([aRow("slow_poll_aircon", 3)], { actualCost: 3 });
    expect(withComparison(now, undefined)).toBe(now);
  });
});

describe("bucketPeriodFor", () => {
  it("buckets a day or two by hour, so a short range still has shape", () => {
    // Given - the picker's "today", part-way through the day
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
    // Given - "20 May to 15 July", the question this ticket exists to answer.
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

    // Then - `change` is the per-bucket delta of a cumulative meter; asking for
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

    // Then - saved is Cost at Grid Price less Actual Cost, so the three
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
    // Given - the remainder is part of what the household actually paid, and
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
      // The by-source split this fixture does not record; a house with no
      // generation or battery reads exactly this way (HEA-51)
      energyFromGrid: 0,
      energyFromGeneration: 0,
      energyFromBattery: 0,
    });
  });

  it("carries each device's cost range where the household publishes one", async () => {
    // Given - a device whose counter reports rarely: its cost accrued somewhere
    // inside a span, and nothing in the data says where (ADR-0016)
    const hass = aHass({
      ...airconResponse,
      "sensor.slow_poll_aircon_lowest_possible_cost": [
        aBucket(DAY_ONE, 0.08),
        aBucket(DAY_TWO, 0.15),
      ],
      "sensor.slow_poll_aircon_highest_possible_cost": [
        aBucket(DAY_ONE, 0.14),
        aBucket(DAY_TWO, 0.29),
      ],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then - the range brackets what was charged, as the engine guarantees
    const [aircon] = result.devices;
    expect(aircon.costFloor).toBeCloseTo(0.23, 10);
    expect(aircon.costCeiling).toBeCloseTo(0.43, 10);
    expect(aircon.costFloor).toBeLessThanOrEqual(aircon.actualCost);
    expect(aircon.actualCost).toBeLessThanOrEqual(aircon.costCeiling);
  });

  it("leaves the range undefined rather than zero when it is not published", async () => {
    // Given - the household has not opted into per-device ranges, so the
    // recorder has no such statistic. Zero would render as "€0.00 - €0.00": a
    // confident claim of perfect precision, which is the opposite of the truth.
    const hass = aHass(airconResponse);

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then
    expect(result.devices[0].costFloor).toBeUndefined();
    expect(result.devices[0].costCeiling).toBeUndefined();
    expect(result.devices[0].actualCost).toBeCloseTo(0.3, 10);
  });

  it("totals the range only when every row has one", async () => {
    // Given - one device opted in and one not. Summing across the gap would
    // quietly bound the household by a subset of itself and read as a narrower
    // range than the truth.
    const other = aDevice("towel_rail", "Towel Rail");
    const hass = aHass({
      ...airconResponse,
      "sensor.slow_poll_aircon_lowest_possible_cost": [aBucket(DAY_ONE, 0.08)],
      "sensor.slow_poll_aircon_highest_possible_cost": [aBucket(DAY_ONE, 0.14)],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON, other], threeDays);

    // Then
    expect(result.totals.costFloor).toBeUndefined();
    expect(result.totals.costCeiling).toBeUndefined();
  });

  it("reads the whole home's range from its own statistics", async () => {
    // Given - the household band, published whether or not the devices are
    const wholeHome = aDevice("whole_home", "Whole Home");
    const hass = aHass({
      ...airconResponse,
      "sensor.whole_home_lowest_possible_cost": [aBucket(DAY_ONE, 5.88)],
      "sensor.whole_home_highest_possible_cost": [aBucket(DAY_ONE, 7.0)],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays, wholeHome);

    // Then
    expect(result.wholeHome).toEqual({
      costFloor: expect.closeTo(5.88, 10),
      costCeiling: expect.closeTo(7.0, 10),
    });
  });

  it("has no whole-home range when the integration is too old to publish one", async () => {
    // Given / When - a household that has not yet updated
    const result = await fetchDeviceStatistics(
      aHass(airconResponse),
      [AIRCON],
      threeDays,
      { key: "whole_home", name: "Whole Home" },
    );

    // Then - undefined, so a card shows nothing rather than a range of zero
    expect(result.wholeHome).toBeUndefined();
  });

  it("carries the period through, so a card can say it is a default range", async () => {
    // Given - no picker on the dashboard
    const fallback = { ...threeDays, fallback: true };

    // When
    const result = await fetchDeviceStatistics(aHass(airconResponse), [AIRCON], fallback);

    // Then
    expect(result.period).toEqual(fallback);
  });

  it("ignores a bucket that starts where the period ends", async () => {
    // Given - the recorder returns any bucket *overlapping* the window, so a
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
    // Given - the recorder moved from ISO strings to epoch milliseconds; a
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
    // Given - a device added today, over a range that predates it
    const newDevice = aDevice("new_heater", "New Heater");
    const hass = aHass(airconResponse);

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON, newDevice], threeDays);

    // Then - zero, and the devices around it are unaffected
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
    // Given - a gap in the statistics, which the recorder reports as null
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
    // Given - HEA set up but with no devices tracked yet. An empty
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
    // Given - the distribution view groups device → room → floor (HEA-58)
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
    // Given - the same fetch has to feed a total and a shape over time, or
    // every chart card costs a second round trip for data already in hand
    const hass = aHass(airconResponse);

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON], threeDays);

    // Then - one row per bucket, oldest first
    expect(result.series).toEqual([
      expect.objectContaining({ start: DAY_ONE, energyUsed: 6.2 }),
      expect.objectContaining({ start: DAY_TWO, energyUsed: 8.0 }),
    ]);
  });

  it("adds the devices together within each bucket", async () => {
    // Given - the chart is of the house, or of whatever the filter selected
    const other = aDevice("fine_meter_aircon", "Fine Meter Aircon");
    const hass = aHass({
      ...airconResponse,
      "sensor.fine_meter_aircon_energy_used": [aBucket(DAY_ONE, 1)],
      "sensor.fine_meter_aircon_actual_cost": [aBucket(DAY_ONE, 0.5)],
      "sensor.fine_meter_aircon_cost_at_grid_price": [aBucket(DAY_ONE, 2.5)],
    });

    // When
    const result = await fetchDeviceStatistics(hass, [AIRCON, other], threeDays);

    // Then - day one carries both devices, day two only the one that ran
    expect(result.series[0].actualCost).toBeCloseTo(0.6, 10);
    expect(result.series[0].costAtGridPrice).toBeCloseTo(3.6, 10);
    expect(result.series[1].actualCost).toBeCloseTo(0.2, 10);
  });

  it("derives each bucket's saving the same way as the totals", async () => {
    // Given / When
    const result = await fetchDeviceStatistics(aHass(airconResponse), [AIRCON], threeDays);

    // Then - so a stacked bar's segments sum to the bar (ADR-0012)
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
    // Given / When / Then - pinned because a typo here shows an empty house
    // rather than an error (ADR-0009 settled the grid-price name)
    expect(CONCEPTS).toEqual({
      energyUsed: "energy_used",
      actualCost: "actual_cost",
      costAtGridPrice: "cost_at_grid_price",
      energyFromGrid: "energy_from_grid",
      energyFromGeneration: "energy_from_generation",
      energyFromBattery: "energy_from_battery",
    });
  });
});
