/**
 * One command: build a demo house, assert against it, then do it again in
 * Spanish (HEA-116).
 *
 *   node demo/run-e2e.mjs          # both passes, then tear the container down
 *   node demo/run-e2e.mjs en       # the English pass only
 *   node demo/run-e2e.mjs es       # the Spanish pass only
 *   node demo/run-e2e.mjs --keep   # leave the instance up to poke at
 *   node demo/run-e2e.mjs --engine # no seed: assert what the engine computed
 *
 * ## The two modes, and what each is worth
 *
 * By default the week is **seeded** - figures written straight into statistics,
 * which is what lets a container ten minutes old show a dashboard worth
 * asserting against. That proves the display path end to end and proves nothing
 * about the accounting: the cards are being checked against numbers we handed
 * them.
 *
 * `--engine` seeds nothing. The demo's meters advance on their own, the engine
 * accounts for them, and every figure on the page is one it computed. That is
 * the product doing what it claims, inside a real Home Assistant. It costs
 * about an hour, for reasons `engine.mjs` sets out and which cannot be removed
 * without changing the product to suit the test.
 *
 * Run the default after a card change. Run `--engine` before a release.
 *
 * ## Why each pass rebuilds from nothing
 *
 * Home Assistant builds an entity id from the entity's translated name, and it
 * does that **once**, when the entity is first registered. The entity registry
 * then keeps that id forever, keyed by `unique_id` - deleting the integration
 * and adding it back restores the ids it had before.
 *
 * So a Spanish pass cannot be a language switch on a running house. It needs an
 * instance whose language was Spanish before the integration ever created an
 * entity, which means a reset. That is the whole reason this takes minutes
 * rather than seconds, and it is not avoidable.
 *
 * ## Only the *instance* language changes
 *
 * The account stays English, so the browser automation keeps meeting English
 * menus while the entity ids underneath it are Spanish. That is deliberate:
 * translating the automation as well would double what can break without
 * testing anything more, and `hass.config.language` is what decides ids.
 */

import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  HaSocket,
  entityIdForUniqueId,
  freshAuth,
  waitForHomeAssistant,
} from "./ha-client.mjs";
import { configureIntegration } from "./configure.mjs";
import { waitForEngine, waitForHourlyStatistics } from "./engine.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const COMPOSE = join(HERE, "compose.yaml");

/** The languages a pass can run in. Spanish because the integration ships it. */
const LANGUAGES = ["en", "es"];

function step(command, args, { allowFailure = false } = {}) {
  try {
    execFileSync(command, args, { stdio: "inherit", cwd: join(HERE, "..") });
    return true;
  } catch (error) {
    if (allowFailure) return false;
    throw error;
  }
}

const node = (script, ...args) => step(process.execPath, [join(HERE, script), ...args]);

/** For the suite itself, whose failure is a result to report, not a crash. */
const nodeReporting = (script, ...args) =>
  step(process.execPath, [join(HERE, script), ...args], { allowFailure: true });

/**
 * Point the instance at a language before the integration creates anything.
 *
 * Ordered between setup and configure for that reason alone. Run it after the
 * integration is added and it changes what the frontend says while every entity
 * id keeps the name it was born with, which looks like a passing Spanish run
 * and is not one.
 */
async function setLanguage(language) {
  const auth = await freshAuth();
  const socket = await HaSocket.connect(auth.access_token);
  try {
    await socket.send({ type: "config/core/update", language });
    console.log(`  instance language set to ${language}`);
  } finally {
    socket.close();
  }
}

async function pass(language, engineMode) {
  console.log("");
  console.log(`=== ${language.toUpperCase()} =======================================`);
  console.log("");

  console.log("Resetting the instance...");
  node("reset.mjs");
  await waitForHomeAssistant();

  console.log("Building the house...");
  node("setup.mjs");

  if (language !== "en") await setLanguage(language);

  console.log("Setting the integration up...");
  const auth = await freshAuth();
  await configureIntegration(auth.access_token);

  if (engineMode) {
    // No seed. The whole point of engine mode is that every figure on the page
    // was computed here, so writing a fabricated week over the top would defeat
    // it entirely.
    console.log("Waiting for the engine to close its first interval...");
    const auth2 = await freshAuth();
    const totals = await waitForEngine(auth2.access_token);
    if (!totals) {
      console.log("  the engine published nothing within the bound; checking anyway");
    } else {
      console.log(
        `  whole home so far: ${totals.wholeHome.cost.toFixed(4)} over ` +
          `${totals.wholeHome.energy.toFixed(3)} kWh`,
      );
      console.log("Waiting for an hourly statistic, which is what the cards read...");
      const socket = await HaSocket.connect(auth2.access_token);
      try {
        const devicesSensor = await entityIdForUniqueId(auth2.access_token, "_devices");
        const sensor = devicesSensor ? await stateOf(auth2.access_token, devicesSensor) : null;
        const wholeHomeCost = sensor?.attributes?.whole_home?.statistics?.actual_cost;
        if (wholeHomeCost) await waitForHourlyStatistics(socket, wholeHomeCost);
      } finally {
        socket.close();
      }
    }
  } else {
    console.log("Seeding a week...");
    node("seed.mjs");
  }

  console.log("");
  console.log("Checking...");
  return nodeReporting("e2e.mjs", ...(engineMode ? ["--engine"] : []));
}

/** One entity's state, for the couple of lookups this file needs. */
async function stateOf(token, entityId) {
  const { BASE_URL } = await import("./ha-client.mjs");
  return fetch(`${BASE_URL}/api/states/${entityId}`, {
    headers: { authorization: `Bearer ${token}` },
  }).then((response) => response.json());
}

async function main() {
  const args = process.argv.slice(2);
  const keep = args.includes("--keep");
  const engineMode = args.includes("--engine");
  const chosen = args.filter((arg) => LANGUAGES.includes(arg));
  // Engine mode defaults to one language. What it asserts is the accounting,
  // which is the same arithmetic whatever the entity ids are called, and the
  // wait is an hour - paying it twice buys nothing the Spanish pass has not
  // already proved in its ten-minute form.
  const fallback = engineMode ? ["en"] : LANGUAGES;
  const languages = chosen.length > 0 ? chosen : fallback;

  if (engineMode) {
    console.log("Engine mode: nothing will be seeded, and this takes about an hour.");
    console.log("The engine publishes nothing for its first 20 minutes by design,");
    console.log("and the cards read hourly statistics compiled on the hour.");
    console.log("");
  }

  console.log("Bringing the demo instance up...");
  step("docker", ["compose", "-f", COMPOSE, "up", "-d"]);
  await waitForHomeAssistant();

  const outcomes = [];
  try {
    for (const language of languages) {
      // Each pass reports rather than throws, so a Spanish failure still gets
      // an English result to be compared against - which is most of what makes
      // a translated-instance failure diagnosable.
      let passed = false;
      try {
        passed = await pass(language, engineMode);
      } catch (error) {
        console.log(`  ${language} pass could not run: ${error.message}`);
      }
      outcomes.push({ language, passed });
    }
  } finally {
    if (keep) {
      console.log("");
      console.log("Instance left running (--keep). `node demo/reset.mjs` when done.");
    } else {
      console.log("");
      console.log("Tearing the instance down...");
      step("docker", ["compose", "-f", COMPOSE, "down"], { allowFailure: true });
    }
  }

  console.log("");
  console.log("=== Result ================================================");
  for (const outcome of outcomes) {
    console.log(`  ${outcome.language}: ${outcome.passed ? "passed" : "FAILED"}`);
  }
  if (outcomes.some((outcome) => !outcome.passed)) process.exitCode = 1;
}

await main();
