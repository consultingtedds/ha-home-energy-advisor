# ADR-0025: The battery's saving is a decomposition of Cost Savings, not a second opinion

## Status

Accepted

Extends ADR-0009, which named Cost at Grid Price for the rule it applies rather
than the hardware it lacks, and ADR-0007, which made every monetary figure
`total`. Adds a figure to the model; reverses nothing.

## Context

Asked for by a household running Predbat, on GitHub issue 29:

> *"My main goal is to see how many money I save using my home battery (or lose
> due incorrect behavior)."*

Cost Savings already contains that answer and buries it. It compares every kWh
against the import price of the moment, whatever served it, so a house with
panels shows a large saving with no battery at all, and a battery charged at the
wrong time can be losing money inside a figure that still looks healthy. The
household cannot tell which of their kit earned what.

Both numbers the answer needs already exist in the same function. `BatteryLedger`
prices each charge at its source and draws discharge down at the weighted-average
stored cost, so at the instant of a discharge the engine knows what that stored
kWh cost; `SourceKind.IMPORT` carries what the same kWh would have cost bought
then. `_price_sources` holds both and throws the difference away.

## Decision

**Publish the battery's share of Cost Savings, as a decomposition of it rather
than as a figure of its own.**

Cost Savings is the sum over sources of `energy x (import price - source price)`.
Only two sources are ever priced below import, so it expands to exactly

    generation x import price  +  battery x (import price - stored cost)

and the second term is published as **Battery Savings**. The first is left as the
subtraction, because a household who wants it can do it and a second entity
cannot be taken back.

That framing is the decision, and four things follow from it.

1. **It has to reconcile, not approximate.** A figure that drifted from Cost
   Savings would be a second opinion about the same money, which is the one thing
   this project does not ship (ADR-0015). So it is shared out by the same
   proportional rule as its two parents, and an overdraw withholds all three in
   step.
2. **It travels every path money reaches a device by**, and there are four: the
   live allocation, a late arrival correcting a retained bucket, a debt repaid out
   of a later bucket's surplus, and a debt that expires. The third was missed in
   the first build and cost EUR 0.0705 per settlement, silently - found by
   probing the identity rather than by reading the code, which is why the
   invariant is now a test on each path rather than an arithmetic example.
3. **Energy the sun put in the battery is the battery's saving, not the
   panels'.** The debatable line, taken deliberately: without the battery that
   surplus would have been exported and the evening's kWh bought at peak, so the
   battery is what made it available then, and *"what did having a battery do for
   me"* is the question that was asked. It inherits ADR-0002's documented optimism
   about forgone export revenue, which HEA-38 tracks and which this does not
   change.
4. **It can fall, and is not clamped.** A battery charged dear and discharged
   cheap costs the household money. The person who asked for this said so first -
   *"or lose due incorrect behavior"* - and a figure that could only rise would
   answer the opposite of the question. `total` and a moving zero point make that
   safe to record (ADR-0007, ADR-0022).

### Rejected

* **Per-device battery savings.** The machinery would answer it, since allocation
  is proportional all the way down. Nobody asked what the dishwasher saved by
  running off the battery, and it would cost an entity per tracked device. The
  per-device split is in the diagnostics if it is ever wanted.
* **Publishing generation's half too**, so the identity is visible on the
  dashboard. Derivable by subtraction, and a second entity is permanent while a
  subtraction is not.
* **Arbitrage only** - the price difference on grid-charged energy, with
  sun-charged discharge credited to the panels. It does not decompose Cost
  Savings, so it would reconcile with nothing.
* **Round-trip efficiency**, which is energy rather than money and is HEA-174.

## Consequences

- **No cycle meters, by inheritance.** The whole-home device is excluded from
  cycle metering (HEA-48), so "what did my battery save this month" comes from
  statistics over a period, as ADR-0008 intends for every period figure. It also
  means this figure adds no `utility_meter` helpers and none of their noise.
- **Created disabled where there is no battery**, on HEA-175's rule: a figure
  that can only read zero is worse than no figure, and creating it anyway fixes
  its identity so fitting a battery later needs no migration. The test asserts a
  solar-but-no-battery home, which neither existing case covered.
- **The snapshot gained a field, and reads an old one as nothing.** Refusing an
  unreadable snapshot is the general rule and stays right, but here the shape is
  understood and one key is absent - so insisting would send every installed
  household through a cold start on upgrade and take the battery's stored-cost
  ledger with it, pricing their next discharge at zero to gain a figure whose
  absence means zero (ADR-0021).
- **The retained ring now keeps each bucket's battery price.** A late arrival is
  priced against the charge that really served it rather than whatever the ledger
  holds when it turns up, which is the same reasoning that settles a repayment at
  the repaying bucket's blend.
- Revisit if the export-price variant (HEA-38) lands, which would change what
  sun-charged energy is worth and therefore point 3.
