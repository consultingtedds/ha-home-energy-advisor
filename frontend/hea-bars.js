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

/** A point's value, whichever of the two shapes ECharts accepts it came in. */
const valueOf = (point) => (Array.isArray(point) ? point : point?.value)?.[1];

/** That point, with something added to the style it already carries. */
const styled = (point, style) => {
  const item = Array.isArray(point) ? { value: point } : { ...point };
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
 */
export const withRoundedCaps = (series) => {
  const buckets = Math.max(...series.map(({ data }) => data.length), 0);
  const data = series.map(({ data: points }) => [...points]);
  for (let bucket = 0; bucket < buckets; bucket++) {
    capBucket(data, bucket);
  }
  return series.map((entry, index) => ({ ...entry, data: data[index] }));
};

/** One bucket's column: its top, its bottom, and the nothings between. */
const capBucket = (data, bucket) => {
  let capped = false;
  let cappedBelow = false;
  for (let index = data.length - 1; index >= 0; index--) {
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
