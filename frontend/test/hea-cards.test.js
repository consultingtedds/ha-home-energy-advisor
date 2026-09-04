/**
 * @vitest-environment happy-dom
 *
 * One resource url, every card (HEA-50). A dashboard listing a url per card
 * would need editing again each time the family grows.
 */

import { describe, expect, it } from "vitest";

import "../hea-cards.js";
import { TAG as CHART_TAG } from "../hea-cost-over-time-card.js";
import { DASHBOARD_TAG, VIEW_TAG } from "../hea-dashboard-strategy.js";
import { TAG as DEVICES_TAG } from "../hea-devices-card.js";
import { TAG as TOTALS_TAG } from "../hea-totals-card.js";

describe("the card bundle", () => {
  it("registers every card and its editor", () => {
    // Given / When / Then - importing the one entry point is enough
    for (const tag of [TOTALS_TAG, DEVICES_TAG, CHART_TAG]) {
      expect(customElements.get(tag)).toBeDefined();
      expect(customElements.get(`${tag}-editor`)).toBeDefined();
    }
  });

  it("offers them all in the card picker", () => {
    // Given / When / Then
    expect(globalThis.customCards.map((card) => card.type)).toEqual(
      expect.arrayContaining([TOTALS_TAG, DEVICES_TAG, CHART_TAG]),
    );
  });

  it("registers the dashboard strategy alongside them", () => {
    // Given / When / Then - the strategy reaches a browser by the same one url
    // the cards do, so an install that has the cards can always offer the
    // dashboard built from them
    expect(customElements.get(DASHBOARD_TAG)).toBeDefined();
    expect(customElements.get(VIEW_TAG)).toBeDefined();
  });
});
