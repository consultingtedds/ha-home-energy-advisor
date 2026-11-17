# ADR-0044: An hour no home could use is left out like an hour with no data

## Status

Accepted

HEA-301 (GitHub discussion 58). Adds an exception to decision 4 of ADR-0043 ("a
recorded zero is data", which treats every recorded value as data) and leaves
the rest of ADR-0043 standing.

## Context

The plan comparison reads the recorder's long-term statistics directly, often
from months before Home Energy Advisor was installed. Nothing checks them. The
live accounting does: a source that steps implausibly raises a Repair
(`implausible_step`), but that guard sees only readings arriving now.

A household on 1.5.0 (hlps4, 2026-11-16) found "Without solar or battery" about
ten times too high. Their house consumption meter had one hour in May 2026 that
recorded +11,041 kWh, left by a template sensor that briefly read an input as
zero long before. The comparison priced that hour as energy bought from the
grid. Home Assistant's Developer Tools > Statistics listed it first among the
outliers, and the household corrected it with Adjust, but finding it took
detective work.

ADR-0043 decision 4 says a recorded value is data, so the comparison has no way
to set an impossible hour aside. A recorded zero is still data, and that stays.
What is missing is a line between a value that is unusual and one that no home
could have produced.

## Decision

**An hour in which any meter the comparison reads recorded more energy than a
home could use is left out of every plan, as an hour with no data is, and the
card names the meter, the hour and the kWh.**

1. **A fixed ceiling: 100 kWh in an hour.** A large three-phase home connection
   delivers around 40 to 45 kW, so no real hour comes near it, while a glitch of
   hundreds or thousands of kWh is far above it. Five-minute statistics are held
   to the same rate: 100/12 kWh in five minutes. The ceiling applies to the
   size of the change either way, so a counter that fell by as much is caught
   too.

2. **Every meter the comparison reads.** The grid meters, which every plan is
   priced from, and the meters "Without solar or battery" is priced from: the
   house consumption meter, or the generation and battery meters where there is
   none.

3. **Left out of every plan, as ADR-0043 leaves out a gap.** Its energy, its
   export, and its share of the daily charges, so every plan is still compared
   over the same hours. A gap of two hours or less is bridged under ADR-0043
   because its energy arrives in the next row; an impossible hour is never
   bridged, because its energy is the fault.

4. **The card says which meter, when, and how much.** A line above the table,
   beside the left-out lines of ADR-0043: the sensor's name and entity id, the
   hour, the kWh recorded, and that it can be corrected in Developer Tools >
   Statistics, where Home Assistant's own Adjust fixes it. Once it is corrected
   the hour is compared again, with nothing more to do.

### Rejected

- **A multiple of the median hour.** It adapts to each home, but trips on a
  genuinely heavy hour, such as a night of electric-vehicle charging, which is
  exactly when a household reads the comparison closely.
- **Pricing the hour and only warning.** The figures stay wrong by the whole
  glitch until the household acts, and a total ten times too high cannot be
  read past.
- **A ceiling the household sets.** One more setting to explain, for a line no
  home approaches.

### Not decided here

Whether Home Energy Advisor should also raise a Repair for the hour, and whether
that Repair should offer to correct it (the recorder's `adjust_sum_statistics`,
which Developer Tools uses), after the household confirms the value the hour
should have recorded. Either would change the household's own statistics,
which the Energy Dashboard reads too, and a correction can only be undone by
adjusting back. It is decided in a later ADR (HEA-301).

## Consequences

- An impossible hour no longer multiplies a plan's figures, and the household is
  told where to fix it rather than having to find it.
- The left-out lines gain a third cause beside the grid meters and a price
  sensor; the comparison's response carries the kWh for it.
- The live accounting's own guard is unchanged: this reads history, that reads
  the readings arriving now.
- Revisit the ceiling if Home Energy Advisor is used on supplies far larger than
  a home's.
