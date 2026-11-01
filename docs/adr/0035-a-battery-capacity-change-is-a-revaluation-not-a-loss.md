# ADR-0035: A battery capacity change is a revaluation, not a loss

## Status

Accepted

Extends ADR-0028's loss measurement to a capacity that moves, and ADR-0031's
battery entry with an optional capacity sensor. Reverses nothing.

## Context

A battery's contents are its level, a percentage, times its usable capacity
(HEA-178). The capacity has been a figure the household types in. Some battery
systems publish the usable capacity their own management system calculates, and
that figure follows the battery as it ages (GitHub discussion 48, HEA-244).

The loss is measured as running totals from one anchor (ADR-0028), and both
bounds subtract what the battery gained since then: what it holds now, less what
it held at the anchor. A capacity that moves changes what the battery holds
without any energy moving. At 50%, a capacity going from 10.0 to 9.9 kWh reads
as 0.05 kWh lost; a capacity going up hides a real loss of the same size.

This is not new with a sensor. The anchor survives a restart and a reload, so a
household who corrects their typed capacity under Reconfigure has always had the
difference booked as loss or hidden from it.

## Decision

**A change in capacity revalues what the battery holds; it is never energy
gained or lost.**

1. **The anchor moves with the capacity.** When a battery's capacity differs from
   the last one used, the pool's loss anchor and that battery's share anchor
   are both shifted by `(new - old) x level`, where the level is the fraction
   it reads now. The gain since the anchor then measures energy only, and the
   measurement carries on without a break.

2. **The last capacity used is kept with the anchor**, in the snapshot, one per
   battery. It is what a change is measured against, so a capacity that moved
   while Home Assistant was down is revalued at the first reading after it, not
   counted. A snapshot without one records the first capacity it sees and
   revalues nothing, since no change is known.

3. **Typed and sensor capacities are revalued alike.** The engine sees a
   capacity, not where it came from, so a Reconfigure edit is revalued like a
   sensor's change.

4. **The capacity comes from one reader**, in this order: the sensor's reading,
   converted between energy units as the meters are; the last capacity used,
   while the sensor is unavailable or reads something that is not a capacity;
   the typed figure; otherwise none, and the battery's contents are unknown, as
   for a level that cannot be read. Never zero.

5. **No plausibility bound on a jump.** A recalibration or a firmware rescale
   moves the capacity at once; revalued, it moves no loss, so there is nothing
   a bound would protect.

### Rejected

* **Re-anchoring on a change.** Simpler, and it discards up to a day of loss not
  yet published (ADR-0028's hold) each time, so a sensor that moves daily would
  never publish a loss at all.
* **Sampling the sensor once a day.** Fewer changes, but each still needs one of
  the two treatments above.
* **One capacity entity for every battery, created by the integration where the
  household has no sensor.** One route in the settings, at the cost of an entity
  per battery to keep, a migration of every battery household's typed figure,
  and an Energy Dashboard comparison that has to tell the integration's entity
  from a battery's own anyway. The reader gives the code one route without them.

## Consequences

- A capacity sensor is optional and sits beside the typed figure; a level needs
  one of them. The sensor wins, and the typed figure covers a sensor that has not
  reported since the battery was set up.
- A battery with a capacity sensor is compared with the Energy Dashboard on its
  meters and level only. Its capacity follows the sensor and rightly drifts from
  the Energy Dashboard's typed figure.
- The pricing ledger needs nothing: a lower capacity writes it down as any lower
  reading does (HEA-202), which only touches pricing, and a higher one is
  ignored as before.
- The diagnostics show the capacity in force, where it came from, and the last
  revaluation.
- Revisit if: a battery system is seen to publish a capacity that swings within
  a day, where the level and the capacity might then disagree about the moment
  they describe.
