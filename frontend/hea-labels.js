/**
 * The words the cards use, from the integration's own translation files.
 *
 * Every card string was hardcoded English until HEA-88, against the project's
 * own day-one rule. `hea-format.js` localises *formats* - money, energy, dates,
 * all through `Intl` - so the numbers were already right in any locale and the
 * words around them were not.
 *
 * The strings live in `strings.json` and `translations/{en,es}.json` under the
 * `common` section with a `card_` prefix - the same files and the same
 * translator workflow as the config flow and the entity names. That works
 * because `frontend/get_translations` takes `category` as a free string and Home
 * Assistant derives the available categories from the translation files
 * themselves, so no second translation system is needed (ADR-0018).
 *
 * One concept had four spellings before this - "Paid" on two cards, "Actual
 * Cost" and "Actual cost" on two others - which is what happens when an idea is
 * written out afresh at each site that shows it. Naming them once removes the
 * drift rather than correcting it.
 *
 * The triad is three past-tense verbs. "Would have paid" carries the
 * counterfactual in its grammar, where "at grid price" left a household to infer
 * that the figure was imaginary. The pricing rule is unchanged and still never
 * named after absent hardware (ADR-0009); it moves into the range note and the
 * explanation card as the *reason* the two differ, which is where an explanation
 * belongs and a column header does not.
 *
 * These are card labels, not entity names. Entity names are nouns that stand
 * alone - `sensor.cloud_polled_pump_actual_cost` reads correctly in a template,
 * where no column header supplies the noun - and stay as ADR-0003 and ADR-0009
 * have them.
 */

/**
 * Where the strings live, and why here rather than in a section of their own.
 *
 * A `cards` section was the obvious shape and hassfest rejects it outright -
 * `gen_strings_schema` is a plain `vol.Schema`, so voluptuous forbids any
 * top-level key it does not name, and CI and HACS validation both run it.
 * `common` is on that list, typed as a flat `{slug: string}` map, which is
 * exactly the shape wanted; a category is whatever a translation file's
 * top-level keys happen to be, so it is fetchable unchanged. The `card_` prefix
 * keeps these apart from the backend strings sharing the section.
 */
const CATEGORY = "common";
const DOMAIN = "home_energy_advisor";
const PREFIX = `component.${DOMAIN}.${CATEGORY}.card_`;

/**
 * English, as the fallback before the fetch resolves and if it fails.
 *
 * Duplicated from `en.json` deliberately: a card must render words on its first
 * paint, and the key alone ("would_have_paid") is worse than the English. The
 * copies are pinned together by `hea-labels.test.js`, so they cannot drift -
 * `en.json` remains the canonical text a translator works from.
 *
 * Keyed without the `card_` prefix the files carry; `strip` removes it, so the
 * cards read `labels.paid` rather than `labels.card_paid`.
 */
export const DEFAULTS = Object.freeze({
  paid: "Paid",
  would_have_paid: "Would have paid",
  saved: "Saved",
  lost: "Lost",
  range_column: "Paid (min-max)",
  range_note:
    "Paid (min-max) is the widest range these readings allow, not a typical " +
    "error: a meter that reports every 30-90 minutes leaves the exact moment " +
    "of use unknown.",
  range_whole_home:
    "What you paid could honestly sit between {range} - the widest these " +
    "readings allow, not a typical error.",
  range_device: "What you paid could be between {range}.",
  compared: "{change} vs {before}",
  change: "Change",
  compared_series: "Earlier period",
  device: "Device",
  energy: "Energy",
  rate: "Rate",
  total: "Total",
  grid: "Grid",
  generation: "Generation",
  battery: "Battery",
  from_grid: "From the grid",
  from_generation: "From generation",
  from_battery: "From the battery",
  energy_used: "Energy used",
  household: "Household",
  title_totals: "Cost summary",
  title_devices: "Cost by device",
  title_device_costs: "What each device cost",
  title_cost_over_time: "Cost over time",
  title_sources: "Where the energy came from",
  title_distribution: "Where the cost went",
  title_distribution_energy: "Where the energy went",
  editor_title: "Title",
  editor_collection_key: "Energy period (collection key)",
  editor_devices: "Devices (all, if none are chosen)",
  editor_sort_by: "Order by",
  editor_layout: "Layout",
  editor_metric: "Measure by",
});

/**
 * The in-flight fetch per language, and the answer once it lands.
 *
 * The *promise* is cached, not just the result: a dashboard mounts its cards
 * together, so they all ask before any answer exists, and caching only the
 * resolved value gives one request per card. The second map serves the
 * synchronous render path, which cannot await a promise.
 */
const pending = new Map();
const resolved = new Map();

const languageOf = (hass) => hass?.locale?.language || hass?.language || "en";

/** Fetch this household's language, once per language per page. */
export const loadLabels = (hass) => {
  const language = languageOf(hass);
  if (!pending.has(language)) {
    pending.set(
      language,
      fetchLabels(hass, language).then((labels) => {
        resolved.set(language, labels);
        return labels;
      }),
    );
  }
  return pending.get(language);
};

/**
 * Failure is not an error worth surfacing: the household gets English, which is
 * what it got before any of this existed. A card whose words are a fallback is
 * still a working card, where one that refused to render would not be.
 */
const fetchLabels = async (hass, language) => {
  try {
    const { resources } = await hass.callWS({
      type: "frontend/get_translations",
      language,
      category: CATEGORY,
      integration: [DOMAIN],
    });
    return Object.freeze({ ...DEFAULTS, ...strip(resources) });
  } catch (error) {
    console.warn("home-energy-advisor: falling back to English labels", error);
    return DEFAULTS;
  }
};

/**
 * What is already loaded, for the synchronous render path.
 *
 * `_render` cannot await, so the words come from whatever `loadLabels` has
 * banked. A card's first paint is its loading state, and the fetch is awaited
 * before the first paint that shows figures.
 */
export const labelsFor = (hass) => resolved.get(languageOf(hass)) ?? DEFAULTS;

/** Home Assistant returns fully-qualified keys; the cards use the bare ones. */
const strip = (resources) =>
  Object.fromEntries(
    Object.entries(resources ?? {})
      .filter(([key, value]) => key.startsWith(PREFIX) && value)
      .map(([key, value]) => [key.slice(PREFIX.length), value]),
  );

/** `{range}`-style placeholders, filled the way Home Assistant fills its own. */
export const fill = (template, values) =>
  Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, value),
    template,
  );

/** Test seam: a fresh page has no cache, and neither should a fresh test. */
export const resetLabels = () => {
  pending.clear();
  resolved.clear();
};
