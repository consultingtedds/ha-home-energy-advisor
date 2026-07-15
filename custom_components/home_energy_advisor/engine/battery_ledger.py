"""Tracks what the energy stored in the battery cost, so discharge can be priced.

A battery breaks the link between when energy is bought and when it is used:
Predbat force-charges cheaply overnight (~€0.093) or banks free surplus solar,
then discharges at the evening peak. Pricing that discharge at the live import
rate would be badly wrong. This ledger instead prices each charge at its source
— grid charge at the import rate of the moment, solar charge at zero — and draws
discharge down at the weighted-average stored cost, the standard moving-average
inventory method.

Deliberate MVP simplifications, each a documented optimistic bias to be measured
against Predbat's own accounting in dogfooding (HEA-28):

- **Starts empty.** Energy already in the battery when the integration starts
  has no known cost. Discharging it — or discharging more than the ledger has
  tracked — prices the shortfall at zero, as if solar-charged. The error is
  transient: it washes out within a cycle or two as real charge data arrives.
- **Round-trip losses are not inflated.** Charging 10 kWh to retrieve 9 leaves
  the lost kWh's cost stranded on the books rather than raising the per-kWh
  discharge price. Correcting it needs a state-of-charge signal to reconcile
  against; deferred.
"""

from __future__ import annotations

from decimal import Decimal


class BatteryLedger:
    """Weighted-average stored-cost ledger for one battery.

    ``charge_from_grid`` and ``charge_from_solar`` add priced energy;
    ``discharge`` removes it and returns what that energy cost. In an interval
    that reports both a charge and a discharge, apply the charge first so the
    discharge is priced against the updated blend.
    """

    def __init__(self) -> None:
        self._stored_kwh = Decimal(0)
        self._stored_cost = Decimal(0)

    @property
    def stored_kwh(self) -> Decimal:
        """Energy the ledger believes is in the battery."""
        return self._stored_kwh

    @property
    def unit_cost(self) -> Decimal:
        """The weighted-average stored cost in currency per kWh, or zero if empty."""
        if self._stored_kwh == 0:
            return Decimal(0)
        return self._stored_cost / self._stored_kwh

    def charge_from_grid(self, kwh: Decimal, price_per_kwh: Decimal) -> None:
        """Adds grid-charged energy at the import price of the moment."""
        if price_per_kwh < 0:
            msg = f"import price cannot be negative: {price_per_kwh}"
            raise ValueError(msg)
        self._charge(kwh, kwh * price_per_kwh)

    def charge_from_solar(self, kwh: Decimal) -> None:
        """Adds solar-charged energy, which costs nothing at the margin."""
        self._charge(kwh, Decimal(0))

    def discharge(self, kwh: Decimal) -> Decimal:
        """Removes energy and returns what it cost, at the stored unit cost.

        Any part of the draw beyond what the ledger has tracked is priced at
        zero (see the module docstring). The ledger never goes negative.
        """
        if kwh < 0:
            msg = f"discharge cannot be negative: {kwh}"
            raise ValueError(msg)

        from_stored = min(kwh, self._stored_kwh)
        if from_stored == self._stored_kwh:
            cost = self._stored_cost
            self._stored_kwh = Decimal(0)
            self._stored_cost = Decimal(0)
        else:
            cost = from_stored * self.unit_cost
            self._stored_kwh -= from_stored
            self._stored_cost -= cost
        return cost

    def _charge(self, kwh: Decimal, cost: Decimal) -> None:
        if kwh < 0:
            msg = f"charge cannot be negative: {kwh}"
            raise ValueError(msg)
        self._stored_kwh += kwh
        self._stored_cost += cost
