/**
 * HEA-50 spike: can a custom card follow Home Assistant's energy period picker?
 *
 * ADR-0012 decided that HEA's cards subscribe to Home Assistant's own energy
 * collection rather than owning a date range. That rests on one unproven
 * assumption, and everything else in the design follows from it or is wasted.
 * This card exists only to settle it.
 *
 * It deliberately *discovers* rather than assumes: `getEnergyDataCollection` is
 * a frontend internal with no published contract, so the probe scans the
 * connection for anything shaped like an energy collection and reports what it
 * finds. What key the picker actually uses is a finding, not an input.
 *
 * Throwaway. Delete once the real cards exist.
 *
 * Usage: drop in /config/www/, register /local/hea-period-probe.js as a
 * JavaScript module resource, then put this on a dashboard beside an
 * `energy-date-selection` card:
 *
 *   type: custom:hea-period-probe
 *   collection_key: ""      # optional; match the picker's own collection_key
 */

const CARD = "hea-period-probe";

/**
 * Home Assistant caches every subscribable collection on the connection —
 * registries, config, services, themes — and they all carry `subscribe` and
 * `refresh`. Shape alone is not enough to find the energy one.
 *
 * Probed 2026-08-09 on 2026.8: the energy collection is keyed
 * `_energy_<collection_key>`, e.g. `_energy_hea-costs`. Discovery still lists
 * everything, because the prefix is an observation and not a published
 * contract; selection prefers the prefix and then insists on a period.
 */
const COLLECTION_SHAPE = ["subscribe", "refresh"];
const ENERGY_PREFIX = "_energy";
const PAYLOAD_KEYS_SHOWN = 8;

const isCollection = (value) =>
  value !== null &&
  typeof value === "object" &&
  COLLECTION_SHAPE.every((member) => typeof value[member] === "function");

/** Every energy-collection-shaped object on the connection, keyed by name. */
const discoverCollections = (hass) => {
  const connection = hass?.connection;
  if (!connection) return {};
  const found = {};
  for (const key of Object.keys(connection)) {
    let value;
    try {
      value = connection[key];
    } catch {
      continue; // a getter that throws is not what we are looking for
    }
    if (isCollection(value)) found[key] = value;
  }
  return found;
};

const asText = (value) => {
  if (value === undefined || value === null) return "—";
  if (value instanceof Date) return value.toISOString();
  return String(value);
};

class HeaPeriodProbe extends HTMLElement {
  #config = {};
  #hass = null;
  #collection = null;
  #collectionKey = null;
  #unsubscribe = null;
  #updates = 0;
  #last = null;
  #error = null;

  setConfig(config) {
    this.#config = config || {};
  }

  set hass(hass) {
    this.#hass = hass;
    // The collection is created lazily by whichever card asks first, so it may
    // not exist on the first hass update. Keep looking until it does — that
    // ordering question is itself part of what this probe is testing.
    if (!this.#collection) this.#attach();
    this.#render();
  }

  disconnectedCallback() {
    this.#detach();
  }

  #attach() {
    const collections = discoverCollections(this.#hass);
    const energyKeys = Object.keys(collections).filter((key) =>
      key.startsWith(ENERGY_PREFIX),
    );
    if (energyKeys.length === 0) return;

    const configured = this.#config.collection_key;
    const wanted = configured ? `${ENERGY_PREFIX}_${configured}` : ENERGY_PREFIX;
    const key = collections[wanted] ? wanted : energyKeys[0];

    try {
      this.#collection = collections[key];
      this.#collectionKey = key;
      this.#unsubscribe = this.#collection.subscribe((data) => {
        this.#updates += 1;
        this.#last = data;
        this.#render();
      });
    } catch (err) {
      this.#error = `subscribe failed: ${err}`;
      this.#collection = null;
    }
  }

  #detach() {
    try {
      if (typeof this.#unsubscribe === "function") this.#unsubscribe();
    } catch {
      // unsubscribing on teardown is best-effort
    }
    this.#unsubscribe = null;
    this.#collection = null;
  }

  #render() {
    const collections = discoverCollections(this.#hass);
    const discovered = Object.keys(collections);
    const energyKeys = discovered.filter((key) => key.startsWith(ENERGY_PREFIX));
    const start = this.#collection?.start;
    const end = this.#collection?.end;

    const payloadKeys = this.#last ? Object.keys(this.#last) : [];
    const payload = payloadKeys.length
      ? `${payloadKeys.slice(0, PAYLOAD_KEYS_SHOWN).join(", ")}${
          payloadKeys.length > PAYLOAD_KEYS_SHOWN
            ? ` … (${payloadKeys.length} keys)`
            : ""
        }`
      : "—";

    const rows = [
      ["energy collections", energyKeys.length ? energyKeys.join(", ") : "none"],
      ["other collections", String(discovered.length - energyKeys.length)],
      ["subscribed to", asText(this.#collectionKey)],
      ["start", asText(start)],
      ["end", asText(end)],
      ["subscription callbacks", String(this.#updates)],
      ["last payload keys", payload],
    ];
    if (this.#error) rows.push(["error", this.#error]);

    const verdict = !energyKeys.length
      ? "No energy collection yet — is an energy-date-selection card on this view?"
      : this.#collection
        ? "Following the picker. Change the period above; callbacks should rise."
        : "Energy collection found but not subscribed — see error.";

    this.innerHTML = `
      <ha-card header="HEA period probe">
        <div class="card-content">
          <p style="margin-top:0">${verdict}</p>
          <table style="width:100%;border-collapse:collapse">
            ${rows
              .map(
                ([name, value]) =>
                  `<tr>
                     <td style="padding:2px 8px 2px 0;opacity:.7;white-space:nowrap">${name}</td>
                     <td style="padding:2px 0;font-family:monospace;word-break:break-all">${value}</td>
                   </tr>`,
              )
              .join("")}
          </table>
        </div>
      </ha-card>`;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define(CARD, HeaPeriodProbe);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD,
  name: "HEA period probe",
  description: "Spike: proves a custom card can follow HA's energy period picker (HEA-50).",
});
