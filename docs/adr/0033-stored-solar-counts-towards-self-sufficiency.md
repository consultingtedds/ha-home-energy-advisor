# ADR-0033: Stored solar counts towards self-sufficiency, per device

## Status

Accepted

Revises the self-sufficiency card's headline decision (maintainer, 2026-08-28,
HEA-91), which left battery discharge out of the headline because nothing could
say what had charged the battery. This answers that reason rather than
overriding it.

## Context

The self-sufficiency gauge reads the share of the period's energy that came
from generation the house used directly. Battery discharge sits beside it as
its own figure, with a note that the readings cannot say whether it was charged
from generation or from the grid. Home Assistant's own gauge is a grid
complement, so it counts every discharge as self-produced, including a battery
filled from cheap overnight import.

A household whose battery only charges from their panels asked for an option to
declare that (HEA-216, Discussion 35). Their gauge undercounts them by the whole
of their battery.

The engine already knows the split. Every charge is booked as grid or
generation, interval by interval, with the household's answer to **How your
battery charges** deciding the minutes the meters cannot (ADR-0002's
2026-10-19 Update, HEA-233). Since ADR-0027 the ledger carries what its stored
sunshine gave up in money. What it does not keep is the stored sunshine in
**kWh**, and the money cannot stand in for it, because it is zero for a
household with no export price.

## Decision

**The ledger carries stored solar in kWh, every discharge hands its share to
the device that used it, and the gauge counts it.**

1. **The ledger holds stored generation kWh** beside stored kWh, cost and
   forgone value, by the same rules: a charge from generation adds to it, a
   charge from the grid does not, a discharge draws it down by the same share
   as the cost, and a write-down scales it with the inventory. A measured loss
   takes its share out like any other discharge, and it is not published:
   energy lost to heat reached no device.
2. **Each discharge's solar share follows its energy.** A device's battery
   energy in an interval is split at that interval's withdrawal, as its forgone
   value already is (ADR-0027).
3. **One new figure per device: Energy From Battery (Solar).** On every device,
   Untracked and Whole Home, beside Energy From Battery, which keeps its
   meaning and history. Created everywhere, enabled only where the household
   has a battery: a solar-only home would read zero for ever (HEA-175).
   Battery Losses does not carry it.
4. **The gauge's headline counts it.** The headline is generation used directly
   plus the battery's solar share, still labelled From generation, with
   "including stored solar" beneath. The breakdown's battery figure becomes
   From battery (grid), the rest of the discharge. The note says what the
   headline now counts. It never counts grid-charged energy as self-produced,
   which is where it still differs from Home Assistant's.
5. **The sources card does not change.** It keeps one battery figure per
   device.
6. **Upgrading starts from nothing stored.** Energy already in the battery has
   no known solar share, so it counts as grid-charged until it cycles out, the
   treatment ADR-0027 gave the forgone value.

Rejected:

- **A declared "my battery only charges from solar".** It is wrong the first
  time the battery takes a little grid, and the meters already know.
- **One household sensor, its period fraction applied to the rows shown.** One
  entity instead of one per device, and exact unfiltered, but approximate under
  a device filter, so the same card would mean two things.
- **Splitting Energy From Battery into two figures.** No extra entity, but it
  changes the meaning of a figure households already chart and breaks its
  history.
- **A card option choosing either headline.** Two meanings for one headline
  across dashboards, and a setting nobody would know to look for.

## Consequences

- One more sensor per device, plus Untracked and Whole Home, on every household
  with a battery, and one per device added later. Accepted reluctantly: the
  entity count has been brought under control before (HEA-175), and this is a
  card most households read less than the Energy Dashboard's own gauge. No
  daily or monthly helpers are made for it.
- A period reaching back before the update reads those days as grid-charged,
  because the new figure has no history there. The gap closes as it ages out.
- The solar share is only as right as the charge split it follows, so a wrong
  answer to How your battery charges moves the headline. That is already true
  of the figures it decomposes.
- A test charges a battery from grid and generation in known amounts,
  discharges part of it, and asserts the exact solar kWh each device is given.
- Built after 0.13.0, for the release that carries HEA-221.
- Revisit if a household finds the per-device figures add nothing the gauge
  needs, in which case the household sensor above is the fallback.
