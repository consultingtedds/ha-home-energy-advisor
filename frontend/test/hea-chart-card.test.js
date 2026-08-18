/**
 * @vitest-environment happy-dom
 *
 * Waiting for a chart component that Home Assistant loads lazily (ADR-0013).
 *
 * Every HEA chart card shares this: a dashboard carrying only HEA cards may
 * never have pulled the component in, so the card nudges Home Assistant into
 * creating a built-in card that imports it.
 *
 * The behaviour tested here is the *race*. Registration does not necessarily
 * happen by the time the nudge returns, and it need not be our nudge that
 * causes it - another card on the dashboard can pull the same component in a
 * moment later. A card that checks once and gives up sits on "not loaded"
 * forever beside a working chart, which is exactly what HEA-90 shipped: on the
 * live dashboard `ha-sankey-chart` was defined and the card's `_chartReady` was
 * still false.
 *
 * Each test gets its own component tag, because `customElements.define` is
 * global and permanent - a tag defined by one test would be already-present for
 * the next, and the race would never be reproduced.
 */

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { HeaChartCard } from "../hea-chart-card.js";

let counter = 0;

/** A minimal chart card with a component tag nothing has defined yet. */
const aProbeCard = ({
  bearingCard = { type: "probe-bearing" },
  alreadyLoaded = false,
} = {}) => {
  counter += 1;
  const chartTag = `probe-chart-${counter}`;
  const cardTag = `probe-card-${counter}`;
  // Before the card class is instantiated, so its constructor sees it - which
  // is the case of a dashboard that already had such a card on it.
  if (alreadyLoaded) customElements.define(chartTag, class extends HTMLElement {});
  class ProbeCard extends HeaChartCard {
    static chartTag = chartTag;
    static bearingCard = bearingCard;
    _isEmpty() {
      return false;
    }
    _chartMarkup() {
      return `<${chartTag}></${chartTag}>`;
    }
    _draw() {
      // Nothing to draw: this suite is about getting the element into the tree.
    }
  }
  customElements.define(cardTag, ProbeCard);
  const card = document.createElement(cardTag);
  card.setConfig({ type: `custom:${cardTag}` });
  return { card, chartTag };
};

const chartIn = (card, chartTag) => card.shadowRoot.querySelector(chartTag);

beforeEach(() => {
  document.body.replaceChildren();
});

afterEach(() => {
  delete globalThis.loadCardHelpers;
});

describe("waiting for the component", () => {
  it("says so while the component is not there", () => {
    // Given / When
    const { card, chartTag } = aProbeCard();
    document.body.append(card);

    // Then - an empty box would leave the user with nothing to act on
    expect(card.shadowRoot.textContent).toMatch(/chart component is not loaded/i);
    expect(chartIn(card, chartTag)).toBe(null);
  });

  it("draws as soon as the component arrives, however late", async () => {
    // Given - the nudge has already run to completion and registration still
    // has not happened. This is the live failure: the component turns up a
    // moment later, brought in by some other card on the dashboard.
    const createCardElement = vi.fn().mockResolvedValue(document.createElement("div"));
    globalThis.loadCardHelpers = vi.fn().mockResolvedValue({ createCardElement });
    const { card, chartTag } = aProbeCard();
    document.body.append(card);
    await vi.waitFor(() => expect(createCardElement).toHaveBeenCalled());
    expect(card._chartReady).toBe(false);

    // When - anything at all defines it, whoever it was
    customElements.define(chartTag, class extends HTMLElement {});

    // Then
    await vi.waitFor(() => expect(chartIn(card, chartTag)).not.toBe(null));
    expect(card._chartReady).toBe(true);
    expect(card.shadowRoot.textContent).not.toMatch(/chart component is not loaded/i);
  });

  it("draws when another card got there first, before this one was added", () => {
    // Given / When - a dashboard already showing a built-in card of the kind
    const { card, chartTag } = aProbeCard({ alreadyLoaded: true });
    document.body.append(card);

    // Then - drawn on the first paint, with no nudge and nothing to wait for
    expect(card._chartReady).toBe(true);
    expect(chartIn(card, chartTag)).not.toBe(null);
  });

  it("asks Home Assistant to create the card that imports it", async () => {
    // Given
    const createCardElement = vi.fn().mockResolvedValue(document.createElement("div"));
    globalThis.loadCardHelpers = vi.fn().mockResolvedValue({ createCardElement });
    const { card } = aProbeCard({ bearingCard: { type: "probe-bearing" } });

    // When
    document.body.append(card);

    // Then
    await vi.waitFor(() => expect(globalThis.loadCardHelpers).toHaveBeenCalled());
    expect(createCardElement).toHaveBeenCalledWith({ type: "probe-bearing" });
  });

  it("still draws when the nudge itself fails but the component turns up anyway", async () => {
    // Given - loadCardHelpers can reject on an instance where the helper is
    // unavailable; that must not stop a component another card brings in
    globalThis.loadCardHelpers = vi.fn().mockRejectedValue(new Error("no helpers"));
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { card, chartTag } = aProbeCard();
    document.body.append(card);
    await vi.waitFor(() => expect(warn).toHaveBeenCalled());

    // When
    customElements.define(chartTag, class extends HTMLElement {});

    // Then
    await vi.waitFor(() => expect(chartIn(card, chartTag)).not.toBe(null));
    warn.mockRestore();
  });

  it("keeps saying so when the component never turns up at all", async () => {
    // Given
    globalThis.loadCardHelpers = vi.fn().mockResolvedValue({
      createCardElement: vi.fn().mockResolvedValue(document.createElement("div")),
    });
    const { card, chartTag } = aProbeCard();

    // When
    document.body.append(card);
    await vi.waitFor(() => expect(globalThis.loadCardHelpers).toHaveBeenCalled());

    // Then - the message is the honest end state, not a spinner forever
    expect(card._chartReady).toBe(false);
    expect(chartIn(card, chartTag)).toBe(null);
    expect(card.shadowRoot.textContent).toMatch(/chart component is not loaded/i);
  });
});
