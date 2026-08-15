# ADR-0018: The frontend is not English

## Status

Accepted (2026-08-14)

## Context

The integration has shipped `strings.json` plus `translations/en.json` and
`es.json` since day one, covering config, options, subentries, entity names,
Repairs, services and exceptions. `CRITICAL_INSTRUCTIONS.md` requires it.

The Lovelace cards were built later and never joined that discipline. An audit
during HEA-88 found two faults with one cause — the cards treat English as the
canonical language rather than as one translation of it.

**Every user-facing word in the cards is hardcoded English.** Around forty-five
strings across seven modules: column headers, card titles, tooltip rows, sort
labels, the range disclosures, the editor's field labels. `hea-format.js`
localises *formats* — money, energy, rates and dates all go through `Intl` with
`hass.locale.language` — so the numbers are right in any locale and the words
around them are not.

**The cards construct entity ids in English.** `hea-statistics.js` builds every
statistic id as `` `sensor.${deviceKey}_${concept}` `` from a hardcoded English
table. But Home Assistant derives an entity's `object_id` from its *translated*
name whenever the instance language is in `NATIVE_ENTITY_IDS`
(`entity_platform.py`), a set of 41 languages that includes `es`. HEA's own
`es.json` already translates `actual_cost` to "Coste real". On a Spanish
instance the entities are `sensor.<device>_coste_real`, the cards ask for
`sensor.<device>_actual_cost`, and the whole family renders empty.

That second fault is the sharper one, because `hea-statistics.js` already
carries a comment stating the rule it breaks — written after HEA-84 shipped
`cost_floor` against a sensor named "Lowest Possible Cost". It fixed the
key-versus-name half of the trap and missed the language half.

## Decision

**1. Card strings live in the integration's own translation files.** A `cards`
section joins `strings.json`, `en.json` and `es.json`, fetched by the cards over
`hass.callWS({type: "frontend/get_translations", category: "cards", …})`.

This works because `frontend/get_translations` declares `category` as a free
string, and `translation.py`'s cache builder derives the available categories
from the translation files themselves rather than an allow-list. So the standard
process reaches the browser unchanged: one set of files, one translator
workflow, no second translation system to keep in step.

*Rejected: a translation bundle inside `frontend/`.* It is the common pattern for
community cards, and it would work, but it splits the household's Spanish across
two places and guarantees they drift. `callWS` is public API, so this costs
nothing on the ADR-0012 internals budget.

*Rejected: reusing the entity-name translations.* `entity.sensor.actual_cost.name`
resolves to "Actual Cost", and HEA-88 deliberately labels that figure "Paid" on a
card. Entity names are nouns that stand alone in a template or an automation;
card labels are verbs that read in the context of their neighbours. Same concept,
different registers, so they need their own keys.

**2. The frontend never constructs an entity or statistic id.** The devices
sensor (HEA-55) publishes the real ids. The integration owns the entities and
knows each id exactly; a card that derives one is guessing, and guessing in
English is how this fault arose. Treat any `` `sensor.${…}_${…}` `` in frontend
code as a defect.

## Consequences

The cards become translatable, and a Spanish install stops rendering empty
(HEA-89, then HEA-88).

**Card-picker strings stay English.** `registerCard` populates
`globalThis.customCards` at module import, where no `hass` exists, so the picker's
name and description cannot be resolved through `callWS`. Documented rather than
worked around: registering English and rewriting the entry once a card is
instantiated would leave the picker showing whichever cards happened to be on the
dashboard.

**Translation now has a cost per string.** A new card label means touching three
files, and Spanish that nobody proofreads is worse than English that is honest
about being English. Accepted: the alternative is what this ADR exists to correct.

**A latent asymmetry is now recorded.** ADR-0003 calls entity naming effectively
permanent and reasons throughout about the English ids. That reasoning holds
within one instance, but the ids themselves are per-language, so "the" entity id
for a concept does not exist. Anything reading ids — dashboards, templates,
HEA-78's 202-id clear list — is instance-specific, not project-wide.

**Revisit if** Home Assistant grows a sanctioned translation category for
Lovelace resources, or if `NATIVE_ENTITY_IDS` stops governing `object_id`
derivation.
