/**
 * Throw the demo house away and leave a container ready to be set up again.
 *
 * A harness whose reset needs a human is not reproducible, and this one gets
 * reset often: onboarding can only be done once per instance, so any failure
 * part-way through setup costs a rebuild (HEA-80).
 *
 * The deletion happens *inside* the container, where the same files are simply
 * `/config`. That is deliberate rather than convenient - the paths are then
 * fixed by the image, not by wherever the repository happens to sit, and the
 * one container it can reach is named in `compose.yaml`.
 *
 *   node demo/reset.mjs
 *
 * `configuration.yaml` survives, because we wrote it. So does the integration,
 * which is mounted read-only and is not ours to delete.
 */

import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const COMPOSE = join(HERE, "compose.yaml");

/** The only container this script may touch, as `compose.yaml` names it. */
const CONTAINER = "hea-demo";

/**
 * What Home Assistant writes and we are willing to destroy.
 *
 * An allowlist rather than "everything except", so a file we have not thought
 * about survives a reset and gets noticed, instead of being deleted by a rule
 * that was too broad to argue with.
 */
const DISPOSABLE = [
  "/config/.storage",
  "/config/.HA_VERSION",
  "/config/.ha_run.lock",
  "/config/home-assistant_v2.db",
  "/config/home-assistant_v2.db-wal",
  "/config/home-assistant_v2.db-shm",
  "/config/home-assistant.log",
  "/config/home-assistant.log.1",
  "/config/home-assistant.log.fault",
  "/config/blueprints",
  "/config/deps",
  "/config/tts",
  "/config/image",
  "/config/backups",
];

const run = (command, args) =>
  execFileSync(command, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });

function containerIsRunning() {
  try {
    return run("docker", ["inspect", "-f", "{{.State.Running}}", CONTAINER]).trim() === "true";
  } catch {
    return false;
  }
}

function main() {
  if (!containerIsRunning()) {
    // Nothing to exec into, so bring it up first. On a half-deleted config this
    // is also how the container gets far enough to be usable again.
    run("docker", ["compose", "-f", COMPOSE, "up", "-d"]);
  }

  run("docker", ["exec", CONTAINER, "rm", "-rf", ...DISPOSABLE]);

  // The token belongs to a user that no longer exists. Leaving it behind makes
  // the next setup fail with a confusing auth error rather than onboarding.
  rmSync(join(HERE, ".demo-session.json"), { force: true });

  // Restart rather than leave it running: Home Assistant has the registries it
  // just lost held in memory, and would write them all back out on shutdown.
  run("docker", ["compose", "-f", COMPOSE, "restart"]);

  console.log("Demo reset. Run `node demo/setup.mjs` to build the house again.");
}

main();
