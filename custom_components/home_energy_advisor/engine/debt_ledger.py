"""Remembers energy charged before the house meters accounted for it.

Within a 5-minute bucket a device's counter and the house meter are rarely
talking about the same instant: the meter reports every few seconds, a
cycle-resetting counter every 30-90 minutes. So a bucket where tracked draw
exceeds metered consumption is ordinary, and the excess is real energy whose
meter reading has not arrived yet. It is charged at the import rate - the only
place unmetered energy can have come from - and remembered here (ADR-0014).

A later bucket where the meter runs ahead of the devices repays it. Flooring the
remainder at zero instead discards every such bucket, which rectifies a
zero-mean signal into a bias that never cancels (ADR-0015).

Settlement is where the money moves - and it is the *only* place it moves. The
overdraw's cost is not published when it happens: the import rate is a guess that
the next few buckets usually overturn, and a published figure that is later taken
back shows up as an hour that cost less than nothing (HEA-85). So the charge
waits here and falls due once, at the price finally learned - the repaying
interval's own blend, which may be the sun, and the sun belongs to whoever used
it.

A debt nobody repays is forgiven at ``expiry``. Timing noise clears within the
span a coarse step is spread over; a counter claiming more than the house ever
consumed never clears, and absorbing that forever would suppress the remainder
while hiding the fault. The *energy* is written off; the money still falls due,
at the import rate, because nothing better was ever learned about it. What is
forgiven is counted, because it measures how far a household's own meters
disagree.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime, timedelta


@dataclass(frozen=True)
class Settlement:
    """A debt coming due: energy withheld, and the money now payable per device.

    ``kwh`` is held back from the remainder, which would otherwise publish energy
    the devices have already been credited with.

    ``actual`` is what the energy really cost, known only now - the repaying
    interval's own blend, or the import rate if the debt expired without one.
    ``naive`` is its counterfactual, always the import rate the debt was recorded
    at, because buying it off the meter is what the household was spared.

    The two are separate rather than one net figure so that Cost Savings moves by
    exactly their difference: zero on expiry, and the real saving when the sun
    turned out to have served it.
    """

    kwh: Decimal
    actual: Mapping[str, Decimal]
    naive: Mapping[str, Decimal]


@dataclass
class _Tranche:
    """One bucket's overdraw: what it was, what it cost, and who drew it."""

    at: datetime
    kwh: Decimal
    charged: Decimal
    debtors: Mapping[str, Decimal]


class DebtLedger:
    """Energy charged ahead of its meter reading, and the refunds settling it."""

    def __init__(self, expiry: timedelta) -> None:
        self._expiry = expiry
        self._tranches: deque[_Tranche] = deque()
        self._forgiven = Decimal(0)

    def owe(
        self,
        at: datetime,
        kwh: Decimal,
        charged: Decimal,
        debtors: Mapping[str, Decimal],
    ) -> None:
        """Records an overdraw, charged at the import rate, against its drawers.

        ``debtors`` maps each device to the draw it claimed in the bucket; shares
        rather than absolute amounts are what a refund is split by, so it need
        not sum to ``kwh``.
        """
        if kwh <= 0:
            return
        self._tranches.append(
            _Tranche(at=at, kwh=kwh, charged=charged, debtors=dict(debtors))
        )

    def repay(self, available_kwh: Decimal, unit_price: Decimal) -> Settlement:
        """Settles as much debt as ``available_kwh`` of surplus covers.

        Oldest first, so a debt cannot be starved into expiring while newer ones
        are settled around it. ``unit_price`` is what the repaying interval's own
        energy cost per kWh - the price the suspended charge was always waiting
        for.
        """
        remaining = available_kwh
        actual: dict[str, Decimal] = {}
        naive: dict[str, Decimal] = {}
        while self._tranches and remaining > 0:
            settled = self._settle(self._tranches[0], remaining, unit_price)
            _merge(actual, settled.actual)
            _merge(naive, settled.naive)
            remaining -= settled.kwh
            if self._tranches[0].kwh == 0:
                self._tranches.popleft()
        return Settlement(kwh=available_kwh - remaining, actual=actual, naive=naive)

    def expire(self, before: datetime) -> Settlement:
        """Forgives debt older than the expiry, charging it at the import rate.

        The energy is written off - the meters never accounted for it, so it can
        no longer be reconciled - but the money is not. Nothing better than the
        import rate was ever learned about it, which is exactly what ADR-0014
        priced it at, so that is what it finally costs. The counterfactual matches,
        leaving no saving: the household was spared nothing.
        """
        forgiven = Decimal(0)
        actual: dict[str, Decimal] = {}
        naive: dict[str, Decimal] = {}
        while self._tranches and self._tranches[0].at + self._expiry <= before:
            tranche = self._tranches.popleft()
            forgiven += tranche.kwh
            due = _split(tranche.charged, tranche.debtors)
            _merge(actual, due)
            _merge(naive, due)
        self._forgiven += forgiven
        return Settlement(kwh=forgiven, actual=actual, naive=naive)

    def outstanding_kwh(self) -> Decimal:
        """Energy charged whose meter reading has still not arrived."""
        return sum((tranche.kwh for tranche in self._tranches), Decimal(0))

    def forgiven_kwh(self) -> Decimal:
        """Energy written off, measuring how far the household's meters disagree."""
        return self._forgiven

    def _settle(
        self, tranche: _Tranche, available: Decimal, unit_price: Decimal
    ) -> Settlement:
        """Takes what ``available`` covers of one tranche, at the price now known."""
        paid = min(available, tranche.kwh)
        # What this portion was recorded as being worth at the import rate: the
        # counterfactual, and what it will cost if the rest of it ever expires.
        recorded = tranche.charged * paid / tranche.kwh
        tranche.kwh -= paid
        tranche.charged -= recorded
        return Settlement(
            kwh=paid,
            actual=_split(paid * unit_price, tranche.debtors),
            naive=_split(recorded, tranche.debtors),
        )


def _merge(into: dict[str, Decimal], amounts: Mapping[str, Decimal]) -> None:
    """Adds one settlement's per-device amounts into a running total."""
    for device, amount in amounts.items():
        into[device] = into.get(device, Decimal(0)) + amount


def _split(amount: Decimal, debtors: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Shares an amount across devices by their draw, residue to the largest.

    The residue matters: a refund that does not sum back to what was charged
    leaves the period reconciling to the wrong figure, which is the defect this
    whole mechanism exists to remove.
    """
    total = sum(debtors.values(), Decimal(0))
    if total <= 0:
        return {}
    shares = {device: amount * drawn / total for device, drawn in debtors.items()}
    residue = amount - sum(shares.values(), Decimal(0))
    if residue != 0:
        largest = max(debtors, key=lambda device: debtors[device])
        shares[largest] += residue
    return shares
