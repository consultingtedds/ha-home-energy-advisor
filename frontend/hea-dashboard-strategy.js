/**
 * The dashboard Home Assistant offers a household under "Add dashboard".
 *
 * A strategy generates its config on every load rather than storing one, so a
 * device added later appears with no dashboard edit and an upgrade brings the
 * current layout with it. A household that wants to change something uses Home
 * Assistant's own "take control", which converts this into ordinary cards they
 * then own outright - so nothing here is a decision they cannot reverse.
 *
 * Registering in `customStrategies` is what puts it in the Add dashboard dialog
 * beside Map and Webpage. The same generated view is exposed as a view strategy
 * for a household that wants an HEA page on a dashboard they already have;
 * Home Assistant offers no picker for those, but it resolves when written into
 * a view by hand.
 */

import { readDevices, readWholeHome } from "./hea-devices.js";
import { hasAnInstallation } from "./hea-installation.js";
import { labelsFor, loadLabels } from "./hea-labels.js";
import { isAGridOnlyHome } from "./hea-statistics.js";

/** The `custom:` type a dashboard config names, without the prefix. */
export const STRATEGY_TYPE = "hea";

/**
 * What the dashboard is called, in the picker and in the create dialog.
 *
 * Two words at least: Home Assistant rejects a single-word url path, and the
 * create dialog derives the url by slugifying this title, so a one-word name
 * would silently become `dashboard-<name>`.
 */
const NAME = "Home Energy Advisor";

const ICON = "mdi:home-lightning-bolt";

export const DASHBOARD_TAG = `ll-strategy-dashboard-${STRATEGY_TYPE}`;
export const VIEW_TAG = `ll-strategy-view-${STRATEGY_TYPE}`;

/** How many columns the view lays sections across on a large screen. */
const MAX_COLUMNS = 4;

/**
 * The cards, in reading order: the headline across the page, then two columns.
 *
 * Money first and largest: the figures a household came for are the summary and
 * the per-device table, and the charts explain them. The table takes the full
 * width because it carries Paid and every add-on beside it in columns of their
 * own (ADR-0029), and squeezing it into half a large screen is what tempts a card
 * into folding them together. No card carries a `title`, because an absent one
 * falls back to the card's own translated default and a title written here would
 * be English everywhere.
 */
const HEADLINE = [
  { type: "custom:hea-totals-card" },
  { type: "custom:hea-devices-card", sort_by: "actual_cost" },
];

const FIGURES = [
  { type: "custom:hea-cost-over-time-card" },
  { type: "custom:hea-sources-card", sort_by: "energy_used" },
];

const CHARTS = [
  { type: "custom:hea-device-costs-card" },
  { type: "custom:hea-distribution-card" },
  { type: "custom:hea-self-sufficiency-card" },
];

/**
 * What the installation earned, after the gauge: the two whole-home answers sit
 * together (ADR-0034). Only for a home with generation or a battery, because on
 * the grid alone it could only say there is nothing to show.
 */
const INSTALLATION = { type: "custom:hea-installation-card" };

/**
 * The cards about where the energy came from, which a home on the grid alone
 * has no use for: the gauge could only read nought and the breakdown would be
 * grid in every row, beside a devices table already saying what each used
 * (HEA-253). They come back once a second source is added, with nothing to
 * configure, since the strategy is generated on every load.
 */
const ABOUT_SOURCES = new Set(["custom:hea-sources-card", "custom:hea-self-sufficiency-card"]);

const forSources = (cards, gridOnly) =>
  gridOnly ? cards.filter((card) => !ABOUT_SOURCES.has(card.type)) : cards;

const chartsFor = (hass) =>
  hasAnInstallation(hass, readWholeHome(hass)) ? [...CHARTS, INSTALLATION] : CHARTS;

const full = (card) => ({
  ...card,
  grid_options: { columns: "full", rows: "auto" },
});

const section = (cards, span) => ({
  type: "grid",
  column_span: span,
  cards: cards.map(full),
});

/**
 * The period picker and the page filter, pinned while the page scrolls.
 *
 * The picker is Home Assistant's own `energy-date-selection`: every HEA card
 * subscribes to the collection it owns rather than holding a date range, so the
 * control and its improvements are Home Assistant's. Neither card names a
 * collection key - both derive the same one from the dashboard's url, and
 * naming it here would be a guess at a url the household chooses.
 */
const footer = () => ({
  card: {
    type: "horizontal-stack",
    cards: [
      {
        type: "energy-date-selection",
        // The card's own option, passed straight through to the period
        // selector, which turns "up" into a `top-start` placement for the
        // calendar. Left at its default the calendar opens downwards from a
        // control already pinned to the bottom of the viewport, where a sticky
        // footer never scrolls to reach it (HEA-115).
        vertical_opening_direction: "up",
      },
      { type: "custom:hea-filter-card" },
    ],
  },
  max_width: 1600,
});

/**
 * What to show a household that has set the integration up but tracked nothing.
 *
 * Every card would render its own "no data" line, and eight of those read as a
 * fault rather than as the one step still outstanding.
 */
const nothingTracked = (hass) => ({
  type: "sections",
  max_columns: MAX_COLUMNS,
  sections: [
    {
      type: "grid",
      cards: [{ type: "markdown", content: labelsFor(hass).no_devices }],
    },
  ],
});

/**
 * The tariff plan comparison, where a household has entered a plan to compare
 * (HEA-255): a tab of its own on the dashboard, and a full-width section after
 * everything else on the single page (HEA-257).
 */
const PLANS = { type: "custom:hea-plans-card" };

/**
 * Whether the household has entered a plan. Asked of the integration, since a
 * plan is an entry rather than an entity; an integration from before plans
 * existed cannot say, and has none.
 */
const hasPlans = async (hass) => {
  try {
    const listed = await hass.callWS({ type: "home_energy_advisor/list_plans" });
    return Array.isArray(listed?.plans) && listed.plans.length > 0;
  } catch {
    return false;
  }
};

/**
 * A page of sections with the pinned controls. A section left with no card,
 * because none of its cards applies to this home, is dropped rather than drawn.
 * Home Assistant stacks sections on a narrow screen, so on a phone a page is
 * one column in this order.
 */
const page = (sections) => ({
  type: "sections",
  max_columns: MAX_COLUMNS,
  sections: sections.filter((built) => built.cards.length > 0),
  footer: footer(),
});

/**
 * Every card on one page: the view a household adds to a dashboard of their
 * own, which cannot hold tabs (HEA-257). Unchanged from before the dashboard
 * had them, so nothing on such a page goes missing on upgrade.
 */
const onePage = (hass, withPlans) => {
  if (readDevices(hass).length === 0) return nothingTracked(hass);
  const gridOnly = isAGridOnlyHome(hass);
  return page([
    section(HEADLINE, MAX_COLUMNS),
    section(forSources(FIGURES, gridOnly), MAX_COLUMNS / 2),
    section(forSources(chartsFor(hass), gridOnly), MAX_COLUMNS / 2),
    ...(withPlans ? [section([PLANS], MAX_COLUMNS)] : []),
  ]);
};

const [TOTALS, DEVICES_TABLE] = HEADLINE;
const [COST_OVER_TIME, SOURCES] = FIGURES;
const [DEVICE_COSTS, DISTRIBUTION, SELF_SUFFICIENCY] = CHARTS;

/** One tab: a page with the path it is linked by and a translated name. */
const tab = (hass, { path, titleKey, icon }, sections) => ({
  ...page(sections),
  path,
  title: labelsFor(hass)[titleKey],
  icon,
});

/**
 * The dashboard's tabs (HEA-257, GitHub discussion 58): the whole-home answers
 * first, the per-device detail behind them, and the plan comparison on a tab of
 * its own once there is a plan. The summary is first, so the dashboard's old
 * `/0` address still opens it. Each tab pins the same controls, and the picker
 * keys its period to the dashboard rather than the tab, so a period picked on
 * one is still picked on the next.
 */
const tabs = (hass, withPlans) => {
  if (readDevices(hass).length === 0) return [nothingTracked(hass)];
  const gridOnly = isAGridOnlyHome(hass);
  const installation = hasAnInstallation(hass, readWholeHome(hass)) ? [INSTALLATION] : [];
  const views = [
    tab(hass, { path: "summary", titleKey: "tab_summary", icon: "mdi:view-dashboard" }, [
      section([TOTALS], MAX_COLUMNS),
      section([COST_OVER_TIME, ...installation], MAX_COLUMNS / 2),
      section(forSources([DISTRIBUTION, SELF_SUFFICIENCY], gridOnly), MAX_COLUMNS / 2),
    ]),
    tab(hass, { path: "devices", titleKey: "tab_devices", icon: "mdi:format-list-bulleted" }, [
      section([DEVICES_TABLE], MAX_COLUMNS),
      section([DEVICE_COSTS], MAX_COLUMNS / 2),
      section(forSources([SOURCES], gridOnly), MAX_COLUMNS / 2),
    ]),
  ];
  if (withPlans) {
    views.push(
      tab(hass, { path: "tariffs", titleKey: "tab_tariffs", icon: "mdi:cash-multiple" }, [
        section([PLANS], MAX_COLUMNS),
      ]),
    );
  }
  return views;
};

/**
 * What every generation needs first: the household's own words, and whether it
 * has a plan to compare.
 *
 * The labels are awaited rather than read synchronously because a strategy runs
 * once per load and has nowhere to re-render from: a card can paint English and
 * correct itself, and this cannot.
 */
const prepare = async (hass) => {
  const [, withPlans] = await Promise.all([loadLabels(hass), hasPlans(hass)]);
  return withPlans;
};

class HeaDashboardStrategy extends HTMLElement {
  static async generate(_config, hass) {
    return { views: tabs(hass, await prepare(hass)) };
  }

  /** There is nothing to configure, so offer no editor for it. */
  static noEditor = true;

  /**
   * Fill in the dialog Home Assistant opens once this is chosen.
   *
   * Without these it opens empty and the household names something we have
   * already named. The url path is not offered here and does not need to be:
   * the dialog slugifies the suggested title into it.
   *
   * `registryDependencies` is deliberately not set. The built-in strategies
   * declare `[]`, which means never regenerating; this layout depends on
   * whether any device is tracked, so the default - entities, devices, areas
   * and floors - is what makes a first device appear without a reload.
   */
  static getCreateSuggestions() {
    return { title: NAME, icon: ICON };
  }
}

class HeaViewStrategy extends HTMLElement {
  static async generate(_config, hass) {
    return onePage(hass, await prepare(hass));
  }
}

const offer = (entry) => {
  globalThis.customStrategies = globalThis.customStrategies ?? [];
  if (!globalThis.customStrategies.some((s) => s.type === entry.type)) {
    globalThis.customStrategies.push(entry);
  }
};

export const register = () => {
  if (!customElements.get(DASHBOARD_TAG)) {
    customElements.define(DASHBOARD_TAG, HeaDashboardStrategy);
  }
  if (!customElements.get(VIEW_TAG)) {
    customElements.define(VIEW_TAG, HeaViewStrategy);
  }
  // Only dashboard strategies are listed: Home Assistant asks this registry for
  // `strategyType: "dashboard"` and nowhere asks it for views.
  offer({
    type: STRATEGY_TYPE,
    strategyType: "dashboard",
    name: NAME,
    description:
      "What each device cost to run, and what solar and the battery saved.",
  });
};

register();
