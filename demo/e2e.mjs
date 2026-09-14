/**
 * End-to-end checks against the demo instance (HEA-116).
 *
 *   node demo/e2e.mjs            # assert against a house that is already built
 *   node demo/run-e2e.mjs        # build one, assert, and do it again in Spanish
 *
 * ## Why a third test stack earns its keep
 *
 * The card unit tests mount a card against a double written from the same
 * belief as the card. A double like that cannot disagree, and HEA-84 shipped
 * broken past 501 green tests because of it. These checks load the real
 * dashboard in a real Home Assistant and read what a household would see, which
 * is the only kind of test here that can tell us we were wrong.
 *
 * They also reach things a unit test structurally cannot: the dashboard
 * strategy Lovelace resolves at runtime, the card picker's registry, the single
 * bundle the integration serves, and entity ids Home Assistant translated.
 *
 * ## What it asserts, and what it refuses to
 *
 * Figures, never pixels. A screenshot comparison rots against Home Assistant's
 * own UI within a release or two and then trains everyone to ignore it.
 *
 * ## Not one of the gates
 *
 * Deliberately outside the five. It is slow, it needs Docker, and Home
 * Assistant ships monthly and will break it periodically. Run it when the
 * answer matters - before a release, or after a change to the cards.
 */

import { chromium } from "playwright";

import {
  BASE_URL,
  browserTokens,
  entityIdForUniqueId,
  freshAuth,
} from "./ha-client.mjs";
import { DEVICES } from "./house.mjs";
import { cardText, stepBackOneDay, strandedCards } from "./browser.mjs";

const DASHBOARD_PATH = "home-energy-advisor";
const VIEWPORT = { width: 1600, height: 1200 };

/** Long enough for a cold module load, which is the slow path (HEA-114). */
const PATIENCE_MS = 30000;

/** Every card the dashboard strategy lays out, by its custom element name. */
const CARDS = [
  "hea-totals-card",
  "hea-devices-card",
  "hea-device-costs-card",
  "hea-cost-over-time-card",
  "hea-sources-card",
  "hea-distribution-card",
  "hea-self-sufficiency-card",
  "hea-filter-card",
];

/**
 * What the served bundle should weigh, and how far it may drift before someone
 * looks. One request of about 51 KB is right; 25 requests means a deploy left
 * the old modules behind, which has happened and looked fine.
 */
const BUNDLE_KB = { min: 30, max: 90 };

const results = [];

/** Run one check, record the outcome, and never let a throw end the suite. */
async function check(name, body) {
  try {
    await body();
    results.push({ name, ok: true });
    console.log(`  ok    ${name}`);
  } catch (error) {
    results.push({ name, ok: false, error });
    console.log(`  FAIL  ${name}`);
    console.log(`        ${error.message}`);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function main() {
  const auth = await freshAuth();
  const tokens = JSON.stringify(browserTokens(auth));
  const browser = await chromium.launch();

  try {
    const context = await browser.newContext({ viewport: VIEWPORT });
    await context.addInitScript(
      `window.localStorage.setItem("hassTokens", ${JSON.stringify(tokens)});`,
    );
    const page = await context.newPage();

    const language = await coreLanguage(auth.access_token);
    console.log(`Home Assistant language: ${language}`);
    console.log("");

    await addDashboardChecks(page, auth.access_token);

    await page.goto(`${BASE_URL}/${DASHBOARD_PATH}`);
    await page
      .locator("hea-totals-card")
      .first()
      .waitFor({ state: "visible", timeout: PATIENCE_MS });
    // Give the cards time before believing what they show. One caught mid-fetch
    // has every figure empty and reads exactly like a broken deploy.
    await page.waitForTimeout(6000);

    await dashboardChecks(page);
    await periodChecks(page);
    await figureChecks(page);
    await bundleChecks(page);
    await entityIdChecks(page, auth.access_token, language);
    await cardPickerChecks(page);
  } finally {
    await browser.close();
  }

  report();
}

/** The instance's own language, which is what decides entity ids (ADR-0018). */
async function coreLanguage(token) {
  const response = await fetch(`${BASE_URL}/api/config`, {
    headers: { authorization: `Bearer ${token}` },
  });
  const config = await response.json();
  return config.language ?? "en";
}

/**
 * The route a household actually takes, driven rather than assumed.
 *
 * The integration registers a dashboard strategy, and what that buys is an
 * entry in Home Assistant's own Add dashboard dialog - no resource to register
 * and nothing to install (ADR-0020). If our entry is not in that list the route
 * silently does not exist, so the dialog is opened and read rather than the
 * dashboard being created behind its back over the websocket.
 *
 * Creating it that way would also have hidden the failure this catches: a
 * strategy that never registers still resolves perfectly well from a config
 * saved by hand.
 */
async function addDashboardChecks(page, token) {
  console.log("Home Assistant offers the dashboard itself:");

  const devicesSensor = await entityIdForUniqueId(token, "_devices");
  assert(devicesSensor, "the integration is not set up on this instance");

  await page.goto(`${BASE_URL}/config/lovelace/dashboards`);
  await page.waitForTimeout(2500);

  const already = await page.locator(`a[href="/${DASHBOARD_PATH}"]`).count();
  await page.getByRole("button", { name: "Add dashboard" }).first().click();
  await page.waitForTimeout(2000);

  await check("Home Energy Advisor is offered in Add dashboard", async () => {
    const offered = await page
      .getByText("Home Energy Advisor", { exact: false })
      .count();
    assert(
      offered > 0,
      "the strategy is not in the Add dashboard dialog, so a household has no " +
        "way to install the dashboard at all",
    );
  });

  if (already > 0) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(1000);
    console.log("");
    return;
  }

  await page.getByText("Home Energy Advisor", { exact: false }).last().click();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Create" }).first().click({ timeout: 20000 });
  await page.waitForTimeout(3000);
  console.log("  ok    the dashboard was created from the dialog");
  console.log("");
}

async function dashboardChecks(page) {
  console.log("The dashboard a household installs:");

  await check("the generated dashboard renders", async () => {
    const title = await page.title();
    assert(title.length > 0, "the page has no title, so nothing rendered");
  });

  for (const card of CARDS) {
    await check(`${card} is laid out by the strategy`, async () => {
      const count = await page.locator(card).count();
      assert(count > 0, `no <${card}> on the dashboard`);
    });
  }
  console.log("");
}

/**
 * Every card follows the dashboard's own period picker.
 *
 * A card that cannot find the picker falls back to a range of its own and says
 * so on its face. That is the fault which produces a page looking entirely
 * reasonable and being wrong - every figure real, and for the wrong dates - and
 * it is what HEA-119 was. Nothing in the unit tests can see it, because the
 * picker is Home Assistant's and the collection is shared through a connection
 * a double does not have.
 *
 * The step back to yesterday belongs here rather than in the fixture: the
 * dashboard opening on a part-finished today is correct behaviour, and a device
 * that runs in the evening reading zero at ten in the morning is not a defect
 * to assert against.
 */
async function periodChecks(page) {
  console.log("The cards follow the dashboard's period picker:");

  await check("no card is stranded on a fallback period", async () => {
    const stranded = await strandedCards(page);
    assert(
      stranded === 0,
      `${stranded} cards never found the period picker, so their figures are ` +
        "for a range of their own choosing",
    );
  });

  await stepBackOneDay(page);
  console.log("  ok    stepped back to the last complete day");
  console.log("");
}

/**
 * The check this suite exists for.
 *
 * HEA-84 rendered cards that were structurally perfect and completely empty,
 * and every unit test passed because each asserted what its own card claimed
 * and none asked what a card must never do. A card showing no figure at all is
 * the failure mode, so it is the thing asserted.
 */
async function figureChecks(page) {
  console.log("Cards carry figures, not just structure:");

  await check("the totals card shows money", async () => {
    const figures = await moneyIn(page, "hea-totals-card");
    assert(figures.length > 0, "the totals card rendered no currency figure at all");
    assert(
      figures.some((amount) => amount > 0),
      `every figure on the totals card is zero: ${figures.join(", ")}`,
    );
  });

  await check("the device costs card names every tracked device", async () => {
    const text = await cardText(page, "hea-device-costs-card");
    const missing = DEVICES.filter((device) => !text.includes(device.name));
    assert(
      missing.length === 0,
      `absent from the card: ${missing.map((device) => device.name).join(", ")}`,
    );
  });

  await check("the devices card shows a figure for every device", async () => {
    const figures = await moneyIn(page, "hea-devices-card");
    // Four money columns a row - paid, would have paid, saved - plus the
    // Untracked remainder alongside the tracked devices.
    assert(
      figures.length >= DEVICES.length,
      `${figures.length} figures for ${DEVICES.length} devices`,
    );
  });

  await check("a device that lost money shows it as a loss", async () => {
    const figures = await moneyIn(page, "hea-devices-card");
    // The demo house runs its car charger off stored energy that cost more than
    // the tariff it displaced, which is a real outcome of battery arbitrage and
    // the one figure a household is most likely to disbelieve. If it renders as
    // a positive the sign has been lost somewhere between the engine and the
    // screen, and every saving on the page is then suspect.
    assert(
      figures.some((amount) => amount < 0),
      "no negative figure anywhere on the card, though the seeded house has one",
    );
  });

  await check("no card renders the empty-period message", async () => {
    const empty = await page.getByText("No cost recorded in this period").count();
    assert(empty === 0, "a card reported an empty period against a seeded week");
  });
  console.log("");
}

/**
 * Every currency figure a card rendered, as numbers.
 *
 * Read from the rendered text rather than from any internal state, because what
 * the household sees is the claim being tested. Parsed for both separators: the
 * demo runs in Europe/Madrid and a Spanish instance formats 1.234,56 where an
 * English one formats 1,234.56.
 */
async function moneyIn(page, card) {
  const text = await cardText(page, card);
  // The minus can fall either side of the symbol: a card renders -€0.29 and a
  // locale may render €-0.29. Reading only one of them turns a loss into a
  // saving, which is the single figure on the page it matters most to get right.
  const matches = text.match(/-?[€$£]\s?-?[\d.,]+|-?[\d.,]+\s?[€$£]/g) ?? [];
  return matches
    .map((raw) => {
      const negative = raw.trimStart().startsWith("-") || raw.includes("-");
      const digits = raw.replace(/[^\d.,]/g, "");
      // Whichever separator comes last is the decimal one.
      const normalised =
        digits.lastIndexOf(",") > digits.lastIndexOf(".")
          ? digits.replace(/\./g, "").replace(",", ".")
          : digits.replace(/,/g, "");
      const amount = Number.parseFloat(normalised);
      return negative ? -amount : amount;
    })
    .filter((amount) => Number.isFinite(amount));
}

/**
 * The deploy check, made automatic.
 *
 * `CLAUDE.local.md` has a human paste this into a console after every deploy,
 * because a stale copy on the share serves old modules that a screenshot cannot
 * distinguish from a good one. Asking the page what it actually fetched is the
 * only reliable answer, so it belongs here rather than in a procedure.
 */
async function bundleChecks(page) {
  console.log("The bundle the integration serves:");

  const requests = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .filter((entry) => entry.name.includes("/home_energy_advisor/"))
      .map((entry) => ({ name: entry.name, size: entry.transferSize || entry.encodedBodySize })),
  );

  await check("the cards arrive as a single request", async () => {
    assert(requests.length > 0, "the page fetched nothing from /home_energy_advisor/");
    assert(
      requests.length === 1,
      `${requests.length} requests, so old module files are still being served:\n` +
        requests.map((request) => `          ${request.name}`).join("\n"),
    );
  });

  await check("the bundle is the expected size", async () => {
    const kb = Math.round(requests[0].size / 1024);
    assert(
      kb >= BUNDLE_KB.min && kb <= BUNDLE_KB.max,
      `the bundle is ${kb} KB, outside the expected ${BUNDLE_KB.min}-${BUNDLE_KB.max} KB`,
    );
  });

  await check("the url carries a content digest", async () => {
    assert(
      /\/home_energy_advisor\/[^/]+-[0-9a-f]{6,}\/hea-cards\.js/.test(requests[0].name),
      `no version and digest in ${requests[0].name}`,
    );
  });
  console.log("");
}

/**
 * The bug class that cannot be reproduced on an English instance at all.
 *
 * Home Assistant builds an entity id from the entity's *translated* name in 41
 * languages, Spanish among them. A card composing `sensor.<key>_actual_cost`
 * asks for something that exists only in English, and every card on a Spanish
 * install renders empty (ADR-0018). The integration publishes the real ids on
 * its devices sensor precisely so nothing has to guess.
 *
 * On a Spanish instance this asserts the ids really did move - otherwise the
 * whole Spanish run could pass while proving nothing, which is the shape of
 * failure this project has already met once.
 */
async function entityIdChecks(page, token, language) {
  console.log("Entity ids come from Home Assistant, not from a template:");

  // Resolved by unique_id, which is the rule this check exists to enforce. The
  // first version of this suite composed the English id and reported that a
  // Spanish instance had published no devices - the bug, in the test for it.
  const devicesSensor = await entityIdForUniqueId(token, "_devices");
  assert(devicesSensor, "no devices sensor is registered on this instance");
  const devices = await fetch(`${BASE_URL}/api/states/${devicesSensor}`, {
    headers: { authorization: `Bearer ${token}` },
  }).then((response) => response.json());
  const rows = devices?.attributes?.devices ?? [];

  await check("the devices sensor publishes a statistic id per device", async () => {
    assert(rows.length > 0, "the devices sensor published no devices");
    for (const row of rows) {
      assert(
        typeof row.statistics?.actual_cost === "string",
        `${row.key} publishes no actual_cost statistic id`,
      );
    }
  });

  if (language === "en") {
    console.log("        (the translated-id check needs a Spanish instance)");
    console.log("");
    return;
  }

  await check("a translated instance really did move the entity ids", async () => {
    const composed = rows.filter((row) => row.statistics.actual_cost.endsWith("_actual_cost"));
    assert(
      composed.length === 0,
      "entity ids still end in the English suffix, so this instance is not " +
        `translated and the run proves nothing: ${composed[0]?.statistics.actual_cost}`,
    );
  });

  await check("the cards still render against translated ids", async () => {
    const figures = await moneyIn(page, "hea-totals-card");
    assert(
      figures.some((amount) => amount > 0),
      "the totals card is empty on a translated instance - the exact failure " +
        "ADR-0018 exists to prevent",
    );
  });
  console.log("");
}

/**
 * That a household can find the cards at all.
 *
 * The dashboard strategy is one of three routes HEA-94 ships; this is the one
 * for somebody who already has a dashboard they like. If the cards are not in
 * the picker, that route silently does not exist.
 */
async function cardPickerChecks(page) {
  console.log("The cards are offered in the card picker:");

  await check("the picker lists Home Energy Advisor's cards", async () => {
    const registered = await page.evaluate(() =>
      Object.keys(window.customCards ?? {}).length > 0
        ? window.customCards.map((card) => card.type)
        : (window.customCards ?? []).map((card) => card.type),
    );
    const ours = registered.filter((type) => type.startsWith("hea-"));
    assert(
      ours.length >= CARDS.length - 1,
      `only ${ours.length} cards registered with the picker: ${ours.join(", ")}`,
    );
  });
  console.log("");
}

function report() {
  const failed = results.filter((result) => !result.ok);
  console.log("");
  console.log(`${results.length - failed.length} of ${results.length} checks passed.`);
  if (failed.length > 0) {
    console.log("");
    console.log("Failed:");
    for (const result of failed) console.log(`  ${result.name}`);
    process.exitCode = 1;
  }
}

await main();
