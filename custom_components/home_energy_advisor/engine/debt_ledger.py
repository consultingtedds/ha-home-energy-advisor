"""Remembers energy charged before the house meters accounted for it.

Within a 5-minute bucket a device's counter and the house meter are rarely
talking about the same instant: the meter reports every few seconds, a
cycle-resetting counter every 30-90 minutes. So a bucket where tracked draw
exceeds metered consumption is ordinary, and the excess is real energy whose
meter reading has not arrived yet. It is charged at the import rate — the only
place unmetered energy can have come from — and remembered here (ADR-0014).

A later bucket where the meter runs ahead of the devices repays it. Flooring the
remainder at zero instead discards every such bucket, which rectifies a
zero-mean signal into a bias that never cancels (ADR-0015).

Repayment is where the money moves. The debt was charged on the assumption its
energy came off the grid; when the meters catch up they may say the interval was
served partly by generation, and free. The devices that overdrew are therefore
refunded the difference, rather than the remainder absorbing it — the sun
belongs to whoever used it.

A debt nobody repays is forgiven at ``expiry``. Timing noise clears within the
span a coarse step is spread over; a counter claiming more than the house ever
consumed never clears, and absorbing that forever would suppress the remainder
while hiding the fault. What is forgiven is counted, because it measures how far
a household's own meters disagree.
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
class Repayment:
    """What a surplus settled: energy withheld, and money owed back per device.

    ``kwh`` is held back from the remainder, which would otherwise publish energy
    the devices have already been credited with. A refund is negative where the
    repaying interval cost more than the import rate the debt was charged at,
    which battery discharge can do (HEA-39).
    """

    kwh: Decimal
    refunds: Mapping[str, Decimal]


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

    def repay(self, available_kwh: Decimal, unit_price: Decimal) -> Repayment:
        """Settles as much debt as ``available_kwh`` of surplus covers.

        Oldest first, so a debt cannot be starved into expiring while newer ones
        are settled around it. ``unit_price`` is what the repaying interval's own
        energy cost per kWh — the truth the debt's import-rate charge is
        reconciled against.
        """
        remaining = available_kwh
        refunds: dict[str, Decimal] = {}
        while self._tranches and remaining > 0:
            settled = self._settle(self._tranches[0], remaining, unit_price)
            for device, amount in settled.refunds.items():
                refunds[device] = refunds.get(device, Decimal(0)) + amount
            remaining -= settled.kwh
            if self._tranches[0].kwh == 0:
                self._tranches.popleft()
        return Repayment(kwh=available_kwh - remaining, refunds=refunds)

    def expire(self, before: datetime) -> Decimal:
        """Forgives debt older than the expiry, returning the energy written off."""
        forgiven = Decimal(0)
        while self._tranches and self._tranches[0].at + self._expiry <= before:
            forgiven += self._tranches.popleft().kwh
        self._forgiven += forgiven
        return forgiven

    def outstanding_kwh(self) -> Decimal:
        """Energy charged whose meter reading has still not arrived."""
        return sum((tranche.kwh for tranche in self._tranches), Decimal(0))

    def forgiven_kwh(self) -> Decimal:
        """Energy written off, measuring how far the household's meters disagree."""
        return self._forgiven

    def _settle(
        self, tranche: _Tranche, available: Decimal, unit_price: Decimal
    ) -> Repayment:
        """Takes what ``available`` covers of one tranche, refunding the difference."""
        paid = min(available, tranche.kwh)
        charged = tranche.charged * paid / tranche.kwh
        owed_back = charged - paid * unit_price
        tranche.kwh -= paid
        tranche.charged -= charged
        return Repayment(kwh=paid, refunds=_split(owed_back, tranche.debtors))


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
