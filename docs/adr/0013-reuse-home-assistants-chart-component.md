# ADR-0013: Reuse Home Assistant's chart component, don't draw our own

## Status

Accepted

Refines ADR-0012 decision 4, which excludes Home Assistant's energy *cards*;
this decides what the HEA cards draw their charts *with*. Corrects a misreading
of ADR-0008 described below. Does not change any decision in either.

## Context

HEA-50's cost-over-time card needs a stacked bar: the whole bar is Cost at Grid
Price, split into what was actually paid and what was saved, with a negative
saving rendered below the axis (ADR-0012 decision 3).

The first attempt drew this as hand-rolled SVG, on the reasoning that ADR-0008
requires the flagship view to work without a separate install, so a charting
library was unavailable. **That reasoning was wrong**, and it is worth recording
why, because the shape of the error is easy to repeat: ADR-0008 excludes taking
a dependency the user must *install* — a HACS card such as ApexCharts or Plotly.
It says nothing about what Home Assistant's frontend already ships. "This option
is excluded" was quietly promoted into "therefore mine is the only one left",
without checking the middle.

Home Assistant's own energy graph card, read on `home-assistant/frontend`:

```ts
import type { BarSeriesOption } from "echarts/charts";
import "../../../../components/chart/ha-chart-base";

<ha-chart-base .hass=${this.hass} .data=${this._chartData}
               .options=${this._createOptions(...)} chart-type="bar" />
```

`ha-chart-base` wraps **ECharts, bundled into the frontend** — not a CDN, not an
install. It is already loaded on any dashboard carrying a statistics or energy
card. Their stacked series use `stack` groups, and exported energy is fed in as
a **negative value** so it renders below the axis: the very convention ADR-0012
decision 3 committed us to, already implemented.

Drawing our own SVG meant reimplementing — worse — something sitting there to be
used, and guaranteeing that our chart never quite matched the graphs beside it.

## Decision

**1. HEA's charts render through `ha-chart-base`.**

Cards build ECharts `data` and `options` and hand them over, exactly as the
Energy Dashboard does. Tooltips, legend, zoom, the reset control, theming, dark
mode and keyboard access come with it and stay consistent with the rest of the
dashboard as Home Assistant improves them.

**2. This extends the boundary already drawn for `ha-card` and `ha-form`.**

These are frontend *elements*, not the energy-collection internals ADR-0012
decision 5 isolates behind one adapter. The distinction that matters is the
failure mode: an element that changes shape breaks visibly and cosmetically,
where a misread energy collection silently shows the wrong period. `ha-chart-base`
is a larger surface than `ha-form` — we author ECharts option objects Home
Assistant could restructure — and that is the cost accepted here.

**3. Cards must not assume the component is loaded.**

Home Assistant loads card modules lazily, so a dashboard carrying only HEA cards
may never have pulled `ha-chart-base` in. A card asks `loadCardHelpers()` to
create a chart-bearing built-in card, which imports it as a side effect, and says
so plainly if it still is not available rather than rendering an empty box.

**4. We still do not reuse the energy graph cards.**

Unchanged from ADR-0012 decision 4: `energy-usage-graph` and its siblings are
bound to Home Assistant's energy preferences and cannot be pointed at per-device
cost. We reuse the chart *component*, not the cards built on it.

### Rejected alternatives

- **Hand-rolled SVG.** Rejected: permanently divergent from the graphs beside
  it, and every affordance users expect — hover detail, legend toggling, zoom —
  becomes ours to write or to go without. It was built and then dropped.
- **ApexCharts or Plotly via HACS.** Still rejected, by ADR-0008: the flagship
  view must not require a separate install. ApexCharts also has no categorical
  x-axis (verified in HEA-25).

  > **Reason corrected by ADR-0017.** ApexCharts' missing categorical axis is a
  > real reason and is the model ADR-0017 decision 3 holds up. Citing ADR-0008's
  > install rule is not, and **Plotly was never evaluated at all** — it was
  > excluded by that citation alone. The conclusion still stands on stronger
  > ground: `ha-chart-base` is core, so it wins the preference order outright and
  > no community chart needs to beat it. Note the irony this ADR's own opening
  > describes — "'this option is excluded' was quietly promoted into 'therefore
  > mine is the only one left', without checking the middle" — corrected here for
  > Home Assistant's bundled component, and left standing one line below for
  > community ones.
- **Waiting for a supported charting API.** Rejected on the same grounds as
  ADR-0012: none is announced, and the feature is the product's central promise.

## Consequences

Our charts look like Home Assistant's because they are drawn by the same engine,
and improvements to it arrive with no work here.

Tests assert the `data` and `options` handed to the component rather than pixel
geometry — the contract we actually own, and the same shape as the `ha-form`
editor tests. A chart that draws the right picture from the wrong arithmetic is
the failure worth catching, and that is visible in the series values.

If Home Assistant restructures the component or its option shapes, the symptom
is a broken or unstyled chart in the HEA cards while the figures elsewhere stay
correct. The fix is per card, not one adapter — the surface is wider than
ADR-0012 decision 5's, deliberately.

This would be worth revisiting if the option shapes proved unstable release to
release, at which point the fallback is the SVG this ADR rejected.
