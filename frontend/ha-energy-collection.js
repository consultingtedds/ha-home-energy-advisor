/**
 * The only module that touches Home Assistant frontend internals (ADR-0012).
 *
 * Home Assistant's energy cards coordinate through a shared *energy
 * collection*, cached on the websocket connection and created by whichever card
 * asks for it first - normally the `energy-date-selection` picker. HEA's cards
 * subscribe to that same collection instead of owning a date range, so the
 * period control is Home Assistant's and its improvements arrive for free.
 *
 * None of this is a published contract. `hass.connection` is an internal, and
 * the key format below was established by probing 2026.8 (HEA-50), not from
 * documentation. ADR-0012 decision 5 accepts that risk on one condition: it
 * lives *here and nowhere else*, so an upstream refactor is a one-file fix.
 *
 * Cards import `subscribeToPeriod` and treat `{start, end, fallback}` as the
 * whole of the contract.
 */

/**
 * A collection is cached on the connection as `_` + its collection key, and
 * Home Assistant requires every collection key to start with `energy_` - so
 * every cached key begins `_energy`.
 */
const ENERGY_PREFIX = "_energy";

/** The prefix Home Assistant demands of a collection key. */
const KEY_PREFIX = "energy_";

/** What a card shows on a dashboard that has no picker at all. */
const FALLBACK_DAYS = 30;

/**
 * The connection key for a collection key, mirroring how the picker caches it.
 *
 * Home Assistant caches at `_` + the collection key, and rejects a key that
 * does not start with `energy_`. It also derives a key from the dashboard's own
 * url when a card declares none, so every dashboard gets its own collection
 * rather than sharing one.
 *
 * A key written without the `energy_` prefix is accepted and prefixed here: no
 * collection can exist under it - the picker would have refused it - so the
 * user meant the prefixed one, and matching what they meant beats showing an
 * empty card.
 *
 * @param {string} [collectionKey] as configured on the `energy-date-selection`
 *   card; absent or empty means the card declared none.
 * @param {string} [panelUrl] the dashboard's url path, `hass.panelUrl`.
 */
export const connectionKeyFor = (collectionKey, panelUrl) => {
  const key = collectionKey || (panelUrl ? `${KEY_PREFIX}${panelUrl}` : "");
  if (!key) return ENERGY_PREFIX;
  return key.startsWith(KEY_PREFIX) ? `_${key}` : `_${KEY_PREFIX}${key}`;
};

/**
 * True for an energy collection, false for Home Assistant's other collections.
 *
 * Shape alone cannot tell them apart: the entity, device, area, floor and
 * repairs registries all expose `subscribe` and `refresh` too, and a probe that
 * tested shape alone latched onto the entity registry and dumped every entity
 * in the house. So the key must carry the energy prefix *and* the object must
 * offer a period.
 */
export const isEnergyCollection = (key, value) =>
  typeof key === "string" &&
  key.startsWith(ENERGY_PREFIX) &&
  value !== null &&
  typeof value === "object" &&
  typeof value.subscribe === "function" &&
  "start" in value;

/**
 * The period a card shows when no picker is present, so it never renders empty.
 *
 * Starts at midnight because a period beginning part-way through a day makes
 * the first bar of any chart a stub, which reads as missing data.
 */
export const fallbackPeriod = (now = new Date()) => {
  const start = new Date(now);
  start.setDate(start.getDate() - FALLBACK_DAYS);
  start.setHours(0, 0, 0, 0);
  return { start, end: now, fallback: true };
};

/** Every energy collection currently on the connection, keyed by connection key. */
export const findEnergyCollections = (hass) => {
  const connection = hass?.connection;
  if (!connection) return {};
  const found = {};
  for (const key of Object.keys(connection)) {
    let value;
    try {
      value = connection[key];
    } catch {
      continue; // a property whose getter throws is not what we are looking for
    }
    if (isEnergyCollection(key, value)) found[key] = value;
  }
  return found;
};

/**
 * The collection a card should follow, or null if none exists yet.
 *
 * Prefers the configured key, then falls back to any picker on the page: a
 * dashboard whose card and picker disagree about `collection_key` should follow
 * the picker the user can see rather than silently show a different period.
 */
export const resolveCollection = (hass, collectionKey) => {
  const collections = findEnergyCollections(hass);
  const wanted = connectionKeyFor(collectionKey, hass?.panelUrl);
  if (collections[wanted]) return collections[wanted];
  const [first] = Object.values(collections);
  return first ?? null;
};

/**
 * The comparison window, from the payload the collection hands its subscribers.
 *
 * Read from `EnergyData` and nowhere else. The collection object carries
 * `compare` - the *mode* - but neither `startCompare` nor `endCompare`, so the
 * dates exist only in what `subscribe` delivers. An adapter reading the
 * collection, as this one does for the period itself, cannot see them (HEA-96).
 *
 * Absent rather than empty when the household has not asked to compare, which
 * is the default: a card decides whether to compare at all, and something
 * truthy carrying no dates is worse than nothing.
 *
 * Nothing is derived. The mode alone would let us compute what "the previous
 * period" means, and computing it risks disagreeing with Home Assistant's own
 * answer - so a card briefly shows no comparison rather than confidently
 * showing the wrong one.
 */
const comparisonIn = (data) =>
  data?.startCompare && data?.endCompare
    ? {
        compare: {
          start: data.startCompare,
          end: data.endCompare,
          mode: data.compareMode,
        },
      }
    : {};

/**
 * Follow the picker's period, calling `onPeriod({start, end, fallback})`.
 *
 * A `compare: {start, end, mode}` rides alongside when the household has turned
 * comparison on in Home Assistant's own picker menu, and is absent otherwise.
 *
 * The collection is created lazily by whichever card asks first, and card order
 * within a view is not guaranteed, so it may not exist when a card is
 * constructed. Call `retry(hass)` on each `hass` update until it returns true.
 *
 * Emits the fallback period immediately so a card always has something to draw,
 * then the picker's period as soon as it is reachable.
 *
 * @returns {{retry: (hass: object) => boolean, unsubscribe: () => void}}
 */
export const subscribeToPeriod = (hass, collectionKey, onPeriod) => {
  let unsubscribe = null;

  const attach = (currentHass) => {
    if (unsubscribe) return true;
    const collection = resolveCollection(currentHass, collectionKey);
    if (!collection) return false;

    const emit = (data) =>
      onPeriod({
        start: collection.start,
        end: collection.end,
        fallback: false,
        ...comparisonIn(data),
      });

    // `subscribe` fires on change, so emit once now: otherwise a card sits on
    // the fallback period until the user happens to touch the picker. This one
    // has no `EnergyData` to read, so it never carries a comparison - see
    // `comparisonIn`.
    unsubscribe = collection.subscribe(emit);
    emit();
    return true;
  };

  onPeriod(fallbackPeriod());
  attach(hass);

  return {
    retry: (currentHass) => attach(currentHass),
    unsubscribe: () => {
      try {
        if (typeof unsubscribe === "function") unsubscribe();
      } catch {
        // teardown is best-effort; the collection may already be gone
      }
      unsubscribe = null;
    },
  };
};
