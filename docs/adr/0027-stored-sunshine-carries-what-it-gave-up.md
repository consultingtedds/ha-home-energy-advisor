# ADR-0027: Stored sunshine carries what it gave up, through the ledger

## Status

Accepted

Supersedes **ADR-0026 decision 5**, which put battery-charged generation out of
scope and said in terms that it had not answered the household who raised it.
Everything else in ADR-0026 stands, and this changes nothing in ADR-0025:
Battery Savings still decomposes Cost Savings, and still inherits ADR-0002's
optimism about what sun-charged energy cost.

Adds a figure to the model; reverses nothing, and moves no published cost.

## Context

ADR-0026 priced the sunshine a device used **directly** at the export rate it
gave up, and left the sunshine that went into the battery at zero. That boundary
was drawn because pricing generation *into* the ledger changes the blend every
later discharge draws down at - so it would move `Actual Cost` for devices that
ran hours later, on energy the sun never touched.

The half that was left out is the half the question came from. `h227`, on the
community forum:

> *"At 0.9 battery round-trip efficiency for example, previous-local-solar from
> the battery would 'cost' 13.333p/kWh. Previous cheap import at 4.1p/kWh would
> 'cost' from the battery about 4.555p/kWh at that example efficiency."*

Nearly three times, which **reverses which source is cheaper to store**. A
household scheduling a battery charge gets opposite advice depending on a
convention they never chose, and ADR-0026 could not tell them: it only values
sunshine at the moment a device consumes it, and stored sunshine is consumed
much later by something else.

HEA-208 was raised asserting that answering this needed the engine to carry two
ledgers at once, one priced each way. **That was wrong, and it is worth saying
why**, because the same mistake would be easy to repeat: it is only true if the
answer has to arrive by *re-pricing the discharge*. It does not.

## Decision

**The ledger carries what its stored energy gave up, beside what it cost, and a
discharge hands both back.**

`BatteryLedger` holds `stored_kwh` and `stored_cost`. It now also holds the
forgone export value of what is stored, accumulated and drawn down by exactly
the same rules:

1. **Charging from generation adds the export revenue it forwent**, at the rate
   in force when the sun was stored. Charging from the grid adds nothing: that
   energy was bought, and buying it forgoes no export.
2. **Discharging draws it down proportionally**, alongside the cost, and the
   device that used the energy adds it to the same `forgone_export` figure
   ADR-0026 already publishes. The value is fixed when the energy is stored,
   because that is the revenue that was actually given up - not what export
   happens to pay when the battery is emptied.
3. **A write-down drops it with the inventory and publishes nothing**, like the
   cost it sits beside. The write-down knows energy left the books and not why
   (ADR-0026's sibling of this argument is HEA-182's).

That is the whole decision, and the point of it is what it does *not* do.
`Actual Cost` does not move. The reconciliation identity is untouched. No
household's history stops matching what follows. The figure is the same sibling
a household can already switch off on the card.

### Rejected

* **Pricing generation into the ledger at the export rate**, so a discharge
  genuinely costs more. It answers the scheduling question inside the figures
  rather than beside them, which is tempting. It also moves `Actual Cost` for
  every solar-and-battery household on the release that ships it, makes that
  figure an economic measure rather than what they paid, and breaks the
  continuity of their recorded history - the three things ADR-0026 decision 1
  exists to prevent. The disclosure answers the question without any of that.
* **Two ledgers, one priced each way**, so both readings are available at full
  fidelity. This is what HEA-208 assumed was necessary. It doubles the most
  delicate state in the engine, and it buys a precision nobody asked for: the
  household's question is "which is cheaper to store", and a figure beside the
  cost answers it.
* **Valuing the discharge at the export rate of the moment it is used.** Simpler
  to compute and wrong: the revenue was forgone when the energy was stored, and
  a household who charged at noon and discharged at midnight did not give up the
  midnight rate.
* **Leaving it, and documenting the bias.** That was ADR-0002's answer and it
  held for three months. It stopped being enough when somebody derived the
  question independently and showed it changes a decision.

## Consequences

- **The two halves become one figure.** A device's forgone export is now what
  its direct sunshine gave up plus what its share of stored sunshine gave up, in
  one sensor and one column. A household does not have to know a battery was
  involved.
- **ADR-0002's bias statement can retire.** ADR-0026 narrowed it to the battery
  half; this covers that half, so the documented optimism about forgone export
  is now disclosed in full rather than partially. The README and
  `docs/dashboard.md` say what remains true.
- **A household with a battery and no export arrangement sees nothing new**, as
  with Half A: there is no rate, so nothing was forgone.
- **HEA-188 becomes answerable.** What "the marginal price" is depends on what
  surplus solar is worth, and that is now defined on both sides of the battery.
  Still unbuilt, on its own reasoning.
- **The ledger's snapshot gains a field**, and reads an old one as nothing. A
  household upgrading has stored energy whose forgone value was never tracked,
  so it starts at zero and is right from the next charge onwards - the same
  treatment every accumulator added to this ledger has had. A restored snapshot
  is the only path a household is on after their first day, so it is tested
  directly rather than inferred from the fresh one (HEA-206).
- Revisit if a household reports that the combined figure hides which half it
  came from, or if the scheduling question turns out to need the figures
  themselves to move after all.
