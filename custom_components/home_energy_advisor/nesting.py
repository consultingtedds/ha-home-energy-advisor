"""Which tracked device sits inside which, per the Energy Dashboard (HEA-168).

A `device_consumption` entry carries `included_in_stat`: the statistic id of the
device whose total already contains this one. For an entity-backed sensor a
statistic id *is* the entity id, which is what lets it be matched to our own
devices at all.

The nesting is applied only where both ends are a device we track **from the
very entity the Energy Dashboard names**. Netting a child against its parent
moves the child's energy out of the parent's counter, and that is only right
when the two counters are the ones the household declared contain each other.

Every other pair is skipped, which leaves the child counted on its own as well
as inside its parent - so each skip is recorded with its reason, for the
diagnostics download (HEA-271). A household asking "is my nesting honoured" can
otherwise not tell.

One skip is worth more than a line in a file. Where the Energy Dashboard names a
different sensor of a Home Assistant device we do track - its power-derived
energy, a yearly counter beside a lifetime one - the household can fix it in a
minute, and nothing else would ever tell them their figures double count.
:attr:`Nesting.misread` names those, for a Repair. They are matched through the
Home Assistant device rather than netted outright, because one device can carry
several meters (a two-channel relay is one device), and guessing which channel
the Energy Dashboard meant would be netting on a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import Any


class SkipReason(StrEnum):
    """Why an Energy Dashboard pair was not applied."""

    # Neither the device's entity nor its Home Assistant device is one we track.
    NOT_TRACKED = "not_tracked"
    # As above, for the device it is declared inside.
    PARENT_NOT_TRACKED = "parent_not_tracked"
    # Both ends are one of our devices. Nothing in Home Assistant forbids it
    # through the websocket API, and netting a device against itself would
    # erase it.
    INSIDE_ITSELF = "inside_itself"
    # Both ends are our devices, but at least one is named by a sensor other
    # than the one we read.
    ANOTHER_SENSOR = "another_sensor"


@dataclass(frozen=True)
class SkippedPair:
    """An Energy Dashboard pair left unapplied, as the dashboard names it."""

    entity: str
    inside: str
    reason: SkipReason
    # The subentry ids of the devices each end was matched to, where it was.
    device: str | None
    parent: str | None


@dataclass(frozen=True)
class Nesting:
    """The nesting in force, and what the Energy Dashboard asked for besides."""

    # Child subentry id to parent subentry id, as handed to the engine.
    applied: dict[str, str] = field(default_factory=dict)
    skipped: tuple[SkippedPair, ...] = ()
    # Subentry id to the sensor the Energy Dashboard names it by, where that is
    # not the one we read and a pair is skipped because of it.
    misread: dict[str, str] = field(default_factory=dict)


def nesting_of(
    prefs: Any,  # noqa: ANN401 - untyped Energy Dashboard preference structure
    device_of_entity: Mapping[str, str],
    owner_of: Callable[[str], str | None],
) -> Nesting:
    """Read the Energy Dashboard's nesting against the devices we track.

    `device_of_entity` maps each entity we read to its device's subentry id.
    `owner_of` answers, for any other entity, the one tracked device sharing its
    Home Assistant device, or None where there is none or more than one.
    """
    applied: dict[str, str] = {}
    skipped: list[SkippedPair] = []
    misread: dict[str, str] = {}

    def match(entity: str) -> str | None:
        return device_of_entity.get(entity) or owner_of(entity)

    for entry in prefs.get("device_consumption", []) if prefs else []:
        inside = entry.get("included_in_stat")
        if not inside:
            continue
        entity = entry.get("stat_consumption", "")
        child, parent = match(entity), match(inside)
        if child is not None and parent is not None and child != parent:
            if entity in device_of_entity and inside in device_of_entity:
                applied[child] = parent
                continue
            misread.update(
                (sub_id, named)
                for sub_id, named in ((child, entity), (parent, inside))
                if named not in device_of_entity
            )
        skipped.append(
            SkippedPair(entity, inside, _reason(child, parent), child, parent)
        )
    return Nesting(applied, tuple(skipped), misread)


def _reason(child: str | None, parent: str | None) -> SkipReason:
    if child is None:
        return SkipReason.NOT_TRACKED
    if parent is None:
        return SkipReason.PARENT_NOT_TRACKED
    if child == parent:
        return SkipReason.INSIDE_ITSELF
    return SkipReason.ANOTHER_SENSOR
