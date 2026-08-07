# ADR-0011: Migrate the generation storage key

## Status

Accepted

Supersedes **decision 3 of ADR-0009**, which kept `CONF_SOLAR_ENTITY`'s storage
key as `"solar_entity"`. That key becomes `"generation_entity"`. Everything else
in ADR-0009 stands, including the renaming principle this decision now applies
one level deeper.

## Context

ADR-0009 renamed the concept from solar to local generation, on the grounds that
naming a source after one technology guarantees the name goes stale — the model
prices any non-metered supply identically, whether it is solar, wind,
micro-hydro or a generator. It renamed the sensor, the `SourceKind`, the
`SourceRole` and the config label.

It deliberately stopped short of the stored key:

> **3. `CONF_SOLAR_ENTITY` keeps its storage key `"solar_entity"`.** It is
> persisted in the live config entry; changing it needs a migration and buys
> nothing, since ADR-0003 makes display labels free to re-word.

That reasoning weighed a certain cost (a migration) against a benefit it judged
to be zero. Both halves have since looked wrong.

**The benefit is not zero.** The key is not merely persisted — it is read in
`coordinator.py`'s `_ROLE_BY_CONF`, in `discovery.py`'s `_HOUSE_CONF_KEYS` and
`_SUPPLY_CONF_KEYS`, and in `config_flow.py`'s `_FULL_BALANCE_ONLY`. A reader
following generation through the integration meets `solar` at every one of those
points, and has to hold in mind that it does not mean solar. That is precisely
the confusion ADR-0009 set out to remove; leaving it in storage left the
principle half-applied.

**The cost is at its floor, and it is falling no further.** There are no git
tags, `manifest.json` is still at `0.0.1`, the integration is not in the HACS
default store, and there is exactly one known installation. Every day that
passes can only add installations, so a migration is cheaper now than it will
ever be again.

**A migration mechanism has to be proven at some point.** This integration has
never run one. Discovering that `async_migrate_entry` is wired up incorrectly is
vastly preferable while the blast radius is a single household whose maintainer
is watching.

## Decision

**1. `CONF_SOLAR_ENTITY` becomes `CONF_GENERATION_ENTITY`, stored as
`"generation_entity"`.**

**2. The config entry moves to `VERSION = 2`, with `async_migrate_entry` moving
the value from the old key to the new one.** A version-1 entry with no
generation configured still advances to version 2, or Home Assistant re-runs the
migration on every start.

**3. The migration is deliberately untested.** It is transient code serving one
installation, and a permanent regression test for it would outlive the thing it
protects. Its correctness is established by the migration running once, on the
one entry that needs it, observed. It should be deleted once no version-1 entry
remains.

**4. Two categories of `solar` deliberately survive:**

- `config_flow.py`'s `elif kind == "solar"` — that is Home Assistant's own
  Energy Dashboard preference schema, not ours to rename.
- Docstrings citing solar as an *example* of generation
  (`allocation.py`, `interval_ledger.py`). Solar is the common case; the
  objection was never to the word, only to naming the concept after it.

### Rejected alternatives

- **Leave the key alone, as ADR-0009 decided.** Rejected: it preserves a
  contradiction in the one place a reader is most likely to trust — the stored
  schema — for a saving that shrinks every day.
- **Rename the key without a migration**, accepting that the existing household
  silently loses its generation input. Rejected: it would present as
  generation quietly reading zero, which under ADR-0005's full-balance branch is
  a wrong number rather than an obvious failure.
- **Ship a regression test for the migration.** Rejected: see decision 3.
  Testing a one-off transformation permanently is dead weight, and the existing
  suite already holds the new key as the standard.

## Consequences

Every consumer of the key now reads `generation`, so following the concept
through the integration no longer requires translating as you go. The naming
principle from ADR-0009 is fully applied rather than applied to the surface.

The live household's config entry is rewritten on the next start. Nothing
accumulated changes — no sensor is renamed, no statistic is orphaned, no reset
is needed. The rename is invisible to a user who is not reading `.storage`.

The migration is throwaway. Carrying it indefinitely costs a branch that can
never be taken again once the single version-1 entry is gone; deleting it is a
follow-up, not a permanent obligation.

This decision would be worth revisiting only if a further rename were proposed
after the first tagged release, when the arithmetic reverses: installations
exist, they cannot be observed, and a botched migration is no longer a
one-household problem. HEA-68.
