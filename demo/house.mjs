/**
 * The imaginary household, in one place.
 *
 * Every name and every number here is invented. Nothing traces to the reference
 * instance, and nothing here was measured - the figures are chosen so each card
 * shows the thing it exists to show, and the relationships between them are
 * arranged rather than computed (HEA-80).
 *
 * Naming is constrained, and the constraint is load-bearing. This repo is public
 * and `scripts/privacy_check.py` refuses a room word joined to another word,
 * because that shape is how the maintainer's floor plan leaked four times. So
 * the rooms here are bare - Bedroom and Guest Room, never a qualified bedroom -
 * and every device name in this file has been run through the checker, which
 * also compares against a local list of the maintainer's real hardware.
 *
 * That is what makes the screenshots safe as well as the source. Images are the
 * one thing the checker cannot read, so the guarantee has to come from the fact
 * that everything in them is generated from this file.
 *
 * To change what the screenshots show, change this file and rerun the harness.
 */

/** Two floors, so the cost distribution card has a hierarchy worth drawing. */
export const FLOORS = [
  { key: "ground", name: "Ground floor", level: 0 },
  { key: "upstairs", name: "Upstairs", level: 1 },
];

export const AREAS = [
  { key: "living_room", name: "Living Room", floor: "ground" },
  { key: "kitchen", name: "Kitchen", floor: "ground" },
  { key: "garage", name: "Garage", floor: "ground" },
  { key: "bedroom", name: "Bedroom", floor: "upstairs" },
  { key: "guest_room", name: "Guest Room", floor: "upstairs" },
  { key: "bathroom", name: "Bathroom", floor: "upstairs" },
];

/**
 * The house-level sensors, as `config/configuration.yaml` names them.
 *
 * Setup asserts each one exists rather than trusting the mapping, so renaming a
 * template sensor fails loudly instead of quietly producing a screenshot with an
 * empty card in it.
 */
export const HOUSE = {
  importPrice: "sensor.electricity_import_price",
  exportPrice: "sensor.electricity_export_price",
  gridImport: "sensor.grid_import",
  gridExport: "sensor.grid_export",
  generation: "sensor.solar_generation",
  batteryCharge: "sensor.battery_charge",
  batteryDischarge: "sensor.battery_discharge",
  houseConsumption: "sensor.house_consumption",
};

/**
 * The tariff the seeded week is priced against, matching the template sensor.
 * Two steps, because a flat rate makes the cost-over-time card a straight line
 * and takes the point out of "run it in the afternoon instead".
 */
export const TARIFF = { peak: 0.312, offPeak: 0.114, peakFrom: 8, peakUntil: 22 };

/**
 * The devices the demo tracks.
 *
 * `share` splits a device's energy across the three sources, and the seed turns
 * that into money at the tariff above. `hours` is the window it runs in, given
 * as `[from, to]` and allowed to wrap past midnight; `baseline` is the share
 * that never stops, for things that tick over all day.
 *
 * The window is what decides the saving, more than the shares do. A device
 * timed for the middle of the day meets generation at its strongest and saves
 * almost everything; the same device left to run at eight in the evening saves
 * nearly nothing, because there is no sun and the tariff is at its dearest.
 *
 * Between them they set what each device *saves*, and the spread across the
 * house is deliberate rather than decorative. The cards colour a device by how
 * its cost compares to grid price, so a house where everything saves a little
 * paints every row the same and shows a reader nothing. These range from a
 * water heater that runs almost entirely on the roof, through devices that save
 * a useful fraction, down to evening loads that save close to nothing, and one
 * that costs more than the grid would have.
 *
 * Battery energy saves the difference between the price at the time and what
 * the charge cost, so it saves well during peak hours and nothing off-peak -
 * which is what lets the car charger's saving go negative.
 *
 * They fall into groups on purpose: three devices on midday timers saving most
 * of their cost, a middle band that saves a useful fraction, an evening band
 * that saves next to nothing, and one device below the line.
 *
 * The car charger is the deliberate exception. It draws battery energy that was
 * stored when electricity was dearer than it was at the moment the car took it,
 * so it cost more than buying the same energy off the meter would have. That is
 * a real outcome of battery arbitrage, HEA-39 renders it below the axis, and a
 * screenshot is the only place a reader meets it before their own dashboard
 * shows them one.
 */
export const DEVICES = [
  {
    name: "Air Conditioner",
    source: "sensor.air_conditioner_energy",
    kind: "energy",
    area: "living_room",
    // Afternoon into the evening, so it starts on the roof and ends on the
    // grid. The middle of the range, and the biggest single cost in the house.
    weekKwh: 41.6,
    share: { grid: 0.32, generation: 0.52, battery: 0.16 },
    hours: [12, 21],
  },
  {
    name: "Wall Lights",
    // A power sensor, so the integration creates an Integral helper for it. The
    // README says that happens; one device here makes it visible.
    source: "sensor.wall_lights_power",
    kind: "power",
    area: "living_room",
    // On after dark, when the roof gives nothing and the tariff is at its
    // dearest. The floor of the range.
    weekKwh: 3.9,
    share: { grid: 0.96, generation: 0.0, battery: 0.04 },
    hours: [19, 24],
  },
  {
    name: "Dishwasher",
    source: "sensor.dishwasher_energy",
    kind: "energy",
    area: "kitchen",
    // Delayed until the early afternoon, which is the whole point of a delay
    // timer. One of the three that save most of what they cost.
    weekKwh: 9.4,
    share: { grid: 0.07, generation: 0.86, battery: 0.07 },
    hours: [13, 17],
  },
  {
    name: "Tumble Dryer",
    source: "sensor.tumble_dryer_energy",
    kind: "energy",
    area: "kitchen",
    // The classic evening load: dear hours, no sun left. The contrast with the
    // washing machine that fed it is the argument the README makes.
    weekKwh: 16.2,
    share: { grid: 0.84, generation: 0.02, battery: 0.14 },
    hours: [18, 22],
  },
  {
    name: "Washing Machine",
    source: "sensor.washing_machine_energy",
    kind: "energy",
    area: "kitchen",
    // Timed for the middle of the day, which is exactly what the README
    // suggests doing, and it shows.
    weekKwh: 7.1,
    share: { grid: 0.03, generation: 0.92, battery: 0.05 },
    hours: [12, 15],
  },
  {
    name: "Car Charger",
    source: "sensor.car_charger_energy",
    kind: "energy",
    area: "garage",
    // Overnight, off the battery, in the hours when the grid was cheapest
    // anyway. Buying it off the meter would have cost less.
    weekKwh: 34.5,
    share: { grid: 0.15, generation: 0.0, battery: 0.85 },
    hours: [1, 6],
    // Stored dear, drawn cheap. The saving comes out negative on purpose.
    storedCostPremium: 1.6,
  },
  {
    name: "Ceiling Fan",
    source: "sensor.ceiling_fan_energy",
    kind: "energy",
    area: "bedroom",
    // Bedtime onwards, largely on stored energy, in hours that are still dear.
    // Saves a fair share without ever seeing the sun.
    weekKwh: 5.2,
    share: { grid: 0.60, generation: 0.05, battery: 0.35 },
    hours: [20, 24],
  },
  {
    name: "Panel Heater",
    source: "sensor.panel_heater_energy",
    kind: "energy",
    area: "guest_room",
    // Heated on demand in the evening, at whatever the grid costs at the time.
    weekKwh: 11.3,
    share: { grid: 0.90, generation: 0.02, battery: 0.08 },
    hours: [18, 23],
  },
  {
    name: "Water Heater",
    source: "sensor.water_heater_energy",
    kind: "energy",
    area: "bathroom",
    // The best case the product has to show: an automation that heats it in
    // the five hours either side of noon, on the roof, for very nearly nothing.
    // This is the row a reader should notice, and the one worth copying.
    weekKwh: 28.7,
    share: { grid: 0.01, generation: 0.96, battery: 0.03 },
    hours: [11, 16],
  },
];

/**
 * Untracked energy: everything the household has not named. The integration
 * creates this pseudo-device itself, and it is what makes the shares add up to
 * the whole bill, so the seed has to give it a share worth showing.
 */
export const UNTRACKED = {
  // Everything else in the house averaged together, so it lands mid-range:
  // neither the best nor the worst row on the card, which is what a remainder
  // made of many unrelated things should look like.
  weekKwh: 63.5,
  share: { grid: 0.58, generation: 0.30, battery: 0.12 },
  hours: [7, 23],
  // Much of it never stops - standby, the router, the fridge - so a good part
  // of the day carries a floor rather than a window.
  baseline: 0.45,
};

/**
 * Sensors the demo deliberately leaves untracked, so the discovery screen has
 * something to list. Two genuine candidates, then two false friends: discovery
 * still offers a battery or a forecast but sorts it last, and the screenshot is
 * where a reader sees that behaviour before meeting it.
 */
export const UNTRACKED_SOURCES = [
  "sensor.fridge_freezer_energy",
  "sensor.oven_energy",
  "sensor.phone_battery_energy",
  "sensor.solar_forecast_today",
];

/**
 * The window the screenshots show: seven whole days ending at last midnight, so
 * a rerun on any day produces the same shape rather than a part-finished today.
 */
export const WINDOW_DAYS = 7;
