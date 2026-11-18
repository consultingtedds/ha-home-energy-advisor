# ADR-0045: An impossible hour is raised as a Repair that offers a correction

## Status

Accepted

HEA-301 (GitHub discussion 58). Decides what ADR-0044 left open: whether Home
Energy Advisor raises a Repair for an hour no home could use, and whether that
Repair corrects it. Leaves ADR-0044 otherwise standing.

## Context

ADR-0044 leaves an impossible hour out of the plan comparison and names it on
the card. That reaches a household only when it opens the comparison, and only
for the period it is looking at. The same hour is wrong everywhere else that
reads the meter's statistics, the Energy Dashboard first among them.

Home Assistant can correct such an hour: Developer Tools > Statistics lists
outliers, and its Adjust dialog sets a new value for one hour through the
recorder's `adjust_sum_statistics`. But the household has to know to look, find
the right hour among years of them, and work out what the hour should have
recorded. The maintainer has spent many hours fixing hours like these by hand,
with SQL against the recorder's database, before Adjust existed. Most of the
time it was clear from the readings what had happened.

So the useful thing is not only to say an hour is wrong, but to say what
probably happened and what it should have been, and to make the correction
there, while being unmistakable that it changes the household's own statistics.

## Decision

**An hour in which a meter the comparison reads changed by more than a home
could use raises a Repair. The Repair says what was recorded, what probably
happened, and what the hour most likely should have been, and offers to set it
to that, or any value the household gives, after a confirmation that says
exactly what will change.**

1. **Checked once a day, over all of each meter's history.** The meters are
   those ADR-0044 checks (the grid meters, and the house consumption,
   generation and battery meters), and every meter in the Energy Dashboard:
   grid import and export, solar, and battery in and out. A meter in both is
   one statistic, checked once. The check reads their hourly statistics with
   the same ceiling: 100 kWh in an hour, either way. It also runs a few minutes
   after Home Assistant starts. Device meters are not part of it: the live
   accounting's own guard covers them.

2. **One Repair per statistic and hour,** a warning, naming the sensor, the
   hour, and what it recorded. It clears itself once the hour is no longer
   impossible, however it was corrected: by this Repair, by Developer Tools,
   or by the household's own SQL. "Ignore" in Repairs is Home Assistant's own
   and is respected.

3. **The Energy Dashboard's cost and compensation are statistics of their own,
   with Repairs of their own.** A meter's glitch is usually priced into the
   Energy Dashboard's cost for the same hour (or its compensation, for export),
   whether Home Assistant made that cost sensor or the household chose one.
   Each is offered separately, never as one "fix everything", because a
   household may want its meter corrected and its Energy Dashboard left alone,
   or the reverse, or to fix one of them by hand. So each must be found on its
   own: a cost Repair raised only beside an impossible energy hour would vanish
   once the energy was corrected, leaving the cost wrong.
   * **Impossible:** a cost hour above what 100 kWh could have cost at the
     meter's dearest real price: the highest cost per kWh among its ordinary
     hours over the week either side. Without such hours to read a price from,
     a cost hour is not judged.
   * **Suggested:** the hour's energy as it now stands, times the hour's price.
     While the energy hour is still impossible, its own suggestion is used, and
     the price is read from the faulty hour itself, cost over energy, since a
     glitch is priced at the hour's real price. Once the energy hour has been
     corrected, the price is the median of the same hour's prices over the week
     either side.
   * **Each Repair names its partner,** so a household correcting one knows the
     other may need correcting too, and has a Repair of its own.

4. **What probably happened, said in words.**
   * A change within 1% of the meter's own reading at that hour: "this looks
     like the meter's whole total being counted again, as happens when a sensor
     briefly reads zero and then comes back".
   * A change below zero: "the meter's statistics fell by this much".
   * Anything else: "the meter jumped by this much in one hour".

5. **What it most likely should have been.**
   * **From the five minutes it happened in, where Home Assistant still keeps
     them** (ten days by default). A fault is nearly always one big jump in a
     small window: the five minutes that carry it are found, and the hour is
     suggested as the rest of the hour as recorded, plus the median of those
     other five-minute windows for the faulty one. "In the five minutes from
     13:35 the meter jumped by 11,040.6 kWh; the rest of the hour recorded
     0.42 kWh, so 0.46 kWh is suggested." The correction is then made at that
     five-minute window, so the five-minute statistics are corrected with the
     hour's. A cost hour's five minutes are read the same way, against its own
     ceiling.
   * **Otherwise, from the same hour on other days.** The median of the same
     meter's change at the same hour of the day over the seven days either
     side, leaving out any other impossible hour, with the lowest and highest
     of those as a range: "Over the week either side, this meter recorded 0.2
     to 1.4 kWh at this hour; 0.6 kWh is suggested." Where fewer than three such
     hours exist, nothing is suggested and the household types the value.
   * Never below zero.

6. **The correction is two steps, and the second says exactly what changes.**
   * **The value.** The suggestion is filled in. The household can change it.
   * **The confirmation.** Before anything is written: the sensor, the hour, the
     value now and the value it will become, and the difference. That every
     chart, the Energy Dashboard and every card reading the sensor's statistics
     will show the new value for that hour, and the sensor's running total from
     that hour on moves by the difference. That the sensor's own readings and
     state history are not touched. That Home Assistant keeps no undo, so to
     reverse it the household sets the same hour back in Developer Tools >
     Statistics, and the value before is given for that.
   * Only then is the hour corrected, with the recorder's
     `async_adjust_statistics`: the call Developer Tools' Adjust makes, on that
     one statistic, from that one hour. Nothing else is written.

7. **What was changed is recorded.** Each correction is logged at warning level
   with the sensor, the hour, the value before and the value after, so it can
   be found and reversed later.

### Rejected

- **Flag only, pointing to Developer Tools.** Safe, but it leaves the household
  to find the hour and work out its value, which is the slow part.
- **Correcting without asking.** A wrong guess would change the household's
  statistics, and the Energy Dashboard's, without their knowing.
- **Suggesting zero.** Usually wrong: the house used something that hour, and a
  zero would leave a hole in every chart.
- **A suggestion from the hours either side.** Those are often part of the same
  fault, or a different time of day with different use. The same hour on other
  days follows the household's own pattern.
- **One Repair correcting the meter and its Energy Dashboard cost together.**
  Simpler to answer, but too strong: a household may want either corrected
  without the other, or to correct one by hand (maintainer, 2026-11-18).
- **Checking only the period the card shows.** An impossible hour outside it
  stays wrong in the Energy Dashboard, unseen.

## Consequences

- Home Energy Advisor writes to the household's own long-term statistics, but
  only one hour of one meter, only after an explicit confirmation, and only
  through the call Home Assistant's own tool makes.
- A household with old glitches sees one Repair for each, once, after updating.
  Each clears when corrected or ignored.
- The card's left-out line says the hour can be corrected from Settings >
  Repairs.
- The check reads every meter's hourly history once a day: one recorder query
  per meter, in the executor.
- Revisit the suggestion if households find it often wrong for one kind of
  meter, such as generation, whose use follows the weather rather than the
  household's routine.
