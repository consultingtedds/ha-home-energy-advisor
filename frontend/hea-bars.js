/**
 * Where a stack of bars begins and ends, as ECharts has to be told (HEA-141).
 *
 * A stacked bar is drawn as separate segments that happen to sit on each
 * other, so nothing in the chart knows which of them is the *bar's* top. Left
 * alone, a rounded corner on every segment draws a column of lozenges, and an
 * outline on a segment of no height draws a hairline across the axis that reads
 * as a bar that is not there.
 *
 * So the ends are found here, bucket by bucket, and marked on the points
 * themselves - the same walk Home Assistant does over its own energy bars
 * (`fillDataGapsAndRoundCaps`), and for the same two reasons.
 */

/** How round a bar's outer end is, in pixels - Home Assistant's own radius. */
const CAP = 4;

const TOP = [CAP, CAP, 0, 0];
const BOTTOM = [0, 0, CAP, CAP];

/** Whether this point is the object form, carrying a value and maybe a style. */
const isWrapped = (point) =>
  point !== null && typeof point === "object" && !Array.isArray(point);

/**
 * A point's value, in any of the shapes ECharts accepts.
 *
 * A time series hands over `[when, amount]` pairs, so the amount is the second
 * element; a category chart hands over the amount on its own. Both arrive here,
 * either bare or wrapped in an object beside a style, which is four shapes for
 * one number.
 */
const valueOf = (point) => {
  const raw = isWrapped(point) ? point.value : point;
  return Array.isArray(raw) ? raw[1] : raw;
};

/**
 * That point, with something added to the style it already carries.
 *
 * A bare point has to be wrapped rather than spread: spreading a number gives an
 * empty object, which silently drops the value and draws nothing.
 */
const styled = (point, style) => {
  const item = isWrapped(point) ? { ...point } : { value: point };
  return { ...item, itemStyle: { ...item.itemStyle, ...style } };
};

/**
 * Each stack's outermost segments rounded, and its empty ones left unoutlined.
 *
 * Read from the top of the stack down, because that is the order the segments
 * are drawn in and the first non-zero from each end is the one that shows. A
 * bar rising above the axis and falling below it - money paid against a saving
 * that turned out to be a loss - has two outer ends, and each is capped in its
 * own direction.
 *
 * The series are returned rebuilt rather than marked in place: a card hands its
 * data to a component that may hold onto it, and a point quietly gaining a
 * style after the fact is the kind of change nothing would catch.
 *
 * **Grouped by `stack`, as Home Assistant's own walk is.** A chart drawing a
 * stack per device has one bar per device in every bucket, and each needs its own
 * ends found: treated as one column they would cap the topmost device and leave
 * every other bar square. Series carrying no `stack` are not stacked by ECharts
 * at all, so each is a bar in its own right and gets its own group.
 */
export const withRoundedCaps = (series) => {
  const buckets = Math.max(...series.map(({ data }) => data.length), 0);
  const data = series.map(({ data: points }) => [...points]);
  for (const stack of stacksIn(series)) {
    for (let bucket = 0; bucket < buckets; bucket++) {
      capBucket(data, bucket, stack);
    }
  }
  return series.map((entry, index) => ({ ...entry, data: data[index] }));
};

/**
 * Which series sit on each other, as lists of their positions.
 *
 * An unstacked series is keyed by a symbol rather than by its index, so it
 * cannot collide with a stack a card happened to name "0".
 */
const stacksIn = (series) => {
  const stacks = new Map();
  series.forEach((entry, index) => {
    const key = entry.stack ?? Symbol(index);
    const found = stacks.get(key);
    if (found) found.push(index);
    else stacks.set(key, [index]);
  });
  return [...stacks.values()];
};

/**
 * One stack's column in one bucket: its top, its bottom, and the nothings between.
 *
 * Walked from the end of the stack backwards, because ECharts draws the last
 * series on top and the first non-zero from each end is the one that shows.
 */
const capBucket = (data, bucket, stack) => {
  let capped = false;
  let cappedBelow = false;
  for (let position = stack.length - 1; position >= 0; position--) {
    const index = stack[position];
    const point = data[index][bucket];
    if (point === undefined) continue;
    const value = valueOf(point);
    if (!value) {
      data[index][bucket] = styled(point, { borderWidth: 0 });
    } else if (value > 0 && !capped) {
      data[index][bucket] = styled(point, { borderRadius: TOP });
      capped = true;
    } else if (value < 0 && !cappedBelow) {
      data[index][bucket] = styled(point, { borderRadius: BOTTOM });
      cappedBelow = true;
    }
  }
};
