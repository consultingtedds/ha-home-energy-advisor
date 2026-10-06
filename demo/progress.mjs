/**
 * Whether the house is still being built, or has stopped (HEA-193).
 *
 * Pure, and separate from the waiting it serves, because the defect this fixes
 * was the *message*: a wait that reported "still moving" while the device count
 * had not changed for a quarter of an hour sent the diagnosis the wrong way
 * twice. A message is a thing a test can pin, so it is kept where one can reach
 * it.
 *
 * Nothing here talks to Home Assistant. It is handed counts and rows and it
 * reports what they mean.
 */

/**
 * A row is ready when it names its statistics, not when it exists.
 *
 * The devices sensor publishes a row as soon as its subentry does, while the
 * entities behind it are still being registered. A row naming no statistics is
 * one the seed would write nothing for, so the card would come up a device short
 * with nothing on the page to say why.
 */
export const hasFigures = (row) => Object.keys(row?.statistics ?? {}).length > 0;

/**
 * Remember when a value last changed, rather than only what it is.
 *
 * Returns the previous record untouched when the value has not moved, so `since`
 * is the moment it *became* this value and not the moment it was last looked at.
 * That difference is the whole point: it is what lets a wait say how long
 * something has been stuck.
 */
export function noted(previous, value, at) {
  if (previous && previous.value === value) return previous;
  return { value, since: at };
}

/** How long this value has been what it is. */
export const stillnessMs = (record, now) => now - record.since;

/**
 * Two classes of missing device, which have different causes.
 *
 * A device **absent** from the list has not been added, or the sensor has not
 * republished since it was. A device **published without figures** is the
 * HEA-192 shape exactly: configured, named in the list, and carrying nothing
 * because its entities were never registered. Naming that class is what would
 * have pointed at HEA-192 on the first run rather than the fifth.
 *
 * Expected names come from `house.mjs`, so they are the names a household typed
 * and are never translated. The Untracked remainder is counted and not named,
 * because its name *is* translated (ADR-0018) and composing it here would be the
 * mistake the cards are forbidden to make.
 */
export function readiness(expectedNames, rows) {
  const byName = new Map(rows.map((row) => [row.name, row]));
  const absent = expectedNames.filter((name) => !byName.has(name));
  const withoutFigures = expectedNames.filter(
    (name) => byName.has(name) && !hasFigures(byName.get(name)),
  );
  const ready = rows.filter(hasFigures).length;
  // The devices plus the remainder the integration derives for itself.
  const wanted = expectedNames.length + 1;
  return {
    ready,
    wanted,
    absent,
    withoutFigures,
    // Every named device arrived and the count is still short, so what is
    // missing is the remainder.
    remainderMissing:
      ready < wanted && absent.length === 0 && withoutFigures.length === 0,
  };
}

/** "2m 45s", "9s" - short enough to sit at the end of a line. */
export function humanMs(ms) {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

/**
 * One signal's line: what it reads, and whether it is going anywhere.
 *
 * **"Still arriving" is only said when something arrived**, which is the whole
 * complaint in HEA-193. Below the threshold a signal is reported as unchanged
 * for however long it has been, and the reader is told to stop waiting rather
 * than encouraged to wait longer.
 */
export function signalLine(label, record, now, { movingWithinMs = 15000 } = {}) {
  const still = stillnessMs(record, now);
  const verdict =
    still < movingWithinMs
      ? `last moved ${humanMs(still)} ago, still arriving`
      : `unchanged for ${humanMs(still)}`;
  return `  ${label}: ${record.value} - ${verdict}`;
}

/**
 * What to print when the wait runs out.
 *
 * Written to be acted on without first writing a probe against the container,
 * which is what settling HEA-192 took. So it names the devices rather than
 * counting them, and separates the two classes of missing because they point at
 * different causes.
 */
export function giveUpReport({ expectedNames, rows, devices, helpers, now, waitedMs }) {
  const state = readiness(expectedNames, rows);
  const lines = [
    `Gave up waiting after ${humanMs(waitedMs)}. Seeding against this would ` +
      "produce cards with devices missing.",
    signalLine(`devices with figures (of ${state.wanted})`, devices, now),
    signalLine("native helpers", helpers, now),
  ];
  if (state.withoutFigures.length > 0) {
    lines.push(
      `  published but carrying no figures: ${state.withoutFigures.join(", ")}`,
      "    That is the HEA-192 shape: configured, listed, and no entities behind it.",
    );
  }
  if (state.absent.length > 0) {
    lines.push(`  not published at all: ${state.absent.join(", ")}`);
  }
  if (state.remainderMissing) {
    lines.push("  every named device arrived; the Untracked remainder has not.");
  }
  return lines.join("\n");
}
