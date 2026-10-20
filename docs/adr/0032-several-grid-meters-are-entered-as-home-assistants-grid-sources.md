# ADR-0032: Several grid meters are entered as Home Assistant's grid sources

## Status

Accepted

## Context

This integration takes one import meter, one import price and one export meter.
Home Assistant's Energy Dashboard takes any number of grid sources, each with
its own import meter, export meter and prices (`GridSourceType` in the `energy`
component, on the source itself from 2026.9 and as `flow_from`/`flow_to` lists
before that).

The common case is not two grid connections. It is a **dual-rate meter** that
publishes a peak counter and an off-peak counter, only one of which moves at a
time, each priced separately; the Energy Dashboard holds it as two grid sources.
A household like that can give us one register, or a template sensor adding
both, and then every kWh is priced at one rate. On those tariffs the off-peak
hours are the point of the battery and the timed appliances, so the figures
this product exists for are the ones it gets wrong (HEA-221).

A grid source can also carry something that is not a meter. The reference
household has one whose "meter" is a daily standing charge, priced by a
standing-charge sensor. That is a fee, not energy.

ADR-0030 settled that the house inputs are this integration's own, prefilled
from the Energy Dashboard, with a change there offered rather than imposed.
ADR-0031 did the same for batteries, one entry per battery system. ADR-0026
reads the export price live from the Energy Dashboard.

## Decision

**Grid meters are entered one per grid source, in Home Assistant's shape, and
each register's energy is priced at its own rate.**

1. **One entry per grid source.** A grid meter is a config subentry, added with
   **Add grid meter** as a battery is, holding a name, its import meter, its
   import price and optionally its export meter. The house screen keeps the
   currency, the house consumption meter and generation.
2. **A price can be a number.** The import price is a sensor, a Number helper
   (HEA-132) or a plain number, as the Energy Dashboard allows. A fixed-rate
   register then comes across complete, without the household making a helper
   to hold a constant.
3. **Prefilled from the Energy Dashboard.** Setup offers every grid source after
   the house screen, filled in, read by shape (HEA-117, HEA-209); **Add grid
   meter** offers any not yet added. Each says where its answers came from.
4. **Only energy is offered.** A grid source whose import meter is not an energy
   counter in kWh or Wh is not offered and is not a difference the Energy
   Dashboard check reports. This is a principle, not only a filter: the figures
   are the cost of the energy used, not the bill, so a standing charge has no
   place in a device's figures or the grid price however it is declared. If it
   is ever shown, it is a household-level line beside Paid (ADR-0029, HEA-97).
   A household can still add a grid meter by hand from any energy counter.
5. **Import is priced per register.** In each interval every register's kWh is
   priced at its own rate and the costs summed. The engine's grid price for the
   interval is that cost over the total kWh, and the allocation already works
   from a per-interval grid price, so nothing downstream changes. In an interval
   where no register imported, the price is the plain average of the registers'
   prices, so forgone grid energy is still priced.
6. **Export meters add up; the export price stays one.** Every entry's export
   meter adds into the house balance, as several generation meters do
   (HEA-219). The export price is still read live from the Energy Dashboard,
   the first grid source that names one, exactly as ADR-0026 has it.
7. **A change in the Energy Dashboard is offered.** The take / keep Repair
   (ADR-0030's Update) covers grid meters too. A grid entry is matched by its
   import meter; a different price or export meter on a matched entry is a
   difference, and a renamed one is not.

Rejected:

- **Lists of meters on the house screen.** It cannot pair each register with its
  own price, which is the whole point of the ticket, and it is further from Home
  Assistant's shape.
- **An export price per grid entry, weighted by what each export meter
  exported.** It is the more general answer, but it would replace a value the
  household already has with a copy that can drift, and no household has been
  seen with export split across registers on different rates.
- **Prefilling the standing-charge source and leaving the household to remove
  it.** It would book a daily fee as energy for every household that prices
  one, until they noticed.
- **The price of the last active register for intervals with no import.** It
  depends on which register happened to move last, which says nothing about the
  rate a solar-only interval displaced.

## Consequences

- A config entry version migration moves the existing import meter, price and
  export meter into one grid subentry, with nothing about them changing. A
  single-register household's figures are unchanged, and a test pins that.
- A test drives energy through two registers in turn and asserts each interval
  is priced at its own register's rate to the cent.
- The cold start and the zero-price log assume one import meter today and have
  to cover each register; a silent register gets its own Repair, as a
  generation meter does.
- Revisit the single export price if a household shows export split across
  registers on different rates.
