# ADR-0021: Persist the accounting runtime across a restart

## Status

Accepted

Supersedes the flush-on-unload mechanism recorded in ADR-0006's 2026-07-28
update, and removes the trade-off that update accepted. Leaves ADR-0002's
allocation, ADR-0005's decomposition and ADR-0015's carried deficit untouched:
this is about what survives the process, not about how a bucket is priced.

## Context

Home Assistant rebuilds an integration from its config entry on every restart.
The engine was rebuilt with it, so everything it held was discarded: open
buckets, each counter's position, the battery's stored-cost ledger, the 24-hour
retained ring, carried debt and held corrections.

Measured on the reference instance over eight days, published whole-home energy
sat **2.04 % below** the metered house load, against reconciliation check 3's
±1.5 % tolerance, and in the direction that check calls "always a failure".
Three restart-free days in the same window landed at +0.094 %, +0.123 % and
-0.027 %, so the accounting was sound and the process boundaries were not.
Hourly, the loss collapsed onto the hours around each restart - up to 1.31 kWh
in a single hour, against a 20-minute lateness margin on a 40 kWh/day house.

`async_unload_entry` covered only part of this. Home Assistant does not unload
config entries when it stops: `EVENT_HOMEASSISTANT_STOP` reaches
`entry.async_shutdown()`, which cancels a pending retry setup and nothing else.
So the flush ran on options changes and reloads, and never on the restart it was
written for.

A listener on `EVENT_HOMEASSISTANT_STOP` was built and rejected. `restore_state`
listens for the same event, `EventBus` starts coroutine listeners as eager tasks,
and `RestoreStateData.async_dump_states` reads the state machine before its first
await - so ordering is decided by registration order alone. It worked on a first
boot and broke silently after any reload, when the integration re-registers
behind `restore_state`. A fix whose correctness depends on the order two
listeners happened to subscribe in is worse than the defect it treats.

Sizing that work surfaced a second symptom of the same cause. The battery ledger
is documented as starting empty on a first install, an error that "washes out
within a cycle or two". It restarted empty on *every* restart, pricing whatever
the battery physically held at zero - understating cost, overstating the saving,
and pointing the same flattering way as HEA-74. `reset_totals` already refuses to
clear that ledger, on the grounds that it records physical fact, so a restart was
destroying what a deliberate rebase carefully keeps.

## Decision

**The engine's runtime state is serialisable, and the integration persists it.**

`Accountant.snapshot()` returns JSON-safe primitives with every `Decimal` as a
string; `Accountant.restore()` reads them back into a freshly configured
accountant. `AccountantStore` owns the file, the timestamp and the age limit. The
engine stays free of Home Assistant and knows nothing about where its state
lives.

Four decisions inside that, each with a rejected alternative.

**1. The snapshot carries the running totals, and the sensors' restored state
becomes the fallback.** The alternative - persisting only in-flight state and
leaving the sensors to own the totals - puts a figure in two stores written at
different moments, and a bucket finalising between the two writes is counted
twice. Two `Store` writes cannot be made atomic, so the ambiguity had to be
removed rather than managed.

Each sensor's baseline is therefore `max(0, restored_state - what the engine
already carries)`. Whichever store is ahead wins, an install with no snapshot
behaves exactly as before, and a `total_increasing` figure can never step
backwards into what Home Assistant would read as a meter reset.

**2. A snapshot older than 24 hours is refused.** Taken from the retained ring
rather than chosen: past it the open buckets and retained context describe
intervals the accounting can no longer reach. The battery ledger is held to the
same bound even though the battery physically still holds its charge - after a
longer outage the state of charge has moved on unobserved, and an empty ledger
that heals within a cycle beats a confidently wrong one.

**3. A snapshot is a cache, and every failure degrades to a cold start.** Absent,
stale, unstamped, corrupt, or shaped in a way this engine cannot read: all return
the household to the behaviour it had before, never a failed setup. Failing setup
over an unreadable cache would cost more than the accounting the cache carries.

**4. Config-derived state is never restored.** Roles, device mappings, units and
windows are rebuilt from the config entry, and anything the snapshot holds for a
device no longer configured is dropped - its counter position, running totals,
share of an open bucket and any correction it was owed. A snapshot must not be
able to reinstate a device a household deleted, and the energy it claimed stays
with the Untracked remainder so the split still reconciles.

Writes go through `Store.async_delay_save` on the finalisation tick. Home
Assistant keeps the earliest pending deadline and flushes on
`EVENT_HOMEASSISTANT_FINAL_WRITE`, so a clean shutdown always writes a current
snapshot and a crash loses only minutes - without this integration listening for
any shutdown event, and with no ordering relationship to `restore_state` at all.

## Consequences

**The flush on unload is gone.** Open buckets survive, so there is no reason to
seal the current one early. ADR-0006's 2026-07-28 update accepted an early seal,
an uncorrectable tail and a retention ring that restarted empty as the price of
banking 20 minutes; that price is no longer paid. A reload is now just a short
restart.

**Late arrival works across a restart.** The retained ring carries, so a coarse
counter reporting after a restart still corrects its own bucket at its own
retained prices rather than being attributed to whenever it happened to arrive.

**The plausibility guard keeps its evidence**, so HEA-60's window is not blind
for its first twelve buckets after every restart, and carried debt and held
corrections are no longer forgiven by the act of restarting.

**Energy metered while Home Assistant was down is now counted.** Restoring each
counter's position before baselining current states means the first reading after
a restart yields a real delta instead of a `FIRST_READING`. This follows from
carrying the counter position and is correct - the counter is cumulative, and
every source has the same gap - but it is a behaviour change beyond the loss this
ADR set out to fix, and the 24-hour bound is what keeps the spread finite.

**A new failure mode: a snapshot that is readable but wrong.** Version 1 is
guarded by a shallow shape check in the store and a typed restore in the engine,
with any error falling back to a cold start. A future change to the state's shape
must bump `STORAGE_VERSION`; the field-classification test fails until a newly
added field is deliberately sorted into persisted, config-derived or transient.

**Revisit if:** restarts stop being distinguishable from control days but a
residual gap remains, which would mean a second cause; or the 24-hour bound
proves wrong in either direction once the reference instance has a long outage on
record.
