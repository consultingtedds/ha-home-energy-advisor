/**
 * The adapter is the only module allowed to touch Home Assistant frontend
 * internals (ADR-0012 decision 5), so it is the only place these assumptions
 * can be pinned. Each test below corresponds to something the HEA-50 spike
 * established by probing 2026.8 — none of it is a published contract.
 */

import { describe, expect, it, vi } from "vitest";

import {
  connectionKeyFor,
  fallbackPeriod,
  findEnergyCollections,
  isEnergyCollection,
  resolveCollection,
  subscribeToPeriod,
} from "../ha-energy-collection.js";

/** A stand-in for Home Assistant's energy collection. */
const anEnergyCollection = (start, end) => {
  const listeners = new Set();
  return {
    start,
    end,
    subscribe(callback) {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    refresh() {},
    // Test-only: let a test act as the picker announcing a new period.
    announce(newStart, newEnd) {
      this.start = newStart;
      this.end = newEnd;
      for (const callback of listeners) callback();
    },
    get listenerCount() {
      return listeners.size;
    },
  };
};

/**
 * One of Home Assistant's own registries. Carries `subscribe` and `refresh`
 * exactly like an energy collection — which is what made shape-matching alone
 * latch onto the entity registry during the spike.
 */
const aRegistry = () => ({
  subscribe: () => () => {},
  refresh: () => {},
});

const aHass = (connection) => ({ connection });

const MAY = new Date("2026-05-20T00:00:00Z");
const JULY = new Date("2026-07-15T23:59:59Z");

describe("connectionKeyFor", () => {
  it("prefixes the collection key the picker was configured with", () => {
    // Given / When / Then — the key observed on the live instance
    expect(connectionKeyFor("hea-costs")).toBe("_energy_hea-costs");
  });

  it("is the bare prefix when the picker declares no key", () => {
    // Given / When / Then — an energy-date-selection card with no collection_key
    expect(connectionKeyFor(undefined)).toBe("_energy");
    expect(connectionKeyFor("")).toBe("_energy");
  });
});

describe("isEnergyCollection", () => {
  it("accepts an energy collection", () => {
    // Given / When / Then
    expect(
      isEnergyCollection("_energy_hea-costs", anEnergyCollection(MAY, JULY)),
    ).toBe(true);
  });

  it("rejects Home Assistant's entity registry", () => {
    // Given — the registry that shape-matching wrongly selected during the spike
    const registry = aRegistry();

    // When / Then — it subscribes and refreshes, but it is not a period
    expect(isEnergyCollection("_ent", registry)).toBe(false);
  });

  it("rejects an energy-prefixed object that carries no period", () => {
    // Given — the right key but the wrong shape
    const notAPeriod = { subscribe: () => () => {}, refresh: () => {} };

    // When / Then — the prefix alone is not enough
    expect(isEnergyCollection("_energy_hea-costs", notAPeriod)).toBe(false);
  });

  it("rejects values that are not objects", () => {
    // Given / When / Then
    expect(isEnergyCollection("_energy", null)).toBe(false);
    expect(isEnergyCollection("_energy", "a string")).toBe(false);
  });
});

describe("fallbackPeriod", () => {
  it("offers a month ending now, so a card without a picker still draws", () => {
    // Given — a dashboard with no energy-date-selection card on it
    const now = new Date("2026-08-09T14:30:00Z");

    // When
    const period = fallbackPeriod(now);

    // Then — 30 whole days back, and flagged so a card can say it is a default
    expect(period.end).toEqual(now);
    expect(period.fallback).toBe(true);
    const days = (period.end - period.start) / (1000 * 60 * 60 * 24);
    expect(days).toBeGreaterThan(29);
    expect(days).toBeLessThan(32);
  });

  it("starts at midnight rather than part-way through a day", () => {
    // Given / When
    const period = fallbackPeriod(new Date("2026-08-09T14:30:00Z"));

    // Then
    expect(period.start.getHours()).toBe(0);
    expect(period.start.getMinutes()).toBe(0);
  });
});

describe("findEnergyCollections", () => {
  it("finds the energy collection among Home Assistant's registries", () => {
    // Given — the connection as observed live: registries plus one picker
    const energy = anEnergyCollection(MAY, JULY);
    const hass = aHass({
      _ent: aRegistry(),
      _dr: aRegistry(),
      _areaRegistry: aRegistry(),
      _repairsIssueRegistry: aRegistry(),
      "_energy_hea-costs": energy,
    });

    // When
    const found = findEnergyCollections(hass);

    // Then — only the energy one, however similar the others look
    expect(Object.keys(found)).toEqual(["_energy_hea-costs"]);
  });

  it("ignores a connection property whose getter throws", () => {
    // Given — a connection carrying a hostile property
    const energy = anEnergyCollection(MAY, JULY);
    const connection = { "_energy_hea-costs": energy };
    Object.defineProperty(connection, "_explosive", {
      enumerable: true,
      get() {
        throw new Error("not for you");
      },
    });

    // When / Then — discovery survives it
    expect(Object.keys(findEnergyCollections(aHass(connection)))).toEqual([
      "_energy_hea-costs",
    ]);
  });

  it("returns nothing when there is no connection", () => {
    // Given / When / Then — a card can be constructed before hass arrives
    expect(findEnergyCollections(undefined)).toEqual({});
    expect(findEnergyCollections({})).toEqual({});
  });
});

describe("resolveCollection", () => {
  it("prefers the collection key the card was configured with", () => {
    // Given — two pickers on one dashboard
    const mine = anEnergyCollection(MAY, JULY);
    const theirs = anEnergyCollection(MAY, JULY);
    const hass = aHass({ "_energy_hea-costs": mine, _energy_other: theirs });

    // When / Then
    expect(resolveCollection(hass, "hea-costs")).toBe(mine);
  });

  it("follows the only picker present when the configured key misses", () => {
    // Given — the card names a key the dashboard's picker does not use
    const onlyOne = anEnergyCollection(MAY, JULY);
    const hass = aHass({ "_energy_hea-costs": onlyOne });

    // When / Then — following the visible picker beats showing a stale period
    expect(resolveCollection(hass, "a-key-nobody-configured")).toBe(onlyOne);
  });

  it("is null when no picker exists", () => {
    // Given / When / Then
    expect(resolveCollection(aHass({ _ent: aRegistry() }), "hea-costs")).toBe(
      null,
    );
  });
});

describe("subscribeToPeriod", () => {
  it("emits a fallback period immediately so a card never renders empty", () => {
    // Given — a dashboard with no picker yet
    const onPeriod = vi.fn();

    // When
    subscribeToPeriod(aHass({}), "hea-costs", onPeriod);

    // Then
    expect(onPeriod).toHaveBeenCalledTimes(1);
    expect(onPeriod.mock.calls[0][0].fallback).toBe(true);
  });

  it("emits the picker's period as soon as it attaches", () => {
    // Given — a picker already on the page
    const energy = anEnergyCollection(MAY, JULY);
    const onPeriod = vi.fn();

    // When
    subscribeToPeriod(aHass({ "_energy_hea-costs": energy }), "hea-costs", onPeriod);

    // Then — the fallback first, then the real period
    expect(onPeriod).toHaveBeenCalledTimes(2);
    expect(onPeriod).toHaveBeenLastCalledWith({
      start: MAY,
      end: JULY,
      fallback: false,
    });
  });

  it("emits again when the user changes the period", () => {
    // Given — a card following the picker
    const energy = anEnergyCollection(MAY, JULY);
    const onPeriod = vi.fn();
    subscribeToPeriod(aHass({ "_energy_hea-costs": energy }), "hea-costs", onPeriod);

    // When — the user picks a different range
    const august = new Date("2026-08-01T00:00:00Z");
    const now = new Date("2026-08-09T00:00:00Z");
    energy.announce(august, now);

    // Then
    expect(onPeriod).toHaveBeenLastCalledWith({
      start: august,
      end: now,
      fallback: false,
    });
  });

  it("attaches later when the picker renders after the card", () => {
    // Given — card ordering on a view is not guaranteed, so the picker may
    // create the collection only after this card's first hass update
    const onPeriod = vi.fn();
    const subscription = subscribeToPeriod(aHass({}), "hea-costs", onPeriod);
    expect(subscription.retry(aHass({}))).toBe(false);

    // When — the picker appears
    const energy = anEnergyCollection(MAY, JULY);
    const attached = subscription.retry(aHass({ "_energy_hea-costs": energy }));

    // Then
    expect(attached).toBe(true);
    expect(onPeriod).toHaveBeenLastCalledWith({
      start: MAY,
      end: JULY,
      fallback: false,
    });
  });

  it("stops updating once unsubscribed, and tolerates being unsubscribed twice", () => {
    // Given — a card following the picker, then removed from the dashboard
    const energy = anEnergyCollection(MAY, JULY);
    const onPeriod = vi.fn();
    const subscription = subscribeToPeriod(
      aHass({ "_energy_hea-costs": energy }),
      "hea-costs",
      onPeriod,
    );

    // When
    subscription.unsubscribe();
    subscription.unsubscribe();
    energy.announce(new Date("2026-08-01T00:00:00Z"), new Date());

    // Then — no listener left behind, and no further callbacks
    expect(energy.listenerCount).toBe(0);
    expect(onPeriod).toHaveBeenCalledTimes(2);
  });
});
