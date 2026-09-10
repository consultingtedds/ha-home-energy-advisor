/**
 * Photograph the demo house.
 *
 * Drives a real browser against the throwaway instance, at a fixed viewport so
 * the images are consistent and can be retaken when the interface moves. Four
 * of them come out of driving the setup flow rather than being staged, which is
 * why the integration is configured here and not in `setup.mjs` (HEA-80).
 *
 *   node demo/screenshots.mjs
 *
 * Nothing in the pictures is real. The house comes from `house.mjs` and the
 * figures from `seed.mjs`, and this script must never be pointed anywhere but
 * the container on loopback.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

import { DEVICES, HOUSE } from "./house.mjs";
import { BASE_URL, HaSocket, browserTokens, freshAuth } from "./ha-client.mjs";

/** Where the generated dashboard lives, as the strategy names it. */
const DASHBOARD_PATH = "home-energy-advisor";

const HERE = dirname(fileURLToPath(import.meta.url));
const IMAGES = join(HERE, "..", "docs", "images");

/**
 * One size for every shot.
 *
 * Wide enough that the cards lay out as they would on a desktop, and doubled in
 * density so the images stay sharp where a README renders them at half width.
 */
const VIEWPORT = { width: 1280, height: 1000 };
const SCALE = 2;

/**
 * The dashboard gets a wider frame than the dialogs do.
 *
 * Home Assistant lays a view out in columns sized to the window, so a narrow
 * frame shows one column and two cards, which is not what the dashboard looks
 * like on anybody's screen. A dialog is the opposite: it stays its own width
 * however much room it is given, and floats in the middle of the excess.
 */
const WIDE = { width: 1920, height: 1200 };

async function main() {
  const auth = await freshAuth();
  mkdirSync(IMAGES, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: SCALE,
    colorScheme: "light",
  });

  // Hand the frontend the session it would otherwise have stored after a login.
  // Driving the login form is a second thing that can break in a script whose
  // job is to photograph something else.
  const tokens = JSON.stringify(browserTokens(auth));
  await context.addInitScript(`window.localStorage.setItem("hassTokens", ${JSON.stringify(tokens)});`);

  const page = await context.newPage();
  try {
    // The setup shots can only be taken once, because they photograph a flow
    // that exists only on an instance that has not been through it. Everything
    // after can be retaken freely, which is what makes it worth checking rather
    // than demanding a rebuild for every run.
    if (await alreadyConfigured(page)) {
      console.log("Already configured, so the setup shots are skipped.");
      console.log("Run `node demo/reset.mjs && node demo/setup.mjs` to retake them.");
    } else {
      await captureSetup(page);
      await captureDevices(page);
    }
    await captureDiscovery(page);
    await captureDashboard(page, await dashboardExists(auth.access_token));

    // Seeded here rather than beforehand, because the seed writes to the
    // integration's own sensors and those do not exist until the devices have
    // been added above. Rerun every time: the window ends at the current hour,
    // so yesterday's figures would leave the cards showing a period that has
    // already slid out from under them.
    console.log("Seeding:");
    execFileSync(process.execPath, [join(HERE, "seed.mjs")], { stdio: "inherit" });

    await captureCards(browser, tokens);
  } catch (error) {
    // A failure here is a browser that is somewhere unexpected, and the message
    // alone never says where. Keep the evidence outside `docs/images`, which
    // holds only images we mean to publish.
    const path = join(HERE, "failure.png");
    await page.screenshot({ path }).catch(() => {});
    console.error(`Failed with the browser here: ${path}`);
    throw error;
  } finally {
    await browser.close();
  }
}

/**
 * Save one image, named as the README refers to it.
 *
 * The whole viewport rather than the element, deliberately. A dialog cropped to
 * its own edges loses the sidebar and the page behind it, and a reader who has
 * not seen the screen yet needs to know where in Home Assistant they are.
 */
async function shot(page, name) {
  await page.screenshot({ path: join(IMAGES, `${name}.png`) });
  console.log(`  ${name}.png`);
}

/**
 * The setup flow, photographed as it is driven.
 *
 * The deep link opens the flow directly rather than going through the add
 * dialog, so the shot does not depend on the integration picker's search
 * behaviour, which is not what these images are about.
 */
async function captureSetup(page) {
  console.log("Setup:");
  await page.goto(`${BASE_URL}/config/integrations/dashboard/add?domain=home_energy_advisor`);

  // The deep link asks before it starts the flow. Not a shot we want - it says
  // nothing a reader needs - so accept it and photograph what it opens.
  await page.getByRole("button", { name: "OK" }).click();

  // `ha-dialog` itself measures zero, so the step is the thing to photograph.
  const step = page.locator("step-flow-form").first();
  await step.waitFor({ state: "visible", timeout: 30000 });
  // The form arrives with the Energy Dashboard's answers already in it, so give
  // the fields a moment to settle before the shutter.
  await page.waitForTimeout(2500);

  // The one thing the Energy Dashboard cannot answer. Filling it before the
  // shot means the image shows a house step that is ready to submit, which is
  // what the README's caption claims it is.
  await pickEntity(page, HOUSE.importPrice);

  // The Energy Dashboard has no notion of a house-consumption meter, so this is
  // the other field it cannot answer. Worth setting rather than leaving: it is
  // what puts the accounting on ADR-0005's residual branch, and without it the
  // discovery screen quite correctly offers the house meter itself as a device
  // to track, which reads as nonsense in a screenshot.
  await pickEntity(page, HOUSE.houseConsumption);

  await page.waitForTimeout(1000);
  await shot(page, "setup-house-inputs");

  await page.getByRole("button", { name: "Submit" }).click({ force: true });
  await finish(page);
}

/**
 * Add every tracked device, photographing the first one.
 *
 * One shot rather than nine: the screen is the same each time, and the README
 * is showing a reader what the step looks like, not the whole house.
 */
async function captureDevices(page) {
  console.log("Devices:");
  for (const [index, device] of DEVICES.entries()) {
    await page.goto(`${BASE_URL}/config/integrations/integration/home_energy_advisor`);
    await page.getByRole("button", { name: "Add device" }).click();
    await page.locator("step-flow-form").first().waitFor({ state: "visible", timeout: 20000 });
    await page.waitForTimeout(1200);

    await page.locator("step-flow-form input").first().fill(device.name);
    // A power sensor goes in the second picker, which is the branch that has
    // the integration create an Integral helper to turn watts into energy.
    await pickEntity(page, device.source, device.kind === "power" ? 1 : 0);

    if (index === 0) await shot(page, "setup-add-device");

    await page.getByRole("button", { name: "Submit" }).click({ force: true });
    await finish(page);
    // Check the device actually arrived. A flow that silently fails leaves a
    // dialog that looks the same as one that succeeded, and the first version
    // of this loop cheerfully reported nine devices having created none.
    await confirmDeviceExists(page, device.name);
  }
  console.log(`  added ${DEVICES.length} devices`);
}

/**
 * Look the device up in the integration's own output rather than trusting the
 * flow to have worked.
 *
 * Polled, because the sensor is republished by a coordinator rather than
 * written by the flow, so it lags the dialog closing by a moment.
 */
async function confirmDeviceExists(page, name) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const found = await page.evaluate(async (deviceName) => {
      const response = await fetch("/api/states/sensor.home_energy_advisor_devices", {
        headers: { authorization: `Bearer ${JSON.parse(localStorage.hassTokens).access_token}` },
      });
      const sensor = await response.json();
      return (sensor.attributes?.devices ?? []).some((row) => row.name === deviceName);
    }, name);
    if (found) return;
    await page.waitForTimeout(500);
  }
  throw new Error(`"${name}" was submitted but never appeared. The flow did not complete.`);
}

/**
 * Close a flow that has just created something.
 *
 * Adding a device ends without a final step, so there is nothing to dismiss,
 * while the first setup of the integration does show one. Waiting for a button
 * that will never appear costs the whole run, so this only clicks one if it is
 * there.
 */
async function finish(page) {
  const button = page.getByRole("button", { name: "Finish" });
  try {
    await button.waitFor({ state: "visible", timeout: 4000 });
    await button.click({ force: true });
  } catch {
    // No closing step on this flow. Nothing to do.
  }
  await page.waitForTimeout(1000);
}

/**
 * Adding the dashboard, and then the dashboard itself.
 *
 * The point of the first shot is that Home Energy Advisor is simply in the list
 * of dashboards a household can add, with its title, icon and address already
 * filled in. There is nothing to install and no resource to register, and a
 * reader will not believe that until they see where it appears.
 */
async function captureDashboard(page, exists) {
  console.log("Dashboard:");
  await page.goto(`${BASE_URL}/config/lovelace/dashboards`);
  await page.waitForTimeout(2500);
  await page.getByRole("button", { name: "Add dashboard" }).first().click();
  await page.waitForTimeout(2000);
  await shot(page, "add-dashboard");

  // The dialog is the shot; creating the dashboard is only worth doing once. A
  // rerun that adds a second one leaves two identical entries in the sidebar,
  // and they turn up in every card shot taken afterwards.
  if (exists) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(1000);
    return;
  }
  await page.getByText("Home Energy Advisor", { exact: false }).last().click();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Create" }).first().click({ timeout: 20000 });
  await page.waitForTimeout(3000);
}

/**
 * Whether the dashboard is already there, asked over the websocket rather than
 * from inside the page. The frontend offers no endpoint that answers this, and
 * guessing wrong adds a duplicate to the sidebar of every later screenshot.
 */
async function dashboardExists(token) {
  const socket = await HaSocket.connect(token);
  try {
    const dashboards = await socket.send({ type: "lovelace/dashboards/list" });
    return dashboards.some((dashboard) => dashboard.url_path === DASHBOARD_PATH);
  } finally {
    socket.close();
  }
}

/**
 * The cards themselves.
 *
 * The page first, then each card on its own. A card is photographed as an
 * element rather than as a slice of the viewport, so the README can show one
 * answer at a time without the reader hunting for it.
 */
const CARDS = [
  ["hea-totals-card", "card-totals"],
  ["hea-devices-card", "card-devices"],
  ["hea-device-costs-card", "card-device-costs"],
  ["hea-cost-over-time-card", "card-cost-over-time"],
  ["hea-distribution-card", "card-distribution"],
  ["hea-self-sufficiency-card", "card-self-sufficiency"],
  ["hea-filter-card", "card-filter"],
];

async function captureCards(browser, tokens) {
  console.log("Cards:");
  // A context of its own, at its own density. The dialogs are photographed at
  // twice scale because they are narrow and their text is the point; the
  // dashboard is already 1920 across, and doubling that gives a 3840-pixel image
  // no README will ever render - it only makes the file too large to commit.
  //
  // A fresh page also matters here. The page that just created the dashboard
  // holds Lovelace's configuration from before it existed, so the cards come up
  // before they can find the period picker. A reload does not clear that; a new
  // page does.
  const context = await browser.newContext({
    viewport: WIDE,
    deviceScaleFactor: 1,
    colorScheme: "light",
  });
  await context.addInitScript(
    `window.localStorage.setItem("hassTokens", ${JSON.stringify(tokens)});`,
  );
  const page = await context.newPage();

  // Load something else first. This is a workaround for HEA-114, not politeness:
  // the dashboard does not render when it is the first page a browser loads,
  // because Lovelace asks for the strategy element before the module that
  // defines it has arrived. Any other Home Assistant page pulls the module in,
  // and the dashboard then works. Take the workaround out when that is fixed -
  // and if these shots start failing again, the bug is back.
  await page.goto(`${BASE_URL}/config/integrations/dashboard`);
  await page.waitForTimeout(4000);

  await page.goto(`${BASE_URL}/${DASHBOARD_PATH}`);

  // Give them time before believing what they show. A card caught mid-fetch has
  // every figure empty and says there is no cost in this period, which reads
  // exactly like a broken deploy.
  await page.locator("hea-totals-card").first().waitFor({ state: "visible", timeout: 30000 });
  await page.waitForTimeout(6000);

  // Never photograph a card that is on a fallback period. It is the one fault
  // that produces a picture which looks entirely reasonable and is wrong.
  //
  // Waited for rather than sampled: a card emits its fallback the moment it is
  // built and swaps to the picker's period a beat later, and cards further down
  // the page are built later still. Sampling once catches whichever happen to
  // be mid-flight.
  let stranded = 0;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    stranded = await page.getByText("Add an Energy date picker card").count();
    if (stranded === 0) break;
    await page.waitForTimeout(1000);
  }
  if (stranded > 0) {
    throw new Error(
      `${stranded} cards did not find the period picker. Their figures are for a ` +
        "fallback range, so the shot would misrepresent what the dashboard does.",
    );
  }

  // Step back to the last complete day. The dashboard opens on today, and today
  // is however many hours old the clock says: a device that runs in the evening
  // has not run yet, so it reads zero, and a house where most devices cost
  // nothing photographs as a broken one. Yesterday is a whole day for every
  // device, which is what the README is illustrating.
  await clickIconButton(page, "Previous");
  await page.waitForTimeout(5000);

  await shot(page, "dashboard");

  for (const [tag, name] of CARDS) {
    const card = page.locator(tag).first();
    if ((await card.count()) === 0) {
      console.log(`  ${tag} is not on the page`);
      continue;
    }
    await card.scrollIntoViewIfNeeded();
    await page.waitForTimeout(1200);
    await card.screenshot({ path: join(IMAGES, `${name}.png`) });
    console.log(`  ${name}.png`);
  }
}

/** Whether this instance has already been through the setup flow. */
async function alreadyConfigured(page) {
  await page.goto(`${BASE_URL}/config/integrations/dashboard`);
  return page.evaluate(async () => {
    const response = await fetch("/api/states/sensor.home_energy_advisor_devices", {
      headers: { authorization: `Bearer ${JSON.parse(localStorage.hassTokens).access_token}` },
    });
    return response.ok;
  });
}

/**
 * The discovery screen, listing the sensors the household has not tracked yet.
 *
 * Photographed and then abandoned rather than submitted. The demo deliberately
 * leaves these untracked so the screen has something to show, and two of them
 * are the false friends the integration sorts last.
 */
async function captureDiscovery(page) {
  console.log("Discovery:");
  await page.goto(`${BASE_URL}/config/integrations/integration/home_energy_advisor`);
  // The entry rows render after the page does, and the button we want is on one
  // of them, so searching immediately finds a page that has not drawn it yet.
  await page.getByText("Untracked Energy Devices").first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(1000);
  await clickIconButton(page, "Configure");
  await page.getByText("Discover devices to track", { exact: false }).first().click();
  await page.locator("step-flow-form").first().waitFor({ state: "visible", timeout: 20000 });
  await page.waitForTimeout(2500);
  await shot(page, "discover-devices");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(1000);
}

/**
 * Click one of Home Assistant's icon buttons by its label.
 *
 * They carry the label as a property rather than an attribute, so none of
 * Playwright's accessible-name selectors can see it and the page offers sixty
 * identical-looking buttons instead.
 */
async function clickIconButton(page, label) {
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
 * Choose an entity in one of Home Assistant's pickers.
 *
 * The picker is a field that opens a search dialog rather than a combo box, so
 * this clicks it open, searches, and takes the result. Setting a value directly
 * would not do: the picker only commits a choice that was actually chosen.
 */
async function pickEntity(page, entityId, nth = 0) {
  // How many search boxes exist before the picker adds its own, so we can tell
  // when it has gone again.
  const searchBoxes = page.getByPlaceholder("Search", { exact: true });
  const before = await searchBoxes.count();

  await page.getByText("Select an entity", { exact: false }).nth(nth).click();
  // The last one on the page, not the first. The integration page has a search
  // box of its own, sitting behind the dialog and unclickable, and the picker's
  // is appended when it opens.
  const search = page.getByPlaceholder("Search", { exact: true }).last();
  await search.waitFor({ state: "visible", timeout: 15000 });
  // Searched by entity id, which is unambiguous, then taken by its displayed
  // name: searching by name would also match the sensors the integration goes
  // on to create from it.
  //
  // Typed at the keyboard, not clicked and filled. The picker focuses its own
  // search box when it opens, so there is nothing to click, and clicking anyway
  // lands on the dialog's scroll lock. Filling the value rather than typing
  // leaves the list unfiltered, which quietly worked only for the entities that
  // happen to sort near the top.
  await page.waitForTimeout(700);
  await search.focus();
  await page.keyboard.type(entityId, { delay: 25 });
  // Wait for the result rather than for a length of time. The list is filtered
  // asynchronously, and a fixed pause is only ever right on the run you tuned it
  // on - this failed on the fourth device, not the first.
  // The last match, because the name also appears on the field being filled in
  // once a previous run has put it there, and the results come later in the DOM.
  const option = page.getByText(friendlyName(entityId), { exact: true }).last();
  await option.waitFor({ state: "visible", timeout: 20000 });

  // Clicked, and not forced. Two things that look like fixes are not: forcing
  // the click puts it through at coordinates something else is covering, and
  // pressing Enter on a highlighted row opens that entity's info dialog instead
  // of choosing it. Both leave the field empty and the run looking fine.
  //
  // An unforced click works here only because the search above has filtered the
  // list down, which is also what stops it moving around.
  await option.click();
  // Wait for the picker's own search box to go, by counting rather than by
  // asking whether it is hidden: once it closes, that locator re-resolves onto
  // the page's search box behind the dialog, which is visible and always will
  // be. This matters more than it looks. The next click is forced, so if the
  // overlay is still up the click lands on the overlay, the form is never
  // submitted, and the run reports a device it did not add.
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if ((await searchBoxes.count()) <= before) break;
    await page.waitForTimeout(250);
  }
  await page.waitForTimeout(400);
}

/**
 * What Home Assistant shows for one of the demo's own sensors.
 *
 * Only sound because we wrote `configuration.yaml`: Home Assistant built each
 * entity id by slugifying the name we gave it, so reversing that is exact here
 * and would not be for a sensor from anywhere else.
 */
function friendlyName(entityId) {
  return entityId
    .replace(/^sensor\./, "")
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

await main();
