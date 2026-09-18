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

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import { PAID, SAVED } from "./hea-concepts.js";
import { formatBucketSpan, formatMoney, savingTone } from "./hea-format.js";
import { bucketPeriodFor } from "./hea-statistics.js";
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
    const rows = this._result?.series ?? [];
    const loss = this._colour(LOSS);
    const labels = this._labels;
    const earlier = this._result?.seriesBefore;
    // One offset for every series on the chart, the bars' own: the earlier
    // line is already aligned onto this period's axis, so shifting it by a
    // different amount would slide the comparison off the bars it is read
    // against.
    const offset = midpointOffset(rows, this._result?.period);
    return [
      {
        ...seriesShape(SERIES.paid, this._colour(SERIES.paid), labels),
        data: rows.map((row) => accruing(row, pointFor(row, row.actualCost, offset))),
      },
      {
        ...seriesShape(SERIES.saved, this._colour(SERIES.saved), labels),
        data: rows.map((row) => {
          const point = pointFor(row, row.costSavings, offset);
          const style = row.costSavings < 0 ? { color: loss } : undefined;
          return accruing(row, point, style);
        }),
      },
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

  _options(locale) {
    const labels = this._labels;
    return {
      xAxis: { type: "time" },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (value) => formatMoney(value, locale),
          // Money labels are wide and a phone-width card is not (HEA-103).
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
  itemStyle: { color: colour },
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
