# ADR-0019: Two colour vocabularies - identity on the mark, verdict on the figure

## Status

Accepted

## Context

Colour arrived in the card family one ticket at a time, and by HEA-104 three
separate schemes were in use with nothing saying how they related.

**A device's hue** means the device (HEA-101). Keyed on the device rather than
its position in a list, drawn from a fixed palette, and stable - the same device
is the same colour on every card, whatever the ranking or the page filter does.

**A verdict** - good news or bad - is `.gain` and `.loss`, green and red. An
absolute saving is judged both ways round (HEA-102) and a *change* is judged per
concept, because a fall in what was paid and a fall in what was saved are
opposite verdicts (HEA-99).

**An identity** - which quantity is this - existed in exactly one place. The
over-time chart drew Paid in `--primary-color` and Saved in `--success-color`,
and nothing else did. So a household learned that blue means Paid from the
stacked bar, then read the totals card where Paid was black.

The trap in unifying them is that the vocabularies collide. `--success-color` is
both the Saved series' *identity* and the *verdict* for good news, and the device
palette contains a blue, a green and an amber of its own. A household seeing
green needs to know which of three claims is being made.

HEA-106 then added a fourth thing to say - how well a device did, as a rate -
which is a verdict that varies continuously rather than a two-state one.

## Decision

**Four vocabularies, each with a surface it owns.**

### 1. A concept's identity goes on a mark, never on the figure

Paid is `--primary-color`; Saved is `--success-color`. Both were already live
and are unchanged, so this names a vocabulary households had read for weeks
rather than altering a chart.

**Would have paid takes no fill.** It is Paid + Saved by construction, so in
every chart that draws it, it is the *container* with the other two as its
segments; a third fill would have a container contradicting its own contents. It
is the outline, and in text an outlined swatch.

In text the mark is a **swatch beside the label**, not colour on the number.
Rejected alternatives:

* *Colour the figure.* It competes directly with the verdict colours, which own
  the numbers. A green figure would be ambiguous between "this is Saved" and
  "this is good news".
* *A coloured caption instead of a swatch.* Text cannot be outlined, so this has
  nothing to offer the one concept whose identity is the absence of a fill.
* *Leave text uncoloured, identity being chart-only.* Defensible and cheapest,
  but it leaves the household to learn the vocabulary twice.

**Saved stays green.** The obvious reading was that separating identity from
verdict required moving it off `--success-color`; that is wrong, because a saving
genuinely *is* good news, so the two agree rather than compete.

**Would have paid is never a warning colour.** An earlier proposal made it
orange. Rejected on its own terms: a *high* counterfactual means a large saving,
so on the best solar day of the year a warning colour would shout loudest.

### 2. Where identity and verdict disagree, the figure wins and the mark holds

A saving can be negative (HEA-39). On a chart the bar itself turns red, because
the verdict has nowhere else to go. In text it does have somewhere else - the
figure already wears `.gain`/`.loss` - so **the mark keeps the identity and the
number takes the verdict**. A green swatch over a red figure is the two
vocabularies each saying their own thing, which is the point of having two.

### 3. A continuous verdict is carried on the figure, weighted by relevance

The saving rate is `costSavings / costAtGridPrice`, drawn red through amber to
green, and it colours the **Would have paid figure** - the quantity the rate is
measured against.

Its denominator goes to nothing constantly, which is the trap HEA-75 measured and
rejected run-signal weighting over. **Weighting by the device's share of the
largest contributor on screen dissolves it rather than patching it**: the devices
whose rate is unreliable are exactly the devices not worth looking at. No
threshold and no cliff.

Two properties of that scale are load-bearing and must not be "tidied":

* **Weight scales saturation only, never lightness.** Scaling both drags a muted
  verdict toward the body-text colour, and dark plus desaturated is precisely how
  a red stops being one. Red suffers this worse than any other hue - a dark green
  is still green; a dark red is a brick - so the fault landed hardest on the end
  of the scale that most needs to be striking.
* **Lightness is monotonic across the ramp, and turns over on a dark theme** so
  the good end is always furthest from the ground it sits on. Red and green is
  the one pairing about 8% of men cannot separate; once the hue collapses,
  brightness is all that is left to read position by.

HEA-106 specified a ramp peaking at the amber, simulated against deuteranopia for
a chart *fill*. This carrier is text, where a light amber is illegible on a white
card, so the ramp was re-derived monotonic - which is also easier to read as an
ordered scale than one whose ends meet at the same brightness. **Re-simulate
before giving this scale to a chart.**

### 4. Colour is never the only cue, and a percentage names its own base

Every figure already carries a label and a sign. The rate additionally appears as
a sentence - in the table cell's `title` and in the device-costs tooltip - which
**names the quantity it is a share of**. A bare percentage beside a column of
money can be read as a share of the bill, of the energy, or of the counterfactual;
that is the ambiguity HEA-88 fixed for the range column.

A negative rate gets a **different sentence rather than a sign**, because it is a
different claim: a reader should not have to work out that a minus means the
device cost more than the grid would have.

### 5. No single chart may use two vocabularies

The concept hues echo hues in the device palette. That is safe *only* because no
chart uses both: device hues live in the device-costs and Sankey cards, concept
hues in the over-time chart and the text.

**Adding a device legend to the over-time chart would break this**, as would
marking the device-costs tooltip with concept swatches - its bars are drawn in
each device's own hue, so a blue Paid mark would sit over an orange bar.

## Consequences

A household learns each vocabulary once. A card added later inherits all four by
using `hea-concepts.js` and `hea-verdict-scale.js`, and a table gains the verdict
band by declaring a column that carries it - derived from the columns rather than
a second flag, so the mark and the figure cannot come apart.

**The continuous verdict deliberately moves with the data.** A device's identity
hue is stable by HEA-101; this is a verdict, so it changes day to day. Recorded
so it is not later read as a regression against that rule.

**A device that ran only after sunset reads red, and that is correct.** It means
"this ran entirely on grid import", which is the actionable signal - shift the
load - not a fault in the device. Do not add a special case for it.

What became harder: any new chart must now declare which vocabulary it is in, and
a mark that varies with data has to be checked in both themes on real figures.
Three defects in this area were found by reading the live dashboard and none by
the test suite, because each card's tests assert what that card claims and none
of them said what a card must *not* do. The suite now pins the properties that
broke silently - the band's absence from tables with no cost column, and equal
lightness across weights.

What would trigger revisiting: giving the chart the continuous scale (needs a
fresh CVD simulation of the monotonic ramp), or a theme where
`--primary-color` and `--success-color` are too close to separate.

Constants are tuning, not decisions - changing a hue or the weighting exponent
does not supersede this ADR. Changing *what carries what* does.

Delivered by HEA-104 and HEA-106; the pip on the device-costs chart was built,
deployed, read on real data and reverted, because the bar's own fill proportion
already is the saving rate at better resolution than a 9px mark.
