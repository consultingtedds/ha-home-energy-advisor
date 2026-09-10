/**
 * The parts of Home Assistant's API the demo harness needs, and nothing else.
 *
 * No dependencies: Node ships `fetch` and `WebSocket`, and the harness is
 * throwaway tooling that should not earn the repo a package to keep current.
 *
 * Everything here talks to the container on localhost. It must never be pointed
 * at a real instance - the whole reason this harness exists is that the
 * reference household's figures cannot appear in a published screenshot
 * (HEA-80, `docs/CRITICAL_INSTRUCTIONS.md`).
 */

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Where the demo lives. Overridable only to move the port, never the host. */
export const BASE_URL = process.env.HEA_DEMO_URL ?? "http://127.0.0.1:8123";

/**
 * Home Assistant treats the OAuth client id as the address the client is served
 * from, and refuses a token request whose id it cannot reach. Ours is the
 * instance itself, which is always true of a script running beside it.
 */
const CLIENT_ID = `${BASE_URL}/`;

/** The demo account. Throwaway by construction; the instance is not reachable
 *  from anywhere but this machine's loopback interface. */
export const ACCOUNT = {
  name: "Demo",
  username: "demo",
  password: "demo-only-not-a-secret",
  language: "en",
};

/** Written by `setup.mjs`, read by every later step, git-ignored. */
const SESSION_FILE = join(HERE, ".demo-session.json");

export function readSession() {
  try {
    return JSON.parse(readFileSync(SESSION_FILE, "utf8"));
  } catch {
    return null;
  }
}

export function writeSession(session) {
  writeFileSync(SESSION_FILE, `${JSON.stringify(session, null, 2)}\n`);
}

/**
 * Block until the container answers.
 *
 * A fresh container spends the best part of a minute importing before it binds
 * the port, so every step that follows would otherwise race it.
 */
export async function waitForHomeAssistant({ timeoutMs = 240000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${BASE_URL}/manifest.json`);
      if (response.ok) return;
    } catch {
      // Not listening yet. The deadline is the only thing that ends this.
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(`Home Assistant did not answer on ${BASE_URL} in time`);
}

async function postJson(path, body, token) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed: ${response.status} ${await response.text()}`);
  }
  return response.status === 204 ? null : response.json();
}

/** Which onboarding steps this instance still owes, by name. */
export async function onboardingSteps() {
  const response = await fetch(`${BASE_URL}/api/onboarding`);
  if (!response.ok) return [];
  const steps = await response.json();
  return steps.filter((step) => !step.done).map((step) => step.step);
}

/**
 * Take a fresh instance through onboarding and return an access token.
 *
 * Doing this by hand is the single thing that would stop the harness being
 * reproducible, which is why it is scripted even though it runs once per
 * rebuild. Returns null if the instance has already been onboarded, so a rerun
 * is harmless.
 */
export async function onboard() {
  const owed = await onboardingSteps();
  if (!owed.includes("user")) return null;

  const { auth_code: authCode } = await postJson("/api/onboarding/users", {
    client_id: CLIENT_ID,
    ...ACCOUNT,
  });

  const auth = await exchangeAuthCode(authCode);
  const token = auth.access_token;

  // The remaining steps only mark themselves done. Skipping them leaves the
  // frontend redirecting into onboarding forever, which no screenshot survives.
  await postJson("/api/onboarding/core_config", {}, token);
  await postJson("/api/onboarding/analytics", {}, token);
  await postJson("/api/onboarding/integration", {
    client_id: CLIENT_ID,
    redirect_uri: CLIENT_ID,
  }, token);

  return auth;
}

/**
 * The browser's own view of a signed-in session.
 *
 * The screenshot run hands this to the page rather than typing into the login
 * form. Driving a login is a second thing that can break in a script whose job
 * is to photograph something else, and the frontend is perfectly happy to be
 * handed the credentials it would have stored itself.
 */
export function browserTokens(auth) {
  return {
    access_token: auth.access_token,
    refresh_token: auth.refresh_token,
    token_type: auth.token_type ?? "Bearer",
    expires_in: auth.expires_in,
    expires: Date.now() + (auth.expires_in ?? 1800) * 1000,
    clientId: CLIENT_ID,
    hassUrl: BASE_URL,
  };
}

async function exchangeAuthCode(code) {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    client_id: CLIENT_ID,
  });
  const response = await fetch(`${BASE_URL}/auth/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    throw new Error(`Token exchange failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

/**
 * A working access token, refreshed if the stored one has gone stale.
 *
 * Home Assistant's access tokens last half an hour, and a session spent
 * building this harness runs a great deal longer than that. Every step calls
 * this rather than reading the token from the session file, so the failure is
 * an expired token nobody sees rather than an authentication error two steps
 * into a rebuild.
 */
export async function freshAuth() {
  const session = readSession();
  if (!session?.auth?.refresh_token) {
    throw new Error("No demo session. Run `node demo/setup.mjs` first.");
  }
  const response = await fetch(`${BASE_URL}/auth/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: session.auth.refresh_token,
      client_id: CLIENT_ID,
    }),
  });
  if (!response.ok) {
    throw new Error(
      "Refreshing the demo token failed. The instance has probably been reset " +
        "underneath the session file - run `node demo/setup.mjs` again.",
    );
  }
  // The refresh response carries no refresh token of its own, so keep ours.
  const auth = { ...session.auth, ...(await response.json()) };
  writeSession({ ...session, token: auth.access_token, auth });
  return auth;
}

/**
 * A websocket connection with the command ids and the auth handshake handled.
 *
 * Almost everything the seed does - registries, energy preferences, importing
 * statistics - is only reachable over the websocket API, so this is the
 * workhorse rather than a convenience.
 */
export class HaSocket {
  #socket;
  #nextId = 1;
  #pending = new Map();

  static async connect(token) {
    const client = new HaSocket();
    await client.#open(token);
    return client;
  }

  #open(token) {
    const url = `${BASE_URL.replace(/^http/, "ws")}/api/websocket`;
    this.#socket = new WebSocket(url);
    return new Promise((resolve, reject) => {
      this.#socket.addEventListener("error", reject, { once: true });
      this.#socket.addEventListener("message", (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "auth_required") {
          this.#socket.send(JSON.stringify({ type: "auth", access_token: token }));
        } else if (message.type === "auth_ok") {
          resolve();
        } else if (message.type === "auth_invalid") {
          reject(new Error(`Websocket auth refused: ${message.message}`));
        } else if (message.type === "result") {
          this.#settle(message);
        }
      });
    });
  }

  #settle(message) {
    const pending = this.#pending.get(message.id);
    if (!pending) return;
    this.#pending.delete(message.id);
    if (message.success) pending.resolve(message.result);
    else pending.reject(new Error(`${message.error?.code}: ${message.error?.message}`));
  }

  /** Send one command and resolve with its result, or throw with its error. */
  send(command) {
    const id = this.#nextId++;
    this.#socket.send(JSON.stringify({ ...command, id }));
    return new Promise((resolve, reject) => {
      this.#pending.set(id, { resolve, reject });
    });
  }

  close() {
    this.#socket.close();
  }
}
