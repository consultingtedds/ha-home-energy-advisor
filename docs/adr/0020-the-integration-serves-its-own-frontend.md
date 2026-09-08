# ADR-0020: The integration serves its own frontend, and offers a dashboard

## Status

Accepted

## Context

HEA-50 required from the start that the cards be "served by the integration
(static path + Lovelace resource registration), not via HACS - the flagship view
must not require a separate install". Until HEA-94 that was unbuilt. The cards
reached an instance by a script copying them into `config/www` and someone
re-pointing a Lovelace resource by hand: two manual steps, and skipping the
second served a two-day-old bundle beside a current backend.

The card family had meanwhile become device-agnostic. Every card enumerates
`sensor.home_energy_advisor_devices` (ADR-0018, HEA-55) rather than naming
entities, so a dashboard built from them contains no household-specific text at
all. That is what made generating one possible; it was not true when the
original hand-listed dashboard was attempted and cancelled.

## Decision

**The integration serves the cards, and Home Assistant offers the dashboard.**

Four parts, each with a rejected alternative.

**1. One bundle, built from `frontend/`, shipped inside the integration.**
`custom_components/` is the directory HACS copies, so the artifact has to live
there; the sources do not, and shipping them too would quadruple the download
for modules no browser loads. The bundle is committed because nothing builds on
a household's machine, and CI rebuilds and fails on a diff so it cannot drift.

*Rejected: plain ES modules, as before.* 25 requests and 230 KB uncompressed,
against 51 KB in one. The bundler was avoided for as long as it bought nothing;
this is what it buys.

**2. `frontend.add_extra_js_url`, not a Lovelace resource.** Its own docstring
offers it to custom integrations, it needs no resource list, and it works
whatever mode Lovelace is in.

*Rejected: registering a Lovelace resource.* `ResourceYAMLCollection` has no
`async_create_item`, so on an install with YAML-managed resources the
registration silently does nothing and no card ever appears. A route that fails
invisibly on a whole class of installation is worse than one that costs a little
more elsewhere. The cost is real and measured: the module is requested on every
frontend page rather than only Lovelace ones, though compiling it is a median
0.6 ms and the transfer is cached per version.

**3. The url carries the release and a content digest of what is served.**
`/<domain>/<version>-<digest>/`. In the path rather than a query string because
the entry point's relative imports do not inherit a query string.

*Rejected: the version alone.* Every build between two releases carries the same
version, and the path is served with a 31-day cache, so a redeploy is invisible
to any browser that already loaded the cards. *Rejected: timestamps.* A deploy
copies the artifact and resets its mtime, so the url would move on every deploy
and discard a cache that was still good.

**4. A dashboard strategy, offered in Home Assistant's own Add dashboard
dialog.** `ll-strategy-dashboard-hea` plus an entry in `window.customStrategies`
makes Home Energy Advisor appear beside Map and Webpage. The household creates
it; the layout regenerates on load, so devices added later appear without a
dashboard edit; Home Assistant's own "take control" is the way out.

*Rejected: creating the dashboard from Python.* `DashboardsCollection` is a
local variable in `lovelace.async_setup` and is never exposed. A second instance
over the same store is a data-loss hazard, not merely inelegant:
`DictStorageCollection.async_create_item` mutates its own in-memory copy and
saves the whole collection, so the next dashboard created in the UI would save
Lovelace's stale view and erase ours - silently, and weeks later.

*Rejected: a sidebar panel*, the shape add-ons use. Integration-owned UI the
household cannot edit, rearrange or put anything beside.

*Rejected: a template to paste.* Rebuilt on this card family a template names no
device either, so the old objection to it had expired - but it is a snapshot.
It cannot adapt to a household, and it goes stale the moment the card family
changes, with no upgrade path. It survives as a documented escape hatch for
YAML-file dashboards, which have no other route.

## Consequences

A household installs the integration and picks the dashboard from a dialog.
Nothing is copied, no resource list is edited, and no YAML is filled in. The
cards can no longer be a different version from the accounting they draw.

Changing anything under `frontend/` now requires `npm run build` and committing
the result. CI enforces it.

The integration deploy must **delete** `custom_components/home_energy_advisor/frontend/`
before copying. A copy never removes files, and that directory shrank from 25
modules to one; stale modules left behind stay fetchable and are folded into the
cache digest though nothing serves them.

A whole HEA *view* on an existing dashboard still needs two lines of YAML:
`getCustomStrategiesForType` is called for dashboards and nowhere for views, and
the view editor offers no strategy option. Tracked as an upstream contribution
(HEA-108).

Precompression is available and deliberately unused. aiohttp serves a `.br`
sibling when the client accepts it, taking 51 KB to 15 KB with no code, but that
binary must stay byte-for-byte in step with the `.js` while the digest globs
`*.js` only. Widen the digest before taking it.

Revisit if Home Assistant gives integrations a supported way to create a
dashboard, if `add_extra_js_url` gains a scope narrower than every page, or if
the bundle grows enough that loading it everywhere stops being free.

## Update - the strategy needs a resource, not only an extra module url (2026-09-08, HEA-114)

This ADR has the integration serve the bundle and register it with
`frontend.add_extra_js_url`, on the grounds that it asks nothing of the
household and replaces a hand-managed Lovelace resource. The first half holds.
The second was wrong about what an extra module url guarantees.

**`add_extra_js_url` is fire-and-forget: nothing awaits it.** Lovelace awaits its
*resources* before rendering a dashboard; extra module urls it never waits for.
On the reference instance the dashboard failed on almost every direct load with
`Timeout waiting for strategy element ll-strategy-dashboard-hea to be
registered`, rendering blank. The bundle was fetched and never threw - it simply
had not registered when Home Assistant stopped waiting, about five seconds in,
while the browser worked through the fifty Lovelace resources that instance
carries, two of which fail outright and stall.

**A strategy dashboard has no graceful degradation.** A late custom card paints
"custom element not found" and recovers when its module lands. A strategy is
asked for once; if the element is not there, nothing renders at all.

So the integration now also owns a Lovelace resource pointing at the url it
serves, reconciled on every setup: created if absent, re-pointed when the digest
moves, and any extra copy of its own removed. A household's own resources are
never touched. Measured after: the bundle loads at 92 ms rather than ~500 ms, and
directly-loaded dashboards stopped failing.

**Why this is not the hazard this ADR rejected for dashboards.** Creating
dashboards from Python was rejected because `DashboardsCollection` is a local in
`lovelace.async_setup`, so a second instance over the same store would erase what
the first held. The resource collection is *not* like that: it is published on
`hass.data[LOVELACE_DATA].resources`, so the integration uses Home Assistant's
own instance and its normal create/update/delete API. Nothing is constructed over
the store a second time.

One sharp edge, recorded because it is easy to get wrong: `async_items()` does
not read storage, and only the mutating calls load it. Reading the collection
without forcing a load first reports a household's existing resources as absent,
and ours would be created again on every start.

Both mechanisms stay. The extra module url covers every page; the resource is
what makes the dashboard's strategy reliable.
