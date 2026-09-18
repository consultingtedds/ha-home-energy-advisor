/**
 * Cost over time, stacked - the headline chart of the family (HEA-50).
 *
 * The whole bar is Cost at Grid Price; the lower segment is what was actually
 * paid, the upper what was saved. One glance gives spend, counterfactual and
 * saving, and the segments sum to something real (ADR-0012).
 *
 * The chart component and its loading live in `HeaChartCard` (ADR-0013); this
 * file is the two series and the axes. A negative saving is fed in as a
 * negative value, which is how Home Assistant renders exported energy: ECharts
 * stacks it below the axis (ADR-0012 decision 3).
 */

import { withRoundedCaps } from "./hea-bars.js";
import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { tint } from "./hea-colour.js";
import { PAID, SAVED } from "./hea-concepts.js";
import {
  currencyLabel,
  formatAxisMoney,
  formatBucketSpan,
  formatMoney,
  savingTone,
} from "./hea-format.js";
import { bucketPeriodFor, bucketsAcross } from "./hea-statistics.js";
import {
  tooltipHeading,
  tooltipKeyedRow,
  tooltipNote,
  tooltipRow,
} from "./hea-tooltip.js";

export const TAG = "hea-cost-over-time-card";
const EDITOR_TAG = `${TAG}-editor`;

/** How long a bucket nominally is, for each period the statistics layer asks for. */
const PERIOD_MS = { hour: 60 * 60 * 1000, day: 24 * 60 * 60 * 1000 };

/**
 * How widely a bar may spread when a period holds only a handful of buckets.
 *
 * The cap Home Assistant puts on its own energy bars. Without it two buckets
 * across a wide card draw as two enormous blocks, which reads as a different
 * kind of chart rather than as a sparse one.
 */
const BAR_MAX_WIDTH = 50;

/**
 * How strongly a bar is filled, against the outline that carries its edge.
 *
 * Half, which is what Home Assistant's energy bars use (`7F` on the hex).
 */
const FILL_ALPHA = 0.5;

/**
 * Half a bucket, because ECharts centres a bar on its x value.
 *
 * A bucket plotted at the instant it begins is therefore drawn half a bucket
 * early - Monday's spending straddling Sunday midday to Monday midday - so
 * every bar disagrees with the axis beneath it. Named as a suspect when this
 * chart was built (HEA-50, 2026-08-10) and confirmed against Home Assistant's
 * own `getPeriodMidpointOffset`, which is this calculation (HEA-93).
 *
 * The measured gap is preferred and the nominal length is the cap, exactly as
 * HA does it: a missing bucket at the start of a period would otherwise
 * measure a gap of two and push every bar a whole bucket out, while a real
 * gap shorter than nominal - a day that lost an hour to a Madrid clock change
 * - is the truth about these particular buckets and beats the constant.
 */
const midpointOffset = (rows, period) => {
  if (!rows.length || !period) return 0;
  const nominal = PERIOD_MS[bucketPeriodFor(period)] ?? 0;
  const measured =
    rows.length >= 2 ? rows[1].start.getTime() - rows[0].start.getTime() : undefined;
  return (measured ? Math.min(measured, nominal) : nominal) / 2;
};

/**
 * `name` is a key into the household's vocabulary, resolved at render.
 *
 * The colours come from `hea-concepts.js` rather than being chosen here. They
 * were chosen here, and were the only place the identity vocabulary existed - so
 * a household learned that blue means Paid from this chart and then read the
 * totals card, where Paid was black (HEA-104). Nothing about this chart changed
 * when they moved; the other cards gained the same words' colours.
 */
const SERIES = {
  paid: { id: "paid", name: "paid", ...PAID },
  saved: { id: "saved", name: "saved", ...SAVED },
};
const LOSS = { variable: "--error-color", fallback: "#db4437" };

/**
 * Good news and bad news, as inline colours.
 *
 * The cards wear `.gain` / `.loss` from the shared stylesheet; a tooltip cannot
 * - it is rendered into the chart component's own container, outside this
 * card's shadow root, so the colour has to travel on the element (HEA-99).
 */
const TONE_COLOUR = {
  gain: { variable: "--success-color", fallback: "#4caf50" },
  loss: LOSS,
};

/** What a hovered point is worth, which is the second of its three values. */
const valueOf = (param) => param.value?.[1] ?? 0;

/** When its bucket began, which a line drawn from another period carries not. */
const startOf = (param) => param.value?.[2];

/**
 * How faint a bar is while its interval is still being counted.
 *
 * Faded rather than hidden: a household watching a device switch on wants to
 * see it now, and a hidden bar is a figure that does not add up. Faded rather
 * than hatched, because a hatch on a stacked segment reads as a third series
 * (HEA-140).
 */
const ACCRUING_OPACITY = 0.45;
/**
 * The earlier period, drawn over the bars rather than inside them.
 *
 * The stack already means something exact - Paid plus Saved is Would have paid
 * - so a third bar in it would stop the total being anything. A line sits above
 * the stack and compares shape without joining the arithmetic (HEA-96).
 *
 * It plots that period's Would have paid, not its Paid, because a bar's *height*
 * is what an eye measures a line against - nobody reads a line against a segment
 * boundary in the middle of a stack. HEA-96 shipped Paid here, and on a solar
 * afternoon the line sat flat on EUR 0.00 beside a EUR 1.14 bar and read as
 * "yesterday cost nothing, today cost EUR 1.14": wrong twice, since today's paid
 * was also nothing and the EUR 1.14 is a counterfactual nobody was billed. The
 * two quantities nearly coincide overnight, which is why it looked right at all
 * (HEA-99).
 */
const BEFORE = {
  id: "before",
  name: "compared_series",
  variable: "--secondary-text-color",
  fallback: "#727272",
};

class HeaCostOverTimeCard extends HeaChartCard {
  static titleKey = "title_cost_over_time";

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * Two stacked bar series: what was paid, and what was saved on top of it.
   *
   * A negative saving keeps its sign so ECharts stacks it below the axis, and
   * carries the error colour per point - the loss is the one figure a user
   * must not misread as a gain (HEA-39).
   */
  _series() {
    // Filled here rather than where the rows are totalled: a period holding no
    // buckets at all must still read as one with nothing in it, and the card
    // decides that from what the statistics layer actually found.
    const rows = bucketsAcross(this._result?.series ?? [], this._result?.period);
    const loss = this._colour(LOSS);
    const labels = this._labels;
    const earlier = this._result?.seriesBefore;
    // One offset for every series on the chart, the bars' own: the earlier
    // line is already aligned onto this period's axis, so shifting it by a
    // different amount would slide the comparison off the bars it is read
    // against.
    const offset = midpointOffset(rows, this._result?.period);
    return [
      ...withRoundedCaps([
        {
          ...seriesShape(SERIES.paid, this._colour(SERIES.paid), labels),
          data: rows.map((row) => accruing(row, pointFor(row, row.actualCost, offset))),
        },
        {
          ...seriesShape(SERIES.saved, this._colour(SERIES.saved), labels),
          data: rows.map((row) => {
            const point = pointFor(row, row.costSavings, offset);
            const style = row.costSavings < 0 ? barStyle(loss) : undefined;
            return accruing(row, point, style);
          }),
        },
      ]),
      ...(earlier?.length
        ? [
            {
              id: BEFORE.id,
              name: labels[BEFORE.name],
              type: "line",
              // No `stack`: the bars' stack sums to Would have paid, and this
              // is a different period rather than a part of that total.
              symbol: "none",
              lineStyle: { type: "dashed", width: 2 },
              itemStyle: { color: this._colour(BEFORE) },
              data: earlier.map((row) => [
                row.start.getTime() + offset,
                row.costAtGridPrice,
              ]),
            },
          ]
        : []),
    ];
  }

  /**
   * The caption, plus what an hourly shape may honestly claim about one device.
   *
   * A device reporting every 30-90 minutes has its energy spread across the
   * buckets its counter spanned (ADR-0006), so this chart is an accrual
   * estimate rather than a record of when the energy was used. Across a house
   * that averages out and nobody is misled; pointed at one device it is the
   * whole picture, and the bars imply a precision ADR-0016's bounds exist
   * precisely because we do not have (HEA-98).
   *
   * Two conditions, because a note shown everywhere is a note nobody reads.
   * Hourly only: a 90-minute counter cannot move energy out of the *day* it was
   * used in, so at daily buckets the caveat would be true of nothing visible.
   * And one device, however it got there - the page filter or a room
   * dashboard's own config both put the reader in front of the same chart.
   *
   * It says nothing about *this* device's counter, because the card cannot
   * know: the published rows carry no reporting cadence, and inventing one
   * would be a claim rather than a caveat. So it describes the method, which is
   * true of every device to a degree the household can weigh for itself.
   */
  _caption(locale) {
    return (
      `${super._caption(locale)}${this._stillAccruingNote()}` + this._accrualNote()
    );
  }

  _stillAccruingNote() {
    if (!(this._result?.series ?? []).some((row) => row.accruing)) return "";
    return `<div class="hint">${this._labels.still_accruing}</div>`;
  }

  _accrualNote() {
    if (this._devices().length !== 1) return "";
    if (!this._period || bucketPeriodFor(this._period) !== "hour") return "";
    return `<div class="hint">${this._labels.hourly_shape_estimate}</div>`;
  }

  /**
   * The hovered bucket: the span it covers, its segments, and their total.
   *
   * Headed by the span rather than by the instant the bar is plotted at, which
   * is the one thing in this chart that was plainly wrong - "13:30" for the
   * hour that began at 13:00, when nothing happened at 13:30 and the figure is
   * the whole hour's (HEA-141).
   *
   * The rows keep this project's reading order - what was paid, what that
   * saved, then the two together - rather than Home Assistant's, which sorts a
   * stack from the top down. Theirs is six series of unrelated sources where
   * mirroring the picture is the only order available; ours is three figures
   * that are one sentence, and every card states them in that order.
   *
   * A segment of no height is left out. It is not in the bar, so a row for it
   * is a line of nothing between the two figures that matter - and a bucket
   * with neither is no tooltip at all, rather than an empty box against the
   * cursor.
   */
  _tooltipFor(params, locale) {
    const hovered = (Array.isArray(params) ? params : [params]).filter(
      (param) => param.componentSubType === "bar",
    );
    const rows = hovered.filter((param) => valueOf(param) !== 0);
    if (!rows.length) return undefined;
    const bucket = this._bucketAt(hovered.map(startOf).find(Boolean));
    const box = document.createElement("div");
    box.append(tooltipHeading(this._spanOf(bucket, locale)));
    for (const param of rows) box.append(this._tooltipRowFor(param, locale));
    const total = hovered.reduce((sum, param) => sum + valueOf(param), 0);
    // Only where the bar has more than one segment: with one, the total would
    // restate the figure directly above it.
    if (rows.length > 1) {
      box.append(
        tooltipRow(this._labels.would_have_paid, formatMoney(total, locale), undefined, {
          bold: true,
        }),
      );
    }
    // The fade says this bar will grow; a hover is where a reader asks what it
    // means (HEA-140).
    if (bucket?.accruing) box.append(tooltipNote(this._labels.still_accruing));
    return box;
  }

  /** One segment: its colour, what it is called, and what it came to. */
  _tooltipRowFor(param, locale) {
    const value = valueOf(param);
    const losing = param.seriesId === SERIES.saved.id && value < 0;
    const label = losing ? this._labels.lost : param.seriesName;
    const tone = param.seriesId === SERIES.saved.id ? savingTone(value) : "";
    return tooltipKeyedRow(
      param.color,
      label,
      formatMoney(value, locale),
      tone ? this._colour(TONE_COLOUR[tone]) : undefined,
    );
  }

  /**
   * The row a hovered bar was drawn from, found by the instant it began.
   *
   * That instant travels on the point, because the x a bar is drawn at is half
   * a bucket later. Read from a *bar* rather than from whatever ECharts listed
   * first: the earlier period's line is plotted on this period's axis and
   * carries no such instant, and taking one from it would head the tooltip with
   * a date from a different week.
   */
  _bucketAt(start) {
    if (start === undefined) return undefined;
    return (this._result?.series ?? []).find((row) => row.start.getTime() === start);
  }

  /** What that bucket covers - an hour named at both ends, or the day itself. */
  _spanOf(bucket, locale) {
    if (!bucket || !this._period) return "";
    return formatBucketSpan(bucket.start, bucketPeriodFor(this._period), locale);
  }

  /**
   * What the period cost, beside the title - as the Energy Dashboard heads its
   * own graph with the total it draws.
   *
   * What was *paid*, where theirs is the total of the bars. The stack's own
   * total is Would have paid, and a bare sum of money in the corner of a card
   * titled "Cost over time" is read as the bill - so the counterfactual would
   * be the one figure here a household could take for what they owe. It is on
   * the chart already, as the height of every bar.
   *
   * Empty rather than absent before the figures arrive, so the heading does not
   * change shape under the reader when they do.
   */
  _headerChip(locale) {
    const paid = this._result?.totals?.actualCost;
    return Number.isFinite(paid) && !this._isEmpty() ? formatMoney(paid, locale) : "";
  }

  /**
   * How far the axis runs, which is not quite how far the period does.
   *
   * A bar is centred on its bucket, so the last one reaches only half a bucket
   * past its own start and an axis drawn to the period's end leaves that much
   * empty chart. Home Assistant rounds the far end back for the same reason
   * (`getSuggestedMax`): to the last bucket's midpoint for hours, and to the
   * start of the last day for days, where the bar sits at the day's own start.
   */
  _axisBounds() {
    if (!this._period) return {};
    const { start, end } = this._period;
    // A period ends where the next one begins, so the last bucket is the one
    // holding the instant before it. Rounding the boundary itself would land
    // half a bucket past the last bar, which is the padding this avoids.
    const last = new Date(end.getTime() - 1);
    if (bucketPeriodFor(this._period) === "hour") {
      last.setMinutes(30, 0, 0);
    } else {
      // Around a clock change the recorder can hand back 00:59 where 23:59 is
      // meant, which would round forward into a day the household never asked
      // for.
      if (last.getHours() === 0) last.setHours(last.getHours() - 1);
      last.setHours(0, 0, 0, 0);
    }
    return { min: start.getTime(), max: last.getTime() };
  }

  _options(locale) {
    const labels = this._labels;
    return {
      // Pinned to the period rather than left to the data. An axis drawn only
      // as wide as the buckets that arrived makes a quiet hour look like the
      // end of the period, and shifts every bar along when one turns up.
      xAxis: { type: "time", ...this._axisBounds() },
      // Home Assistant's own grid. Left to ECharts, a tenth of the width is
      // held back on each side and the plot floats in the middle of the card.
      grid: { top: 15, bottom: 0, left: 1, right: 1, containLabel: true },
      yAxis: {
        type: "value",
        // The currency named once, as Home Assistant heads its own energy axis
        // "kWh" - rather than a symbol repeated down every tick, in the column
        // where a phone-width card has least room to spare (HEA-103).
        name: currencyLabel(locale),
        nameGap: 2,
        nameTextStyle: { align: "left" },
        // Anchored at zero, so the bars stand on the axis rather than floating
        // above a gap ECharts would otherwise leave beneath them.
        boundaryGap: [0, 0],
        splitNumber: 5,
        splitLine: { show: true },
        axisLabel: {
          formatter: (value) => formatAxisMoney(value, locale),
          hideOverlap: true,
        },
      },
      // The three figures belong together on hover: paid, saved, and the bar.
      // Formatted as money, because an allocated share is a proportion of a
      // blended price and divides into a long recurring decimal - a raw hover
      // reads out fourteen places of a euro, which is unreadable and claims a
      // precision money does not have. The axis is already in currency; the
      // tooltip should match it rather than contradict it.
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params) => this._tooltipFor(params, locale),
      },
      // Named explicitly, for the same reason the device-costs card does it:
      // `show` alone falls through to ECharts' own in-canvas legend, which
      // renders - so it never looks broken - but wears different spacing, no
      // overflow chip and no toggling, beside a card that has all three
      // (HEA-87, docs/notes/CHART_COMPONENT_CONTRACT.md).
      //
      // One entry per series here, where that card needs `secondaryIds`: its
      // series are a pair per device, ours are one per concept.
      legend: {
        show: true,
        type: "custom",
        data: [
          SERIES.paid,
          SERIES.saved,
          ...(this._result?.seriesBefore?.length ? [BEFORE] : []),
        ].map((series) => ({
          id: series.id,
          name: labels[series.name],
          // The series colour, not whatever the last point drew: the saving
          // recolours an individual losing bar, and a swatch keyed to that
          // would change with the data.
          itemStyle: { color: this._colour(series) },
        })),
      },
    };
  }
}

/**
 * One point, faded where its interval has not finished being counted.
 *
 * A plain `[x, y]` where it has, so the common case stays the shape ECharts
 * reads fastest and the difference is visible in the data a test reads.
 */
const accruing = (row, point, style = undefined) => {
  if (!row.accruing) return style ? { value: point, itemStyle: style } : point;
  return { value: point, itemStyle: { ...style, opacity: ACCRUING_OPACITY } };
};

/**
 * One point: where to draw it, what it is worth, and when it began.
 *
 * The third value is the instant the bucket started, which the x it is drawn at
 * is deliberately not - a bar is centred on its x, so an hour beginning at
 * 13:00 is plotted at 13:30. Carried on the point rather than re-derived from
 * the axis value, because that is where a tooltip can reach it, and it is the
 * shape Home Assistant's own energy charts use for the same reason
 * (`EnergyDataPoint`, HEA-141).
 */
const pointFor = (row, value, offset) => [
  row.start.getTime() + offset,
  value,
  row.start.getTime(),
];

const seriesShape = ({ id, name }, colour, labels) => ({
  id,
  name: labels[name],
  type: "bar",
  // One stack, so the segments sit on each other and sum to the whole bar.
  stack: "cost",
  barMaxWidth: BAR_MAX_WIDTH,
  itemStyle: barStyle(colour),
});

/**
 * A segment: the concept's colour at half strength, edged in the colour itself.
 *
 * How Home Assistant draws its own energy bars, and worth copying rather than
 * inventing: a solid fill of a strong hue dominates the card, while a wash of
 * one loses its boundary against the segment above it. The outline keeps the
 * edge exactly where the arithmetic puts it, and the fill stays light enough
 * that a gridline behind the bar still reads.
 *
 * The hue is untouched - it is the concept's own (ADR-0019), and a household
 * who learned that blue means Paid on one card still reads it here.
 */
const barStyle = (colour) => ({
  color: tint(colour, FILL_ALPHA),
  borderColor: colour,
  borderWidth: 1,
});

/** Nothing beyond the shared fields; the chart has no options of its own yet. */
class HeaCostOverTimeCardEditor extends HeaCardEditor {}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaCostOverTimeCardEditor);
  registerCard(TAG, HeaCostOverTimeCard, {
    name: "Home Energy Advisor: Cost over time",
    description:
      "What the period cost, stacked against what it would have cost at grid price.",
  });
};

register();
