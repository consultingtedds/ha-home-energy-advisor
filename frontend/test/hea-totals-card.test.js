/**
 * @vitest-environment happy-dom
 *
 * The first card on the data layer (HEA-50): what the period actually cost,
 * what it would have cost at grid price, and the difference.
 *
 * The element's lifecycle is where card bugs live - a subscription left behind
 * on a removed card, a stale response overwriting a newer one, a dashboard
 * placed before the integration is set up - so it is exercised here as a real
 * DOM element rather than through a view-model standing in for one.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatPeriod } from "../hea-format.js";
import { DEFAULTS as LABELS, resetLabels } from "../hea-labels.js";
import { TAG, register } from "../hea-totals-card.js";
import {
  AIRCON_BUCKETS,
  JULY,
  MAY,
  aDeviceRow,
  aHass,
  anEnergyCollection,
  bucketsFor,
  mountCard,
  settled as settledOn,
  stateOf,
  text,
} from "./doubles.js";

/** The locale the doubles hand every card. */
const EN_GB = { language: "en-GB", currency: "EUR" };

const figure = (card, name) =>
  card.shadowRoot.querySelector(`[data-figure="${name}"]`);

const mount = (hass, config = {}) => mountCard(TAG, hass, config);

/** Wait for the card to settle on something other than its first paint. */
const settled = (card, state = "ready") => settledOn(expect, card, state);

beforeEach(() => {
  document.body.replaceChildren();
  // A theme variable set by one test would otherwise leak into the next, and
  // these rules turn on whether it resolves. Cleared here rather than at the
  // end of the test that sets one: a failing assertion never reaches its own
  // cleanup, so the next test would fail too and hide which one broke.
  for (const variable of ["--primary-text-color", "--primary-color"]) {
    document.documentElement.style.removeProperty(variable);
  }
});

describe("registration", () => {
  it("is registered as a custom element", () => {
    // Given / When / Then
    expect(customElements.get(TAG)).toBeDefined();
  });

  it("survives the resource being added to a dashboard twice", () => {
    // Given - a user who lists the same resource url twice; a second
    // `customElements.define` throws and takes the whole dashboard with it
    // When / Then
    expect(() => register()).not.toThrow();
  });

  it("offers itself in the card picker", () => {
    // Given / When / Then
    expect(globalThis.customCards).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: TAG })]),
    );
  });
});

describe("configuration", () => {
  it("rejects a device filter that is not a list", () => {
    // Given - a hand-edited dashboard yaml
    const card = document.createElement(TAG);

    // When / Then - Home Assistant shows the thrown message in the card editor
    expect(() => card.setConfig({ type: `custom:${TAG}`, devices: "fine_meter_aircon" })).toThrow(
      /devices/,
    );
  });

  it("takes a title when one is configured", () => {
    // Given / When
    const card = mount(aHass(), { title: "Running costs" });

    // Then
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "Running costs",
    );
  });

  it("names itself when no title is configured", () => {
    // Given / When - added from the picker, with nothing filled in
    const card = mount(aHass());

    // Then - three unlabelled money figures do not say what they are
    expect(card.shadowRoot.querySelector("ha-card").getAttribute("header")).toBe(
      "Cost summary",
    );
  });

  it("has a card size, so it lays out in a masonry view", () => {
    // Given / When / Then
    expect(mount(aHass()).getCardSize()).toBe(3);
  });
});

describe("the figures", () => {
  it("shows what the period cost, what it would have cost, and the difference", async () => {
    // Given
    const card = mount(aHass());

    // When
    await settled(card);

    // Then - Saved is the difference, so the three always reconcile on screen
    expect(figure(card, "actualCost").textContent).toMatch(/0[.,]11/);
    expect(figure(card, "costAtGridPrice").textContent).toMatch(/5[.,]78/);
    expect(figure(card, "costSavings").textContent).toMatch(/5[.,]67/);
  });

  it("labels each figure by the name the project settled on", async () => {
    // Given / When - the same three words every card uses, so a household does
    // not have to learn that "Actual Cost" here and "Paid" there are one figure
    // (HEA-88). "Would have paid" carries the counterfactual in its grammar,
    // where "at grid price" left it to be inferred; the pricing rule itself is
    // unchanged and still never names absent hardware (ADR-0009)
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(text(card)).toContain(LABELS.paid);
    expect(text(card)).toContain(LABELS.would_have_paid);
    expect(text(card)).toContain(LABELS.saved);
    expect(text(card)).not.toContain("Without Solar");
    expect(text(card)).not.toContain("Actual Cost");
  });

  it("totals the whole house, the Untracked remainder included", async () => {
    // Given - the remainder is part of what the household actually paid
    const hass = aHass({
      devices: [
        aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"),
        aDeviceRow("untracked_energy_devices", "Untracked", true),
      ],
      response: {
        ...AIRCON_BUCKETS,
        ...bucketsFor("untracked_energy_devices", 100, 4, 5),
      },
    });

    // When
    const card = mount(hass);
    await settled(card);

    // Then
    expect(figure(card, "actualCost").textContent).toMatch(/4[.,]11/);
  });

  it("counts only the devices a filter names", async () => {
    // Given - "this device, or these devices, cost x"
    const hass = aHass({
      devices: [
        aDeviceRow("slow_poll_aircon", "Slow Poll Aircon"),
        aDeviceRow("fine_meter_aircon", "Fine Meter Aircon"),
      ],
    });

    // When
    const card = mount(hass, { devices: ["slow_poll_aircon"] });
    await settled(card);

    // Then - the other device is never even asked about, and neither is the
    // whole home: a card filtered to one device is not bounded by the
    // household's range, and offering it would invite comparing a subset with
    // its whole (ADR-0016)
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({
        statistic_ids: [
          "sensor.slow_poll_aircon_energy_used",
          "sensor.slow_poll_aircon_actual_cost",
          "sensor.slow_poll_aircon_cost_at_grid_price",
          "sensor.slow_poll_aircon_energy_from_grid",
          "sensor.slow_poll_aircon_energy_from_generation",
          "sensor.slow_poll_aircon_energy_from_battery",
          "sensor.slow_poll_aircon_lowest_possible_cost",
          "sensor.slow_poll_aircon_highest_possible_cost",
        ],
      }),
    );
  });

  it("shows nothing about comparison when the household has not asked", async () => {
    // Given - comparison is off by default, which is the normal case
    const hass = aHass();
    const card = mount(hass);

    // When
    await settled(card);

    // Then - the card looks exactly as it always has, and asks the recorder
    // once rather than speculatively fetching a window nobody wanted
    expect(card.shadowRoot.querySelector(".compare")).toBeNull();
    expect(hass.callWS).toHaveBeenCalledTimes(1);
  });

  it("compares against the period Home Assistant announces", async () => {
    // Given - a household that turned on "Compare data" in the picker menu.
    // Both windows are fetched, so the card renders once rather than showing
    // this period and then shifting when the other lands.
    const collection = anEnergyCollection();
    const hass = aHass({ collection });
    const card = mount(hass);
    await settled(card);

    // When - the picker announces the same period with a comparison window.
    // The recorder answers both fetches, so the response carries a bucket in
    // each window: EUR 0.11 in May for the period shown, EUR 1.31 in April for
    // the one before it. The data layer keeps only the buckets that start
    // inside the period it asked for, which is what separates them.
    const may = new Date(2026, 4, 20);
    const april = new Date(2026, 3, 1);
    hass.callWS = vi.fn().mockResolvedValue({
      "sensor.slow_poll_aircon_energy_used": [
        { start: may.getTime(), change: 38.6 },
        { start: april.getTime(), change: 40 },
      ],
      "sensor.slow_poll_aircon_actual_cost": [
        { start: may.getTime(), change: 0.11 },
        { start: april.getTime(), change: 1.31 },
      ],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: may.getTime(), change: 5.78 },
        { start: april.getTime(), change: 6.0 },
      ],
    });
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });

    // Then - the figure carries what changed and what it is measured against.
    // Signed, because the direction is the whole question: "1.20" leaves the
    // reader to work out whether they did better or worse
    await vi.waitFor(() =>
      expect(card.shadowRoot.querySelector(".compare")).not.toBeNull(),
    );
    const compared = card.shadowRoot.querySelector(
      '[data-compare="actualCost"]',
    ).textContent;
    expect(compared).toMatch(/[-−]/);
    expect(compared).toMatch(/1[.,]20/);
  });

  it("colours a change by whether it is good news for that concept", async () => {
    // Given - a period where the household paid EUR 1.00 against EUR 2.00
    // before, on generation worth less than it was: Paid falls by EUR 1.00 and
    // Saved falls by EUR 2.00. Down is good news on the first and bad news on
    // the second, and both rendered in the same grey - so the sign carried no
    // meaning at a glance, which is the whole complaint (HEA-99).
    const collection = anEnergyCollection();
    const hass = aHass({ collection });
    const card = mount(hass);
    await settled(card);

    const may = new Date(2026, 4, 20);
    const april = new Date(2026, 3, 1);
    hass.callWS = vi.fn().mockResolvedValue({
      "sensor.slow_poll_aircon_energy_used": [
        { start: may.getTime(), change: 10 },
        { start: april.getTime(), change: 20 },
      ],
      "sensor.slow_poll_aircon_actual_cost": [
        { start: may.getTime(), change: 1 },
        { start: april.getTime(), change: 2 },
      ],
      "sensor.slow_poll_aircon_cost_at_grid_price": [
        { start: may.getTime(), change: 2 },
        { start: april.getTime(), change: 5 },
      ],
    });

    // When
    collection.announce(may, new Date(2026, 6, 15), {
      startCompare: new Date(2026, 2, 20),
      endCompare: new Date(2026, 4, 15),
      compareMode: "previous",
    });
    await vi.waitFor(() =>
      expect(card.shadowRoot.querySelector(".compare")).not.toBeNull(),
    );

    // Then - one card, one direction, two opposite verdicts
    const compared = (key) =>
      card.shadowRoot.querySelector(`[data-compare="${key}"]`).classList;
    expect(compared("actualCost").contains("gain")).toBe(true);
    expect(compared("costAtGridPrice").contains("gain")).toBe(true);
    expect(compared("costSavings").contains("loss")).toBe(true);
  });

  it("marks a real saving as the good news it is", async () => {
    // Given - the same theme this card's loss rule needs to be visible at all.
    // Red meant something and the absence of red meant either "fine" or "no
    // rule here", which a reader cannot tell apart (HEA-102)
    document.documentElement.style.setProperty("--primary-text-color", "#111111");
    const hass = aHass({
      response: bucketsFor("slow_poll_aircon", 10, 3, 5),
    });

    // When - paid 3 where the grid would have cost 5, so 2 was saved
    const card = mount(hass);
    await settled(card);

    // Then - green, and actually painted rather than merely classed
    expect(figure(card, "costSavings").classList.contains("gain")).toBe(true);
    expect(getComputedStyle(figure(card, "costSavings")).color).toBe("#4caf50");
  });

  it("leaves a saving of nothing uncoloured", async () => {
    // Given - paid exactly what the grid would have cost. Colour is a claim,
    // and "you saved nothing" is neither good news nor bad
    document.documentElement.style.setProperty("--primary-text-color", "#111111");
    const hass = aHass({
      response: bucketsFor("slow_poll_aircon", 10, 3, 3),
    });

    // When
    const card = mount(hass);
    await settled(card);

    // Then
    const saved = figure(card, "costSavings").classList;
    expect(saved.contains("gain")).toBe(false);
    expect(saved.contains("loss")).toBe(false);
  });

  it("leaves what was paid uncoloured, whatever it was", async () => {
    // Given - spending money is not bad news, it is the bill. Only a *change*
    // in it has a direction, which `changeTone` handles per concept (HEA-99)
    document.documentElement.style.setProperty("--primary-text-color", "#111111");
    const hass = aHass({
      response: bucketsFor("slow_poll_aircon", 10, 3, 5),
    });

    // When
    const card = mount(hass);
    await settled(card);

    // Then
    for (const key of ["actualCost", "costAtGridPrice"]) {
      const classes = figure(card, key).classList;
      expect(classes.contains("gain"), `${key} should carry no verdict`).toBe(false);
      expect(classes.contains("loss"), `${key} should carry no verdict`).toBe(false);
    }
  });

  it("marks a saving that is really a loss", async () => {
    // Given - battery arbitrage cost more than the grid would have (HEA-39),
    // on a dashboard whose theme defines the text colour. That variable is the
    // whole test: `.loss` sits in the shared base style and `.value` in this
    // card's own, which is concatenated after it, so the two are equal
    // specificity and the later one wins. With no theme `var(--primary-text-
    // color)` resolves to nothing, `.value`'s declaration collapses and `.loss`
    // paints - which is why a suite with no theme could not see this at all
    // and HEA-39's colour shipped applied-then-overridden (HEA-99).
    document.documentElement.style.setProperty("--primary-text-color", "#111111");
    const hass = aHass({
      response: bucketsFor("slow_poll_aircon", 10, 5, 3),
    });

    // When
    const card = mount(hass);
    await settled(card);

    // Then - signed, marked, and actually painted the error colour
    expect(figure(card, "costSavings").textContent).toMatch(/-/);
    expect(figure(card, "costSavings").classList.contains("loss")).toBe(true);
    expect(getComputedStyle(figure(card, "costSavings")).color).toBe("#db4437");
  });
});

describe("what each concept wears", () => {
  /** The mark on one figure's label, from the shared vocabulary (HEA-104). */
  const markOn = (card, concept) =>
    card.shadowRoot.querySelector(`.swatch.${concept}`);

  it("marks Paid and Saved in the colours the chart draws them", async () => {
    // Given - a household reading the stacked bar learns that blue means Paid
    // and green means Saved. They then read this card, where both were black,
    // so the vocabulary was colour-coded in one place and not the other
    const card = mount(aHass());

    // When
    await settled(card);

    // Then - actually painted, not merely classed
    expect(getComputedStyle(markOn(card, "paid")).backgroundColor).toBe("#03a9f4");
    expect(getComputedStyle(markOn(card, "saved")).backgroundColor).toBe("#4caf50");
  });

  it("draws Would have paid as a container rather than a third fill", async () => {
    // Given - it is Paid plus Saved by construction, so in every chart that
    // draws it, it is the whole bar with the other two as its segments
    const card = mount(aHass());

    // When
    await settled(card);

    // Then - an outline, and nothing painted inside it. A third fill would have
    // a container contradicting its own contents
    const mark = getComputedStyle(markOn(card, "would-have-paid"));
    expect(mark.border).toContain("#212121");
    expect(mark.backgroundColor).toBeFalsy();
  });

  it("keeps the mark on Saved green when the figure itself is a loss", async () => {
    // Given - battery arbitrage cost more than the grid would have (HEA-39),
    // so the figure is negative and wears `.loss`
    document.documentElement.style.setProperty("--primary-text-color", "#111111");
    const card = mount(aHass({ response: bucketsFor("slow_poll_aircon", 10, 5, 3) }));

    // When
    await settled(card);

    // Then - the number carries the verdict and the mark keeps the identity.
    // On a chart the bar itself turns red, because the verdict has nowhere else
    // to go; here it does, and a mark that moved with the data would stop
    // naming which quantity this is (HEA-104)
    expect(figure(card, "costSavings").classList.contains("loss")).toBe(true);
    expect(getComputedStyle(markOn(card, "saved")).backgroundColor).toBe("#4caf50");
  });

  it("follows a theme that sets the variables itself", async () => {
    // Given - a household on a theme of their own. The marks name variables
    // rather than hexes, so the cards move with the dashboard around them
    document.documentElement.style.setProperty("--primary-color", "#7b1fa2");
    const card = mount(aHass());

    // When
    await settled(card);

    // Then
    expect(getComputedStyle(markOn(card, "paid")).backgroundColor).toBe("#7b1fa2");
  });

  it("leaves the mark out of what a screen reader announces", async () => {
    // Given / When - colour is reinforcement and never the only cue: the label
    // beside it is already the whole meaning
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(markOn(card, "paid").getAttribute("aria-hidden")).toBe("true");
    expect(text(card)).toContain(LABELS.paid);
  });
});

describe("the period", () => {
  it("says which range the figures cover", async () => {
    // Given / When
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(text(card)).toMatch(/20 May/);
    expect(text(card)).toMatch(/15 Jul/);
  });

  it("follows the picker to a new range", async () => {
    // Given - a card already showing May to July
    const collection = anEnergyCollection();
    const hass = aHass({ collection });
    const card = mount(hass);
    await settled(card);

    // When - the user picks a different range
    collection.announce(new Date(2026, 7, 1), new Date(2026, 7, 9));

    // Then - the figures are fetched again for it
    await vi.waitFor(() => expect(text(card)).toMatch(/9 Aug 2026/));
    expect(hass.callWS).toHaveBeenCalledTimes(2);
  });

  it("says so when it is showing a default range", async () => {
    // Given - a dashboard with no energy-date-selection card on it
    const card = mount(aHass({ collection: null }));

    // When
    await settled(card);

    // Then - the user is told why the range is not the one they expected
    expect(text(card)).toMatch(/date picker/i);
  });

  it("does not claim a default range once it is following the picker", async () => {
    // Given / When
    const card = mount(aHass());
    await settled(card);

    // Then
    expect(text(card)).not.toMatch(/date picker/i);
  });

  /** The caption, which is the base's and so is every card's (HEA-99). */
  const captionOf = (card) =>
    card.shadowRoot.querySelector(".period").textContent;

  /**
   * A single day each side, as the picker's "today" and "yesterday" arrive -
   * ending part-way through the day, which is what lets `formatRange` collapse
   * each to one date rather than a range against itself.
   */
  const AUG_18 = new Date(2026, 7, 18);
  const AUG_18_END = new Date(2026, 7, 18, 23, 59);
  const AUG_17 = new Date(2026, 7, 17);
  const AUG_17_END = new Date(2026, 7, 17, 23, 59);

  it("names the range it is comparing against", async () => {
    // Given - a comparing card reads "-EUR 0.77 vs EUR 1.87" over a caption
    // saying only "18 Aug 2026". Against which day? The picker knows and the
    // card never said, so the one figure whose whole job is to be read at a
    // glance had no baseline on screen (HEA-99).
    const collection = anEnergyCollection();
    const card = mount(aHass({ collection }));
    await settled(card);

    // When - the household turns comparison on in the picker's own menu
    collection.announce(AUG_18, AUG_18_END, {
      startCompare: AUG_17,
      endCompare: AUG_17_END,
      compareMode: "previous",
    });

    // Then - the same "vs" the figures above it use, so the caption reads as
    // the baseline for them rather than as a second unrelated date
    await vi.waitFor(() =>
      expect(captionOf(card)).toBe("18 Aug 2026 vs 17 Aug 2026"),
    );
  });

  it("names only the picked range when nobody asked to compare", async () => {
    // Given / When - the default, and much the commoner case: a "vs" with
    // nothing after it would be worse than the bare date
    const card = mount(aHass());
    await settled(card);

    // Then - the caption is the range and nothing appended. Built through
    // `formatPeriod` rather than written out, because `Intl` joins a range with
    // thin spaces around an en dash and the exact code points move with ICU -
    // what is asserted here is the composition, which is ours, not the
    // formatting, which is the platform's and has its own tests.
    expect(captionOf(card)).toBe(formatPeriod({ start: MAY, end: JULY }, EN_GB));
  });

  it("drops the compared range when the household turns comparison off", async () => {
    // Given - a card already naming both windows
    const collection = anEnergyCollection();
    const card = mount(aHass({ collection }));
    await settled(card);
    collection.announce(AUG_18, AUG_18_END, {
      startCompare: AUG_17,
      endCompare: AUG_17_END,
      compareMode: "previous",
    });
    await vi.waitFor(() => expect(captionOf(card)).toMatch(/vs/));

    // When - comparison is turned back off, which the picker announces as a
    // period carrying no compare window at all
    collection.announce(AUG_18, AUG_18_END);

    // Then - a caption still naming a baseline no figure is measured against
    // would be the same bug pointing the other way
    await vi.waitFor(() => expect(captionOf(card)).toBe("18 Aug 2026"));
  });
});

describe("when there is nothing to show", () => {
  it("says so when no devices are tracked yet", async () => {
    // Given - HEA installed but no devices added
    const hass = aHass({ devices: [] });

    // When
    const card = mount(hass);
    await settled(card, "empty");

    // Then - and the recorder is never asked for every statistic in the house.
    //
    // Named by request type rather than "never called at all": the card now
    // fetches its vocabulary before it says anything, so that it can say it in
    // the household's own language, and `callWS` carries both conversations.
    // The blanket assertion passed only while some earlier test had already
    // warmed the label cache, and failed when run on its own (HEA-93).
    expect(text(card)).toMatch(/no devices/i);
    expect(hass.callWS).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "recorder/statistics_during_period" }),
    );
  });

  it("says so in the household's own words, not in fallback English", async () => {
    // Given - a Spanish instance with nothing tracked yet. This branch renders
    // and returns, so there is no later paint to correct the words: if the
    // vocabulary is not in hand by then, English is what the household keeps
    // (ADR-0018, HEA-93)
    resetLabels();
    const spanish = "Todavía no se sigue ningún dispositivo.";
    const hass = aHass({ devices: [] });
    hass.locale = { language: "es" };
    hass.callWS = vi.fn().mockResolvedValue({
      resources: { "component.home_energy_advisor.common.card_no_devices": spanish },
    });

    // When
    const card = mount(hass);
    await settled(card, "empty");

    // Then
    await vi.waitFor(() => expect(text(card)).toContain(spanish));
  });

  it("says so when the integration is not loaded at all", async () => {
    // Given - a dashboard placed before HEA is set up
    const hass = aHass({ devices: null });

    // When
    const card = mount(hass);

    // Then
    await settled(card, "empty");
  });

  it("reports a failure rather than showing a house that cost nothing", async () => {
    // Given - the recorder is unavailable
    const hass = aHass({ callWS: vi.fn().mockRejectedValue(new Error("no recorder")) });

    // When
    const card = mount(hass);
    await settled(card, "error");

    // Then - zeroes would read as a free week, which is worse than an error
    expect(text(card)).toMatch(/could not/i);
  });
});

describe("lifecycle", () => {
  it("waits for the picker when the card renders first", async () => {
    // Given - card order within a view is not guaranteed, so the collection
    // may not exist on the first hass update
    const hass = aHass({ collection: null });
    const card = mount(hass);
    await settled(card);
    expect(text(card)).toMatch(/date picker/i);

    // When - the picker appears and a later hass update carries it
    const collection = anEnergyCollection();
    card.hass = { ...hass, connection: { "_energy_hea-costs": collection } };

    // Then - the card switches to the picker's range
    await vi.waitFor(() => expect(text(card)).not.toMatch(/date picker/i));
  });

  it("leaves no subscription behind when removed from the dashboard", async () => {
    // Given
    const collection = anEnergyCollection();
    const card = mount(aHass({ collection }));
    await settled(card);
    expect(collection.listenerCount).toBe(1);

    // When
    card.remove();

    // Then
    expect(collection.listenerCount).toBe(0);
  });

  it("subscribes again when the dashboard moves it", async () => {
    // Given - Home Assistant re-appends cards when a view is edited, and a card
    // that does not re-subscribe silently freezes on the range it last saw
    const collection = anEnergyCollection();
    const card = mount(aHass({ collection }));
    await settled(card);

    // When
    card.remove();
    document.body.append(card);

    // Then
    expect(collection.listenerCount).toBe(1);
  });

  it("ignores a failure from a request that has been overtaken", async () => {
    // Given - the first fetch fails, but only after a later one has succeeded;
    // letting it through would replace good figures with an error
    const collection = anEnergyCollection();
    const pending = [];
    const callWS = vi.fn(
      () => new Promise((resolve, reject) => pending.push({ resolve, reject })),
    );
    const card = mount(aHass({ collection, callWS }));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(1));

    // When
    collection.announce(new Date(2026, 3, 1), new Date(2026, 7, 9));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(2));
    pending[1].resolve(bucketsFor("slow_poll_aircon", 1, 2, 3));
    await settled(card);
    pending[0].reject(new Error("too late"));
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Then
    expect(stateOf(card)).toBe("ready");
    expect(figure(card, "actualCost").textContent).toMatch(/2[.,]00/);
  });

  it("ignores a stale response that lands after a newer one", async () => {
    // Given - a slow first fetch and a fast second; without a guard the slow
    // one lands last and the card shows the range the user already left
    const collection = anEnergyCollection();
    const resolvers = [];
    const callWS = vi.fn(
      () => new Promise((resolve) => resolvers.push(resolve)),
    );
    const card = mount(aHass({ collection, callWS }));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(1));

    // When - the user picks another range before the first answer arrives,
    // and the answers come back out of order
    collection.announce(new Date(2026, 3, 1), new Date(2026, 7, 9));
    await vi.waitFor(() => expect(callWS).toHaveBeenCalledTimes(2));
    resolvers[1](bucketsFor("slow_poll_aircon", 1, 2, 3));
    await settled(card);
    resolvers[0](bucketsFor("slow_poll_aircon", 9, 9, 9));

    // Then - the newer figures stand
    await vi.waitFor(() => expect(figure(card, "actualCost").textContent).toMatch(/2[.,]00/));
    expect(figure(card, "actualCost").textContent).toMatch(/2[.,]00/);
  });
});
