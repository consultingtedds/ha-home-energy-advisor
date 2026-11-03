/**
 * The browser manoeuvres both the screenshot run and the end-to-end suite need.
 *
 * Small, but each one encodes something about Home Assistant's frontend that
 * cost a run to discover. Two copies of that would rot separately, and the copy
 * nobody was looking at would be the one that mattered.
 */

/**
 * Click one of Home Assistant's icon buttons by its label.
 *
 * They carry the label as a *property* rather than an attribute, so none of
 * Playwright's accessible-name selectors can see it and the page offers sixty
 * identical-looking buttons instead. Hence the walk, and hence the walk into
 * every shadow root: the period picker's buttons are several roots deep.
 */
export async function clickIconButton(page, label) {
  const clicked = await page.evaluate((wanted) => {
    const search = (root) => {
      for (const element of root.querySelectorAll("*")) {
        if (element.tagName.toLowerCase() === "ha-icon-button" && element.label === wanted) {
          element.click();
          return true;
        }
        if (element.shadowRoot && search(element.shadowRoot)) return true;
      }
      return false;
    };
    return search(document);
  }, label);
  if (!clicked) throw new Error(`No icon button labelled "${label}"`);
  await page.waitForTimeout(1500);
}

/**
 * How many cards are showing their no-picker fallback.
 *
 * A card that cannot find the period picker falls back to a range of its own
 * and says so. That is the one fault which produces a page looking entirely
 * reasonable and being wrong - every figure is real, and for the wrong dates.
 * It is what HEA-119 was.
 *
 * Polled rather than sampled. A card emits the fallback the moment it is built
 * and swaps to the picker's period a beat later, and cards further down the
 * page are built later still, so a single look catches whichever happen to be
 * mid-flight and calls a healthy page broken.
 */
export async function strandedCards(page, { attempts = 30 } = {}) {
  let stranded = 0;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    stranded = await page.getByText("Add an Energy date picker card").count();
    if (stranded === 0) return 0;
    await page.waitForTimeout(1000);
  }
  return stranded;
}

/**
 * Which of the dashboard's tabs carries each card (HEA-257). The filter sits in
 * the pinned footer of every tab, so it is on whichever is open.
 */
const TAB_OF = {
  "hea-totals-card": "summary",
  "hea-cost-over-time-card": "summary",
  "hea-distribution-card": "summary",
  "hea-self-sufficiency-card": "summary",
  "hea-installation-card": "summary",
  "hea-devices-card": "devices",
  "hea-device-costs-card": "devices",
  "hea-sources-card": "devices",
  "hea-plans-card": "tariffs",
};

/** Long enough for a tab's cards to be built and fetch their figures. */
const CARD_PATIENCE_MS = 30000;

/**
 * Open the tab a card is on, and wait for that card to finish loading.
 *
 * Switched the way Home Assistant's own tabs switch, by pushing the path and
 * announcing it, never by loading the url: a load would rebuild the page and
 * throw away the period the picker was stepped to, which is exactly what a
 * household moving between tabs keeps.
 */
export async function showCard(page, dashboardPath, card) {
  const tab = TAB_OF[card];
  if (tab) {
    const wanted = `/${dashboardPath}/${tab}`;
    if (new URL(page.url()).pathname !== wanted) {
      await page.evaluate((path) => {
        history.pushState(null, "", path);
        window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
      }, wanted);
    }
  }
  const host = page.locator(card).first();
  await host.waitFor({ state: "attached", timeout: CARD_PATIENCE_MS });
  // Only a card with figures loads anything; the filter is drawn at once and
  // carries no loading state to wait on.
  if (!tab) return;
  const deadline = Date.now() + CARD_PATIENCE_MS;
  while (Date.now() < deadline) {
    const state = await host.evaluate(
      (element) => element.shadowRoot?.querySelector("[data-state]")?.dataset.state,
    );
    if (state && state !== "loading") return;
    await page.waitForTimeout(500);
  }
  throw new Error(`<${card}> was still loading after ${CARD_PATIENCE_MS / 1000}s`);
}

/** The period a card says it is showing, as its caption words it. */
export async function periodShown(page, card) {
  return page
    .locator(card)
    .first()
    .evaluate((element) => element.shadowRoot?.querySelector(".period")?.textContent?.trim());
}

/**
 * All the text one card renders, shadow roots included.
 *
 * A card is a custom element, so everything it draws lives in a shadow root and
 * `innerText` on the host returns an empty string. Playwright's locators pierce
 * shadow DOM, but reading text off the host does not, which is a quiet way to
 * conclude that a perfectly healthy card renders nothing.
 *
 * Anything a chart draws to a canvas is invisible to this and always will be.
 * That is a real limit on what can be asserted, not an oversight: the figures
 * this reads are the ones a screen reader could reach too.
 */
export async function cardText(page, tag) {
  return page.evaluate((wanted) => {
    const findHost = (root) => {
      for (const element of root.querySelectorAll("*")) {
        if (element.tagName.toLowerCase() === wanted) return element;
        if (element.shadowRoot) {
          const found = findHost(element.shadowRoot);
          if (found) return found;
        }
      }
      return null;
    };

    // A shadow root's stylesheet is a text node like any other, and a card's
    // CSS dwarfs its content - reading it back as "what the card renders" turns
    // an empty card into eight hundred characters of apparent success.
    const ignored = new Set(["style", "script", "template"]);

    const parts = [];
    const collect = (node) => {
      for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
          const text = child.textContent.trim();
          if (text) parts.push(text);
        } else if (child.nodeType === Node.ELEMENT_NODE) {
          if (ignored.has(child.tagName.toLowerCase())) continue;
          if (child.shadowRoot) collect(child.shadowRoot);
          collect(child);
        }
      }
    };

    const host = findHost(document);
    if (!host) return "";
    if (host.shadowRoot) collect(host.shadowRoot);
    collect(host);
    return parts.join(" ");
  }, tag);
}

/**
 * The names a chart card handed to the chart, rather than the ones on screen.
 *
 * `cardText` reads what is rendered, and a legend collapses its overflow behind
 * a "more" chip once there are more devices than fit - so on a house with a
 * dozen, reading the text says a card is missing devices it drew perfectly well.
 * This asks the card instead, which is the honest question for "did it draw
 * this": the legend's behaviour is HEA-100's deliberate trade and not the
 * subject of the check.
 */
export async function chartSeriesNames(page, tag) {
  return page.evaluate((wanted) => {
    const findHost = (root) => {
      for (const element of root.querySelectorAll("*")) {
        if (element.tagName.toLowerCase() === wanted) return element;
        if (element.shadowRoot) {
          const found = findHost(element.shadowRoot);
          if (found) return found;
        }
      }
      return null;
    };
    const host = findHost(document);
    const chart = host?.shadowRoot?.querySelector("ha-chart-base");
    const series = chart?.data ?? chart?.options?.series ?? [];
    return [...new Set(series.map((entry) => entry?.name).filter(Boolean))];
  }, tag);
}

/**
 * Step the dashboard back to the last complete day.
 *
 * The dashboard opens on today, and today is however many hours old the clock
 * says. A device that runs in the evening has not run yet, so it reads zero,
 * and a house where most devices cost nothing looks broken whether it is being
 * photographed or asserted against. Yesterday is a whole day for every device.
 */
export async function stepBackOneDay(page) {
  await clickIconButton(page, "Previous");
  await page.waitForTimeout(5000);
}
