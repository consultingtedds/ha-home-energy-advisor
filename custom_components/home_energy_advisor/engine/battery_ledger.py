"""Tracks what the energy stored in the battery cost, so discharge can be priced.

A battery breaks the link between when energy is bought and when it is used:
Predbat force-charges cheaply overnight (~€0.093) or banks free surplus local
generation, then discharges at the evening peak. Pricing that discharge at the
live import rate would be badly wrong. This ledger instead prices each charge at
its source - grid charge at the import rate of the moment, generated charge at
zero - and draws discharge down at the weighted-average stored cost, the standard
moving-average inventory method.

Deliberate MVP simplifications, each a documented optimistic bias to be measured
against Predbat's own accounting in dogfooding (HEA-28):

- **Starts empty.** Energy already in the battery when the integration starts
  has no known cost. Discharging it - or discharging more than the ledger has
  tracked - prices the shortfall at zero, as if locally generated. The error is
  transient: it washes out within a cycle or two as real charge data arrives.
- **Round-trip losses are not inflated.** Charging 10 kWh to retrieve 9 leaves
  the lost kWh's cost on the books rather than raising the per-kWh discharge
  price.

Left alone, that stranded energy never leaves: the only way this ledger corrects
itself is being drained to empty, and a growing phantom is precisely what stops
that happening. A household who tells us how full their battery is gets
:meth:`reconcile`, which writes the inventory down to what is really there and
hands back the cost to be booked. One who does not is on the path above, and the
bias stays as documented (HEA-178).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class Withdrawal:
    """What a discharge took out: what it cost, and what it gave up.

    Two figures rather than one because they answer different questions and are
    treated differently. ``cost`` is what the household paid to put that energy
    there and enters their totals; ``forgone`` is the export revenue the stored
    sunshine gave up, which is published beside those totals and never inside
    them (ADR-0026, ADR-0027).
    """

    cost: Decimal
    forgone: Decimal


class BatteryLedger:
    """Weighted-average stored-cost ledger for one battery.

    ``charge_from_grid`` and ``charge_from_generation`` add priced energy;
    ``discharge`` removes it and returns what that energy cost. In an interval
    that reports both a charge and a discharge, apply the charge first so the
    discharge is priced against the updated blend.
    """

    def __init__(self) -> None:
        self._stored_kwh = Decimal(0)
        self._stored_cost = Decimal(0)
        # What the stored sunshine would have earned had it been exported
        # instead, at the rate in force when it was stored (ADR-0027).
        # Accumulated and drawn down by exactly the rules `_stored_cost` is, so
        # a discharge carries its share of both.
        self._stored_forgone = Decimal(0)
        # What reconciliation has written off in total, kept so a cost published
        # on the household's figures can be accounted for in the diagnostics, and
        # so the loss itself can be published (HEA-174).
        self._written_off_kwh = Decimal(0)
        self._written_off_cost = Decimal(0)

    @property
    def stored_kwh(self) -> Decimal:
        """Energy the ledger believes is in the battery."""
        return self._stored_kwh

    @property
    def losses(self) -> tuple[Decimal, Decimal]:
        """Energy reconciliation has written off, and what it cost (HEA-174).

        The household's round-trip loss, measured rather than subtracted: taking
        `charged - discharged` over a window is wrong by whatever the battery's
        level did across it, while this is the same quantity reconciled against
        what the battery actually holds, so the level cancels.

        Running totals, so a period's loss is the change across it - the way
        every other figure here is read (ADR-0008).
        """
        return self._written_off_kwh, self._written_off_cost

    @property
    def unit_cost(self) -> Decimal:
        """The weighted-average stored cost in currency per kWh, or zero if empty."""
        if self._stored_kwh == 0:
            return Decimal(0)
        return self._stored_cost / self._stored_kwh

    def charge_from_grid(self, kwh: Decimal, price_per_kwh: Decimal) -> None:
        """Adds grid-charged energy at the import price of the moment.

        The price may be **negative**, and that is not an error to guard: on a
        wholesale tariff a negative spot price is an ordinary market state, and
        a household whose automation charges the battery because the price went
        below zero was paid to store that energy. Carrying the sign is what the
        rest of the engine already does - a negative price reaches
        ``SourceKind.IMPORT`` unaltered for energy served straight to the house -
        and it is what the reconciliation invariant requires, since what is
        allocated must equal the real grid bill, which was negative (HEA-165).
        """
        # Buying energy forgoes no export: it was imported, not generated.
        self._charge(kwh, kwh * price_per_kwh, Decimal(0))

    def charge_from_generation(
        self, kwh: Decimal, export_price: Decimal = Decimal(0)
    ) -> None:
        """Adds locally-generated charge, which costs nothing at the margin.

        It is not free, though, and ``export_price`` is what it gave up: this
        energy could have been exported instead, at the rate in force now rather
        than whenever the battery is next emptied (ADR-0027). Zero for a
        household who export nothing, which is what they forgo.
        """
        self._charge(kwh, Decimal(0), kwh * export_price)

    def discharge(self, kwh: Decimal) -> Withdrawal:
        """Removes energy and returns what it cost and what it gave up.

        Any part of the draw beyond what the ledger has tracked is priced at
        zero and forgoes nothing (see the module docstring): energy the ledger
        never saw cannot have given anything up. The ledger never goes negative.

        The forgone revenue is drawn down by the same share as the cost, so a
        partial discharge takes its part of a blend that may have been stored at
        several different export rates (ADR-0027).
        """
        if kwh < 0:
            msg = f"discharge cannot be negative: {kwh}"
            raise ValueError(msg)

        from_stored = min(kwh, self._stored_kwh)
        if from_stored == self._stored_kwh:
            cost = self._stored_cost
            forgone = self._stored_forgone
            self._stored_kwh = Decimal(0)
            self._stored_cost = Decimal(0)
            self._stored_forgone = Decimal(0)
        else:
            share = from_stored / self._stored_kwh
            cost = from_stored * self.unit_cost
            forgone = self._stored_forgone * share
            self._stored_kwh -= from_stored
            self._stored_cost -= cost
            self._stored_forgone -= forgone
        return Withdrawal(cost=cost, forgone=forgone)

    def reconcile(
        self, available_kwh: Decimal, ceiling: Decimal | None = None
    ) -> Decimal:
        """Writes the inventory down to what the battery really holds.

        Returns the cost of the energy written off, for the caller to book.

        The inventory here is inferred rather than measured - charge in, discharge
        out - and two things leave the battery by a door it does not subtract
        from: round-trip losses, and any discharge the configured meter does not
        count. Both stay on the books for ever, and because the only other way
        this ledger corrects itself is being drained to empty, a growing phantom
        is precisely what stops that happening. Measured on the reference
        instance at 15.69 kWh in a 5 kWh battery (HEA-178).

        **Down only.** A ledger holding *less* than the battery does is the
        ordinary state of a household who installed this with a battery already
        part full, and that shortfall is already priced at zero on discharge (see
        the module docstring). Writing it up would invent energy at a cost nobody
        paid and drag the blend of what really is in there towards free.

        **The blend is preserved**, because a write-down says nothing about what
        the energy still in there cost. Moving the price to fix the inventory
        would make every later discharge wrong in order to correct a figure
        nobody reads.

        The cost handed back carries its sign: energy a household was *paid* to
        store (HEA-165) is written off as a credit, since charging them for
        losing it would be the same sign error in reverse.
        """
        if available_kwh >= self._stored_kwh:
            return Decimal(0)
        # A ceiling is what the household's *other* meters can account for, and
        # it refuses a write-down they cannot explain. A discharge meter counting
        # only what reached the house makes the battery's exports look like
        # losses, and publishing those as energy the household used would claim
        # more than the house drew. Held on the books instead, which is the
        # honest "we cannot tell" rather than a confident wrong answer.
        if ceiling is not None:
            available_kwh = max(available_kwh, self._stored_kwh - ceiling)
            if available_kwh >= self._stored_kwh:
                return Decimal(0)
        self._written_off_kwh += self._stored_kwh - max(available_kwh, Decimal(0))
        # The forgone revenue of a phantom is as phantom as its energy, so it
        # goes with the inventory - and like the cost beside it, nothing about
        # the write-down is published (ADR-0027).
        kept_share = (
            Decimal(0)
            if self._stored_kwh == 0
            else max(available_kwh, Decimal(0)) / self._stored_kwh
        )
        if available_kwh <= 0:
            written_off = self._stored_cost
            self._stored_kwh = Decimal(0)
            self._stored_cost = Decimal(0)
            self._stored_forgone = Decimal(0)
        else:
            kept = available_kwh * self.unit_cost
            written_off = self._stored_cost - kept
            self._stored_kwh = available_kwh
            self._stored_cost = kept
            self._stored_forgone *= kept_share
        self._written_off_cost += written_off
        return written_off

    def forget_losses(self) -> None:
        """Rebases the running loss totals, leaving the inventory alone (HEA-57).

        The inventory is physical fact about the present and survives a rebase;
        these two are a published running total of the past and do not.
        """
        self._written_off_kwh = Decimal(0)
        self._written_off_cost = Decimal(0)

    def _charge(self, kwh: Decimal, cost: Decimal, forgone: Decimal) -> None:
        if kwh < 0:
            msg = f"charge cannot be negative: {kwh}"
            raise ValueError(msg)
        self._stored_kwh += kwh
        self._stored_cost += cost
        self._stored_forgone += forgone

    def diagnostics(self) -> dict[str, str]:
        """What the ledger holds, so a discharge price can be explained.

        Unrounded: these two figures are what set the rate the next discharge is
        priced at, and a rounded pair cannot reproduce it.
        """
        return {
            "stored_kwh": str(self._stored_kwh),
            "stored_cost": str(self._stored_cost),
            "written_off_kwh": str(self._written_off_kwh),
            "written_off_cost": str(self._written_off_cost),
        }

    def snapshot(self) -> dict[str, str]:
        """What the battery holds, so a restart resumes pricing rather than reset.

        The stored cost is physical fact: the battery holds energy bought at a
        known price, and discharging it after a restart is no more free than
        after a rebase.

        ``Decimal`` goes to ``str``, never ``float`` - the ledger exists to price
        energy exactly.
        """
        return {
            "stored_kwh": str(self._stored_kwh),
            "stored_cost": str(self._stored_cost),
            "stored_forgone": str(self._stored_forgone),
            "written_off_kwh": str(self._written_off_kwh),
            "written_off_cost": str(self._written_off_cost),
        }

    def restore(self, data: Mapping[str, str]) -> None:
        """Reinstates a snapshot taken by :meth:`snapshot`.

        The written-off total is absent from every snapshot taken before
        reconciliation existed, and is read as nothing rather than refused: the
        shape is understood, and insisting would cold-start every installed
        household and discard the very ledger this exists to correct (ADR-0021).
        """
        self._stored_kwh = Decimal(data["stored_kwh"])
        self._stored_cost = Decimal(data["stored_cost"])
        # Absent from every snapshot written before this was tracked. A
        # household upgrading holds sunshine whose forgone value nobody
        # recorded, so it starts at nothing and is right from the next charge.
        self._stored_forgone = Decimal(data.get("stored_forgone", 0))
        self._written_off_kwh = Decimal(data.get("written_off_kwh", 0))
        self._written_off_cost = Decimal(data.get("written_off_cost", 0))
