/**
 * Load the dashboard cold, over and over, and count how often it comes up.
 *
 * This is HEA-114's acceptance criterion made runnable: ten consecutive direct
 * loads with no timeout. Until the demo instance existed there was nowhere to
 * ask that question, so the fix for it was written from an inference about how
 * Home Assistant loads modules, shipped green, and did not work.
 *
 *   node demo/cold-load.mjs [runs]
 *
 * Cold means cold. Each run gets its own browser, so nothing is cached from the
 * one before: no module, no strategy element, no connection. That is what a
 * household does when they click the sidebar entry after restarting their
 * browser, and it is the path that fails.
 */

import { chromium } from "playwright";

import { BASE_URL, browserTokens, freshAuth } from "./ha-client.mjs";

const DASHBOARD_PATH = "home-energy-advisor";

/** How long to give the page before calling it a failure. */
const PATIENCE_MS = 20000;

/** The error Home Assistant logs when it gives up waiting for our strategy. */
const STRATEGY_ERROR = "strategy element";

async function main() {
  const runs = Number(process.argv[2] ?? 10);
  const auth = await freshAuth();
  const tokens = JSON.stringify(browserTokens(auth));

  const results = [];
  for (let run = 1; run <= runs; run += 1) {
    const result = await coldLoad(tokens);
    results.push(result);
    const outcome = result.rendered ? `${result.ms} ms` : "FAILED";
    console.log(`  run ${String(run).padStart(2)}: ${outcome}${result.strategyError ? "  (strategy timeout)" : ""}`);
  }

  const failures = results.filter((result) => !result.rendered);
  const times = results.filter((result) => result.rendered).map((result) => result.ms);
  console.log("");
  console.log(`${results.length - failures.length} of ${results.length} loads rendered the cards.`);
  if (times.length > 0) {
    const slowest = Math.max(...times);
    const median = times.sort((a, b) => a - b)[Math.floor(times.length / 2)];
    console.log(`median ${median} ms, slowest ${slowest} ms.`);
  }
  if (failures.length > 0) {
    process.exitCode = 1;
  }
}

async function coldLoad(tokens) {
  // A whole browser rather than a context. A context shares the browser's
  // compiled module cache, which is exactly the thing that makes the second
  // load succeed where the first did not.
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    await context.addInitScript(
      `window.localStorage.setItem("hassTokens", ${JSON.stringify(tokens)});`,
    );
    const page = await context.newPage();

    let strategyError = false;
    page.on("console", (message) => {
      if (message.type() === "error" && message.text().includes(STRATEGY_ERROR)) {
        strategyError = true;
      }
    });

    const started = Date.now();
    await page.goto(`${BASE_URL}/${DASHBOARD_PATH}`);
    try {
      await page
        .locator("hea-totals-card")
        .first()
        .waitFor({ state: "visible", timeout: PATIENCE_MS });
      return { rendered: true, ms: Date.now() - started, strategyError };
    } catch {
      return { rendered: false, ms: Date.now() - started, strategyError };
    }
  } finally {
    await browser.close();
  }
}

await main();
