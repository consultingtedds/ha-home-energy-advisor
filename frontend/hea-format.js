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
 * A change in money, always signed - "+€1.20", "-€0.80" (HEA-96).
 *
 * `signDisplay: "exceptZero"` because the direction *is* the information: a
 * comparison that renders "€1.20" leaves the reader to work out whether the
 * household did better or worse, which is the entire question they asked.
 * Zero stays unsigned, since "+€0.00" claims a change that did not happen.
 *
 * Deliberately not a percentage. `(now - then) / then` explodes as the base
 * approaches zero, which is most devices on most days - the same near-zero
 * denominator that sank run-signal weighting (HEA-75) and that ADR-0016
 * decision 5 forbids for the cost bounds.
 */
export const formatMoneyChange = (value, { language, currency }) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return NO_FIGURE;
  const options = currency
    ? { style: "currency", currency, signDisplay: "exceptZero" }
    : {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        signDisplay: "exceptZero",
      };
  return new Intl.NumberFormat(language, options).format(value);
};

/**
 * Which way each concept is good news, keyed by the row field it lands on.
 *
 * The whole point is that it is per concept. "Down is good" holds for every
 * cost and is false of the saving, so one rule applied to all of them would
 * say the opposite of the truth on whichever it got wrong: a household that
 * saved EUR 1.46 less than the week before has done worse, not better, and a
 * green figure would tell them otherwise (HEA-99).
 *
 * A concept absent from both sets has no polarity and is left alone. That is a
 * decision, not an oversight - the effective rate is a blended price, and
 * whether a fall in it is good depends on why it fell.
 */
const BETTER_WHEN_LOWER = new Set(["actualCost", "costAtGridPrice", "energyUsed"]);
const BETTER_WHEN_HIGHER = new Set(["costSavings"]);

/**
 * How a change should read: good news, bad news, or neither.
 *
 * Returns the class a card puts on the figure, and an empty string where there
 * is nothing to say - an unmoved period, a figure that is not a number, or a
 * concept the project has taken no view on. Colour is a claim, so silence is
 * the honest default.
 *
 * Note this is reinforcement, never the only cue: `formatMoneyChange` already
 * signs every figure, so a reader who cannot separate the two colours still
 * has the direction. What the colour adds is whether that direction is welcome.
 */
/**
 * How an *absolute* saving reads: good news, bad news, or neither.
 *
 * Distinct from `changeTone`, which judges a movement. A saving is the one
 * money figure with a direction of its own - more of it is better, and less
 * than none is a battery-arbitrage loss (HEA-39). What was paid has no such
 * direction: spending is the bill, not bad news, and only a change in it points
 * anywhere.
 *
 * Zero is uncoloured. Colour is a claim, and "you saved nothing" is neither.
 *
 * Only bad news was marked before this, so the absence of red meant either
 * "fine" or "no rule applies here" and a reader could not tell which (HEA-102).
 */
export const savingTone = (saving) => {
  if (typeof saving !== "number" || !Number.isFinite(saving) || saving === 0) {
    return "";
  }
  return saving > 0 ? "gain" : "loss";
};

export const changeTone = (concept, change) => {
  if (typeof change !== "number" || !Number.isFinite(change) || change === 0) {
    return "";
  }
  if (BETTER_WHEN_LOWER.has(concept)) return change < 0 ? "gain" : "loss";
  if (BETTER_WHEN_HIGHER.has(concept)) return change > 0 ? "gain" : "loss";
  return "";
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
