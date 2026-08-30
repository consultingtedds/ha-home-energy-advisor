/**
 * @vitest-environment happy-dom
 *
 * The filter the whole page shares (HEA-95).
 *
 * A card can already be filtered to named devices when it is *configured*,
 * which answers a question you knew you had. This answers the other kind -
 * "what did the aircon cost this week", asked on the page - so the selection
 * belongs to the page rather than to any one card, exactly as the period does
 * (ADR-0012).
 *
 * Keyed by the same `collection_key` the cards already agree on, so two HEA
 * dashboards on one instance filter independently for the same reason they
 * already pick periods independently.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  EVERYTHING,
  filterFor,
  matchesFilter,
  resetFilters,
  setFilter,
  subscribeToFilter,
} from "../hea-filter.js";

const KEY = "energy_hea-costs";

/**
 * A row as a card sees it: normalised by `readDevices`, not as the sensor
 * publishes it. Matching against the published snake_case would match nothing
 * and quietly filter the whole house away.
 */
const aDevice = (overrides = {}) => ({
  key: "slow_poll_aircon",
  name: "Slow Poll Aircon",
  untracked: false,
  areaId: "a-lounge",
  areaName: "Lounge",
  floorId: "f-ground",
  floorName: "Ground Floor",
  labels: ["aircon"],
  ...overrides,
});

beforeEach(() => {
  resetFilters();
});

describe("the shared selection", () => {
  it("starts on everything, so a page nobody has filtered is the whole house", () => {
    // Given / When / Then
    expect(filterFor(KEY)).toEqual(EVERYTHING);
  });

  it("tells every card that shares the key", () => {
    // Given - the point of the page filter: one control, every card follows
    const seen = [];
    subscribeToFilter(KEY, (filter) => seen.push(filter));

    // When
    setFilter(KEY, { kind: "area", id: "a-lounge" });

    // Then
    expect(seen).toEqual([{ kind: "area", id: "a-lounge" }]);
    expect(filterFor(KEY)).toEqual({ kind: "area", id: "a-lounge" });
  });

  it("keeps two dashboards apart", () => {
    // Given - the cards already pick their period per collection key, and a
    // second HEA dashboard filtering the first would be the same bug
    const other = [];
    subscribeToFilter("energy_other", (filter) => other.push(filter));

    // When
    setFilter(KEY, { kind: "area", id: "a-lounge" });

    // Then
    expect(other).toEqual([]);
    expect(filterFor("energy_other")).toEqual(EVERYTHING);
  });

  it("stops telling a card that has left the page", () => {
    // Given - a card removed from a view would otherwise be re-rendered for as
    // long as the tab lived, and held in memory by the subscription
    const seen = [];
    const unsubscribe = subscribeToFilter(KEY, (filter) => seen.push(filter));

    // When
    unsubscribe();
    setFilter(KEY, { kind: "area", id: "a-lounge" });

    // Then
    expect(seen).toEqual([]);
  });

  it("says nothing when the selection has not actually changed", () => {
    // Given - every card refetches on a change, so a repeated selection would
    // ask the recorder again for the answer it just gave
    const seen = [];
    subscribeToFilter(KEY, (filter) => seen.push(filter));

    // When
    setFilter(KEY, { kind: "area", id: "a-lounge" });
    setFilter(KEY, { kind: "area", id: "a-lounge" });

    // Then
    expect(seen).toHaveLength(1);
  });

  it("reads a half-written selection as everything", () => {
    // Given / When / Then - a selection restored from somewhere, or a control
    // that sent only half of one. Everything is the safe reading: it shows the
    // house rather than silently hiding most of it
    setFilter(KEY, {});
    expect(filterFor(KEY)).toEqual(EVERYTHING);
    setFilter(KEY, { kind: "area", id: "a-lounge" });
    setFilter(KEY, undefined);
    expect(filterFor(KEY)).toEqual(EVERYTHING);
  });

  it("carries on when one card's listener throws", () => {
    // Given - a card that fails to react must not stop the rest of the page
    // following the selection
    const seen = [];
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    subscribeToFilter(KEY, () => {
      throw new Error("this card is broken");
    });
    subscribeToFilter(KEY, (filter) => seen.push(filter));

    // When
    setFilter(KEY, { kind: "area", id: "a-lounge" });

    // Then
    expect(seen).toHaveLength(1);
    warn.mockRestore();
  });
});

describe("what a filter matches", () => {
  it("takes everything when nothing is selected", () => {
    // Given / When / Then
    expect(matchesFilter(aDevice(), EVERYTHING)).toBe(true);
    expect(matchesFilter(aDevice({ untracked: true }), EVERYTHING)).toBe(true);
  });

  it("matches a room by its id, never by its name", () => {
    // Given - a household may rename a room, and two rooms may share a name in
    // different houses. The id is what Home Assistant considers the room
    const device = aDevice();

    // When / Then
    expect(matchesFilter(device, { kind: "area", id: "a-lounge" })).toBe(true);
    expect(matchesFilter(device, { kind: "area", id: "a-kitchen" })).toBe(false);
    expect(matchesFilter(device, { kind: "area", id: "Lounge" })).toBe(false);
  });

  it("matches a floor the same way", () => {
    // Given / When / Then
    const device = aDevice();
    expect(matchesFilter(device, { kind: "floor", id: "f-ground" })).toBe(true);
    expect(matchesFilter(device, { kind: "floor", id: "f-first" })).toBe(false);
  });

  it("matches a label a device carries among several", () => {
    // Given - labels are a set, unlike a room
    const device = aDevice({ labels: ["aircon", "upstairs"] });

    // When / Then
    expect(matchesFilter(device, { kind: "label", id: "upstairs" })).toBe(true);
    expect(matchesFilter(device, { kind: "label", id: "pumps" })).toBe(false);
  });

  it("survives a device the integration published before labels existed", () => {
    // Given - the sensor gains `labels` in a later version, and a card may run
    // against an integration that has not been updated yet. A card that threw
    // here would take the whole dashboard with it
    const device = aDevice({ labels: undefined });

    // When / Then
    expect(matchesFilter(device, { kind: "label", id: "aircon" })).toBe(false);
    expect(matchesFilter(device, EVERYTHING)).toBe(true);
  });

  it("gathers the unfiled rather than letting them vanish", () => {
    // Given - measured on the reference instance: one tracked device has no
    // area, and five have no floor because their rooms are filed under none.
    // Silently dropping them would lose over a third of the tracked house from
    // a floor filter, and the household would have no way to see it happen
    const noFloor = aDevice({ floorId: null, floorName: null });

    // When / Then
    expect(matchesFilter(noFloor, { kind: "floor", id: null })).toBe(true);
    expect(matchesFilter(aDevice(), { kind: "floor", id: null })).toBe(false);
  });

  it("takes everything for a kind it does not know", () => {
    // Given - a selection from a newer control, or a hand-edited one. Showing
    // the house is the safe reading; matching nothing would look like a house
    // that recorded nothing at all
    expect(matchesFilter(aDevice(), { kind: "colour", id: "blue" })).toBe(true);
  });

  it("drops the Untracked remainder from any real filter", () => {
    // Given - the remainder is not in a room and carries no label by
    // definition. Filter to the aircons and it has to go, or the card claims a
    // subset it is not showing
    const untracked = aDevice({
      untracked: true,
      areaId: null,
      floorId: null,
      labels: [],
    });

    // When / Then
    expect(matchesFilter(untracked, { kind: "area", id: "a-lounge" })).toBe(false);
    // Not even into the unfiled bucket, which is a claim about rooms
    expect(matchesFilter(untracked, { kind: "area", id: null })).toBe(false);
  });
});
