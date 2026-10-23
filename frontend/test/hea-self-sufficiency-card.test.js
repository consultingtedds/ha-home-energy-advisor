/**
 * @vitest-environment happy-dom
 *
 * What share of the period's energy the household produced itself (HEA-91).
 *
 * The lifecycle and the lazy-component race live in `HeaCard` and
 * `HeaChartCard` and are tested by their own suites. What is tested here is the
 * arithmetic and the claim it makes: that the share is weighted by energy
 * rather than averaged across devices, that the battery counts towards the
 * headline only as far as it held stored sunshine (ADR-0033), that energy the
 * meters never accounted for is shown rather than absorbed, and that no energy
 * produces no figure rather than nought percent.
 */

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { DEFAULTS as LABELS, resetLabels } from "../hea-labels.js";
import { TAG, register } from "../hea-self-sufficiency-card.js";
import {
  aDeviceRow,
  aHass,
  bucketsFor,
  mountCard,
  settled,
  solarFor,
  sourcesFor,
  text,
} from "./doubles.js";

const AIRCON = aDeviceRow("slow_poll_aircon", "Slow Poll Aircon");
const METER = aDeviceRow("fine_meter_aircon", "Fine Meter Aircon");

/**
 * Two devices whose own shares are nothing like the household's.
 *
 * The aircon used 100 kWh at 10% generation; the meter used 10 kWh at 90%. The
 * mean of those two rows is 50%, and the household's real figure is 19/110 -
 * about 17%. A fixture where the two agreed could not tell the implementations
 * apart.
 *
 * Battery is deliberately 1 kWh of the 110, none of it known to be sunshine:
 * enough that counting it in the headline would move the figure to 18%, so the
 * decision to keep it out is visible in the number rather than only in a label.
 */
const TWO_DEVICES = {
  ...bucketsFor("slow_poll_aircon", 100, 12.5, 14.0),
  ...sourcesFor("slow_poll_aircon", 90, 10, 0),
  ...bucketsFor("fine_meter_aircon", 10, 0.2, 1.4),
  ...sourcesFor("fine_meter_aircon", 0, 9, 1),
};

/**
 * A battery holding some of each: 30 of the aircon's 100 kWh came out of it, 20
 * of those were sunshine stored earlier and 10 were bought.
 *
 * Far enough apart that each reading lands on its own number: 10% leaving the
 * battery out, 30% counting its sunshine, 40% counting all of it as Home
 * Assistant's own gauge does.
 */
const STORED_SUNSHINE = {
  ...bucketsFor("slow_poll_aircon", 100, 12.5, 14.0),
  ...sourcesFor("slow_poll_aircon", 60, 10, 30),
  ...solarFor("slow_poll_aircon", 20),
};

const mount = (hass, config) => mountCard(TAG, hass, config);
const ready = (card) => settled(expect, card);
const gaugeOf = (card) => card.shadowRoot.querySelector("ha-gauge");

const aHouse = (response = TWO_DEVICES) =>
  aHass({ devices: [AIRCON, METER], response });

beforeEach(() => {
  document.body.replaceChildren();
  resetLabels();
  // The gauge is a component Home Assistant loads lazily; a test that never
  // defines it would only ever see the "not loaded" message.
  if (!customElements.get("ha-gauge")) {
    customElements.define("ha-gauge", class extends HTMLElement {});
  }
});

afterEach(() => {
  delete globalThis.loadCardHelpers;
});

describe("registration", () => {
  it("is registered, and offers itself in the card picker", () => {
    // Given / When / Then
    expect(customElements.get(TAG)).toBeDefined();
    expect(globalThis.customCards).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: TAG })]),
    );
  });

  it("survives the resource being added to a dashboard twice", () => {
    // Given / When / Then
    expect(() => register()).not.toThrow();
  });

  it("offers an editor and a height, so it behaves in a Lovelace view", async () => {
    // Given
    const card = mount(aHouse());
    await ready(card);

    // Then - without an editor Home Assistant drops the user into raw YAML
    // (HEA-73), and a masonry view needs a height estimate. A gauge and a row
    // of figures is shorter than the graphs, which take the base's 6
    expect(customElements.get(TAG).getConfigElement()).toBeInstanceOf(HTMLElement);
    expect(card.getCardSize()).toBe(4);
  });
});

describe("the share", () => {
  it("weights by energy rather than averaging the devices' own shares", async () => {
    // Given - a big device at 10% and a small one at 90%
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - 19 kWh generated of 110 used. Averaging the two rows gives 50%,
    // which would let a device that used a tenth of a kilowatt-hour count for
    // as much as one that used twenty
    expect(gaugeOf(card).value).toBeCloseTo(17.27, 1);
    expect(gaugeOf(card).value).not.toBeCloseTo(50, 1);
  });

  it("keeps battery energy out of the headline where none was sunshine", async () => {
    // Given - 1 kWh of the 110 came out of the battery, with no stored sunshine
    // published: a battery filled from the grid, or a period from before the
    // figure existed, which counts the same way (ADR-0033)
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - 17%, not the 18% that counting the battery as ours would give
    expect(gaugeOf(card).value).toBeCloseTo(17.27, 1);
    expect(gaugeOf(card).value).not.toBeCloseTo(18.18, 1);
  });

  it("counts the sunshine the battery stored towards the headline", async () => {
    // Given - 10 kWh straight off the panels and 20 more that went through the
    // battery first
    const card = mount(aHouse(STORED_SUNSHINE));

    // When
    await ready(card);

    // Then - 30%. Leaving the battery out undercounts this household by the
    // whole of it, which is what they asked about (HEA-216)
    expect(gaugeOf(card).value).toBeCloseTo(30, 1);
    expect(gaugeOf(card).value).not.toBeCloseTo(10, 1);
  });

  it("never counts battery energy bought from the grid as the household's own", async () => {
    // Given - 10 of the battery's 30 kWh were bought
    const card = mount(aHouse(STORED_SUNSHINE));

    // When
    await ready(card);

    // Then - not 40%, which is what Home Assistant's grid-complement gauge
    // reads, counting a battery filled from cheap overnight import as self-made.
    // The bought part is its own figure beside the headline
    expect(gaugeOf(card).value).not.toBeCloseTo(40, 1);
    const shown = text(card);
    expect(shown).toContain(LABELS.from_battery_grid);
    expect(shown).toMatch(/10\s*%/);
  });

  it("says the headline includes stored solar when it does", async () => {
    // Given
    const card = mount(aHouse(STORED_SUNSHINE));

    // When
    await ready(card);

    // Then - beneath the headline, so the figure is never read as sunshine used
    // straight off the panels alone
    expect(text(card)).toContain(LABELS.including_stored_solar);
  });

  it("says nothing about stored solar when there was none", async () => {
    // Given - no stored sunshine in the period
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - a home with panels and no battery would otherwise be told about a
    // battery it does not have
    expect(text(card)).not.toContain(LABELS.including_stored_solar);
  });

  it("shows the bought battery energy and the grid beside it, each named", async () => {
    // Given
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - 1 of 110 from the battery, none of it known to be sunshine, and 90
    // of 110 from the grid. Shown so a household with a battery still sees where
    // its energy came from, without one figure claiming more than the data
    // supports
    const shown = text(card);
    expect(shown).toContain(LABELS.from_battery_grid);
    expect(shown).toMatch(/1\s*%/);
    expect(shown).toContain(LABELS.from_grid);
    expect(shown).toMatch(/82\s*%/);
  });

  it("says what the headline counts", async () => {
    // Given
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - the ticket's requirement: decide, and say so on the card
    expect(text(card)).toContain(LABELS.self_sufficiency_note);
  });
});

describe("what the readings do not cover", () => {
  it("shows the shortfall rather than letting the shares imply the whole", async () => {
    // Given - 70 kWh of the 100 has a source; the rest was drawn in buckets the
    // house-level meters never accounted for
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: {
          ...bucketsFor("slow_poll_aircon", 100, 12.5, 14.0),
          ...sourcesFor("slow_poll_aircon", 50, 20, 0),
        },
      }),
    );

    // When
    await ready(card);

    // Then - 30% unaccounted, named. Absorbing it into any of the three would
    // make the card claim a split it cannot support
    expect(text(card)).toContain(LABELS.unaccounted);
    expect(text(card)).toMatch(/30\s*%/);
    expect(gaugeOf(card).value).toBeCloseTo(20, 1);
  });

  it("says nothing about a shortfall when the sources cover the energy", async () => {
    // Given - 90 + 10 + 0 is exactly the 100 used
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - a nought-percent row would read as a fault rather than as nothing
    // to report
    expect(text(card)).not.toContain(LABELS.unaccounted);
  });
});

describe("no energy at all", () => {
  it("gives no figure rather than nought percent", async () => {
    // Given - a period in which the devices recorded nothing
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: {
          ...bucketsFor("slow_poll_aircon", 0, 0, 0),
          ...sourcesFor("slow_poll_aircon", 0, 0, 0),
        },
      }),
    );

    // When
    await ready(card);

    // Then - "none of it came from generation" and "we cannot say" are
    // different claims, and a gauge reading zero makes the first one
    expect(gaugeOf(card)).toBe(null);
    expect(text(card)).not.toMatch(/0\s*%/);
  });

  it("says no energy was recorded, not no cost", async () => {
    // Given - this card never shows money, so the shared "no cost recorded"
    // message made a claim about a quantity it was not measuring (HEA-93)
    const card = mount(
      aHass({
        devices: [AIRCON],
        response: {
          ...bucketsFor("slow_poll_aircon", 0, 0, 0),
          ...sourcesFor("slow_poll_aircon", 0, 0, 0),
        },
      }),
    );

    // When
    await ready(card);

    // Then
    expect(text(card)).toContain(LABELS.no_energy_in_period);
    expect(text(card)).not.toContain(LABELS.no_cost_in_period);
  });
});

describe("the gauge itself", () => {
  it("hands Home Assistant's own component the numbers it needs", async () => {
    // Given
    const card = mount(aHouse());

    // When
    await ready(card);

    // Then - `ha-gauge` renders its own SVG from properties, so the value has
    // to be set as one; an attribute would be a string it never reads
    const gauge = gaugeOf(card);
    expect(gauge.min).toBe(0);
    expect(gauge.max).toBe(100);
    expect(gauge.label).toBe("%");
    expect(gauge.locale).toBe(card._hass.locale);
  });

  it("names the component to wait for and the card that imports it", () => {
    // Given / When - the waiting itself is `HeaChartCard`'s and is tested
    // there against probe tags; what is this card's own is which two names it
    // gives that machinery
    const cardClass = customElements.get(TAG);

    // Then - `energy-self-sufficiency-gauge` is safe to create unconfigured,
    // which is why it is the one nudged: read against home-assistant/frontend
    // `dev` on 2026-08-28, its `setConfig` validates only a `collection_key`
    // it was not given, and it subscribes in `hassSubscribe`, which
    // `createCardElement` never reaches. A card whose `setConfig` demanded an
    // entity - the plain `gauge` card does - would throw on every load
    expect(cardClass.chartTag).toBe("ha-gauge");
    expect(cardClass.bearingCard).toEqual({ type: "energy-self-sufficiency-gauge" });
  });
});
