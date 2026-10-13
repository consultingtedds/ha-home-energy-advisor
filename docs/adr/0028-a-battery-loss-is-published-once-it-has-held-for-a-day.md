# ADR-0028: A battery loss is published once it has held for a day

## Status

Accepted

Applies ADR-0015's carry-don't-clamp to the battery loss measurement, and
HEA-85's publish-late-never-retract to a figure whose input is an estimate.
Reverses nothing.

## Context

Battery Losses (HEA-174, HEA-182) is measured rather than assumed. Two figures
bound it, and the lower is the loss:

- **What the house's meters cannot explain**, `import + generation - export -
  house`, less what the battery's level gained. A residual of four meters, so it
  inherits every disagreement between them (HEA-196).
- **What the battery's own meters allow**, `charge - discharge - gain`, since
  energy in has to come out, stay in or be lost.

Both subtract the level's gain, and the level is the weak input: a percentage
from the battery's own estimate, converted at a capacity the household typed in.

One household on GitHub 34 sent the readings that showed what that costs, four
times over. The relevant two:

**Measured per span and floored, the bound did not bind.** It was evaluated every
coordinator tick, and the battery's counters (0.1 kWh steps) and its level (1%
steps) move at different moments. A tick where the charge counter moved and the
level had not allowed the whole step; the tick where the level caught up owed it
back, and flooring at zero forgave it. Over one of their mornings the floored
bound allowed 7.6 kWh where their meters allowed 0.23 (HEA-211). That is the
rectification ADR-0015 exists to stop, one layer down from where it was first
fixed.

**Carried, it still published the level's drift.** Over 48 hours of their data
the level ran about 1 kWh either side of their meters, low through the evening
and caught up at the next charge, which fits a lithium iron phosphate charge
estimate. Published as soon as the meters allowed it, the figure landed on the
peak of that drift: 1.77 kWh against the 0.875 their meters allowed. A loss is a
running total that only counts upwards, so a peak published once stays for ever
(HEA-213).

## Decision

**Measure the loss as running totals from one anchor, and publish only what the
lower of them has held for 24 hours without a break.**

1. **Running totals, not spans.** Where the headroom, the level and the
   battery's metered charge and discharge stood when measuring began is the
   anchor. Both bounds are totals from it, so meter and level steps that land at
   different moments cancel instead of accumulating. There is nothing to floor.

2. **The published loss is the least the lower total has read over the last 24
   hours, and it never goes down.** A sliding minimum, a handful of entries,
   persisted with the snapshot. A drift that lasts less than a day never reaches
   the figure; a real loss arrives a day after it happened.

3. **A day, by the clock.** It is the cycle the drift was seen to follow, and it
   depends on nothing but time.

4. **The anchor survives a restart and a reset.** Re-anchoring would hold the
   figure still for another day and forgive whatever the level had not yet
   caught up. A reset rebases the published figure and nothing underneath it, so
   the same loss cannot be published twice.

5. **A snapshot that measured span by span re-anchors at the first tick after
   it is restored**, within seconds of startup, because its state cannot be
   turned into a running total. That tick is the starting point HEA-206 found an
   upgraded household had never been given.

6. **What the diagnostics call refused is the current gap** between the house's
   claim and the battery's allowance since the anchor - how far the household's
   meters disagree, rather than a running count of ticks.

### Rejected

* **Publishing as soon as the meters allow, with the bound carried** (HEA-211
  alone). Removes the rounding and keeps the drift: the published figure is the
  running peak of the allowance, about twice what the meters allowed on the
  reporter's data.
* **Holding only the bound for a day.** The house side refused each tick's
  excess outright, so by the time the bound's allowance arrived there would be
  nothing left to publish and the figure would sit near zero. Comparing running
  totals is what makes the refusal safe without discarding anything.
* **Measuring only between returns to full**, where the level corrects itself.
  The most physical reference point, and one a battery capped below full never
  reaches: the reference household's sits at 90% and rarely sees 100%, so it
  would never publish.
* **A shorter hold.** Twelve hours came out right on the reporter's data and may
  not cover a full cycle on another household's battery. The cost of the longer
  hold is a day's delay on a figure nobody acts on within the day.
* **Reading the level against closed intervals instead of live.** Removes the
  15-minute skew between a live level and meters counted after the lateness
  margin, and nothing larger. The hold absorbs that skew too.

## Consequences

- **Battery Losses runs a day behind.** Today's loss is published tomorrow. The
  whole-home total includes it and moves with it; nothing else does. The README
  says so.
- **It holds still for a day** on a fresh install, after first filling in the
  battery level, and after an upgrade from a release that measured span by span.
  `docs/UPGRADING.md` says so for the release that ships this.
- **The figure is now as good as the battery's meters**, and no better: on the
  reporter's 48 hours it publishes exactly what they allow. A discharge meter
  that misses energy is still caught by the house's claim, the lower of the two.
- **The ledger's draw-down through published loss is a day later too.** The
  reconcile's write-down is unaffected, so HEA-202's ledger keeps correcting.
- HEA-212 asks for the level, the capacity and this measurement's own state in
  the diagnostics, without which every report needs another export.
- Revisit if: a battery is seen to drift for longer than a day, which a winter
  regime might show (HEA-123); a household needs the loss within the day; or a
  battery integration exposes a reading better than a charge estimate.
