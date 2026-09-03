/**
 * How well a device did, as a colour (HEA-106).
 *
 * The cards say what each device **cost**. Nothing said how well each device
 * **did** - a device costing EUR 0.50 with 60% of its grid-price cost avoided
 * is doing better than one costing EUR 0.10 with 5% avoided, and that
 * comparison was arithmetic the household had to do per row.
 *
 * This is a **verdict**, not an identity, so unlike a device's own hue
 * (HEA-101) it is *meant* to move with the data and will change day to day.
 * Recorded here so it is not later read as a regression against that rule.
 *
 * ## Why this is not HEA-75 again
 *
 * It nearly is. `costSavings / costAtGridPrice` has a denominator that goes to
 * nothing constantly - on real data most devices sit at EUR 0.00 - and HEA-75
 * measured exactly this and rejected run-signal weighting because near-zero
 * denominators inflate a percentage into noise.
 *
 * Weighting the colour by the device's **share of the household total**
 * dissolves that rather than patching it: the thing that makes a rate
 * untrustworthy is the same thing that makes it not worth looking at, so the
 * devices whose rate is noise are exactly the devices that fade out. No
 * threshold, no magic number, no cliff.
 *
 * Two dimensions, then:
 *
 * * **Hue** is the saving rate. Red where nearly all the grid price was paid
 *   anyway, amber in between, green where almost none of it was.
 * * **How loudly it is said** is the share. Its job is suppressing the
 *   irrelevant, not announcing the large - see `AUDIBLE` for why that is a
 *   soft-saturating curve rather than the square root it started as.
 *
 * ## The lightness ramp is deliberate, and re-derived for text
 *
 * Red-green is the one pairing about 8% of men cannot separate. Once the hue
 * collapses, brightness is all that is left to read position by, so the ramp
 * carries lightness as well as hue and **flattening it would break the scale
 * for those readers silently**.
 *
 * HEA-106 specified a ramp that rises into the amber and falls again, which was
 * simulated against deuteranopia for a **chart fill**. This carrier is *text*,
 * and a light amber that reads well as a bar is illegible as a figure on a white
 * card - so the ramp here is monotonic instead: it falls from red through amber
 * to green on a light ground, and rises on a dark one. That is not a weakening.
 * A monotonic ramp is *easier* to read as an ordered scale than one that peaks
 * in the middle, where the two ends meet at the same brightness. The change of
 * carrier is what forced it, and it should be re-simulated if the chart ever
 * takes this scale too.
 *
 * The ramp turns over on a dark card so the good end is always the highest
 * contrast against the ground it sits on. Getting that backwards is how the
 * device palette's yellow was lost, which is why it is asserted in the tests
 * rather than eyeballed.
 *
 * ## Colour is never the only cue
 *
 * The standing rule. Here it is met by the table itself: the two figures this
 * rate is derived from, Paid and Would have paid, sit on the same row as the
 * cell being coloured, so the colour saves the reader a division rather than
 * carrying anything they could not otherwise get. The percentage goes on the
 * cell's `title` as well, for a reader who wants it stated.
 */

import { formatPercent } from "./hea-format.js";
import { fill } from "./hea-labels.js";

/**
 * The rate said in words, so the colour is never carrying it alone.
 *
 * Two sentences rather than one with a sign, because a negative saving is a
 * different claim rather than the same one pointing the other way: "-20% of what
 * you would have paid was saved" is not English, and a reader should not have to
 * work out that a minus means the device cost *more* than the grid would have.
 * The tooltip already swaps its "Saved" row to "Lost" on the same test.
 *
 * Both name the base outright - what you would have paid - so the figure needs
 * no arithmetic to interpret. Passive, and the number leads, because these are
 * read at a glance rather than as prose.
 */
export const verdictSentence = (rate, labels, locale) => {
  const template = rate < 0 ? labels.lost_share : labels.saved_share;
  return fill(template, { percent: formatPercent(Math.abs(rate), locale) });
};

/**
 * The share of a device's grid-price cost that never had to be spent.
 *
 * Undefined where there is no counterfactual to have avoided - a device that
 * drew nothing has no rate, and zero would claim it did badly, which is a
 * verdict on a device that did not run.
 *
 * Unclamped, and negative where battery arbitrage cost more than the grid would
 * have (HEA-39). The colour clamps; the number does not, because a caller
 * showing the figure should show what happened.
 */
export const savingRate = ({ costSavings, costAtGridPrice }) => {
  if (!Number.isFinite(costSavings) || !Number.isFinite(costAtGridPrice)) {
    return undefined;
  }
  if (costAtGridPrice <= 0) return undefined;
  return costSavings / costAtGridPrice;
};

/**
 * The scale's three stops, as hue and as lightness on each ground.
 *
 * `light` and `dark` are the *card's* ground, not the colour's: on a light card
 * the ramp falls toward green, on a dark card it rises, so in both the best
 * news is the furthest from the background.
 */
const STOPS = [
  { at: 0, hue: 6, light: 46, dark: 58 },
  { at: 0.5, hue: 38, light: 40, dark: 66 },
  { at: 1, hue: 142, light: 30, dark: 74 },
];

/** How saturated the strongest verdict is, and what the text fades toward. */
const SATURATION = { light: 70, dark: 62 };
/** The lightness of ordinary body text, which a trivial device settles back to. */
const NEUTRAL = { light: 20, dark: 88 };

const between = (from, to, position) => from + (to - from) * position;

/**
 * How quickly the good half of the ramp leaves the yellows behind.
 *
 * Interpolated straight, the amber-to-green half crosses hue 45-75 in its first
 * third, so a device that avoided 60% of its grid-price cost - a good result -
 * rendered olive. Yellow is the hue this project already dropped from the
 * device palette for vanishing against a light card (HEA-101), and reading
 * "middling" off a good number is worse than merely ugly.
 *
 * Easing the position moves that crossing down into the rates that deserve it:
 * 60% now reads yellow-green and 70% is properly green, while 0%, 50% and 100%
 * stay exactly where the scale says they are. The ramp is ordinal - the
 * percentage itself is on the cell's `title` - so bending the middle costs
 * nothing a reader relies on.
 */
const TOWARD_GREEN = 0.6;

/** The stop pair a rate falls between, and how far along it sits. */
const rampAt = (rate, ground) => {
  const upper = STOPS.findIndex((stop) => rate <= stop.at);
  if (upper <= 0) return { hue: STOPS[0].hue, lightness: STOPS[0][ground] };
  const low = STOPS[upper - 1];
  const high = STOPS[upper];
  const position = (rate - low.at) / (high.at - low.at);
  // Only the good half is eased. The bad half is red to amber, which crosses
  // nothing worth avoiding.
  const hueAt = upper === 1 ? position : position ** TOWARD_GREEN;
  return {
    hue: between(low.hue, high.hue, hueAt),
    lightness: between(low[ground], high[ground], position),
  };
};

/**
 * The share at which a device is already half as loud as the largest one.
 *
 * The weighting exists to suppress rates that are **unreliable** - HEA-75's
 * near-zero denominators, where a percentage over EUR 0.00 is noise dressed as
 * a verdict. It started as `sqrt(share)`, which conflated *unreliable* with
 * merely *smaller*, and the two are not the same thing.
 *
 * Read on the real instance for 28 August: a device at 18% of the largest fell
 * to 42% volume and one at 9% to 30%, and both were reading 9% and 0% saved -
 * the worst verdicts on the page, rendered nearly invisible. The poor
 * performers on any given day tend to be the smaller devices, so the curve was
 * muting exactly the rows worth looking at, while every large well-performing
 * device shouted. Good news was structurally louder than bad.
 *
 * `share / (share + AUDIBLE)` collapses hard at the very bottom and stays flat
 * through the middle, which is the shape the intent actually wanted: a real
 * EUR 0.53 keeps its verdict, two cents does not. Still no threshold and no
 * cliff - it is one smooth curve, just one that bends where the data stops
 * meaning anything rather than where the arithmetic happened to.
 */
const AUDIBLE = 0.05;

const round = (value) => Math.round(value * 10) / 10;

/**
 * A verdict for every row, weighted against the rows it is shown beside.
 *
 * Built for a set rather than per row because the weighting is relative: a
 * device matters in proportion to the largest contributor *on screen*, so a
 * filtered card weights against what it is showing rather than against a
 * household total it is not claiming to represent.
 *
 * @param {Array<object>} rows the device rows being drawn
 * @param {{dark?: boolean}} options whether the card sits on a dark ground
 * @returns {(row: object) => ({rate: number, text: string, edge: string}|undefined)}
 */
export const verdictScaleFor = (rows, { dark = false } = {}) => {
  const ground = dark ? "dark" : "light";
  const costOf = (row) => Math.max(0, row?.costAtGridPrice ?? 0);
  const largest = Math.max(0, ...(rows ?? []).map(costOf));

  return (row) => {
    const rate = savingRate(row ?? {});
    if (rate === undefined || largest <= 0) return undefined;
    // Capped, because a caller may pass a row that is not one of the set - a
    // table's totals line outspends every device summed into it, and uncapped
    // it would oversaturate past the top of the scale.
    const share = Math.min(1, costOf(row) / largest);
    // Normalised so the largest contributor lands on exactly 1 rather than on
    // whatever the curve happens to reach there.
    const weight = (share * (1 + AUDIBLE)) / (share + AUDIBLE);
    // Clamped for the *colour* only. The rate handed back is the real one: a
    // caller stating it in words has to be able to say a device paid 20% more
    // than the grid would have, which a rate floored at zero cannot express.
    const clamped = Math.min(1, Math.max(0, rate));
    const { hue, lightness } = rampAt(clamped, ground);
    const saturation = SATURATION[ground] * weight;
    // Text recedes toward the ordinary text colour and the edge recedes toward
    // nothing at all. Both are "this device does not matter", each said the way
    // its own medium can: fading a figure to transparent would make it
    // unreadable, and a grey bar on every trivial row is noise rather than the
    // absence of a claim.
    const settled = between(NEUTRAL[ground], lightness, weight);
    return {
      rate,
      text: `hsl(${round(hue)}, ${round(saturation)}%, ${round(settled)}%)`,
      edge: `hsla(${round(hue)}, ${round(SATURATION[ground])}%, ${round(lightness)}%, ${round(weight)})`,
    };
  };
};
