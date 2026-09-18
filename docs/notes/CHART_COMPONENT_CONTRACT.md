# `ha-chart-base` - the contract behind ADR-0013 (2026-08-12)

> Read from `home-assistant/frontend`, branch `dev`, against the reference
> instance running **core-2026.8.1**. Method: the component source itself
> (`src/components/chart/ha-chart-base.ts`, `src/components/chart/lit-tooltip-formatter.ts`)
> plus ECharts' own `getDataParams` (`apache/echarts`, `src/model/mixin/dataFormat.ts`),
> rather than the rendered output.
>
> Written after the device-costs chart shipped with no legend at all. ADR-0013
> decision 1 says tooltips, legend and zoom "come with it"; that is true of the
> *behaviour*, but the legend in particular has an exact option shape and
> **fails silently** when it is not met. This note qualifies that sentence for
> the next card rather than restating the decision, which stands.

## The legend renders only for an exact shape

`_getLegendItems` looks for one option that is **both** `show` and
`type: "custom"`, and returns nothing otherwise:

```ts
const legend = ensureArray(this.options.legend).find(
  (l) => l.show && l.type === "custom"
) as CustomLegendOption | undefined;
if (!legend) return undefined;      // _renderLegend then returns `nothing`
```

Two ways to fall through it, both of which look like a working chart:

- **`type: "custom"` without `show`** - no legend at all. ECharts does not step
  in, because `_createOptions` rewrites a custom legend to `{ show: false }`
  before handing the options on, precisely so the two cannot both draw.
- **`show` without `type: "custom"`** - HA's HTML legend is skipped, and the
  option passes through to ECharts, which draws its *own* legend inside the
  canvas. This renders, so it never looks broken; it is simply a different
  legend from the one on every other card, with no overflow chip and no
  toggling through `_hiddenDatasets`.

## A legend entry hides by id, not by position

`_renderLegend` resolves each entry against the series with
`datasetById.get(id) ?? datasetByName.get(id)`, and `_getSeries` blanks a
series whose `String(s.id ?? s.name)` is in `_hiddenDatasets`. An entry naming
neither renders happily and then does nothing when clicked.

Where one legend entry owns several series - a device drawn as two stacked
segments - the entry names one series in `id` and the rest in `secondaryIds`;
`_handleDatasetToggle` hides the whole set together:

```ts
this._getAllIdsFromLegend(this.options, id).forEach((i) =>
  this._hiddenDatasets.add(i)
);
```

The swatch colour resolves as `{ color: dataset?.color, ...dataset?.itemStyle,
...item.itemStyle }`, so an entry's own `itemStyle` wins - which is how a bar
whose fill is a faded tint can still show a solid key.

Overflow beyond `LEGEND_OVERFLOW_LIMIT` (lower on mobile) collapses behind a
"more" chip automatically. Nothing is needed for it.

## A tooltip formatter returns a node, not markup

Every formatter **function** is wrapped, whether or not it was written for HA:

```ts
if (typeof formatter === "function") {
  next.formatter = toEChartsFormatter(wrapLitTooltipFormatter(formatter));
}
```

The wrapper renders the return value with lit and hands the container to
ECharts. So a function returning an HTML *string* is escaped and shown as
literal text - the ECharts idiom does not survive. Return a DOM node (lit
commits nodes directly) or a lit template; return `undefined` to suppress the
tooltip entirely.

`valueFormatter` survives the conversion untouched, and applies only where no
`formatter` is given.

## What the formatter is handed

ECharts builds the params, and `seriesId` is among them - worth knowing,
because keying a per-series tooltip off it is otherwise a guess:

```ts
seriesId: isSeries ? this.id : null,
seriesName: isSeries ? this.name : null,
```

`this.id` is the `id` given in the series option, so ids assigned by a card
come back intact.

## Bars: what is not adjustable

`itemStyle.borderWidth` is a single value for the whole shape - ECharts has no
per-side border width. Two stacked segments that both carry a border therefore
draw their shared edge twice, and the usual escape (overlaying two series with
`barGap: "-100%"`) is unavailable per pair: `barGap` is read once for all bar
series on a coordinate system, so it would overlap every device at once.
Bordering one of the two segments is the way out.

## Nothing can be drawn *behind* one bar of a group (2026-08-14)

The same `barGap` limit rules out the obvious way to shade a range behind a
device's bar, and it is worth writing down because the alternative looks
available and is not:

- A third series sharing the device's `stack` **stacks on top of** the other
  two. Stacking is the only relationship series in one stack can have.
- A third series in its own stack takes **its own slot** in the group, so the
  band sits beside the bar rather than behind it.
- `barGap: "-100%"` would overlap them - and every other device's pair at the
  same time, collapsing the chart.

What remains is a `custom` series positioned with `api.barLayout()`, the
documented ECharts recipe for error bars over grouped bars. It stays inside the
component ADR-0013 requires, but it re-derives bar geometry ECharts owns and is
coupled to the number of bar groups, which changes whenever a device is added
or removed. HEA-84 measured the trade and put the range in the tooltip instead.

## How the Energy Dashboard draws its own charts (2026-09-18)

> Read the same way, from `hui-energy-usage-graph-card.ts`,
> `common/energy-chart-options.ts`, `common/color.ts` and
> `components/chart/round-caps.ts`, and checked against the option object of a
> live electricity graph on core-2026.9.2.
>
> The section above is the component's contract - what it requires. This one is
> a *house style*: what Home Assistant does with that component, and the
> mechanisms behind the parts of the look that cannot be guessed from a
> screenshot. HEA-141 applied it to the cost-over-time chart; the device-costs
> chart has not had it yet.

### A bar's fill is its colour at half alpha, and the border is the colour

`getEnergyColor(styles, darkMode, background, compare, property, idx)` appends
an alpha to the hex it resolves: `7F` for a fill, nothing for the border, and
`32` for a compare period's fill. So each series carries

```js
color: "#ff98007F",              // 50% - the fill
itemStyle: { borderColor: "#ff9800" }   // solid - the edge
```

A solid fill of a strong hue dominates a card and a wash of one loses its
boundary against the segment above it. The outline keeps the edge where the
arithmetic puts it, and the fill stays light enough that a gridline behind the
bar still reads.

### Only the ends of a stack are rounded, and zero segments lose their border

`fillDataGapsAndRoundCaps` walks each bucket's column from the top of the stack
down and marks the points themselves:

- the first positive segment it meets gets `borderRadius: [4, 4, 0, 0]`
- the first negative gets `[0, 0, 4, 4]`
- any segment whose value is `0` gets `borderWidth: 0`

Nothing in a stacked chart knows which segment is the *bar's* top, so rounding
every series draws a column of lozenges; and a border on a segment of no height
draws a hairline across the axis that reads as a bar that is not there. They key
the walk by `stack`, which is what a chart drawing a stack per device needs -
ours (`hea-bars.js`) treats everything handed to it as one stack.

### A point carries the instant its bucket began, as a third value

```ts
type EnergyDataPoint = [displayX, value, originalStart];
```

`displayX` is the bucket's midpoint for sub-daily periods, because ECharts
centres a bar on its x. `originalStart` exists so a tooltip can name the span
rather than the midpoint it is drawn at. Extra dimensions on a cartesian bar
point are ignored by the plot and come back on `params.value`, which is what
makes this work at all.

### Time and dates come from the household's settings, not the language

`formatTime` asks `useAmPm(locale)`, which honours `time_format` (`12` / `24`)
and, for its two deferring values, formats ten at night in the language and
looks for a "10". `resolveTimeZone(locale.time_zone, config.time_zone)` picks
the browser's zone or the server's. The same helpers label the time axis inside
`ha-chart-base`, so anything we write beside that axis has to read both settings
or it will contradict the axis under it. The hour is `hour: "numeric"`, so a
24-hour clock renders "3:00" rather than "03:00".

### The grid, the axis bounds, and what they switch on

```js
grid: { top: 15, bottom: 0, left: 1, right: 1, containLabel: true }
xAxis: { type: "time", min: start, max: getSuggestedMax(period, end) }
yAxis: { name: unit, nameGap: 2, nameTextStyle: { align: "left" },
         splitLine: { show: true }, boundaryGap: [0, 0], splitNumber: 5 }
```

Left to itself ECharts holds a tenth of the width back on each side, and the
plot floats in the middle of the card. `getSuggestedMax` rounds the far end back
to where the last bar is *centred* - the bucket's midpoint at hourly, the day's
own start at daily - because an axis drawn to the period's end leaves half a
bucket of empty chart.

Setting `xAxis.min` also has an effect nothing in the option says: `ha-chart-base`
derives `minInterval` from `max - min`, and only when `min` is present. Without
it a chart gets none, so tick density on a multi-day range differs from theirs
for a reason that is invisible in both option objects.

The unit is named once at the head of the axis rather than repeated down every
tick, which is what a phone-width card has room for (HEA-103).

### Sparse data has to be zero-filled, or the bars lie about their width

`generateFillBuckets` builds the expected bucket grid and `fillDataGapsAndRoundCaps`
inserts `{ value: [bucket, 0], itemStyle: { borderWidth: 0 } }` wherever a series
has no point. Two failures make it necessary: ECharts derives the bar band width
from the *smallest gap* between points, so one missing hour draws its neighbours
at double width; and a single lone point makes it expand the time axis by ±40%
either side, ignoring the configured `min`/`max` entirely.

The grid is anchored on a real bucket rather than on the period's start, because
the recorder aligns buckets to UTC and they do not sit on local boundaries in a
half-hour zone. Days are stepped as days, not as 86,400,000 ms, or the grid walks
off midnight the first time the clocks change.

### The tooltip is a heading, rows, and a bold total

`formatTooltip` heads the tooltip with the span (`13:00 – 14:00`, or the date at
daily buckets), lists one row per series with a `ha-chart-tooltip-marker` dot,
**skips any row whose formatted value is zero**, and adds a bold total when more
than one positive bar is in the hover. It returns `nothing` when no row survives,
which is how a tooltip is suppressed rather than drawn empty.

Their rows are sorted positives-first and then from the top of the stack down.
That is right for six unrelated sources where mirroring the picture is the only
order available; ours are three figures that make one sentence, so the
cost-over-time chart keeps its own order (HEA-141).

`ha-chart-tooltip-marker` is a 10px round span with a 4px inline-end margin. It
is registered by their energy cards, so a dashboard carrying only ours may never
have loaded it and an unknown tag renders as nothing - `hea-tooltip.js`
reproduces it rather than using it.

### The legend swatch takes the *fill* colour

`_renderLegend` resolves `{ color: dataset.color, ...dataset.itemStyle,
...item.itemStyle }` and paints a `mdiCheckCircle` with it. With their 50% fills
that tick is drawn at half alpha. An entry's own `itemStyle` still wins, which is
how a card keeps a solid key over a faded bar (which is what ours does).

### `ha-card` styles a *slotted* `.card-header` exactly like its own

`ha-card` renders `<h1 class="card-header">` from its `header` property and has
nowhere to put anything beside it - but its stylesheet also carries
`:host ::slotted(.card-header)`, with the same typography. So a card that needs a
figure next to its title writes its own header element and keeps the dashboard's
heading style, without copying any values that could then drift. Their energy
cards do this to carry a chip of the period's total:

```css
.chip {
  font-size: var(--ha-font-size-m);
  font-weight: var(--ha-font-weight-medium);
  padding: var(--ha-space-1) var(--ha-space-2);
  border-radius: var(--ha-border-radius-md);
  border: 1px solid var(--divider-color);
}
```

One catch: `::slotted` from the component's shadow root beats an ordinary rule of
ours on specificity, so the layout that turns that heading into a row has to be
written on the element.

### The axis tooltip's heading can be set without replacing the tooltip

Worth knowing even though HEA-141 did not need it in the end. For
`trigger: "axis"`, ECharts builds the heading with
`getValueLabel(..., axisItem.valueLabelOpt)`, and `valueLabelOpt.formatter` comes
from `axisPointer.label.formatter`. `ha-chart-base` wraps only
`tooltip.formatter` and `series[].tooltip.formatter`, spreading the rest of the
tooltip through untouched - so `tooltip.axisPointer.label.formatter` reaches
ECharts intact and can relabel the heading while leaving their rows, markers and
`valueFormatter` alone.
