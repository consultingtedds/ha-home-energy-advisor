/**
 * The filter the whole page shares (HEA-95).
 *
 * A card can already be filtered to named devices when it is *configured*,
 * which answers a question the household knew it had. This answers the other
 * kind - "what did the aircon cost this week", asked on the page and answered
 * without editing anything - so the selection belongs to the page rather than
 * to any one card.
 *
 * The shape is the period picker's, one layer down (ADR-0012): a control card
 * owns the selection and every other card follows it. Home Assistant has no
 * registry for this the way it does for energy collections, so the store is
 * ours - keyed by the same `collection_key` the cards already agree on, so two
 * HEA dashboards on one instance filter independently for the same reason they
 * already pick periods independently.
 *
 * A selection names an **id**, never a name. A household may rename a room, and
 * two houses may spell one differently; the id is what Home Assistant considers
 * the room to be, and the name is only how it says it.
 */

/** No selection: the whole house, which is what an untouched page shows. */
export const EVERYTHING = Object.freeze({ kind: "all", id: null });

/**
 * What a device row carries for each kind of selection.
 *
 * The normalised names `readDevices` produces, not the sensor's own snake_case:
 * rows reach a card already converted, and reading the published spelling here
 * would match nothing and filter everything away.
 */
const FIELD = { area: "areaId", floor: "floorId" };

const stores = new Map();

const storeFor = (key) => {
  if (!stores.has(key)) {
    stores.set(key, { filter: EVERYTHING, listeners: new Set() });
  }
  return stores.get(key);
};

/** What this page is showing now. */
export const filterFor = (key) => storeFor(key).filter;

/**
 * Follow the page's selection, until the returned function is called.
 *
 * Returning the unsubscribe rather than offering a `remove` is the shape
 * `subscribeToPeriod` already uses, so a card tears both down the same way.
 */
export const subscribeToFilter = (key, onChange) => {
  const { listeners } = storeFor(key);
  listeners.add(onChange);
  return () => listeners.delete(onChange);
};

/**
 * Change what the page is showing, and tell every card that shares the key.
 *
 * Silent when the selection has not moved: each card refetches on a change, and
 * re-selecting what is already selected would ask the recorder again for the
 * answer it has just given.
 *
 * A listener that throws is reported and stepped over. One card failing to
 * react must not leave the rest of the page showing a selection nobody made.
 */
export const setFilter = (key, filter) => {
  const store = storeFor(key);
  const next = { kind: filter?.kind ?? "all", id: filter?.id ?? null };
  if (next.kind === store.filter.kind && next.id === store.filter.id) return;
  store.filter = next;
  for (const listener of store.listeners) {
    try {
      listener(next);
    } catch (error) {
      console.warn("home-energy-advisor: a card could not follow the filter", error);
    }
  }
};

/**
 * Whether a device row belongs in the current selection.
 *
 * The **Untracked remainder is in no grouping**. It is not in a room and
 * carries no label by definition, so a filtered view must not show it - and
 * must not sweep it into the unfiled bucket either, which is a claim about
 * rooms rather than a bucket for everything without one.
 *
 * Naming it *as a device* is a different act, and is allowed, which is why the
 * device kind is answered before that rule rather than after it. The remainder
 * is frequently the largest line in the house; a drill-down that could name
 * every device except that one would be a strange thing to offer, and there is
 * nothing ambiguous about picking it by name (HEA-98).
 *
 * `id: null` is the unfiled bucket, and it earns its place: measured on the
 * reference instance, one tracked device has no area and five have no floor,
 * because their rooms are filed under none. Without somewhere to put them a
 * floor filter would silently lose over a third of the tracked house.
 */
export const matchesFilter = (device, filter) => {
  const { kind, id } = filter ?? EVERYTHING;
  if (kind === "all") return true;
  // The key identifies a device the way an area id identifies a room; a name is
  // only how the household says it, and may be changed at any time.
  if (kind === "device") return device.key === id;
  if (device.untracked) return false;
  if (kind === "label") {
    // Absent rather than empty on an integration published before labels
    // existed: a card may be newer than the instance it is running against.
    return (device.labels ?? []).includes(id);
  }
  const field = FIELD[kind];
  return field ? (device[field] ?? null) === id : true;
};

/** Test seam: a fresh page shares nothing with the last one. */
export const resetFilters = () => stores.clear();
