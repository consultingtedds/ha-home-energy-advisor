"""Each battery's share of a pooled battery's loss (ADR-0031).

Several batteries are accounted as one pool, the way Home Assistant's Energy
Dashboard weights their levels into one state of charge: their meters add up,
their contents add up, and the loss is measured for the pool. A household with
two batteries still wants to know which of them is losing more, so each loss the
pool publishes is split across them here.

The split follows each battery's own bound since the measurement's anchor: what
its meters say went in, less what they say came out, less what its level gained.
Energy put into a battery has to be somewhere, so that is the most the battery
can have lost, and it is measured from that battery alone. A loss is shared in
proportion to those bounds and priced at the pool's cost - the only price any of
this energy has, since one ledger holds it all. What it could have earned is
shared the same way, for the same reason (HEA-229).

It is an apportionment of a measured figure, not a measurement of its own. Where
nothing has been measured since the split began - a household upgrading in the
middle of a measurement - the batteries share a loss equally rather than one of
them being blamed for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping


class BatteryMeters(NamedTuple):
    """One battery's charge and discharge meters, as its battery system holds them."""

    charge: tuple[str, ...]
    discharge: tuple[str, ...]


class BatteryLoss(NamedTuple):
    """Energy lost, what it cost, and the export it could have earned (HEA-229)."""

    kwh: Decimal
    cost: Decimal
    forgone: Decimal


class _Anchor(NamedTuple):
    """Where a battery's bound is measured from."""

    charged: Decimal
    discharged: Decimal
    level: Decimal


@dataclass
class _Battery:
    """What one battery's meters have carried, and what it has been apportioned."""

    charged: Decimal = Decimal(0)
    discharged: Decimal = Decimal(0)
    loss_kwh: Decimal = Decimal(0)
    loss_cost: Decimal = Decimal(0)
    loss_forgone: Decimal = Decimal(0)
    anchor: _Anchor | None = None


@dataclass
class BatteryShares:
    """Splits a pooled battery's published loss across the batteries in it."""

    batteries: Mapping[str, BatteryMeters]
    _state: dict[str, _Battery] = field(init=False)
    _battery_of: dict[str, tuple[str, bool]] = field(init=False)

    def __post_init__(self) -> None:
        """Index every meter by the battery it belongs to."""
        self._state = {battery: _Battery() for battery in self.batteries}
        # Which battery a meter belongs to, and whether it counts what went in.
        self._battery_of = {
            meter: (battery, is_charge)
            for battery, meters in self.batteries.items()
            for is_charge, entities in (
                (True, meters.charge),
                (False, meters.discharge),
            )
            for meter in entities
        }

    @property
    def splits(self) -> bool:
        """Whether there is anything to split: one battery is the pool itself."""
        return len(self.batteries) > 1

    @property
    def anchored(self) -> bool:
        """Whether every battery has a point its bound is measured from."""
        return bool(self._state) and all(
            battery.anchor is not None for battery in self._state.values()
        )

    def carried(self, meter: str, kwh: Decimal) -> None:
        """Count energy one of a battery's meters reported."""
        owner = self._battery_of.get(meter)
        if owner is None:
            return
        battery, is_charge = owner
        state = self._state[battery]
        if is_charge:
            state.charged += kwh
        else:
            state.discharged += kwh

    def anchor(self, levels: Mapping[str, Decimal]) -> None:
        """Start measuring each battery's bound from where it stands now."""
        for battery, state in self._state.items():
            state.anchor = _Anchor(
                charged=state.charged,
                discharged=state.discharged,
                level=levels.get(battery, Decimal(0)),
            )

    def apportion(self, loss: BatteryLoss, levels: Mapping[str, Decimal]) -> None:
        """Share a published loss, what it cost and could have earned, across them."""
        weights = {
            battery: max(Decimal(0), self._bound(state, levels.get(battery)))
            for battery, state in self._state.items()
        }
        total = sum(weights.values(), Decimal(0))
        if total <= 0:
            # Nothing measured since the split began: no battery can be said to
            # have lost more than another.
            weights = dict.fromkeys(self._state, Decimal(1))
            total = Decimal(len(weights))
        for battery, weight in weights.items():
            state = self._state[battery]
            state.loss_kwh += loss.kwh * weight / total
            state.loss_cost += loss.cost * weight / total
            state.loss_forgone += loss.forgone * weight / total

    @staticmethod
    def _bound(state: _Battery, level: Decimal | None) -> Decimal:
        """The most this battery can have lost since the anchor, from its own meters."""
        anchor = state.anchor
        if anchor is None or level is None:
            return Decimal(0)
        return (
            (state.charged - anchor.charged)
            - (state.discharged - anchor.discharged)
            - (level - anchor.level)
        )

    def losses(self) -> dict[str, BatteryLoss]:
        """Each battery's apportioned loss, where there is a split."""
        if not self.splits:
            return {}
        return {
            battery: BatteryLoss(state.loss_kwh, state.loss_cost, state.loss_forgone)
            for battery, state in self._state.items()
        }

    def forget_losses(self) -> None:
        """Rebase the published shares, as every other figure is on a reset."""
        for state in self._state.values():
            state.loss_kwh = Decimal(0)
            state.loss_cost = Decimal(0)
            state.loss_forgone = Decimal(0)

    def diagnostics(
        self, levels: Mapping[str, Decimal] | None = None
    ) -> dict[str, Any]:
        """What each battery has carried, its bound and its share, for the download."""
        return {
            battery: {
                "charged": str(state.charged),
                "discharged": str(state.discharged),
                "bound_since_anchor": (
                    None
                    if levels is None or state.anchor is None
                    else str(self._bound(state, levels.get(battery)))
                ),
                "loss_kwh": str(state.loss_kwh),
                "loss_cost": str(state.loss_cost),
                "loss_forgone": str(state.loss_forgone),
            }
            for battery, state in self._state.items()
        }

    def snapshot(self) -> dict[str, Any]:
        """Each battery's meters, anchor and share, for the trip across a restart."""
        return {
            battery: {
                "charged": str(state.charged),
                "discharged": str(state.discharged),
                "loss": [
                    str(state.loss_kwh),
                    str(state.loss_cost),
                    str(state.loss_forgone),
                ],
                "anchor": (
                    None
                    if state.anchor is None
                    else [str(part) for part in state.anchor]
                ),
            }
            for battery, state in self._state.items()
        }

    def restore(self, data: Mapping[str, Any]) -> None:
        """Reinstate what was carried; a battery the snapshot never knew is fresh."""
        for battery, state in self._state.items():
            saved = data.get(battery)
            if saved is None:
                continue
            state.charged = Decimal(saved["charged"])
            state.discharged = Decimal(saved["discharged"])
            # A share saved before HEA-229 has no forgone part: nothing was
            # published as forgone then, so it carries on from nothing.
            kwh, cost, *forgone = (Decimal(part) for part in saved["loss"])
            state.loss_kwh, state.loss_cost = kwh, cost
            state.loss_forgone = forgone[0] if forgone else Decimal(0)
            anchor = saved.get("anchor")
            state.anchor = (
                None if anchor is None else _Anchor(*(Decimal(part) for part in anchor))
            )
