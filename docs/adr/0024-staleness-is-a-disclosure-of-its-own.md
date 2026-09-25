# ADR-0024: Staleness is a disclosure of its own, not a hole in the figures

## Status

Accepted

Extends HEA-24's Repairs policy, which settled that device unavailability never
raises a Repair, by answering the consequence that policy left standing. Leaves
the policy itself intact: nothing here raises anything a household has to
dismiss.

## Context

A cumulative figure that stops being fed does not go blank. It holds its last
value for ever, so a household sees a plausible number that has quietly stopped
moving, and nothing anywhere says so.

Reported on the community thread, 2026-09-23 (HEA-176). The report is precise
about why the household's own tooling could not help: Spook and Watchman look for
*missing* entities, and every figure here is present and perfectly healthy. It is
simply no longer being added to. The integration's own warning is in the Edit
Device dialog, which is a place someone has to go and look.

The obvious answer is the one Home Assistant's own derived sensors use.
`integration` and `utility_meter` - the two helpers this integration auto-creates
- both mark themselves unavailable when the source they derive from is
unavailable. Propagating the same way would reach every dashboard, automation and
entity-watching tool with nothing new for anyone to learn.

**It is the wrong answer here, and the reason is what the figures mean.** Two
situations produce an unavailable source, and this integration cannot tell them
apart:

* a sensor dies while its device runs on. The figure is now *wrong* - understated
  - and the device's energy is silently moving into the Untracked remainder. This
  is the reported case, and it is rare;
* a device is unplugged and its sensor dies with it. The figure is *complete and
  correct*. A radiator that ran all week and was then put away really did cost
  EUR 3.40, and it will be eight months before it says anything again. This is
  the ordinary case, and on the reference instance it is most of the fleet.

Propagation treats them identically, so it pays for disclosing the rare one by
withdrawing a correct figure for a whole season - from the device page, from any
template or automation reading the state, and from the `utility_meter` cycle
helpers, which would follow their source down. That Home Assistant added
`always_available` to `utility_meter` is evidence the default is contested in core
too.

## Decision

**The staleness is published as a fact of its own, on one diagnostic entity per
tracked device, and no cost figure is ever withdrawn.**

Each tracked device gains a **Last Reading** sensor: a timestamp, diagnostic,
whose value is the moment its source last produced a reading the engine could
count, and which reports `unavailable` once that moment is more than thirty
minutes old.

Four properties are as much the decision as the entity itself.

1. **The figures never move.** What a device has cost so far stays published,
   and stays true, however long its meter has been quiet. Nothing is rebased, no
   zero point is stamped, and the statistics carry on untouched - which is also
   what keeps ADR-0022's defect out of reach, since a `total` figure that fell to
   zero would be booked by the compiler as the loss of a whole balance.
2. **Two readings, for two audiences.** The value answers a person: a timestamp
   on the device page, rendered as how long ago, needing no tooling at all and
   never wrong. The availability answers a machine: an unavailable-entity check
   already understands it, which is what the report asked for.
3. **Nothing is raised, so nothing is dismissed.** A device offline for a season
   goes quiet here and says nothing else - no Repair, no notification, no
   acknowledgement wanted at either end. That is what makes it cheap enough to be
   on by default, and it is the condition the whole shape was accepted under.
4. **Thirty minutes, derived rather than picked.** The engine settles a bucket
   three buckets of lateness plus the bucket behind real time, so for twenty
   minutes after a source falls silent its last real energy is still being
   published. A shorter grace would call a figure stale while it is still moving.
   Thirty is past that and rides out a restart or an integration reload.

Measured at the entity that feeds the engine, which for a power-only device is
the auto-created Integral helper rather than the power sensor the household
chose. That is the reading whose silence freezes the figures, and the helper
propagates its own source's unavailability, so both kinds of device are covered
by watching one entity each.

### Rejected

* **Propagate `unavailable` to the device's own cost figures.** The answer Home
  Assistant's own derived sensors give, and the one this ADR started as. See the
  context: it withdraws a correct figure for a season to disclose a rare fault,
  and the two cases are indistinguishable from here.
* **The same, with an opt-out** in the shape of `utility_meter`'s
  `always_available`. Better, but the maintainer would switch it off on his own
  instance, which says plainly what the default should have been.
* **A Repair once a device source has been unavailable past some grace.** What
  was asked for. It reopens the seasonal-noise problem HEA-24 settled, tells the
  household only where they have to go and look, and is something to dismiss
  every few days for months.
* **An attribute on each figure.** Fails the only complaint there was: the tools
  that would act on it read state, not attributes.
* **Nothing, on the argument that the Edit Device dialog already warns.** True,
  and it is a dialog nobody opens until they already suspect something.

## Consequences

- **A seasonally offline device's Last Reading is unavailable for the season**,
  and an unavailable-entity check will list it. One entity per device rather than
  the seven or nine a propagating design would have contributed, and the source
  sensor itself is in that list before either.
- **Watchman sees this only if the household references the entity**, because it
  reports on entities named in their own YAML and dashboards. Spook's
  unavailable-entity check sees it either way. Propagation would have reached
  both; this is the price of keeping the figures, and it is worth naming when
  answering the report.
- **The cards show nothing.** They read the hub's device list and the statistics,
  and a dead device's change over a period is zero whether anything is disclosed
  or not. A staleness signal on the cards is separate work.
- **The moment comes from the engine, not from the entity's own restored state.**
  A household restarting mid-outage would otherwise come back with nothing to
  show, the entity having been unavailable when it went down. The engine persists
  each counter's position for the accounting's sake, and the moment of the last
  reading travels with it (ADR-0021).
- **"Reading" means one the engine could count.** A counter reporting in an
  unreadable unit, or refused for an implausible step, leaves no reading here
  however healthy its sensor looks - which is the right reading of the word,
  because it is exactly the moment after which the figures could not have moved.
- **HEA-158 is narrowed, not answered.** A source that reports `0` rather than
  going unavailable when its backend fails keeps this entity perfectly current,
  and still needs its own argument.
- Revisit if Home Assistant gains a state meaning *stale* as distinct from
  *unknown*, which is what these figures actually are, or if households report
  that one diagnostic entity per device is not where they look.
