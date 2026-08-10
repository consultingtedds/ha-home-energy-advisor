/**
 * Money and dates as the household reads them (HEA-50).
 *
 * Home Assistant already knows the currency and the language, so nothing here
 * hardcodes a symbol or a date order: a euro household and a dollar one each
 * see their own, and 20/05 never becomes 05/20.
 */

/** What a figure shows before any statistics have arrived. */
const NO_FIGURE = "—";

const DATE_FORMAT = { day: "numeric", month: "short", year: "numeric" };

/** The language and currency Home Assistant is configured with. */
export const localeFrom = (hass) => ({
  // Undefined lets Intl fall back to the browser's own default, which beats
  // guessing at English or dollars.
  language: hass?.locale?.language || undefined,
  currency: hass?.config?.currency || undefined,
});

/**
 * An amount in the household's currency, or a dash if there is no figure.
 *
 * A negative amount keeps its sign: battery arbitrage can turn Cost Savings
 * into a loss (HEA-39), and hiding that would be a lie in the user's favour.
 */
export const formatMoney = (value, { language, currency }) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return NO_FIGURE;
  const options = currency
    ? { style: "currency", currency }
    : // A bare number beats a wrong symbol.
      { minimumFractionDigits: 2, maximumFractionDigits: 2 };
  return new Intl.NumberFormat(language, options).format(value);
};

/** An amount of energy, in the unit the sensors record it in. */
export const formatEnergy = (value, { language }) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return NO_FIGURE;
  const number = new Intl.NumberFormat(language, {
    maximumFractionDigits: 1,
  }).format(value);
  return `${number} kWh`;
};

/**
 * Text safe to interpolate into markup.
 *
 * A device name is whatever the household typed into their own registry, and a
 * card builds its rows as a string, so it is escaped rather than trusted. An
 * apostrophe alone is reason enough.
 */
export const escapeText = (value) =>
  String(value)
    // The ampersand first, or the escapes below would be escaped in turn.
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

/**
 * The picked range, as one label — "20 May – 15 Jul 2026".
 *
 * `formatRange` collapses a range inside a single day to one date, which is
 * what the picker's "today" should read as.
 */
export const formatPeriod = (period, { language }) => {
  if (!period) return "";
  return new Intl.DateTimeFormat(language, DATE_FORMAT).formatRange(
    period.start,
    period.end,
  );
};
