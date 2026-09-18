"""Which source served the house, when its meters tick at different moments.

A house without its own consumption meter has what it used worked out from the
meters around it: what came in from the grid, what the sun made, what went back
out, and what the battery took and gave. Every one of those is a counter
belonging to somebody else's integration, and they are quantised and published
independently. An inverter reporting whole kilowatt-hours ticks its generation
figure in one interval and its export figure in another, and neither is late or
wrong - that is simply the resolution the household has.

So a 5-minute interval regularly holds half a story: export with no generation
to take it from, or a battery charge before the import that supplied it. The
quantity the balance needs is not knowable *within* that interval, only across
the few that follow.

What is left over is therefore carried, never dropped. A deficit dropped is a
figure biased one way: it can only ever raise what the house is said to have
used, and it never cancels, so a household with coarse counters watches their
total drift above their own meter (ADR-0015's rectification, one layer up -
HEA-133).

Two things are carried, each until the counterpart arrives:

- **Export waiting for a source.** Export is taken off generation first, then
  off the battery's own discharge - a house with no battery can only ever
  export what it made, and a house with one can export what it discharged
  instead of, or as well as, what it generated. What neither can cover yet
  suppresses the generation that follows, rather than being floored at zero and
  forgotten.
- **A charge waiting for its import.** Battery charging only counts as charged
  from the grid up to the import measured alongside it; the rest waits, and a
  later import that arrives is spent on the charge before it is booked as
  something the house burned. Without that, the same kilowatt-hour is counted
  twice: once on its way into the battery, once on its way out.

Both expire, on the same span a suspended charge does. What expires is written
off, which is the trade ADR-0015 already made.

A house that exports straight from its battery - discharging for the grid
rather than for itself, with little or no generation beside it - is not an edge
case this gives up on: the export is charged to the discharge before it is
booked as consumption, the same way it is charged to generation. What is left
over after both is what genuinely cannot be explained yet, and that is what the
carry holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import timedelta


@dataclass(frozen=True)
class HouseReadings:
    """One interval's house-level meter deltas, as configured meters reported them.

    ``house`` is the household's own consumption meter where it has one, and
    ``None`` where it has not: the branch that derives consumption from the
    balance is the one that needs anything carried.
    """

    imported: Decimal
    exported: Decimal
    generated: Decimal
    charged: Decimal
    discharged: Decimal
    house: Decimal | None
    generation_metered: bool


@dataclass(frozen=True)
class Served:
    """House-served energy for one interval, after decomposition.

    ``battery`` is the share of discharge that served the house - what
    consumption and cost are built from. ``discharged`` is the battery's own
    raw meter delta for the interval, kept alongside it because the battery
    ledger's inventory must fall by what physically left the battery, whether
    or not the house is the one billed for it: a discharge that went straight
    to export is gone from the battery regardless of who paid for it.
    """

    grid: Decimal
    generation: Decimal
    battery: Decimal
    discharged: Decimal
    grid_charge: Decimal
    generation_charge: Decimal


@dataclass
class _Carry:
    """Energy still waiting for the counterpart that explains it."""

    kwh: Decimal = Decimal(0)
    since: datetime | None = None

    def hold(self, kwh: Decimal, at: datetime) -> None:
        """Keep what is left over, dating the wait from its first interval."""
        if kwh <= 0:
            self.kwh = Decimal(0)
            self.since = None
            return
        if self.since is None:
            self.since = at
        self.kwh = kwh

    def available(self, at: datetime, expiry: timedelta) -> Decimal:
        """What is still worth waiting for, forgiving anything older than ``expiry``."""
        if self.since is not None and at - self.since >= expiry:
            self.kwh = Decimal(0)
            self.since = None
        return self.kwh

    def persisted(self) -> dict[str, str]:
        return {
            "kwh": str(self.kwh),
            "since": self.since.isoformat() if self.since else "",
        }

    def restore(self, data: Mapping[str, str]) -> None:
        self.kwh = Decimal(data.get("kwh", "0"))
        since = data.get("since") or ""
        self.since = datetime.fromisoformat(since) if since else None


class HouseBalance:
    """Decomposes each interval's house meters into the sources that served it."""

    def __init__(self, expiry: timedelta) -> None:
        self._expiry = expiry
        self._export = _Carry()
        self._charge = _Carry()

    def decompose(self, readings: HouseReadings, at: datetime) -> Served:
        """Split one interval's readings into grid, generation and battery."""
        grid_charge, generation_charge, spare_generation = self._attribute_charge(
            imported=readings.imported,
            generated=readings.generated,
            charged=readings.charged,
            at=at,
        )
        grid = readings.imported - grid_charge

        if readings.house is not None:
            # What the battery discharged beyond the house's own residual need
            # left the same way surplus generation does: out. Capping it here,
            # rather than booking the full raw discharge, is what keeps a house
            # that empties its battery into the grid from being told it burned
            # every kWh the battery gave up (HEA-133's counterpart on discharge).
            residual = max(Decimal(0), readings.house - grid)
            battery = min(readings.discharged, residual)
            generation = residual - battery
        elif readings.generation_metered:
            generation, battery = self._split_export(
                spare_generation, readings.discharged, readings.exported, at
            )
        else:
            generation = Decimal(0)
            battery = readings.discharged

        return Served(
            grid=grid,
            generation=generation,
            battery=battery,
            discharged=readings.discharged,
            grid_charge=grid_charge,
            generation_charge=generation_charge,
        )

    def _attribute_charge(
        self, *, imported: Decimal, generated: Decimal, charged: Decimal, at: datetime
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Where the energy that went into the battery came from.

        Import first, because import measured beside a charge is the supply for
        it, then generation. A charge with neither alongside it waits: the meter
        that supplied it is quantised, and its tick is coming.
        """
        waiting = charged + self._charge.available(at, self._expiry)
        grid_charge = min(waiting, imported)
        waiting -= grid_charge
        generation_charge = min(waiting, generated)
        waiting -= generation_charge
        self._charge.hold(waiting, at)
        return grid_charge, generation_charge, generated - generation_charge

    def _split_export(
        self,
        generated: Decimal,
        discharged: Decimal,
        exported: Decimal,
        at: datetime,
    ) -> tuple[Decimal, Decimal]:
        """What left as export, taken off generation first and the battery next.

        Export is generation's own surplus before it is anything else's - a
        house with no battery can only ever export what it made, which is the
        one-source case this reduces to. What generation cannot account for is
        charged to the battery's discharge instead, because between the two
        there is nowhere else it could have come from: a battery that never
        discharged cannot have exported, and export attributed to the battery is
        export that must not also be booked as the battery serving the house.

        Only what neither can cover is carried, waiting for a generation tick -
        or a discharge - still to come, the same carry the charge side keeps and
        for the same reason.

        Returns ``(generation served, battery served)``.
        """
        leaving = exported + self._export.available(at, self._expiry)
        generation_to_export = min(generated, leaving)
        leaving -= generation_to_export
        battery_to_export = min(discharged, leaving)
        leaving -= battery_to_export
        self._export.hold(leaving, at)
        return generated - generation_to_export, discharged - battery_to_export

    def diagnostics(self) -> dict[str, str]:
        """What is still waiting for its counterpart, for the download."""
        return {
            "export_awaiting_generation": str(self._export.kwh),
            "charge_awaiting_supply": str(self._charge.kwh),
        }

    def snapshot(self) -> dict[str, Any]:
        """Both carries, for the trip across a restart."""
        return {"export": self._export.persisted(), "charge": self._charge.persisted()}

    def restore(self, data: Mapping[str, Any]) -> None:
        """Reinstates the carries. A snapshot without them simply starts at zero."""
        self._export.restore(data.get("export", {}))
        self._charge.restore(data.get("charge", {}))
