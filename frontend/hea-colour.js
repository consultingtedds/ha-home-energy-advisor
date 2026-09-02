/**
 * Reading and mixing colours, for the cards that have to compute one.
 *
 * Extracted from `hea-device-costs-card` when a second caller arrived (HEA-106).
 * Most colour in this project is a constant or a theme variable and needs
 * nothing from here; what needs code is the two cases where a colour has to be
 * taken apart - fading one to an alpha, and asking how light the ground is.
 */

const HEX = /^#([\da-f]{3}|[\da-f]{6})$/i;
const RGB = /^rgba?\(([^)]+)\)$/i;

/**
 * The red, green and blue of a colour, or nothing where it is not written so.
 *
 * A theme is free to write a variable as `rgb()` rather than as hex, and may
 * write it in a form we do not parse at all.
 */
export const channelsOf = (colour) => {
  const hex = HEX.exec(String(colour).trim());
  if (hex) {
    const digits = hex[1];
    const pairs =
      digits.length === 3
        ? [...digits].map((digit) => digit + digit)
        : [0, 2, 4].map((at) => digits.slice(at, at + 2));
    return pairs.map((pair) => Number.parseInt(pair, 16));
  }
  const rgb = RGB.exec(String(colour).trim());
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
 * An unreadable colour is returned as it came: that loses the fade, where
 * composing `rgba(NaN, NaN, NaN)` would lose the bar.
 */
export const tint = (colour, alpha) => {
  const channels = channelsOf(String(colour).trim());
  return channels ? `rgba(${channels.join(", ")}, ${alpha})` : colour;
};

/** How bright a colour is, 0 to 1, on the usual perceptual weighting. */
const brightnessOf = ([red, green, blue]) =>
  (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255;

/**
 * Whether this card is drawn on a dark ground, judged by the text it writes.
 *
 * Asked of the *text* colour rather than the background, because a card's own
 * background is often unset and inherited, while `--primary-text-color` is one
 * of the handful of variables every Home Assistant theme defines. Light text
 * means a dark ground.
 *
 * Deliberately not `prefers-color-scheme`: Home Assistant's theme is picked in
 * Home Assistant, so a household running a dark theme on a light operating
 * system - or the reverse - would get the wrong answer from the media query.
 * That is the mistake this whole check exists to avoid, and it is invisible on
 * the developer's own machine.
 *
 * Falls back to a light ground where nothing can be read. A ramp built for a
 * light card on a light card is right; the wrong guess is only ever a
 * legibility cost, and the commoner default is the safer one.
 */
export const drawsOnDark = (element) => {
  const channels = channelsOf(textColourOf(element));
  return channels ? brightnessOf(channels) > 0.5 : false;
};

/**
 * The text colour in force, asked of the card and then of the document.
 *
 * Home Assistant sets its theme's variables on the document element, and a
 * custom property inherits from there through a shadow root - so in a browser
 * the card alone would answer. The root is asked as well because a resolved
 * *inherited* custom property is not something every engine reports on an
 * element that does not declare it, and a ramp silently stuck on its light
 * variant is exactly the kind of theme bug that ships unnoticed.
 */
const textColourOf = (element) => {
  const sources = [element, element?.ownerDocument?.documentElement].filter(
    Boolean,
  );
  for (const source of sources) {
    const styles = getComputedStyle(source);
    const value =
      styles.getPropertyValue("--primary-text-color").trim() || styles.color;
    if (channelsOf(value)) return value;
  }
  return "";
};
