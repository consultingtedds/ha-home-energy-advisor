# ADR-0038: A band applies to days of its own choosing, with holidays a day of their own

## Status

Accepted

HEA-268 (GitHub discussion 58). Widens ADR-0036's band days and its holiday
rule (decisions 2 and 6); leaves the rest of ADR-0036 standing.

## Context

ADR-0036 gave a band one of three sets of days: weekdays, weekends and holidays,
or every day. A public holiday named by the plan's calendar was priced as a
weekend day. Two shapes Australian households report cannot be written that
way (Roving-Ronin, 2026-11-04):

- **Three kinds of day.** Weekday, weekend and public holiday each at prices of
  their own.
- **A weekend that starts on Friday evening.** Monday 00:00 to Friday 22:00 at
  weekday prices, then Friday 22:00 to Sunday 23:59 at weekend prices. Friday
  after 22:00 is priced unlike Friday before it, which no set of whole weeks of
  days can say.

Home Assistant's forms have no timetable editor, so whatever a band can say has
to be entered one band at a time (ADR-0036).

## Decision

**A band applies to any of Monday to Sunday and public holidays. The three sets
ADR-0036 named stay as shortcuts. A holiday is a day of its own only in a plan
that has a band for holidays; in any other plan it is priced as the day of the
week it falls on.**

1. **Eight days.** A band covers some of Monday, Tuesday, Wednesday, Thursday,
   Friday, Saturday, Sunday and Holiday, at least one. The Friday-evening weekend
   is a weekday band to 22:00, a Friday band from 22:00 at the weekend price, and
   a weekend band.

2. **Shortcuts kept.** Weekdays is Monday to Friday; weekends and holidays is
   Saturday, Sunday and Holiday; every day is all eight. The band form offers
   them first, as before, with "Choose days" opening a list of the eight to tick.
   A plan's entry stores either the shortcut's name or the list of days, so every
   plan already entered reads exactly as it did, with no migration.

3. **A holiday falls back to its day of the week.** A plan none of whose bands
   includes Holiday prices a holiday as the Monday or Saturday it is. A plan with
   any band for holidays treats a holiday as a day of its own, every hour of which
   must be covered once, like any other day. So a household that ticks days one by
   one and never thinks about holidays gets a plan that saves and prices, and a
   plan built from the shortcuts prices holidays as weekends, as ADR-0036 did.

4. **Gaps grouped by the hours they miss.** Coverage is checked for each day the
   plan prices. Days missing the same hours are reported together, by the
   shortcut's name where they match one ("Weekdays: 22:00-24:00") and one by one
   otherwise.

### Rejected

- **A list of the eight days only, with no shortcuts.** One step per band and a
  form like Home Assistant's own time condition, but the common case, a weekday
  band, becomes unticking three boxes on every band. The maintainer chose to keep
  the shortcuts.
- **A holiday always a day of its own when a calendar is named.** Stricter and
  more predictable, but a plan built from chosen days would fail to save until
  Holiday was ticked somewhere, though most such plans price a holiday as the day
  it falls on.
- **Bands with start and end days, such as Friday 22:00 to Monday 00:00.** Closer
  to how the Friday-evening weekend is written, but a band would no longer be the
  same hours on each of its days, and coverage could not be checked day by day.

## Consequences

- The two shapes from discussion 58 can be entered, and every plan entered before
  prices as it did.
- A plan built from chosen days with no holiday band prices a holiday as its day
  of the week, though the plan names a holiday calendar. The form says so where
  the days are chosen.
- The review lists a weekday-only start as missing "Weekends" rather than
  "Weekends and holidays": until a band includes holidays, they are not a day of
  their own.
- Revisit if an offer prices part of a day by date rather than by day of the
  week, such as a holiday eve.
