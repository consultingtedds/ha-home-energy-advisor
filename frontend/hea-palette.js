/**
 * One colour per device, meaning the device (HEA-101).
 *
 * Every card that draws devices shares this, because a colour that differs
 * between two cards on one screen is worse than no colour at all. Reported
 * filtering the testing view to the aircons: one was blue on the device-costs
 * chart and yellow on the Sankey, and another the other way round.
 *
 * The cause was that each card indexed the palette by a device's **position in
 * that card's own list**, and the two lists are ordered differently - one by
 * what was paid, the other by key with zero-valued devices dropped, since a
 * flow diagram cannot draw a quantity of nothing. So position 0 named a
 * different device in each, and the mismatch moved as the data did.
 *
 * A colour is therefore keyed on the device, from the **whole** device list
 * rather than whatever a card is currently drawing. Filtering the page,
 * re-sorting a chart, or a device recording nothing today all leave the rest
 * where they were.
 */

/**
 * Hues that stay apart from each other, and apart on either theme.
 *
 * Chosen for distinguishability rather than brand: a household may track a
 * dozen devices, and the palette cycles rather than running out. Adapted from
 * Okabe-Ito, dropping the yellow, which disappears against a light card.
 *
 * Eight is not an arbitrary stopping point - it is about as far as a
 * categorical palette goes before the hues stop being tellable apart - so a
 * household with more devices than this has two sharing a colour. Cycling makes
 * that *predictable*, which is the best available answer; widening the palette
 * would trade distinction for count.
 */
export const PALETTE = Object.freeze([
  "#0072b2",
  "#e69f00",
  "#009e73",
  "#cc79a7",
  "#56b4e9",
  "#d55e00",
  "#8c6bb1",
  "#3d9970",
]);

/**
 * A second lap, for a household with more devices than the palette has hues.
 *
 * Each hue rotated into the gap beside it. Cycling `PALETTE` alone handed the
 * ninth device byte-for-byte the hex the first already had, which nobody saw
 * while they sat nine bars apart - and which a page filter puts side by side
 * the moment it narrows to one floor (HEA-105).
 *
 * **Rotation rather than lightness, because lightness is already spent.** A
 * device is drawn at three alphas on one hue - what it paid, the earlier
 * period, the saving above it - so a lap told apart by lightness would put one
 * device's Paid in the band where another draws its earlier period. Hue is the
 * axis that is free, and rotating leaves that ramp untouched.
 *
 * These sit closer to their lap-0 neighbours than the originals sit to each
 * other, which is the price of eight hues already spanning the wheel. Closer is
 * not identical, and identical was the defect.
 */
export const SECOND_LAP = Object.freeze([
  "#4b46b3",
  "#8d9b1f",
  "#00a2ab",
  "#b07ad2",
  "#7fa0ee",
  "#a8761b",
  "#b26596",
  "#5b8f3f",
]);

/** Every lap, in order. Lap 0 is untouched, so no household is repainted. */
const LAPS = Object.freeze([PALETTE, SECOND_LAP]);

/** How many devices get a colour of their own before anything repeats. */
export const SLOTS = PALETTE.length * LAPS.length;

/** The remainder is not a device; colouring it like one invites a hunt for it. */
export const UNTRACKED_COLOUR = Object.freeze({
  variable: "--secondary-text-color",
  fallback: "#8a8a8a",
});

/**
 * A colour for every tracked device, keyed by the key that identifies it.
 *
 * Sorted by key rather than taken in the order given, so two callers holding
 * the same devices in different orders agree - which is the entire point.
 *
 * The Untracked remainder is left out rather than given a slot: it wears its
 * own neutral, and counting it here would shift every real device along by one
 * depending on where it happened to sit.
 *
 * @param {Array<{key: string, untracked: boolean}>} devices
 * @returns {Map<string, string>}
 */
export const coloursFor = (devices) => {
  const keys = (devices ?? [])
    .filter((device) => !device.untracked)
    .map((device) => device.key)
    .sort(byCodeUnit);
  return new Map(
    keys.map((key, index) => {
      // Which lap, then which hue within it. Past every lap it cycles again -
      // a palette cannot grow without limit, and a predictable repeat past
      // sixteen devices is still better than an arbitrary one.
      const lap = Math.floor(index / PALETTE.length) % LAPS.length;
      return [key, LAPS[lap][index % PALETTE.length]];
    }),
  );
};

/**
 * A fixed order, deliberately not `localeCompare`.
 *
 * This ordering is not for reading - nobody sees it - it is what makes a
 * device's colour the same everywhere. A locale-aware sort would make that
 * assignment depend on the browser's language, so the same household could see
 * one set of colours in English and another in Spanish, which is precisely the
 * instability this file exists to remove.
 */
const byCodeUnit = (left, right) => {
  if (left === right) return 0;
  return left < right ? -1 : 1;
};
