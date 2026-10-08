# ADR-0026: Forgone export is published beside the cost, not inside it

## Status

Accepted

Narrows ADR-0002's deferral of export opportunity cost and leaves its
solar-at-zero pricing in force. Adds a figure to the model; reverses nothing.
ADR-0025's point 3 is untouched, and this names the condition that would revisit
it.

## Context

ADR-0002 prices self-consumed solar at zero and says plainly what that costs:

> **Export opportunity cost is deferred.** Pricing solar at zero ignores that
> self-consumed solar forgoes export revenue, so the saving figure is knowingly
> *optimistic*.

Three months of that being a documented bias ended on 2026-10-02, when `h227`
arrived at it unprompted on the community forum, running solar on a dynamic
tariff with no battery:

> *"I'm not sure whether to weight 'local solar' as 12p/kWh 'not exported', so
> that it is usually preferable to grab cheaper electricity if there is any."*

And then with figures, which this question had never had:

> *"At 0.9 battery round-trip efficiency for example, previous-local-solar from
> the battery would 'cost' 13.333p/kWh. Previous cheap import at 4.1p/kWh would
> 'cost' from the battery about 4.555p/kWh at that example efficiency."*

That is the part which makes this more than a presentation bias. On a tariff with
a wide spread the two conventions **disagree about which source is cheaper to
store**, by a factor of three. A household scheduling a battery charge gets
opposite advice depending on a convention they never chose.

Two constraints bound any answer.

**HEA-97 settled where such a figure may live**, before this one existed:

> **Never inside the allocation.** Any such figure is a *sibling* of the
> per-device split, never part of it. The moment one enters a device's
> `Actual Cost`, ADR-0002's reconciliation stops meaning what it says.

**And the question has two halves that are different in kind.** Solar a device
used directly is a price attached to energy already allocated to it. Solar that
charged the battery is an input to `BatteryLedger`, whose blend prices every
later discharge - so re-pricing it moves money for devices that ran hours later,
on energy the sun never touched.

## Decision

**Publish what self-consumed solar gave up as a figure beside the cost, never
inside it, priced at the household's own export rate.**

Five things follow, and the fifth is a deliberate boundary.

1. **A sibling, not a re-pricing.** A new per-device figure accumulates the value
   of generation a device consumed. No device's `Actual Cost` moves, the
   reconciliation identity is untouched, and *"Actual Cost is the cost of metered
   energy at the price at the time"* stays literally true - which is the sentence
   the README and the dashboard's explanation card use to stop a household
   comparing our total against their bill and concluding we are wrong.

2. **Accumulated against the rate in force at the time**, as the sum over
   intervals of generation consumed times the export rate then. Never kWh times
   an average over the period: the rate moves on a dynamic tariff, which is the
   tariff the person who asked is on, and an average would be a different number
   wearing the right name.

3. **The rate is the Energy Dashboard's, read live, and there is no new input.**
   A household who exports has already declared what they are paid for it, and a
   second copy of that is a second source of truth. It is read from the grid
   source's `flow_to`, the same mapping the config flow already takes the export
   *meter* from and walks past the price beside it. Both preference shapes are
   handled, as that code already does: on the source itself from 2026.9, and as
   flow lists before it.

   The precedent is HEA-153's device hierarchy, not the import price. The import
   price is a required input the integration cannot work without, so it is asked
   for and copied into the entry. The hierarchy - and now this - is optional
   enrichment the household has already declared elsewhere, so it is read through
   `async_get_manager`, re-read on `async_listen_updates`, and held in one place
   *"so the figures and the cards cannot come to disagree about it"*. **The
   asymmetry between the two prices is the difference between a precondition and
   an enrichment**, not an oversight.

4. **The household chooses whether to add it, on the card**, defaulting to
   including it. Both readings are honest and they answer different questions -
   what left the bank account, and what the energy was worth - so this is
   ADR-0013's and HEA-100's case for offering both rather than picking one. Where
   no export rate is configured the figure does not exist and **no control is
   offered**, because a switch between two identical pictures is worse than no
   switch.

5. **Energy the sun put into the battery is out of scope here, and stays priced
   at zero.** It cannot be a sibling figure: `charge_from_generation` books it
   into the ledger with no price at all, so pricing it changes the blend every
   later discharge draws down at. That moves `Actual Cost` for devices that ran
   later, cannot be recomputed by a card from published statistics, and would
   need the engine to carry two ledgers at once. It is also the half h227's
   figures turn on, so this ADR does not pretend to have answered him.

### Rejected

* **Re-pricing self-consumed solar outright**, so there is one convention and no
  control. It moves every solar household's figures on the release that ships it,
  leaves their history incomparable with what follows, and makes `Actual Cost` an
  economic measure rather than what they paid. The honest way to show a bias
  exists is to let it be seen both ways, not to swap one unstated convention for
  another.
* **Our own export-price input**, matching the import price's shape. Rejected as
  a duplicate with no single source of truth: it would silently diverge the first
  time a household edited one and not the other, and nothing on any screen would
  show which was in force.
* **A settings option rather than a card control.** The figure is additive and
  derivable per period, so there is nothing an options flow buys except a reload
  and a question asked once, at the moment a household knows least about it.
* **Treating it as negative saving inside Cost Savings.** It would reconcile with
  nothing, and ADR-0025 has already decomposed that figure on the understanding
  that generation's half is a subtraction.
* **Waiting for more demand.** HEA-97 applies the demand test to standing charges
  and export payback and this inherits it, but the test is met: one household
  derived the question independently, and ADR-0002 has owed an answer since the
  engine was designed.

## Consequences

- **The bias statement narrows rather than retires.** ADR-0002's deferral stays
  true of battery-stored solar and stops being true of directly consumed solar.
  The README and `docs/dashboard.md` say which half remains.
- **ADR-0025's point 3 is unchanged.** Battery Savings still credits sun-charged
  discharge to the battery, and still inherits ADR-0002's optimism, because this
  changes nothing about what enters the ledger. ADR-0025 asks to be revisited
  "if the export-price variant lands" - it has landed for the half that does not
  touch the ledger, and point 3 is revisited by decision 5 above, not by this.
- **HEA-188 becomes answerable.** Whether a battery charge should be priced
  marginally depends on what surplus solar is worth, and that was previously
  undefined. Still unbuilt, on its own reasoning.
- **HEA-97's other two items get harder to leave alone.** A household shown what
  their export was worth will ask why what they actually earned is not counted.
  That is export payback, item 2, and it is now a question with a date on it.
- **A household with no export arrangement sees no change at all** - no figure,
  no control, no new entity. That includes a household tracking export as a
  compensation statistic rather than a price, which carries no rate to read.
- **The engine gains a second price series to record**, with the same lateness
  and retention behaviour as the import price, since a figure accumulated against
  the rate at the time needs the rate at the time to still be known.
- Revisit if: a household reports that the two readings confuse rather than
  inform; the Energy Dashboard stops carrying an export price in a readable
  shape; or decision 5 is taken up, which would supersede this ADR's boundary
  rather than amend it.
