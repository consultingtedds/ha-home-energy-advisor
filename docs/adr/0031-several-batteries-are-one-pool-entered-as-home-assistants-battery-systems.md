# ADR-0031: Several batteries are one pool, entered as Home Assistant's battery systems

## Status

Accepted

## Context

A household with two batteries could give this integration only one: one charge
meter, one discharge meter, one level and one capacity. The README told them to
add the two batteries' meters together with Group helpers and to leave the level
empty, which also lost them the loss measurement and the ledger write-down
(HEA-178). One household did exactly that with template sensors, wrapping a
meter to get past the form's refusal and averaging two levels by hand, and asked
for the batteries to be taken as they already stood in the Energy Dashboard
(Discussion 42).

Home Assistant's Energy Dashboard holds each battery as its own *battery
system*: a charge meter, a discharge meter, an optional state-of-charge sensor,
an optional usable capacity and an optional name (`BatterySourceType` in the
`energy` component). Its own comment on the capacity says what it is for:
weighting the combined state of charge. So Home Assistant already treats several
batteries as one store whose level is their capacity-weighted sum.

ADR-0030 settled that the house inputs are this integration's own, prefilled
from the Energy Dashboard, with the Energy Dashboard the recommended place to
enter them and a change there offered rather than imposed.

## Decision

**Batteries are entered one per battery, in Home Assistant's shape, and
accounted as one pool.**

1. **One entry per battery.** A battery is a config subentry, added with **Add
   battery** as a device is, holding a name, its charge and discharge meters, and
   optionally its level and usable capacity - the battery system's own fields.
   The battery fields leave the house screen. The question of how the battery
   charges (HEA-233) stays there, one answer for the household.
2. **Prefilled from the Energy Dashboard.** Setup offers the Energy Dashboard's
   battery systems straight after the house screen, filled in; **Add battery**
   offers any not yet added. Each says where its answers came from.
3. **One pool.** The meters of every battery add up into the house balance as
   several generation meters do (HEA-219). The pool's contents are the sum of
   each battery's level times its capacity, which is Home Assistant's own
   weighting. There is one stored-cost ledger: energy is priced on the way in
   and drawn at the pool's blended cost on the way out.
4. **A level needs a capacity.** A percentage says nothing in kWh without the
   capacity it is a percentage of, so a battery with one and not the other is
   refused on the form (the pairing HEA-178 already required).
5. **The loss is measured for the pool, and only when every battery's contents
   are known.** It is measured as it is today, against the house's meters and
   bounded by the battery's own (ADR-0002's 2026-09-29 Update, HEA-196). The
   pool's gain is only known when every battery has a level and a capacity; a
   battery without them still has its meters counted and its energy priced.
6. **Each battery's share of the loss is apportioned, and said to be.** With two
   or more batteries, each has its own Battery Losses device beside the combined
   one. Each published loss is split across the batteries by their own bound
   since the measurement's anchor - charge less discharge less gain, all from
   that battery's meters and level - and priced at the pool's cost. A household
   with one battery sees no second device.

Rejected:

- **Lists on the house screen**, as generation now takes several meters. It
  covers the meters but cannot pair each level with its capacity, so a
  two-battery household would get no loss measurement, or one capacity for both,
  and no figure per battery. It is also further from Home Assistant's shape,
  which never separates a battery's meters from its level and capacity.
- **A ledger per battery.** A discharge would have to be traced to the battery
  it came from, and the price of a kWh in one battery is the price of the
  energy that went into it - which the house's meters cannot split between
  batteries charging at the same time. The pooled blend is what the meters can
  honestly say.
- **Following the Energy Dashboard's battery systems live**: ADR-0030.

## Consequences

- Config entry version 6 moves an existing battery into one subentry, with
  nothing about it changing; its figures carry on.
- The pool's loss and ledger are unchanged for a one-battery household, so its
  figures are too.
- A per-battery loss is an apportionment of a measured figure, not a measurement
  of its own, and the README says so. Where two batteries' bounds are close the
  split is close to even; it reflects which one took in energy it did not give
  back.
- HEA-220 also builds the Repair that offers an Energy Dashboard change (take
  them / keep mine), which HEA-221 extends to grid meters.
- Revisit the single household-wide charging answer if a household mixes a
  battery charged from the grid with one that is not.
