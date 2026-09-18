/**
 * The pieces a chart tooltip is built from (HEA-141).
 *
 * Built as nodes rather than written as markup: Home Assistant renders a
 * tooltip formatter's return value with lit, which takes a node as it is and
 * escapes a string - and what goes in one of these is a device name the
 * household typed into their own registry, or a figure formatted for their
 * locale. An apostrophe alone is reason enough
 * (`docs/notes/CHART_COMPONENT_CONTRACT.md`).
 *
 * A tooltip is also rendered into the chart component's container, outside the
 * card's shadow root, so no rule of ours reaches it: every style here travels
 * on the element (HEA-99).
 *
 * Extracted from `hea-device-costs-card` when the over-time chart needed the
 * same rows, so the two tooltips on one dashboard are laid out by one piece of
 * code rather than by two that agree today.
 */

/**
 * A figure and what it is - the label left, the amount right.
 *
 * Right-aligned and tabular so a column of money lines up on the decimal point,
 * which is the whole reason these are rows rather than Home Assistant's inline
 * "name: value": theirs carries one quantity per series, ours carries a small
 * table of amounts that are meant to be compared down the column.
 */
export const tooltipRow = (label, amount, colour, { bold = false } = {}) => {
  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.justifyContent = "space-between";
  row.style.gap = "16px";
  if (bold) row.style.fontWeight = "bold";
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
 * The dot that keys a row to its colour on the chart.
 *
 * Ten pixels, round, and a four-pixel gap - Home Assistant's own
 * `ha-chart-tooltip-marker`, reproduced rather than used. That element is
 * registered by their energy cards, so a dashboard carrying only ours may never
 * have loaded it, and an unknown tag renders as nothing at all.
 */
export const tooltipMarker = (colour) => {
  const dot = document.createElement("span");
  dot.style.display = "inline-block";
  dot.style.width = "10px";
  dot.style.height = "10px";
  dot.style.borderRadius = "10px";
  dot.style.marginInlineEnd = "4px";
  dot.style.verticalAlign = "middle";
  dot.style.backgroundColor = colour;
  return dot;
};

/** One row, keyed to the series it came from by a dot of its colour. */
export const tooltipKeyedRow = (colour, label, amount, valueColour) => {
  const row = tooltipRow(label, amount, valueColour);
  row.firstChild.prepend(tooltipMarker(colour));
  return row;
};

/**
 * What the tooltip is about, above the figures.
 *
 * Centred and bold, as Home Assistant heads its own energy tooltips, so the
 * two read as one interface for a household hovering both (HEA-141).
 */
export const tooltipHeading = (text) => {
  const heading = document.createElement("div");
  heading.textContent = text;
  heading.style.fontWeight = "bold";
  heading.style.textAlign = "center";
  heading.style.marginBottom = "4px";
  return heading;
};

/**
 * A sentence under the figures, qualifying them rather than adding one.
 *
 * Dimmer and smaller than a row: it is a caveat about what the numbers above
 * can honestly claim, and a reader scanning amounts should be able to skip it.
 */
export const tooltipNote = (text) => {
  const note = document.createElement("div");
  note.textContent = text;
  note.style.marginTop = "4px";
  note.style.maxWidth = "260px";
  note.style.whiteSpace = "normal";
  note.style.opacity = "0.7";
  return note;
};
