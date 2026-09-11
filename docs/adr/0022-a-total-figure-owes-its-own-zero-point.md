# ADR-0022: A `total` figure owes its own zero point

## Status

Accepted

Extends ADR-0007, which moved every monetary figure to `state_class: total` and
recorded that the actual and naive costs "lose nothing" by the move. They lost
one thing, and this ADR names it. Leaves ADR-0007's decision itself intact:
`total` is still right for money, for the reasons ADR-0007 gives.

## Context

ADR-0007 reasoned that `total` "models a monotonic accumulator perfectly well -
it simply does not *assume* monotonicity", so a figure that only ever grows is
no worse off under it. That is true of the value, and false of what Home
Assistant does with the value.

Home Assistant's statistics compiler has two ways to learn that an accumulator
has gone back to zero, and the state class decides which one it uses:

* a `total_increasing` counter falling is read as a new cycle on sight,
* a `total` figure falling is read as a *decrease*, unless the `last_reset`
  attribute has moved.

So moving money to `total` did lose something: the free reset detection that
`total_increasing` carries. Nothing needed it until `reset_totals` shipped a few
weeks later (HEA-57), which is why ADR-0007 reads fine on its own terms.

The bill arrived on the reference instance. The rebase of 2026-08-18 sent every
figure to zero, and the compiler booked the fall as a loss of the whole balance:

| Sensor | State class | Change on the reset day |
| -- | -- | -- |
| `whole_home_energy_used` | `total_increasing` | +3.03, clean |
| `whole_home_cost_savings` | `total` | **-94.86** |
| `whole_home_actual_cost` | `total` | **-23.90** |

The cards read `change` and sum the buckets in a period, so every period
containing that day reported money that was not merely wrong but inverted, by
the entire previous balance. Periods wholly after the rebase were correct, which
is why it went unnoticed for three weeks (HEA-122).

## Decision

**Every sensor this integration publishes with `state_class: total` carries a
`last_reset`, and moves it when the figure starts again.** The stamp lives on
`_HeaRestoringSensor`, so it reaches every figure by inheritance rather than by
each sensor remembering to opt in.

Three properties are as much the decision as the stamp itself, because each is a
way to reintroduce the same defect:

1. **Absent until a rebase actually happens.** A household that merely upgrades
   already has statistics compiled with no stamp, so a stamp appearing from
   nowhere reads as a new cycle on a series that never had one - and the
   compiler books its whole lifetime balance as a *positive* change. The same
   defect with its sign flipped, and the one a careless reading of Home
   Assistant's documentation produces.
2. **Unchanged across a restart**, read back from the sensor's own restored
   state. A stamp that moved on every startup would book the restored lifetime
   balance as a change at every startup.
3. **Never on a `total_increasing` figure.** Home Assistant raises a
   `ValueError` out of `state_attributes` for a stamp on any other state class,
   and it would be redundant: those counters already get reset detection.

### Rejected

* **Move the money back to `total_increasing`.** Home Assistant rejects
  `monetary` + `total_increasing` outright, and Cost Savings genuinely dips
  under battery arbitrage. ADR-0007's decision stands.
* **Guard the card against a negative change.** A negative Cost Savings is a
  real signal that ADR-0012 deliberately renders below the axis. Suppressing it
  to hide one bad bucket would blind the card to the case it exists to show.
* **Clear the statistics harder at reset time.** The clear is not the problem.
  It already works - there is no history at all before the rebase. The crater is
  what the clear leaves *behind* it: the next window to compile holds a full
  balance and then a zero, with no prior statistic to anchor them, so the fall
  between them is booked as the first thing that series ever recorded.
* **Say "this period contains a reset and cannot be totalled".** Considered,
  because it is arguably the truthful answer. Unnecessary once the compiler is
  told what happened: the period can be totalled, and correctly.

## Consequences

- The obligation now travels with the state class rather than with a particular
  sensor. Any future `total` figure that does not inherit
  `_HeaRestoringSensor` has to publish its own stamp, and the property's
  docstring is where that is written down.
- The `utility_meter` cycle helpers need nothing. They stamp a zero point when
  they are built and carry one ever after, so once the rebase has cleared the
  statistics behind them the compiler reads the existing stamp as a new cycle.
  Checked rather than assumed: the test passes with the fix reverted, and says
  so.
- **Nothing repairs a crater already recorded.** The reference instance keeps
  its 2026-08-18 bucket, and any household that rebased on an earlier build
  keeps theirs. `recorder/adjust_sum_statistics` is the only supported way to
  correct a single bucket if it is ever judged worth doing; the README instead
  tells the household to avoid ranges that straddle such a day.
- The tests for this run against the real recorder and the real compiler, driven
  through the real service, because the whole claim is about what Home Assistant
  records. A double built from our own reading of the compiler would have agreed
  with the bug.
- Revisit if Home Assistant changes how a `total` series' resets are detected,
  or if it gains a way to mark a period as spanning a discontinuity - which is
  the honest answer the rejected option above was reaching for.
