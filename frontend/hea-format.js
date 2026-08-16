/**
 * Money and dates as the household reads them (HEA-50).
 *
 * Home Assistant already knows the currency and the language, so nothing here
 * hardcodes a symbol or a date order: a euro household and a dollar one each
 * see their own, and 20/05 never becomes 05/20.
 */

/** What a figure shows before any statistics have arrived. */
const NO_FIGURE = "-";

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

/**
 * The range a cost could honestly sit in - "€3.61 - €4.72" (ADR-0016).
 *
 * In money, never as a percentage. `(ceiling − floor) / actual` explodes as the
 * cost approaches zero: a device that cost under a cent reads as ±1252 %, which
 * says nothing except that division happened. That is the same near-zero
 * denominator that sank run-signal weighting in HEA-75, and currency has no such
 * failure mode.
 *
 * Composed here rather than by `Intl`'s own `formatRange`, which renders an
 * equal pair as "~€1.50" - an approximation sign on the one figure that is
 * exact. A remainder derived per interval has no span to be uncertain about, so
 * that case is common and reads as its single value.
 */
export const formatMoneyRange = (pair, locale) => {
  if (!Array.isArray(pair)) return NO_FIGURE;
  const [low, high] = pair;
  if (![low, high].every((value) => Number.isFinite(value))) return NO_FIGURE;
  if (low === high) return formatMoney(low, locale);
  // Ordered here so a floor and ceiling handed over the wrong way round still
  // reads as a range rather than as a backwards one.
  const [from, to] = low <= high ? [low, high] : [high, low];
  return `${formatMoney(from, locale)} - ${formatMoney(to, locale)}`;
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
 * Currencies whose minor unit has a symbol everyone writing a tariff uses.
 *
 * The one place in this file that names a symbol, and a deliberate exception:
 * `Intl` models major units only and has no notion of a subunit, so there is
 * nothing to ask. A tariff is universally advertised in the minor unit - 9.3
 * c/kWh, not €0.093/kWh - and a column of the latter reads as leading zeroes.
 *
 * Anything absent here keeps its major unit rather than inventing a symbol.
 */
const MINOR_UNITS = {
  EUR: { symbol: "c", per: 100 },
  USD: { symbol: "¢", per: 100 },
  GBP: { symbol: "p", per: 100 },
};

/** The currency's own symbol, as Intl writes it. */
const currencySymbol = (language, currency) =>
  new Intl.NumberFormat(language, { style: "currency", currency })
    .formatToParts(0)
    .find((part) => part.type === "currency")?.value ?? "";

/**
 * What one row of the unit-price column is measured in - for the header.
 *
 * Carried once at the top rather than on every row: this is the only column
 * that would otherwise hold both a currency prefix and a unit suffix, which
 * made it twice the width of every other and repeated six characters down the
 * table.
 */
export const rateUnit = ({ language, currency }) => {
  if (!currency) return "/kWh";
  const minor = MINOR_UNITS[currency];
  return `${minor ? minor.symbol : currencySymbol(language, currency)}/kWh`;
};

/**
 * A unit price - what a kWh actually cost - as a bare number, or a dash.
 *
 * In minor units where the currency has them, so the figure reads the way a
 * tariff is quoted. Two decimals at most: a device running on surplus
 * generation costs a fraction of a cent, and rounding that to zero would say
 * "free", which is a different claim.
 *
 * This is the figure that made HEA-74 visible - a device priced at a sixth of
 * the tariff on a night when every kWh came off the grid. Cost and energy each
 * looked ordinary; only their ratio did not.
 */
export const formatRate = (value, { language, currency }) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return NO_FIGURE;
  const minor = currency ? MINOR_UNITS[currency] : undefined;
  return new Intl.NumberFormat(language, {
    minimumFractionDigits: minor ? 1 : 0,
    maximumFractionDigits: minor ? 2 : 3,
  }).format(minor ? value * minor.per : value);
};

/**
 * A share, given as a fraction - or a dash where there is no share to give.
 *
 * Whole percent: the underlying split is an allocation of a coarse counter's
 * energy, and a decimal place would claim a precision the estimate does not
 * have. `Intl` places the sign the locale expects rather than appending "%".
 */
export const formatPercent = (value, { language }) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return NO_FIGURE;
  return new Intl.NumberFormat(language, {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
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
 * The picked range, as one label - "20 May - 15 Jul 2026".
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
