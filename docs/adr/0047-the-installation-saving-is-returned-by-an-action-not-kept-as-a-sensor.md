# ADR-0047: The installation saving is returned by an action, not kept as a sensor

## Status

Accepted

HEA-306 (GitHub discussion 58). Follows ADR-0036 (the plan comparison) and
HEA-302 (the `compare_plans` action), which declined a sensor per plan for the
same kind of reason.

## Context

A household asked for one sensor holding what its installation has saved since
day one: what the plan it would be on without its own generation and battery
would cost buying everything from the grid, less what its current plan actually
cost. Other tools would read it, for payback and return on investment.

The figure can be worked out for any period the recorded statistics reach, as
the plan comparison already does. A sensor's own history can be constructed too:
Home Assistant lets an integration write statistics for past hours, so a sensor
need not start with its whole lifetime landing as one hour.

But the saving is not a measurement. It is recomputed from things that change
after the fact:

- the typed prices of the plan the household would be on without its
  installation, which it can correct at any time;
- the recorded statistics themselves, which an impossible hour's Repair
  (ADR-0045) or a gap later filled can change;
- where the sensor's live value has to carry on exactly from its last written
  statistic, or it steps.

A history written once would hold the figures as they were, while the comparison
showed them as they now are.

## Decision

**The installation saving is returned by the `compare_plans` action for the
period asked, worked out from today's inputs on every call. No sensor keeps it.**

A household or another tool keeps a running total by calling the action, for
example daily from the installation's date. Each answer carries the period's
days and the stretches left out, so whatever reads it can say how much it
covers.

### Rejected

- **A sensor whose history is written once.** Simple, but it goes stale the
  first time a plan or an input is corrected, and then disagrees with the card.
- **A statistic rewritten in full whenever its inputs change**, on a plan edit,
  an answered Repair and nightly. It would stay in step, but it is the most work
  and the most risk for one request, and it is a statistic rather than a sensor,
  so a tool reading it would need to read statistics.
- **A sensor with no history written**, whose first value is its whole lifetime:
  Home Assistant's statistics would read it as one hour's jump.

## Consequences

- The saving can never disagree with the plan comparison: both are the same
  calculation on the same inputs.
- A household that wants a running total needs a script or another tool to call
  the action.
- **Revisit** if more households ask for a sensor, or a use appears that the
  action cannot serve. The statistic rewritten in full is then the way to do it
  properly, and this ADR is superseded rather than edited.
