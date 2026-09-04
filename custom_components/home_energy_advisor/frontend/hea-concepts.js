/**
 * What a cost concept wears, wherever it is named (HEA-104).
 *
 * Two colour vocabularies already existed and only one was applied everywhere.
 * A **verdict** - good news or bad, `.gain` and `.loss` - is settled and
 * consistent (HEA-102, HEA-99). An **identity** - which quantity is this - lived
 * in the over-time chart alone, so a household learned that blue means Paid from
 * the stacked bar and then read the totals card where Paid was black.
 *
 * This is that identity, named once. It is deliberately the least disruptive
 * answer rather than the most: nothing here changes what any chart already
 * draws.
 *
 * ## The vocabulary
 *
 * * **Paid** is `--primary-color` and **Saved** is `--success-color`, both live
 *   in `hea-cost-over-time-card` for weeks before this file existed.
 * * **Would have paid takes no fill.** It is Paid plus Saved by construction, so
 *   it is not a third quantity sitting beside them - in every chart that draws
 *   it, it is the whole bar with the other two as its segments. Giving it a fill
 *   would have a container contradicting its own contents, so it is the outline.
 *
 * Saved staying green was the substantive choice. Moving it off `--success-color`
 * to keep identity clear of verdict was the obvious reading and it is wrong: a
 * saving genuinely *is* good news, so the two agree rather than compete. An
 * earlier proposal to make Would have paid **orange, as a warning**, is rejected
 * on the same ground pointing the other way - a *high* counterfactual means a
 * large saving, so on the best solar day of the year a warning colour would
 * shout loudest. Identity only, never a verdict.
 *
 * ## Where the identity yields
 *
 * A saving can be negative - battery arbitrage costs more than the grid would
 * have (HEA-39) - and the charts draw that bar in `--error-color`. There the
 * verdict has nowhere else to go, so it takes the fill. In text it does have
 * somewhere else: the figure already wears `.gain` or `.loss`, so the mark keeps
 * the identity and the number keeps the verdict. A green mark over a red figure
 * is the two vocabularies each saying their own thing, which is the point of
 * having two.
 *
 * ## What this must not collide with
 *
 * Blue, green and amber all appear in the device `PALETTE` too (HEA-101). That
 * is safe only because no single chart uses both vocabularies - device hues live
 * in the device-costs and Sankey cards, concept hues in the over-time chart and
 * the text. **Adding a device legend to the over-time chart would break it**, as
 * would marking the device-costs tooltip with these: its bars are drawn in each
 * device's own hue, so a blue Paid mark would sit over an orange bar.
 *
 * The mark is a swatch rather than a coloured caption because text cannot be
 * outlined, and an outline is exactly what the third concept needs. Colour stays
 * reinforcement either way: every figure already carries its label and its sign.
 */

/**
 * The two filled concepts, as a chart resolves them.
 *
 * `{variable, fallback}` because a chart reads a colour in JavaScript, where an
 * unset theme variable comes back as an empty string and would draw nothing. The
 * text cards need no such pair - CSS resolves `var()` with its own fallback.
 */
export const PAID = Object.freeze({
  variable: "--primary-color",
  fallback: "#03a9f4",
});
export const SAVED = Object.freeze({
  variable: "--success-color",
  fallback: "#4caf50",
});

/**
 * Which concepts carry a mark, keyed by the label they already wear.
 *
 * Keyed on the label rather than on a second `concept` field a card would have
 * to set: a card naming a concept has said which one it is, and asking it to say
 * so twice is how the two drift apart. Anything absent - a device name, an
 * amount of energy, a rate - gets nothing, because a mark against it would
 * invent a meaning the reader would then go looking for.
 */
const MARKS = Object.freeze({
  paid: "paid",
  would_have_paid: "would-have-paid",
  saved: "saved",
});

/**
 * The rules for those marks, concatenated into a card's own stylesheet.
 *
 * `box-sizing` so the outlined mark measures the same as the filled ones; its
 * border is drawn inside the square rather than around it, and without this the
 * one concept with no fill would be the largest of the three.
 */
export const CONCEPT_STYLE = `
  .swatch {
    display: inline-block;
    box-sizing: border-box;
    width: 0.62em;
    height: 0.62em;
    margin-right: 0.45em;
    border-radius: 2px;
  }
  .swatch.paid { background: var(--primary-color, #03a9f4); }
  .swatch.saved { background: var(--success-color, #4caf50); }
  .swatch.would-have-paid { border: 1.5px solid var(--primary-text-color, #212121); }
`;

/**
 * The mark for a concept, or nothing at all.
 *
 * A label may be a function - the rate column builds its own, because its unit
 * follows the household's currency - so this has to tolerate being handed one
 * rather than trusting every caller to check first.
 *
 * @param {string|Function|undefined} concept the label key the card renders
 * @returns {string} markup for the mark, or "" where the concept wears none
 */
export const swatch = (concept) => {
  const mark = typeof concept === "string" ? MARKS[concept] : undefined;
  return mark ? `<span class="swatch ${mark}" aria-hidden="true"></span>` : "";
};
