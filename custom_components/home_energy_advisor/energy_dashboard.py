"""What the Energy Dashboard holds of the house, and what differs here (ADR-0030).

The house inputs are this integration's own, prefilled from the Energy Dashboard
and never followed. The Energy Dashboard is still the place a household is
encouraged to enter them, so a change there is noticed and offered: a Repair
lists what differs, and the household takes the Energy Dashboard's or keeps
their own. Nothing is applied without that answer, because a household may keep
better meters here on purpose.

Batteries are compared here (HEA-220). Each role is compared on its own and
listed on its own, so the grid meters join as another role (HEA-221).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_ENERGY_DASHBOARD_ANSWERED,
    SUBENTRY_TYPE_BATTERY,
)
from .house_inputs import Battery, batteries_of, battery_from
from .issues import (
    ISSUE_ENERGY_DASHBOARD_CHANGED,
    async_ask,
    async_clear,
    energy_dashboard_changed_issue_id,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_energy_prefs(hass: HomeAssistant) -> Any:  # noqa: ANN401 - untyped HA prefs
    """The Energy Dashboard's preferences, or ``None`` where it has none.

    Best-effort, as every read of them is: a household with no Energy Dashboard
    is ordinary, and nothing here is a precondition for the figures.
    """
    try:
        manager = await async_get_manager(hass)
    except Exception:  # noqa: BLE001 - optional; it must never block anything
        return None
    return manager.data


def batteries_in(prefs: Any) -> list[dict[str, Any]]:  # noqa: ANN401 - untyped HA prefs
    """The Energy Dashboard's battery systems, each as a battery entry would hold it.

    Only those with both meters: a battery system always has both, and one
    without is not something this integration could count.
    """
    sources: Any = (prefs or {}).get("energy_sources", [])
    systems = [
        source
        for source in sources
        if source.get("type") == "battery"
        and source.get("stat_energy_to")
        and source.get("stat_energy_from")
    ]
    return [
        battery_answers(source, position)
        for position, source in enumerate(systems, start=1)
    ]


def battery_answers(
    source: Any,  # noqa: ANN401 - untyped Energy Dashboard preference structure
    position: int,
) -> dict[str, Any]:
    """One battery system's fields, under the names a battery entry uses."""
    answers: dict[str, Any] = {
        # Its own name where the Energy Dashboard has one; otherwise numbered,
        # the first simply "Battery", which is what a one-battery house expects.
        CONF_NAME: source.get("name")
        or ("Battery" if position == 1 else f"Battery {position}"),
        CONF_BATTERY_CHARGE_ENTITY: source["stat_energy_to"],
        CONF_BATTERY_DISCHARGE_ENTITY: source["stat_energy_from"],
    }
    if level := source.get("stat_soc"):
        answers[CONF_BATTERY_SOC_ENTITY] = level
    if (capacity := source.get("capacity")) is not None:
        answers[CONF_BATTERY_CAPACITY_KWH] = capacity
    return answers


def answered(prefs: Any) -> list[list[str | None]]:  # noqa: ANN401 - untyped HA prefs
    """The Energy Dashboard's house as it is remembered once answered for.

    Only what is compared, so renaming a battery there is not a change to ask
    about. JSON-shaped, because it is kept in the entry's data.
    """
    return [
        list(_compared(battery_from("", answers))) for answers in batteries_in(prefs)
    ]


@dataclass(frozen=True)
class Differences:
    """What the Energy Dashboard holds that is not entered here, and the reverse."""

    theirs: tuple[dict[str, Any], ...]
    ours: tuple[str, ...]

    def __bool__(self) -> bool:
        """Whether there is anything to ask about."""
        return bool(self.theirs or self.ours)


def differences_from(prefs: Any, entry: ConfigEntry) -> Differences:  # noqa: ANN401
    """Every battery held on only one side, or held differently on the two.

    Matched by meters, which is what makes a battery the same battery. A level
    and capacity in the Energy Dashboard are compared too, since that is where a
    household is told to add them; where the Energy Dashboard holds neither,
    a level entered here is not a difference, because there is nothing to take.

    An Energy Dashboard with no batteries asks nothing: there is nothing in it
    to take, and offering to remove every battery entered here would be a
    question no household needs.
    """
    offered = batteries_in(prefs)
    if not offered:
        return Differences(theirs=(), ours=())
    ours = batteries_of(entry)
    matched: set[str] = set()
    theirs: list[dict[str, Any]] = []
    for answers in offered:
        match = next(
            (
                battery_id
                for battery_id, battery in ours.items()
                if battery_id not in matched and _holds(battery, answers)
            ),
            None,
        )
        if match is None:
            theirs.append(answers)
        else:
            matched.add(match)
    return Differences(
        theirs=tuple(theirs),
        ours=tuple(battery_id for battery_id in ours if battery_id not in matched),
    )


def _holds(battery: Battery, answers: Mapping[str, Any]) -> bool:
    """Whether a battery entered here is the Energy Dashboard's, as it holds it."""
    offered = battery_from("", answers)
    if (battery.charge, battery.discharge) != (offered.charge, offered.discharge):
        return False
    if not offered.knows_its_contents:
        return True
    return (battery.level, battery.capacity) == (offered.level, offered.capacity)


def _compared(battery: Battery) -> tuple[str | None, ...]:
    """A battery as it is compared: its meters, and its contents where known."""
    contents = (
        (battery.level, str(battery.capacity))
        if battery.knows_its_contents
        else (None, None)
    )
    return (battery.charge, battery.discharge, *contents)


def taken(answers: Mapping[str, Any]) -> dict[str, Any]:
    """An Energy Dashboard battery as it is taken.

    A level without a capacity is left behind. The Energy Dashboard holds the
    two apart, and a percentage this integration cannot turn into kWh would be
    refused on the form (HEA-178); taken without it, the battery is still
    counted, and adding the capacity there brings the level with it.
    """
    if answers.get(CONF_BATTERY_CAPACITY_KWH) is not None:
        return dict(answers)
    return {
        key: value for key, value in answers.items() if key != CONF_BATTERY_SOC_ENTITY
    }


def async_check(hass: HomeAssistant, entry: ConfigEntry, prefs: Any) -> None:  # noqa: ANN401
    """Ask about the Energy Dashboard's house where it differs from what is here.

    Not asked again once answered: the Energy Dashboard as it stood when the
    household kept their own is remembered, and only a further change there
    raises the question once more. Setup remembers it too, since choosing which
    of its batteries to take is that same answer.
    """
    issue_id = energy_dashboard_changed_issue_id(entry.entry_id)
    found = differences_from(prefs, entry)
    if not found or entry.data.get(CONF_ENERGY_DASHBOARD_ANSWERED) == answered(prefs):
        async_clear(hass, issue_id)
        return
    ours = batteries_of(entry)
    async_ask(
        hass,
        issue_id,
        ISSUE_ENERGY_DASHBOARD_CHANGED,
        placeholders=listed_differences(found, ours),
        fix_data={"entry_id": entry.entry_id},
    )


def listed_differences(
    found: Differences, ours: Mapping[str, Battery]
) -> dict[str, str]:
    """Each side's batteries as lines a Repair can show.

    Only names, entity ids and capacities, which read the same in every
    language, so nothing here needs translating.
    """
    return {
        "theirs": _lines(battery_from(a[CONF_NAME], a) for a in found.theirs),
        "ours": _lines(ours[battery_id] for battery_id in found.ours),
    }


def _lines(batteries: Iterable[Battery]) -> str:
    lines = [
        f"- {battery.name}: "
        + ", ".join(
            part
            for part in (
                battery.charge,
                battery.discharge,
                battery.level,
                f"{battery.capacity} kWh" if battery.capacity is not None else None,
            )
            if part
        )
        for battery in batteries
    ]
    return "\n".join(lines) or "-"


def async_take(hass: HomeAssistant, entry: ConfigEntry, prefs: Any) -> None:  # noqa: ANN401
    """Make the batteries entered here the Energy Dashboard's, as an edit would.

    A battery held on both sides with the same meters keeps its entry and its
    name, and takes the Energy Dashboard's level and capacity, so its figures
    carry on. One only in the Energy Dashboard is added, and one only here is
    removed.
    """
    found = differences_from(prefs, entry)
    left = list(found.ours)
    for answers in (taken(answers) for answers in found.theirs):
        same = next(
            (
                battery_id
                for battery_id in left
                if _same_meters(entry.subentries[battery_id].data, answers)
            ),
            None,
        )
        if same is None:
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(answers),
                    subentry_type=SUBENTRY_TYPE_BATTERY,
                    title=answers[CONF_NAME],
                    unique_id=None,
                ),
            )
            continue
        left.remove(same)
        subentry = entry.subentries[same]
        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data={**answers, CONF_NAME: subentry.data.get(CONF_NAME, subentry.title)},
        )
    for battery_id in left:
        hass.config_entries.async_remove_subentry(entry, battery_id)
    async_keep(hass, entry, prefs)


def _same_meters(data: Mapping[str, Any], answers: Mapping[str, Any]) -> bool:
    return all(
        data.get(key) == answers[key]
        for key in (CONF_BATTERY_CHARGE_ENTITY, CONF_BATTERY_DISCHARGE_ENTITY)
    )


def async_keep(hass: HomeAssistant, entry: ConfigEntry, prefs: Any) -> None:  # noqa: ANN401
    """Remember the Energy Dashboard as it stands, so it is not offered again."""
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_ENERGY_DASHBOARD_ANSWERED: answered(prefs)}
    )
    async_clear(hass, energy_dashboard_changed_issue_id(entry.entry_id))
