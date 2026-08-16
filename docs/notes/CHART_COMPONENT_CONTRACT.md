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
