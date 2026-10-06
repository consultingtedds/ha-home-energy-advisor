/**
 * What a maintainer would otherwise go and fetch, printed at the moment of
 * failure (HEA-193).
 *
 * Settling HEA-192 took a dozen lines written against the container by hand:
 * entities per subentry, our config entries by domain, the entry's settings. All
 * of it was readable when the harness gave up and none of it was printed, so the
 * same house got re-diagnosed on every run.
 *
 * Read-only, and it never throws: this runs on a path that is already failing,
 * and a diagnostic that masks the error it was called about is worse than no
 * diagnostic.
 */

import { BASE_URL, HaSocket } from "./ha-client.mjs";

const DOMAIN = "home_energy_advisor";

async function json(path, token) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { authorization: `Bearer ${token}` },
  });
  return response.ok ? response.json() : null;
}

/**
 * Our own diagnostics download, which already carries the entry's settings.
 *
 * Preferred over reading the config entry: neither the REST entry nor
 * `config_entries/get` exposes `options` at all, and HEA-189 put the entry's
 * own settings in here for exactly this purpose. The snapshot block is worth
 * having too, since a restored snapshot and its age say whether the engine came
 * back with history or started cold.
 */
async function ourDiagnostics(token, entryId) {
  const payload = await json(`/api/diagnostics/config_entry/${entryId}`, token);
  return payload?.data ?? payload;
}

/** Entities per subentry, named. A subentry at zero is the HEA-192 shape. */
async function entitiesPerSubentry(token, entryId) {
  let socket;
  try {
    socket = await HaSocket.connect(token);
    const subentries = await socket.send({
      type: "config_entries/subentries/list",
      entry_id: entryId,
    });
    const registry = await socket.send({ type: "config/entity_registry/list" });
    const titles = new Map(subentries.map((sub) => [sub.subentry_id, sub.title]));
    const counts = new Map();
    for (const entry of registry) {
      if (entry.config_entry_id !== entryId) continue;
      // Hub-level entities carry no subentry: the devices sensor and the
      // whole-home figures belong to the entry itself.
      const key = entry.config_subentry_id ?? "(hub level)";
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts].map(([key, count]) => ({
      name: titles.get(key) ?? key,
      count,
    }));
  } catch {
    return null;
  } finally {
    socket?.close();
  }
}

/** Every config entry we or our helpers own, counted by domain. */
async function entriesByDomain(token) {
  const entries = await json("/api/config/config_entries/entry", token);
  if (!entries) return null;
  const counts = new Map();
  for (const entry of entries) {
    if (![DOMAIN, "utility_meter", "integration"].includes(entry.domain)) continue;
    counts.set(entry.domain, (counts.get(entry.domain) ?? 0) + 1);
  }
  return [...counts];
}

/**
 * Print what the instance actually looks like. Never throws.
 *
 * Takes the entry id when the caller has it; finds it otherwise, because the
 * most interesting failure is one where the caller never got that far.
 */
export async function describeHouse(token, entryId = null) {
  const lines = ["  --- what the instance looks like ---"];
  try {
    const ours = await json(`/api/config/config_entries/entry?domain=${DOMAIN}`, token);
    const entry = ours?.[0] ?? null;
    const id = entryId ?? entry?.entry_id ?? null;
    if (!entry) {
      lines.push("  the integration has no config entry at all");
      console.log(lines.join("\n"));
      return;
    }

    lines.push(`  entry ${id}: ${entry.state}, ${entry.num_subentries} subentries`);

    const diagnostics = await ourDiagnostics(token, id);
    if (diagnostics?.entry) {
      const { total, disabled } = diagnostics.entry.entities ?? {};
      lines.push(`  entities: ${total} total, ${disabled} disabled`);
    }
    if (diagnostics?.snapshot) {
      const { status, age_seconds: age } = diagnostics.snapshot;
      const age_ = typeof age === "number" ? `${Math.round(age)}s old` : "no age";
      lines.push(`  accounting snapshot: ${status}, ${age_}`);
    }
    if (diagnostics?.config) {
      lines.push(`  settings: ${JSON.stringify(diagnostics.config)}`);
    }

    const domains = await entriesByDomain(token);
    if (domains) {
      lines.push(
        `  config entries: ${domains.map(([d, n]) => `${d} ${n}`).join(", ")}`,
      );
    }

    const perSubentry = await entitiesPerSubentry(token, id);
    if (perSubentry) {
      lines.push("  entities per subentry:");
      for (const { name, count } of perSubentry) {
        const flag = count === 0 ? "   <- nothing registered" : "";
        lines.push(`    ${String(name).padEnd(26)} ${String(count).padStart(3)}${flag}`);
      }
    }
  } catch (error) {
    lines.push(`  (could not be read: ${error.message})`);
  }
  console.log(lines.join("\n"));
}
