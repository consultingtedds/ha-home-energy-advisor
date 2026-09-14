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
