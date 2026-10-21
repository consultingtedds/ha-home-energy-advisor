"""What the Energy Dashboard holds of the house, and what differs here (ADR-0030).

The house inputs are this integration's own, prefilled from the Energy Dashboard
and never followed. The Energy Dashboard is still the place a household is
encouraged to enter them, so a change there is noticed and offered: a Repair
lists what differs, and the household takes the Energy Dashboard's or keeps
their own. Nothing is applied without that answer, because a household may keep
better meters here on purpose.

Batteries (HEA-220) and grid meters (HEA-221) are compared here, each on its own
and listed together.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from homeassistant.components.energy.data import async_get_manager
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.helpers import translation

from .const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_ENERGY_DASHBOARD_ANSWERED,
    CONF_FIXED_PRICE,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_GRID,
)
from .discovery import source_unit
from .house_inputs import (
    Battery,
    GridMeter,
    batteries_of,
    battery_from,
    grid_meter_from,
    grid_meters_of,
)
from .issues import (
    ISSUE_ENERGY_DASHBOARD_CHANGED,
    async_ask,
    async_clear,
    energy_dashboard_changed_issue_id,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# The two sides of the house remembered once answered for, as keys of the answer.
_BATTERIES = "batteries"
_GRID = "grid"


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


def grid_meters_in(hass: HomeAssistant, prefs: Any) -> list[dict[str, Any]]:  # noqa: ANN401 - untyped HA prefs
    """The Energy Dashboard's grid sources, each as a grid entry would hold it.

    Only those whose import meter is an energy counter in kWh or Wh. A grid
    source can carry a fee instead - a daily standing charge declared as a
    "meter" so that it can be priced - and the figures are the cost of the
    energy used, not the bill, so a fee has no place in them (ADR-0032). The
    unit is what tells them apart, whatever either is called.
    """
    sources: Any = (prefs or {}).get("energy_sources", [])
    grids = [
        answers
        for source in sources
        if source.get("type") == "grid"
        and (answers := _grid_answers(source)) is not None
        and _counts_energy(hass, answers[CONF_GRID_IMPORT_ENTITY])
    ]
    for position, answers in enumerate(grids, start=1):
        # Numbered, the first simply "Grid", which is what a one-meter house
        # expects. The Energy Dashboard gives a grid source no name.
        answers[CONF_NAME] = "Grid" if position == 1 else f"Grid {position}"
    return grids


def priced(answers: Mapping[str, Any]) -> bool:
    """Whether an Energy Dashboard grid source carries a price to take with it.

    One tracked as a cost statistic rather than a rate carries none, which is an
    ordinary configuration; it is entered by hand with a price instead, and is
    not something a Repair could take.
    """
    return bool(answers.get(CONF_PRICE_ENTITY)) or (
        answers.get(CONF_FIXED_PRICE) is not None
    )


def _priced_grid_meters_in(hass: HomeAssistant, prefs: Any) -> list[dict[str, Any]]:  # noqa: ANN401 - untyped HA prefs
    return [grid for grid in grid_meters_in(hass, prefs) if priced(grid)]


def _grid_answers(source: Any) -> dict[str, Any] | None:  # noqa: ANN401 - untyped Energy Dashboard preference structure
    """One grid source's import meter, its price and its export meter.

    Read by shape, never by falling back from one to the other: from 2026.9 the
    flows sit on the source, before that in `flow_from`/`flow_to` lists, and the
    prices are named differently in the two (HEA-117, HEA-209). The import price
    is taken from the flow its meter came from, so one source's tariff is never
    paired with another's meter (HEA-118).

    ``None`` where the source meters no import.
    """
    imports = source.get("flow_from")
    exports = source.get("flow_to")
    flow = imports[0] if imports else source
    if not (meter := flow.get("stat_energy_from")):
        return None
    answers: dict[str, Any] = {CONF_GRID_IMPORT_ENTITY: meter}
    if price := flow.get("entity_energy_price"):
        answers[CONF_PRICE_ENTITY] = price
    elif (number := flow.get("number_energy_price")) is not None:
        answers[CONF_FIXED_PRICE] = number
    if exported := (
        exports[0].get("stat_energy_to") if exports else source.get("stat_energy_to")
    ):
        answers[CONF_GRID_EXPORT_ENTITY] = exported
    return answers


def _counts_energy(hass: HomeAssistant, entity_id: str) -> bool:
    unit = source_unit(hass, entity_id)
    return unit is not None and unit.strip().lower() in {"kwh", "wh"}


def answered(hass: HomeAssistant, prefs: Any) -> dict[str, list[list[str | None]]]:  # noqa: ANN401 - untyped HA prefs
    """The Energy Dashboard's house as it is remembered once answered for.

    Only what is compared, so renaming a battery there is not a change to ask
    about. JSON-shaped, because it is kept in the entry's data.
    """
    return {
        _BATTERIES: [
            list(_compared(battery_from("", answers)))
            for answers in batteries_in(prefs)
        ],
        _GRID: [
            list(_grid_compared(grid_meter_from("", answers)))
            for answers in _priced_grid_meters_in(hass, prefs)
        ],
    }


def _remembered(stored: Any) -> dict[str, Any]:  # noqa: ANN401 - entry data
    """What was answered for, as it is held now.

    The batteries alone before the grid meters were compared, so a list is
    what they were remembered as.
    """
    if isinstance(stored, list):
        return {_BATTERIES: stored}
    return dict(stored or {})


@dataclass(frozen=True)
class Differences:
    """What the Energy Dashboard holds that is not entered here, and the reverse.

    Batteries and grid meters apart, each matched on its own terms.
    """

    theirs: tuple[dict[str, Any], ...]
    ours: tuple[str, ...]
    grid_theirs: tuple[dict[str, Any], ...] = ()
    grid_ours: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        """Whether there is anything to ask about."""
        return bool(self.theirs or self.ours or self.grid_theirs or self.grid_ours)


def differences_from(
    hass: HomeAssistant,
    prefs: Any,  # noqa: ANN401 - untyped HA prefs
    entry: ConfigEntry,
) -> Differences:
    """Every battery and grid meter held on only one side, or held differently.

    A battery is matched by its meters, which is what makes it the same
    battery. A level and capacity in the Energy Dashboard are compared too,
    since that is where a household is told to add them; where the Energy
    Dashboard holds neither, a level entered here is not a difference, because
    there is nothing to take.

    A grid meter is matched by its import meter, price and export meter
    together, since a register priced differently is a different answer.

    An Energy Dashboard with none of one kind asks nothing about that kind:
    there is nothing in it to take, and offering to remove everything entered
    here would be a question no household needs.
    """
    theirs, ours = _unmatched(batteries_in(prefs), batteries_of(entry), _holds)
    grid_theirs, grid_ours = _unmatched(
        _priced_grid_meters_in(hass, prefs), grid_meters_of(entry), _grid_holds
    )
    return Differences(
        theirs=theirs, ours=ours, grid_theirs=grid_theirs, grid_ours=grid_ours
    )


def _unmatched[T](
    offered: list[dict[str, Any]],
    ours: Mapping[str, T],
    holds: Callable[[T, Mapping[str, Any]], bool],
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    if not offered:
        return (), ()
    matched: set[str] = set()
    theirs: list[dict[str, Any]] = []
    for answers in offered:
        match = next(
            (
                entry_id
                for entry_id, held in ours.items()
                if entry_id not in matched and holds(held, answers)
            ),
            None,
        )
        if match is None:
            theirs.append(answers)
        else:
            matched.add(match)
    return tuple(theirs), tuple(
        entry_id for entry_id in ours if entry_id not in matched
    )


def _holds(battery: Battery, answers: Mapping[str, Any]) -> bool:
    """Whether a battery entered here is the Energy Dashboard's, as it holds it."""
    offered = battery_from("", answers)
    if (battery.charge, battery.discharge) != (offered.charge, offered.discharge):
        return False
    if not offered.knows_its_contents:
        return True
    return (battery.level, battery.capacity) == (offered.level, offered.capacity)


def _grid_holds(grid: GridMeter, answers: Mapping[str, Any]) -> bool:
    """Whether a grid meter entered here is the Energy Dashboard's, as it holds it."""
    return _grid_compared(grid) == _grid_compared(grid_meter_from("", answers))


def _compared(battery: Battery) -> tuple[str | None, ...]:
    """A battery as it is compared: its meters, and its contents where known."""
    contents = (
        (battery.level, str(battery.capacity))
        if battery.knows_its_contents
        else (None, None)
    )
    return (battery.charge, battery.discharge, *contents)


def _grid_compared(grid: GridMeter) -> tuple[str | None, ...]:
    """A grid meter as it is compared: its meters and what prices its import."""
    fixed = None if grid.fixed_price is None else str(grid.fixed_price)
    return (grid.imported, grid.price_entity, fixed, grid.exported)


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


async def async_check(hass: HomeAssistant, entry: ConfigEntry, prefs: Any) -> None:  # noqa: ANN401
    """Ask about the Energy Dashboard's house where it differs from what is here.

    Not asked again once answered: the Energy Dashboard as it stood when the
    household kept their own is remembered, and only a further change there
    raises the question once more. Setup remembers it too, since choosing which
    of its batteries and grid meters to take is that same answer.

    An answer given before grid meters were compared counts for the grid as the
    Energy Dashboard holds it now. Every such household chose its grid meter at
    setup, and nothing in the Energy Dashboard has changed to ask about.
    """
    issue_id = energy_dashboard_changed_issue_id(entry.entry_id)
    current = answered(hass, prefs)
    remembered = _remembered(entry.data.get(CONF_ENERGY_DASHBOARD_ANSWERED))
    if _GRID not in remembered:
        remembered[_GRID] = current[_GRID]
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ENERGY_DASHBOARD_ANSWERED: remembered}
        )
    found = differences_from(hass, prefs, entry)
    if not found or remembered == current:
        async_clear(hass, issue_id)
        return
    async_ask(
        hass,
        issue_id,
        ISSUE_ENERGY_DASHBOARD_CHANGED,
        placeholders=await async_listed_differences(hass, found, entry),
        fix_data={"entry_id": entry.entry_id},
    )


async def async_listed_differences(
    hass: HomeAssistant, found: Differences, entry: ConfigEntry
) -> dict[str, str]:
    """Each side's batteries and grid meters as lines a Repair can show.

    The Energy Dashboard's batteries are listed as they will be taken, not as it
    holds them: a level without a capacity is left behind (`taken`), and listing
    it promised what taking it did not do (HEA-236). Where one is left behind the
    line says so, in the household's language; everything else is names, entity
    ids, prices and capacities, which read the same in every language.
    """
    left_out = await _left_out_note(hass)
    batteries = batteries_of(entry)
    grids = grid_meters_of(entry)
    return {
        "theirs": _lines(
            [
                *(
                    _battery_line(battery_from(a[CONF_NAME], taken(a)))
                    + (f" ({left_out})" if _level_left_behind(a) else "")
                    for a in found.theirs
                ),
                *(
                    _grid_line(grid_meter_from(a[CONF_NAME], a))
                    for a in found.grid_theirs
                ),
            ]
        ),
        "ours": _lines(
            [
                *(_battery_line(batteries[battery_id]) for battery_id in found.ours),
                *(_grid_line(grids[grid_id]) for grid_id in found.grid_ours),
            ]
        ),
    }


def _level_left_behind(answers: Mapping[str, Any]) -> bool:
    return bool(answers.get(CONF_BATTERY_SOC_ENTITY)) and (
        CONF_BATTERY_SOC_ENTITY not in taken(answers)
    )


async def _left_out_note(hass: HomeAssistant) -> str:
    """The note on a battery whose level is left behind, translated."""
    strings = await translation.async_get_translations(
        hass, hass.config.language, "common", {DOMAIN}
    )
    return strings.get(
        f"component.{DOMAIN}.common.repair_level_left_out",
        "level left out: add its capacity",
    )


def _lines(lines: Iterable[str]) -> str:
    return "\n".join(lines) or "-"


def _battery_line(battery: Battery) -> str:
    return _line(
        battery.name,
        battery.charge,
        battery.discharge,
        battery.level,
        f"{battery.capacity} kWh" if battery.capacity is not None else None,
    )


def _grid_line(grid: GridMeter) -> str:
    return _line(
        grid.name,
        grid.imported,
        grid.price_entity
        or (None if grid.fixed_price is None else str(grid.fixed_price)),
        grid.exported,
    )


def _line(name: str, *parts: str | None) -> str:
    return f"- {name}: " + ", ".join(part for part in parts if part)


def async_take(hass: HomeAssistant, entry: ConfigEntry, prefs: Any) -> None:  # noqa: ANN401
    """Make the batteries and grid meters entered here the Energy Dashboard's.

    As an edit would. One held on both sides with the same meters keeps its
    entry and its name, and takes the Energy Dashboard's other answers, so its
    figures carry on. One only in the Energy Dashboard is added, and one only
    here is removed.
    """
    found = differences_from(hass, prefs, entry)
    _replace(
        hass,
        entry,
        subentry_type=SUBENTRY_TYPE_BATTERY,
        theirs=[taken(answers) for answers in found.theirs],
        left=list(found.ours),
        meters=(CONF_BATTERY_CHARGE_ENTITY, CONF_BATTERY_DISCHARGE_ENTITY),
    )
    _replace(
        hass,
        entry,
        subentry_type=SUBENTRY_TYPE_GRID,
        theirs=[dict(answers) for answers in found.grid_theirs],
        left=list(found.grid_ours),
        meters=(CONF_GRID_IMPORT_ENTITY,),
    )
    async_keep(hass, entry, prefs)


def _replace(  # noqa: PLR0913 - each argument is one side of the replacement
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    subentry_type: str,
    theirs: list[dict[str, Any]],
    left: list[str],
    meters: tuple[str, ...],
) -> None:
    """Put the Energy Dashboard's in place of ours, keeping what matches by meter."""
    for answers in theirs:
        same = next(
            (
                entry_id
                for entry_id in left
                if all(
                    entry.subentries[entry_id].data.get(key) == answers[key]
                    for key in meters
                )
            ),
            None,
        )
        if same is None:
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(answers),
                    subentry_type=subentry_type,
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
    for entry_id in left:
        hass.config_entries.async_remove_subentry(entry, entry_id)


def async_keep(hass: HomeAssistant, entry: ConfigEntry, prefs: Any) -> None:  # noqa: ANN401
    """Remember the Energy Dashboard as it stands, so it is not offered again."""
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_ENERGY_DASHBOARD_ANSWERED: answered(hass, prefs)},
    )
    async_clear(hass, energy_dashboard_changed_issue_id(entry.entry_id))
