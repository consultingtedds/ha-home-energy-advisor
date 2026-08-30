/**
 * What each device cost over the period, as bars (HEA-50).
 *
 * The over-time chart answers "how did this week go"; this one answers "which
 * of these is costing me most", side by side for one period.
 *
 * Each device is one bar in its own colour. The bar runs to Cost at Grid Price
 * and the stronger fill stops at what was actually paid, so the paler band
 * above it is the saving - the same three figures the other cards carry, read
 * off a single shape.
 *
 * Only the upper band carries a border. Two stacked segments each with one
 * would draw the shared edge twice, and ECharts has no per-side border width;
 * bordering the saving alone leaves a single line, sitting at the level that
 * was paid.
 *
 * **The household picks which way the bars run** (`layout`, HEA-100), because
 * the two readings trade against each other and neither wins outright.
 *
 * Standing up: devices are named in the legend rather than along
 * the axis, because fourteen names on a *vertical* category axis overlap into
 * illegibility, and Home Assistant's own charts solve it the same way -
 * `ha-chart-base` builds an HTML legend and collapses the overflow behind a
 * "more" chip, so the axis is left to the period. The legend is not only an
 * index: clicking an entry hides that device, which is the only way to take a
 * dominant one out and see the rest against each other.
 *
 * Sideways, the alternative: the names move to the axis, where each has a row
 * to itself and reads perfectly, and the legend goes with them. That buys back
 * real estate a narrow card cannot spare - measured at 610px with fifteen
 * devices, 164px of legend against 141px of plot, against 514px of plot and no
 * legend once turned. What it costs is the toggling, since an axis label cannot
 * be clicked to hide its device.
 *
 * That legend has an exact contract, and failing it is silent. The component
 * looks for an option that is both `show` and `type: "custom"`, draws nothing
 * at all when it finds neither, and hides a series by matching a legend entry's
 * `id` against a series `id` - so an entry names one of the device's two
 * series and reaches the other through `secondaryIds`. A custom legend without
 * `show` renders nothing; ECharts does not step in, because the component
 * rewrites a custom legend to `{ show: false }` before handing the options on.
 */

import { registerCard } from "./hea-card-base.js";
import { HeaCardEditor, registerEditor } from "./hea-card-editor.js";
import { HeaChartCard } from "./hea-chart-card.js";
import {
  changeTone,
  formatMoney,
  formatMoneyChange,
  formatMoneyRange,
  formatPeriod,
} from "./hea-format.js";
import { fill } from "./hea-labels.js";

export const TAG = "hea-device-costs-card";
const EDITOR_TAG = `${TAG}-editor`;

/**
 * Hues that stay apart from each other, and apart on either theme.
 *
 * Chosen for distinguishability rather than brand: a household may track a
 * dozen devices, and the palette cycles rather than running out. Adapted from
 * Okabe-Ito, dropping the yellow, which disappears against a light card.
 */
const PALETTE = [
  "#0072b2",
  "#e69f00",
  "#009e73",
  "#cc79a7",
  "#56b4e9",
  "#d55e00",
  "#8c6bb1",
  "#3d9970",
];

/** The remainder is not a device; colouring it like one invites a hunt for it. */
const UNTRACKED_COLOUR = { variable: "--secondary-text-color", fallback: "#8a8a8a" };

/** A loss must not read as a gain, whatever the device's own colour is. */
const LOSS = { variable: "--error-color", fallback: "#db4437" };

/**
 * Neutral, like the over-time chart's earlier line: a period, not a device.
 *
 * The same grey the Untracked remainder wears, which is a real collision in a
 * legend they share - and accepted. The swatch is approximate here whatever it
 * is: the ghost bars are each drawn in their own device's hue, so no single
 * colour represents them, and the words are what carry this entry.
 */
const EARLIER_COLOUR = { variable: "--secondary-text-color", fallback: "#727272" };

/**
 * The legend key for the earlier period, and why its id names no series.
 *
 * `ha-chart-base` marks an entry hidden by testing that entry's *own* id
 * against the hidden set, while a click hides that id together with its
 * `secondaryIds`. Every `:before` series is already owned by its device's
 * entry - it has to be, or hiding a device would strand its ghost bar - so an
 * entry whose id was one of them would grey itself out the moment that one
 * device was hidden, with every other device's ghost still on the chart.
 *
 * A sentinel belongs to no series and so is never swept in by a device. The
 * component adds a clicked id to the hidden set whether or not it resolves,
 * which is all this needs: the ghosts hide through `secondaryIds`, and the key
 * greys out with them. The hyphen keeps it clear of the `key:segment`
 * namespace the series use.
 */
export const EARLIER_ID = "earlier-period";

/**
 * Which way the bars run, and why the household picks rather than the card.
 *
 * **Vertical** is the original: a bar per device standing up,
 * named in the legend. The legend is the point - clicking an entry hides that
 * device, which is the only way to take a dominant device out and see the rest
 * against each other. Nothing on a chart axis can do that.
 *
 * **Horizontal** lays the same bars on their side with the names down the axis.
 * It exists because the legend costs real height on a narrow card: measured at
 * 610px with fifteen devices, 164px of legend against 141px of plot, because
 * fifteen entries wrap to about seven rows. Horizontal spends that height on
 * the chart instead - the same measurement came back 514px of plot and no
 * legend at all.
 *
 * Neither is right for everyone, so both ship (HEA-100). A household with four
 * devices wants the toggles; one with fifteen on a phone wants the room. The
 * card can be placed twice with a different layout each if both are wanted.
 *
 * **`auto` is the default**, and asks the screen. Measured at 500px card width
 * with fifteen devices, the standing chart is not merely cramped: its 156px of
 * plot has to carry a value axis too, so the bars compress to about 20px and
 * the axis labels collapse on top of each other into an illegible smudge.
 * There is no trade-off left to weigh at that width - the toggles are worth
 * nothing on a chart that cannot be read - so the choice only really exists on
 * a wide screen, and a household should not have to know the option is there
 * to avoid the smudge.
 */
const LAYOUTS = ["auto", "vertical", "horizontal"];

/**
 * Where the standing bars stop fitting.
 *
 * Home Assistant's own `_isMobileSize` breakpoint, which the distribution card
 * already turns at - so the two cards on one screen turn together rather than
 * one going sideways beside another that has not.
 */
const NARROW = "(max-width: 767px)";

/** The series ids the horizontal layout uses, one per concept rather than per device. */
const PAID_ID = "paid";
const SAVED_ID = "saved";
const BEFORE_ID = "before";

/**
 * How much height one device's row needs when the bars run sideways.
 *
 * A chart of categories cannot take its height from the viewport: fifteen
 * devices need fifteen rows whatever the screen is. Comparing puts a second bar
 * beside each device, so a row needs more of them.
 */
const ROW_HEIGHT = 30;
const COMPARING_ROW_HEIGHT = 46;
const AXIS_HEADROOM = 64;
/** Below this a two-device household would draw as a sliver of a card. */
const MIN_HEIGHT = 240;

/**
 * What the standing layout's legend will take, so the card can budget for it.
 *
 * The legend is content-sized and sits below the chart, so it takes what it
 * needs and the plot gets the remainder. A card sized without it in mind hands
 * the legend its height: at 768px this card resolved to its 320px floor, the
 * legend took 164px and the plot was left 156px - the same squeeze that drove
 * the sideways layout, in the band where `auto` has just decided to stand the
 * bars up (HEA-100).
 *
 * The numbers mirror `ha-chart-base`'s own, which are hardcoded there and
 * cannot be read or configured: 24px an entry, 12px of padding above, and no
 * more than ten entries before the rest collapse behind a "more" chip. Two per
 * row is what a narrow card fits, measured at 467px - deliberately the
 * pessimistic assumption, because this sets a *floor* and the floor is what
 * matters at the width where the legend hurts. A wide card wraps the same
 * entries into fewer rows and simply has room to spare.
 */
const LEGEND_ROW_HEIGHT = 24;
const LEGEND_PADDING = 12;
const LEGEND_PER_ROW = 2;
const LEGEND_ENTRY_LIMIT = 10;
/** What the plot itself is worth keeping, once the legend has taken its share. */
const STANDING_PLOT = 300;
/** How much taller than its floor the standing card may grow on a big screen. */
const STANDING_HEADROOM = 120;
/** The base class's middle term, kept in step with `HeaChartCard.chartHeight`. */
const PREFERRED_HEIGHT = "40vw";

/**
 * What the sideways chart leaves around its plot.
 *
 * ECharts' defaults leave roughly 80px above and 90px below, which on a card
 * sized to its rows is dead space rather than breathing room - it was the one
 * complaint left after the layout was first tried. `containLabel` keeps the
 * device names inside these bounds however long the household made them.
 */
const HORIZONTAL_GRID = {
  left: 8,
  right: 16,
  top: 8,
  bottom: 28,
  containLabel: true,
};

const BORDER_WIDTH = 1.5;
/** How strongly the spend is filled, and how faintly the saving above it. */
const PAID_ALPHA = 0.8;
/**
 * The earlier period's bar, fainter than the spend it is measured against.
 *
 * Weaker than `PAID_ALPHA` so this period reads as the subject and the earlier
 * one as the reference, and stronger than `SAVED_ALPHA` so it is not mistaken
 * for part of the stack beside it (HEA-96).
 */
const BEFORE_ALPHA = 0.45;
const SAVED_ALPHA = 0.22;

const HEX = /^#([\da-f]{3}|[\da-f]{6})$/i;
const RGB = /^rgba?\(([^)]+)\)$/i;

/** The red, green and blue of a colour, or nothing where it is not written so. */
const channelsOf = (colour) => {
  const hex = HEX.exec(colour);
  if (hex) {
    const digits = hex[1];
    const pairs =
      digits.length === 3
        ? [...digits].map((digit) => digit + digit)
        : [0, 2, 4].map((at) => digits.slice(at, at + 2));
    return pairs.map((pair) => Number.parseInt(pair, 16));
  }
  const rgb = RGB.exec(colour);
  if (!rgb) return undefined;
  const parts = rgb[1]
    .split(/[\s,/]+/)
    .filter(Boolean)
    .slice(0, 3)
    .map(Number);
  return parts.length === 3 && parts.every(Number.isFinite) ? parts : undefined;
};

/**
 * A colour at the given alpha, so a fill and its outline read as one hue.
 *
 * A theme is free to write a variable as `rgb()` rather than as hex, and may
 * write it in a form we do not parse at all. An unreadable colour is returned
 * as it came: that loses the fade, where composing `rgba(NaN, NaN, NaN)` would
 * lose the bar.
 */
export const tint = (colour, alpha) => {
  const channels = channelsOf(String(colour).trim());
  return channels ? `rgba(${channels.join(", ")}, ${alpha})` : colour;
};

/** Which of a device's two segments a series id belongs to. */
const SEGMENT = /:(?:paid|saved|before)$/;

/**
 * Good news and bad news, as inline colours.
 *
 * The cards wear `.gain` / `.loss` from the shared stylesheet; a tooltip
 * cannot. It is rendered into the chart component's own container, outside
 * this card's shadow root, so no rule of ours reaches it and the colour has to
 * travel on the element (HEA-99).
 */
const TONE_COLOUR = {
  gain: { variable: "--success-color", fallback: "#4caf50" },
  loss: { variable: "--error-color", fallback: "#db4437" },
};

/** One line of the tooltip: what it is, and how much of it. */
const tooltipRow = (label, amount, colour) => {
  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.gap = "16px";
  const name = document.createElement("span");
  name.textContent = label;
  const value = document.createElement("span");
  value.textContent = amount;
  value.style.fontVariantNumeric = "tabular-nums";
  if (colour) value.style.color = colour;
  row.append(name, value);
  return row;
};

/**
 * One device's three figures, as a node.
 *
 * Built rather than written as markup: Home Assistant renders a tooltip
 * formatter's return value with lit, which takes a node as it is and escapes a
 * string - and a device name is whatever the household typed into their own
 * registry.
 */
const tooltipFor = (device, locale, labels, toneColour) => {
  const box = document.createElement("div");
  const title = document.createElement("div");
  title.textContent = device.name;
  title.style.fontWeight = "bold";
  title.style.marginBottom = "4px";
  box.append(
    title,
    tooltipRow(labels.paid, formatMoney(device.actualCost, locale)),
    // A negative saving is a loss, and calling it "Saved" would read as a gain.
    tooltipRow(
      device.costSavings < 0 ? labels.lost : labels.saved,
      formatMoney(device.costSavings, locale),
    ),
    tooltipRow(labels.would_have_paid, formatMoney(device.costAtGridPrice, locale)),
  );
  const change = changeRow(device, locale, labels, toneColour);
  if (change) box.append(change);
  const range = rangeNote(device, locale, labels);
  if (range) box.append(range);
  return box;
};

/**
 * What this device's spend did against the earlier period (HEA-96).
 *
 * A row rather than a sentence, because unlike the range it is a figure in its
 * own right rather than a qualification of the one above it. Signed, and beside
 * what it is measured against, for the reason the totals card gives: a bare
 * amount leaves the direction to be worked out, and a bare "was" makes the
 * reader do the subtraction.
 *
 * Absent unless the household asked to compare, which is the default.
 */
const changeRow = (device, locale, labels, toneColour) => {
  const before = device.before?.actualCost;
  if (!Number.isFinite(before) || !Number.isFinite(device.actualCost)) {
    return undefined;
  }
  const change = device.actualCost - before;
  // A change in spend, so spend's polarity: down is good. Named rather than
  // assumed, because the same fall in Saved would be the opposite verdict.
  const tone = changeTone("actualCost", change);
  return tooltipRow(
    labels.change,
    fill(labels.compared, {
      change: formatMoneyChange(change, locale),
      before: formatMoney(before, locale),
    }),
    tone ? toneColour(tone) : undefined,
  );
};

/**
 * What this device's figure could honestly have been (ADR-0016).
 *
 * A sentence rather than a row, because it qualifies the "Paid" line above it
 * rather than adding a fourth figure - and because the wording is doing work:
 * summing each delta's worst case assumes every kWh landed in that device's own
 * dearest 5-minute slice, which is an outer bound and not an error bar
 * (ADR-0016 decision 4).
 *
 * Absent where the household publishes no per-device range, which is the
 * default: silence beats a range of zero, which would claim exactness.
 */
const rangeNote = ({ costFloor, costCeiling }, locale, labels) => {
  if (![costFloor, costCeiling].every((value) => Number.isFinite(value))) {
    return undefined;
  }
  const note = document.createElement("div");
  note.style.marginTop = "4px";
  note.style.opacity = "0.75";
  // Names its subject. The bounds bracket what was paid and nothing else, so a
  // bare "Could be between…" under three figures left the reader to guess
  // which of them it qualified (HEA-88).
  note.textContent = fill(labels.range_device, {
    range: formatMoneyRange([costFloor, costCeiling], locale),
  });
  return note;
};

class HeaDeviceCostsCard extends HeaChartCard {
  static titleKey = "title_device_costs";

  /** `auto` reads this, so the card must redraw when its answer changes. */
  static narrowQuery = NARROW;

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  /**
   * Nothing to draw when no configured device recorded anything.
   *
   * A row exists for every device whether or not it reported, so an empty
   * period still yields rows - all of them zero. Bars of nothing read as "it
   * cost nothing", which is a different claim from "there is nothing here".
   */
  _isEmpty() {
    return this._ranked().every(
      (device) => !device.costAtGridPrice && !device.actualCost,
    );
  }

  /**
   * Dearest first, by what was actually paid, and by name where two tie.
   *
   * Ranked by actual cost rather than by bar height, so it answers the same
   * question the table does and in the same order. Bars therefore need not
   * descend - a tall bar on a small fill is a device that ran mostly on
   * generation, which is worth seeing rather than sorting away.
   */
  _ranked() {
    return [...(this._result?.devices ?? [])].sort(
      (left, right) =>
        right.actualCost - left.actualCost || left.name.localeCompare(right.name),
    );
  }

  /** One colour per device, cycling, with the remainder set apart. */
  _colourFor(device, index) {
    return device.untracked
      ? this._colour(UNTRACKED_COLOUR)
      : PALETTE[index % PALETTE.length];
  }

  /**
   * Whether the bars lie down, which a household may settle or leave to the
   * screen.
   *
   * A configured choice is honoured either way; anything else - including a
   * layout this card does not offer, from a hand-edited dashboard - asks the
   * screen. Where the browser cannot answer, because `matchMedia` is not
   * universally present, the bars stand up: the legend and its toggles are the
   * richer reading, and an unknown screen size is not a reason to give them up.
   */
  _sideways() {
    const layout = this._config?.layout;
    if (layout === "horizontal") return true;
    if (layout === "vertical") return false;
    return Boolean(globalThis.matchMedia?.(NARROW)?.matches);
  }

  /** True once any device carries an earlier self, which adds a second bar. */
  _comparing() {
    return this._ranked().some((device) => device.before);
  }

  _series() {
    return this._sideways()
      ? this._sidewaysSeries()
      : this._standingSeries();
  }

  /**
   * Three series across every device: the spend, the saving beyond it, and the
   * earlier period beside them.
   *
   * Two series holding every device rather than two per device, which is what
   * frees the legend and lets the names go on the axis. Colour is carried on
   * each **point**, so a device keeps its own hue - carried on the series it
   * would encode Paid and Saved instead, and every device on the chart would
   * share one colour.
   */
  _sidewaysSeries() {
    const rows = this._ranked();
    const loss = this._colour(LOSS);
    const labels = this._labels;
    const hue = (device, index) => this._colourFor(device, index);
    return [
      {
        id: PAID_ID,
        name: labels.paid,
        type: "bar",
        stack: "cost",
        data: rows.map((device, index) => ({
          value: device.actualCost,
          itemStyle: { color: tint(hue(device, index), PAID_ALPHA) },
        })),
      },
      {
        id: SAVED_ID,
        name: labels.saved,
        type: "bar",
        stack: "cost",
        data: rows.map((device, index) => {
          const outline = device.costSavings < 0 ? loss : hue(device, index);
          return {
            value: device.costSavings,
            itemStyle: {
              color: tint(outline, SAVED_ALPHA),
              borderColor: outline,
              borderWidth: BORDER_WIDTH,
            },
          };
        }),
      },
      ...(this._comparing()
        ? [
            {
              id: BEFORE_ID,
              name: labels.compared_series,
              type: "bar",
              stack: "earlier",
              data: rows.map((device, index) => ({
                value: device.before ? device.before.actualCost : null,
                itemStyle: { color: tint(hue(device, index), BEFORE_ALPHA) },
              })),
            },
          ]
        : []),
    ];
  }

  /**
   * Two series per device sharing one stack: the spend, and the saving above.
   *
   * A device's own stack, never a shared one - stacking every device together
   * would pile the whole household into a single column.
   */
  _standingSeries() {
    const loss = this._colour(LOSS);
    return this._ranked().flatMap((device, index) => {
      const colour = this._colourFor(device, index);
      const outline = device.costSavings < 0 ? loss : colour;
      return [
        {
          id: `${device.key}:paid`,
          name: device.name,
          type: "bar",
          stack: device.key,
          // Unbordered: the outline above it would otherwise be drawn twice
          // where the two segments meet.
          itemStyle: { color: tint(colour, PAID_ALPHA) },
          data: [device.actualCost],
        },
        {
          id: `${device.key}:saved`,
          name: device.name,
          type: "bar",
          stack: device.key,
          itemStyle: {
            color: tint(outline, SAVED_ALPHA),
            borderColor: outline,
            borderWidth: BORDER_WIDTH,
          },
          data: [device.costSavings],
        },
        // A stack of its own, so ECharts sets it beside the device rather than
        // piling it on. The two segments sharing `stack: device.key` are parts
        // of one bar; an earlier period is not a part of this one (HEA-96).
        ...(device.before
          ? [
              {
                id: `${device.key}:before`,
                name: device.name,
                type: "bar",
                stack: `${device.key}:before`,
                itemStyle: { color: tint(colour, BEFORE_ALPHA) },
                data: [device.before.actualCost],
              },
            ]
          : []),
      ];
    });
  }

  /**
   * The device a hovered segment belongs to, and its three figures.
   *
   * By device rather than by segment: an axis tooltip lists every series at the
   * category, which for a dozen devices is two dozen rows, each device named
   * twice with nothing to say which row is the spend and which the saving.
   */
  _tooltipFor({ seriesId, dataIndex }, locale) {
    const rows = this._ranked();
    // Sideways, every series holds every device, so the row is what identifies
    // one. Standing up, a device owns its series and the id carries its key.
    const device =
      this._sideways()
        ? rows[dataIndex]
        : rows.find(
            (candidate) =>
              candidate.key === String(seriesId ?? "").replace(SEGMENT, ""),
          );
    // Undefined suppresses the tooltip, where a half-built one would render an
    // empty box against the cursor.
    return device
      ? tooltipFor(device, locale, this._labels, (tone) =>
          this._colour(TONE_COLOUR[tone]),
        )
      : undefined;
  }

  /**
   * One key saying the fainter bar is the earlier period, or nothing.
   *
   * The devices are named; which of a device's two bars is which period was
   * not, so two adjacent strengths of one hue read as two devices before they
   * read as two periods. The same words and the same neutral as the over-time
   * chart's line, so two charts on one screen say it the same way (HEA-99).
   */
  _earlierKey() {
    if (!this._comparing()) return [];
    const name = this._labels.compared_series;
    const itemStyle = { color: this._colour(EARLIER_COLOUR) };
    // Sideways there is one ghost series rather than one per device, so the
    // entry's id can simply be it - nothing to fan out to, and no sentinel
    // needed to keep this key from greying itself out with a single device.
    if (this._sideways()) {
      return [{ id: BEFORE_ID, name, itemStyle }];
    }
    return [
      {
        id: EARLIER_ID,
        secondaryIds: this._ranked()
          .filter((device) => device.before)
          .map((device) => `${device.key}:before`),
        name,
        itemStyle,
      },
    ];
  }

  /**
   * A row per device when the bars run sideways, not a share of the screen.
   *
   * Fifteen devices need fifteen rows whatever the size of the window. The base
   * class's viewport clamp is right for a chart against time and wrong for one
   * against categories, which is why the height is overridable at all.
   */
  _chartHeight() {
    if (this._sideways()) {
      const rows = this._ranked().length;
      const each = this._comparing() ? COMPARING_ROW_HEIGHT : ROW_HEIGHT;
      return `${Math.max(MIN_HEIGHT, AXIS_HEADROOM + rows * each)}px`;
    }
    // Standing up, the floor has to cover the legend as well as the plot, or
    // the legend takes the plot's height instead of the card's.
    const floor = STANDING_PLOT + this._legendHeight();
    return `clamp(${floor}px, ${PREFERRED_HEIGHT}, ${floor + STANDING_HEADROOM}px)`;
  }

  /** What the standing layout's legend will take, at its widest wrap. */
  _legendHeight() {
    const entries =
      Math.min(this._ranked().length, LEGEND_ENTRY_LIMIT) + this._earlierKey().length;
    return Math.ceil(entries / LEGEND_PER_ROW) * LEGEND_ROW_HEIGHT + LEGEND_PADDING;
  }

  _options(locale) {
    return this._sideways()
      ? this._sidewaysOptions(locale)
      : this._standingOptions(locale);
  }

  /**
   * Sideways: value along the bottom, devices down the side, one row each.
   *
   * The legend is at most one entry here - the neutral "Earlier period" key -
   * because the names are on the axis and there is nothing left for a legend to
   * index. What that costs is the toggling: an axis label cannot be clicked to
   * hide its device, which is why the standing layout is still the default.
   */
  _sidewaysOptions(locale) {
    const earlier = this._earlierKey();
    return {
      xAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      yAxis: {
        type: "category",
        data: this._ranked().map((device) => device.name),
        // Dearest at the top. A category axis counts up from the bottom, which
        // would stand the ranking on its head.
        inverse: true,
      },
      grid: HORIZONTAL_GRID,
      tooltip: {
        trigger: "item",
        formatter: (params) => this._tooltipFor(params, locale),
      },
      ...(earlier.length
        ? { legend: { show: true, type: "custom", data: earlier } }
        : {}),
    };
  }

  _standingOptions(locale) {
    return {
      xAxis: {
        type: "category",
        // One column for the whole period: the comparison is device against
        // device, not against time.
        data: [formatPeriod(this._period, locale)],
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (value) => formatMoney(value, locale) },
      },
      tooltip: {
        trigger: "item",
        formatter: (params) => this._tooltipFor(params, locale),
      },
      // Named explicitly: each device is two series, and the legend should name
      // the device once rather than list both of its segments. `show` is what
      // the component filters on, and the ids are what it hides by.
      legend: {
        show: true,
        type: "custom",
        data: [
          ...this._ranked().map((device, index) => ({
            id: `${device.key}:paid`,
            // Every series the device owns, or hiding it would strand one
            // behind. The earlier bar is owned here as well as by the period
            // key below - two entries may name one series, and only an entry's
            // own id decides how it draws itself.
            secondaryIds: [
              `${device.key}:saved`,
              ...(device.before ? [`${device.key}:before`] : []),
            ],
            name: device.name,
            // The solid colour, not the fill: a wash of a hue is harder to tell
            // from its neighbour than the hue itself.
            itemStyle: { color: this._colourFor(device, index) },
          })),
          ...this._earlierKey(),
        ],
      },
    };
  }
}

/** The layout choice, named the way the distribution card names its own. */
class HeaDeviceCostsCardEditor extends HeaCardEditor {
  _extraSchema() {
    return [
      {
        name: "layout",
        selector: { select: { mode: "dropdown", options: LAYOUTS } },
      },
    ];
  }
}

export const register = () => {
  registerEditor(EDITOR_TAG, HeaDeviceCostsCardEditor);
  registerCard(TAG, HeaDeviceCostsCard, {
    name: "Home Energy Advisor: Device costs (chart)",
    description:
      "What each device cost over the selected period, dearest first.",
  });
};

register();
