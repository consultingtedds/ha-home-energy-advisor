"""An hour no home could use in a meter's statistics, raised as a Repair (ADR-0045).

Driven through the real recorder, issue registry and Repairs flow manager: the
statistics are imported as Home Assistant keeps them, and the correction is the
recorder's own adjustment, read back afterwards.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.recorder.db_schema import StatisticsShortTerm
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    statistics_during_period,
)
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.recorder import get_instance
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.home_energy_advisor import impossible_hours
from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_GRID,
)
from custom_components.home_energy_advisor.energy_dashboard import dashboard_money

if TYPE_CHECKING:
    from typing import Literal

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

LOCAL = ZoneInfo("Europe/Madrid")
METER = "sensor.grid_import"
# The faulty hour: 20:00 on Wednesday 14 October 2026, local time.
FAULT = datetime(2026, 10, 14, 20, tzinfo=LOCAL)
# What the meter recorded at 20:00 on each of the seven days either side.
EVENINGS = [0.2, 0.6, 1.4, 0.5, 0.8, 0.3, 0.7, 0.9, 0.4, 1.1, 0.6, 0.5, 0.2, 1.0]
# Every other hour of the fortnight.
ORDINARY_HOUR = 0.25

_GRID = {
    CONF_NAME: "Grid",
    CONF_GRID_IMPORT_ENTITY: METER,
    CONF_GRID_EXPORT_ENTITY: "sensor.grid_export",
    CONF_FIXED_PRICE: 0.2,
}


def _house() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_GRID,
                title="Grid",
                data=_GRID,
                unique_id=None,
            )
        ],
    )


def _fortnight(
    fault_kwh: float | None, evenings: list[float] = EVENINGS
) -> list[tuple[datetime, float]]:
    """Each hour of the fortnight around the fault, and what the meter recorded.

    Each evening at 20:00 records the next of `evenings`, every other hour
    `ORDINARY_HOUR`, and the faulty hour `fault_kwh`.
    """
    first = FAULT - timedelta(days=7, hours=20)
    evening = iter(evenings)
    hours = []
    for index in range(15 * 24):
        start = first + timedelta(hours=index)
        if start == FAULT:
            change = fault_kwh if fault_kwh is not None else ORDINARY_HOUR
        elif start.hour == FAULT.hour:
            change = next(evening, ORDINARY_HOUR)
        else:
            change = ORDINARY_HOUR
        hours.append((start, change))
    return hours


def _record_fortnight(
    hass: HomeAssistant,
    fault_kwh: float | None,
    *,
    fault_reading: float | None = None,
    evenings: list[float] = EVENINGS,
    statistic_id: str = METER,
) -> None:
    """A fortnight of a meter's hourly statistics around the fault.

    `fault_reading` is the meter's own reading at the end of the faulty hour,
    where it differs from the running total, as when a sensor read zero and
    came back.
    """
    total = 1000.0
    rows = []
    for start, change in _fortnight(fault_kwh, evenings):
        total += change
        state = fault_reading if start == FAULT and fault_reading else total
        rows.append(StatisticData(start=start.astimezone(UTC), state=state, sum=total))
    async_import_statistics(hass, _metadata(statistic_id), rows)


# What the import was charged: evenings dearer than the rest of the day.
EVENING_PRICE = 0.3
DAY_PRICE = 0.2
COST = "sensor.grid_import_cost"


def _record_cost(hass: HomeAssistant, fault_kwh: float) -> None:
    """The Energy Dashboard's cost of the same fortnight, its fault priced too.

    A glitch is priced at the hour's real price, as Home Assistant's cost sensor
    prices whatever the meter reports.
    """
    total = 0.0
    rows = []
    for start, change in _fortnight(fault_kwh):
        price = EVENING_PRICE if start.hour == FAULT.hour else DAY_PRICE
        total += change * price
        rows.append(StatisticData(start=start.astimezone(UTC), state=total, sum=total))
    metadata = StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=None,
        source="recorder",
        statistic_id=COST,
        unit_class=None,
        unit_of_measurement="EUR",
    )
    async_import_statistics(hass, metadata, rows)


async def _energy_dashboard(hass: HomeAssistant, *sources: dict[str, Any]) -> None:
    """Save the Energy Dashboard's sources, as its own editor does."""
    manager = await async_get_manager(hass)
    update: Any = {"energy_sources": [dict(source) for source in sources]}
    await manager.async_update(update)
    await hass.async_block_till_done()


# The Energy Dashboard's grid source, its import priced by a cost statistic.
_PRICED_GRID = {
    "type": "grid",
    "stat_energy_from": METER,
    "stat_energy_to": "sensor.grid_export",
    "stat_cost": COST,
}


def _record_five_minutes(hass: HomeAssistant, windows: dict[int, float]) -> None:
    """The faulty hour's five-minute statistics: each window's change by minute."""
    total = 1000.0
    rows = [
        StatisticData(
            start=(FAULT - timedelta(minutes=5)).astimezone(UTC), state=total, sum=total
        )
    ]
    for minute in range(0, 60, 5):
        total += windows.get(minute, 0.0)
        start = FAULT + timedelta(minutes=minute)
        rows.append(StatisticData(start=start.astimezone(UTC), state=total, sum=total))
    get_instance(hass).async_import_statistics(
        _metadata(METER), rows, StatisticsShortTerm
    )


def _metadata(statistic_id: str) -> StatisticMetaData:
    return StatisticMetaData(
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=None,
        source="recorder",
        statistic_id=statistic_id,
        unit_class="energy",
        unit_of_measurement="kWh",
    )


async def _set_up(hass: HomeAssistant) -> MockConfigEntry:
    await hass.config.async_set_time_zone("Europe/Madrid")
    await async_wait_recording_done(hass)
    entry = _house()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _issue_id(key: str = "impossible_hour", statistic_id: str = METER) -> str:
    return f"{key}_{statistic_id}_{int(FAULT.timestamp())}"


def _cost_issue_id() -> str:
    return _issue_id("impossible_cost", COST)


def _issue(hass: HomeAssistant, issue_id: str | None = None) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id or _issue_id())


async def _open(hass: HomeAssistant, issue_id: str | None = None) -> Any:  # noqa: ANN401 - the flow's result
    """Open the Repair, as selecting it in Settings does."""
    await async_setup_component(hass, "repairs", {})
    manager = repairs_flow_manager(hass)
    assert manager is not None
    return await manager.async_init(DOMAIN, data={"issue_id": issue_id or _issue_id()})


async def _answer(flow_id: str, answer: dict[str, Any], hass: HomeAssistant) -> Any:  # noqa: ANN401
    manager = repairs_flow_manager(hass)
    assert manager is not None
    result = await manager.async_configure(flow_id, answer)
    await hass.async_block_till_done()
    return result


def _hour_now(
    hass: HomeAssistant,
    period: Literal["hour", "5minute"] = "hour",
    at: datetime = FAULT,
) -> float:
    """What the recorder now holds as the meter's change in that interval."""
    length = timedelta(hours=1) if period == "hour" else timedelta(minutes=5)
    rows = statistics_during_period(
        hass, at, at + length, {METER}, period, {"energy": "kWh"}, {"change"}
    )
    change = rows[METER][0]["change"]
    assert change is not None
    return float(change)


# Finding it


@pytest.mark.usefixtures("recorder_mock")
async def test_an_impossible_hour_raises_a_repair_naming_meter_hour_and_kwh(
    hass: HomeAssistant,
) -> None:
    # Given - 11,041 kWh recorded in one hour on the grid meter
    _record_fortnight(hass, 11041.0)
    entry = await _set_up(hass)

    # When - the daily check runs
    await impossible_hours.async_check(hass, entry)

    # Then - one Repair the household can answer, saying which, when and how much
    issue = _issue(hass)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.translation_key == "impossible_hour"
    assert issue.translation_placeholders == {
        "sensor": METER,
        "when": "2026-10-14 20:00",
        "recorded": "11041.00 kWh",
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_an_hour_at_the_ceiling_raises_nothing(hass: HomeAssistant) -> None:
    # Given - exactly 100 kWh, more than this home would use, but possible
    _record_fortnight(hass, 100.0)
    entry = await _set_up(hass)

    # When
    found = await impossible_hours.async_check(hass, entry)

    # Then
    assert found == []
    assert _issue(hass) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_the_repair_clears_once_the_hour_is_corrected_elsewhere(
    hass: HomeAssistant,
) -> None:
    # Given - raised, then corrected in Developer Tools rather than here
    _record_fortnight(hass, 11041.0)
    entry = await _set_up(hass)
    await impossible_hours.async_check(hass, entry)
    get_instance(hass).async_adjust_statistics(
        METER, FAULT.astimezone(UTC), -11040.5, "kWh"
    )
    await async_wait_recording_done(hass)

    # When - the next day's check
    await impossible_hours.async_check(hass, entry)

    # Then - nothing left to answer
    assert _issue(hass) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_the_check_runs_after_setup_and_then_daily(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    await _set_up(hass)
    assert _issue(hass) is None

    # When - a few minutes after Home Assistant starts
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Then
    assert _issue(hass) is not None


# What probably happened, and what it should have been


@pytest.mark.usefixtures("recorder_mock")
async def test_a_whole_total_counted_again_is_named_as_such(
    hass: HomeAssistant,
) -> None:
    # Given - the change is the meter's own reading: it read zero, then came
    # back, and its whole total was counted as that hour's use
    _record_fortnight(hass, 1084.65, fault_reading=1084.7)
    entry = await _set_up(hass)

    # When
    (found,) = await impossible_hours.async_check(hass, entry)

    # Then
    assert found.cause == impossible_hours.CAUSE_COUNTED_AGAIN


def test_a_fall_and_a_plain_jump_are_told_apart() -> None:
    # Given / When / Then - a fall is a fall, and a jump not matching the
    # reading is a jump
    fell = impossible_hours.ImpossibleHour(METER, FAULT, -500.0, 900.0)
    jumped = impossible_hours.ImpossibleHour(METER, FAULT, 500.0, 2500.0)
    assert fell.cause == impossible_hours.CAUSE_FELL
    assert jumped.cause == impossible_hours.CAUSE_JUMPED


@pytest.mark.usefixtures("recorder_mock")
async def test_the_same_hour_either_side_suggests_its_median_and_range(
    hass: HomeAssistant,
) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    entry = await _set_up(hass)

    # When
    (found,) = await impossible_hours.async_check(hass, entry)

    # Then - the household's own evenings, not the hours around the fault, to
    # the watt-hour, as it is typed into a form
    assert found.suggestion is not None
    assert found.suggestion.value == round(median(EVENINGS), 3)
    assert (found.suggestion.low, found.suggestion.high) == pytest.approx(
        (min(EVENINGS), max(EVENINGS))
    )
    assert found.suggestion.window is None
    assert found.corrected_at == FAULT


@pytest.mark.usefixtures("recorder_mock")
async def test_too_few_similar_hours_suggest_nothing(hass: HomeAssistant) -> None:
    # Given - only two evenings either side differ from an impossible one
    _record_fortnight(hass, 11041.0, evenings=[0.6, 0.8, *[500.0] * 12])
    entry = await _set_up(hass)

    # When
    found = await impossible_hours.async_check(hass, entry)

    # Then - the fault, but nothing to suggest for it
    fault = next(hour for hour in found if hour.start == FAULT)
    assert fault.suggestion is None


@pytest.mark.usefixtures("recorder_mock")
async def test_five_minutes_pin_the_jump_and_the_rest_of_the_hour(
    hass: HomeAssistant,
) -> None:
    # Given - the hour is recent enough to have its five-minute statistics:
    # 11,040.6 kWh in the five minutes from 20:35, 0.04 in each of the others
    windows = dict.fromkeys(range(0, 60, 5), 0.04) | {35: 11040.6}
    _record_fortnight(hass, sum(windows.values()))
    _record_five_minutes(hass, windows)
    entry = await _set_up(hass)

    # When
    (found,) = await impossible_hours.async_check(hass, entry)

    # Then - the rest of the hour as recorded, and a typical five minutes for
    # the faulty one, corrected where the jump is
    assert found.suggestion is not None
    assert found.suggestion.value == pytest.approx(0.44 + 0.04)
    assert found.suggestion.rest == pytest.approx(0.44)
    assert found.suggestion.jump == pytest.approx(11040.6)
    assert found.corrected_at == FAULT + timedelta(minutes=35)


# The Energy Dashboard's meters, and its cost, each with a Repair of its own


def test_the_energy_dashboard_costs_are_read_on_both_shapes() -> None:
    # Given - a cost the household chose on the source itself, and Home
    # Assistant's own cost and compensation sensors on the older flow lists
    on_source = {
        "energy_sources": [
            {"type": "grid", "stat_energy_from": METER, "stat_cost": COST}
        ]
    }
    flow_lists = {
        "energy_sources": [
            {
                "type": "grid",
                "flow_from": [{"stat_energy_from": METER}],
                "flow_to": [{"stat_energy_to": "sensor.grid_export"}],
            },
            {"type": "solar", "stat_energy_from": "sensor.solar"},
        ]
    }
    made = {
        METER: "sensor.grid_import_cost_2",
        "sensor.grid_export": "sensor.grid_export_compensation",
    }

    # When / Then - each money statistic, with the meter it prices
    assert dashboard_money(on_source, {}) == {COST: METER}
    assert dashboard_money(flow_lists, made) == {
        "sensor.grid_import_cost_2": METER,
        "sensor.grid_export_compensation": "sensor.grid_export",
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_a_meter_only_the_energy_dashboard_uses_is_checked_too(
    hass: HomeAssistant,
) -> None:
    # Given - a solar meter in the Energy Dashboard that Home Energy Advisor
    # does not read, recording 11,041 kWh in an hour
    _record_fortnight(hass, None)
    _record_fortnight(hass, 11041.0, statistic_id="sensor.solar")
    entry = await _set_up(hass)
    await _energy_dashboard(
        hass, _PRICED_GRID, {"type": "solar", "stat_energy_from": "sensor.solar"}
    )

    # When
    await impossible_hours.async_check(hass, entry)

    # Then
    assert _issue(hass, _issue_id(statistic_id="sensor.solar")) is not None
    assert _issue(hass) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_the_meter_and_its_cost_each_raise_a_repair_of_their_own(
    hass: HomeAssistant,
) -> None:
    # Given - the glitch priced into the Energy Dashboard's cost: 11,041 kWh at
    # the evening's 0.30 is 3,312.30 EUR, where 100 kWh at that week's dearest
    # price would be 30 EUR
    _record_fortnight(hass, 11041.0)
    _record_cost(hass, 11041.0)
    entry = await _set_up(hass)
    await _energy_dashboard(hass, _PRICED_GRID)

    # When
    await impossible_hours.async_check(hass, entry)

    # Then - two Repairs, one for each statistic, so each is answered on its own
    energy = _issue(hass)
    cost = _issue(hass, _cost_issue_id())
    assert energy is not None
    assert cost is not None
    assert cost.translation_key == "impossible_cost"
    assert cost.translation_placeholders == {
        "sensor": COST,
        "when": "2026-10-14 20:00",
        "recorded": "3312.30 EUR",
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cost_is_suggested_from_the_meter_s_suggestion_at_the_hour_s_price(
    hass: HomeAssistant,
) -> None:
    # Given - the meter's hour still uncorrected
    _record_fortnight(hass, 11041.0)
    _record_cost(hass, 11041.0)
    entry = await _set_up(hass)
    await _energy_dashboard(hass, _PRICED_GRID)

    # When
    found = await impossible_hours.async_check(hass, entry)

    # Then - the meter's suggested evening at the price the glitch was charged
    cost = next(hour for hour in found if hour.statistic_id == COST)
    assert cost.suggestion is not None
    assert cost.suggestion.energy == round(median(EVENINGS), 3)
    assert cost.suggestion.price == pytest.approx(EVENING_PRICE)
    assert cost.suggestion.value == pytest.approx(
        round(median(EVENINGS), 3) * EVENING_PRICE, abs=1e-3
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_correcting_the_meter_leaves_the_cost_s_repair_standing(
    hass: HomeAssistant,
) -> None:
    # Given - the household corrects the meter's hour to 0.6 kWh, and not the
    # cost
    _record_fortnight(hass, 11041.0)
    _record_cost(hass, 11041.0)
    entry = await _set_up(hass)
    await _energy_dashboard(hass, _PRICED_GRID)
    await impossible_hours.async_check(hass, entry)
    get_instance(hass).async_adjust_statistics(
        METER, FAULT.astimezone(UTC), 0.6 - 11041.0, "kWh"
    )
    await async_wait_recording_done(hass)

    # When - the next check
    found = await impossible_hours.async_check(hass, entry)

    # Then - the meter's Repair is gone, the cost's stands, now suggested at the
    # corrected kWh and the evening's usual price
    assert _issue(hass) is None
    assert _issue(hass, _cost_issue_id()) is not None
    (cost,) = found
    assert cost.suggestion is not None
    assert cost.suggestion.value == pytest.approx(0.6 * EVENING_PRICE, abs=1e-3)


@pytest.mark.usefixtures("recorder_mock")
async def test_each_repair_names_its_partner(hass: HomeAssistant) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    _record_cost(hass, 11041.0)
    entry = await _set_up(hass)
    await _energy_dashboard(hass, _PRICED_GRID)
    await impossible_hours.async_check(hass, entry)

    # When
    energy = await _open(hass)
    cost = await _open(hass, _cost_issue_id())

    # Then - each says the other may need correcting, and has its own Repair
    assert COST in energy["description_placeholders"]["partner"]
    assert METER in cost["description_placeholders"]["partner"]
    assert cost["description_placeholders"]["ceiling"] == "30.00 EUR"


@pytest.mark.usefixtures("recorder_mock")
async def test_correcting_the_cost_changes_the_cost_alone(
    hass: HomeAssistant,
) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    _record_cost(hass, 11041.0)
    entry = await _set_up(hass)
    await _energy_dashboard(hass, _PRICED_GRID)
    await impossible_hours.async_check(hass, entry)
    opened = await _open(hass, _cost_issue_id())
    confirm = await _answer(opened["flow_id"], {"value": 0.18}, hass)
    assert confirm["description_placeholders"]["value"] == "0.18 EUR"

    # When
    await _answer(confirm["flow_id"], {}, hass)
    await async_wait_recording_done(hass)

    # Then - the cost corrected in its own currency, the meter as it was
    assert _cost_now(hass) == pytest.approx(0.18)
    assert _hour_now(hass) == pytest.approx(11041.0)
    assert _issue(hass, _cost_issue_id()) is None
    assert _issue(hass) is not None


def _cost_now(hass: HomeAssistant) -> float:
    rows = statistics_during_period(
        hass, FAULT, FAULT + timedelta(hours=1), {COST}, "hour", None, {"change"}
    )
    change = rows[COST][0]["change"]
    assert change is not None
    return float(change)


# Correcting it


@pytest.mark.usefixtures("recorder_mock")
async def test_the_repair_offers_the_suggestion_and_says_why(
    hass: HomeAssistant,
) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    entry = await _set_up(hass)
    await impossible_hours.async_check(hass, entry)

    # When
    opened = await _open(hass)

    # Then - the suggested value filled in, and what it came from in words
    assert opened["step_id"] == "init"
    placeholders = opened["description_placeholders"]
    assert placeholders["sensor"] == METER
    assert placeholders["recorded"] == "11041.00 kWh"
    assert "0.20 kWh to 1.40 kWh" in placeholders["suggestion"]
    field = opened["data_schema"].schema
    (value,) = list(field)
    assert value.description == {"suggested_value": pytest.approx(median(EVENINGS))}


@pytest.mark.usefixtures("recorder_mock")
async def test_nothing_is_written_until_the_change_is_confirmed(
    hass: HomeAssistant,
) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    entry = await _set_up(hass)
    await impossible_hours.async_check(hass, entry)
    opened = await _open(hass)

    # When - a value given, but not yet confirmed
    confirm = await _answer(opened["flow_id"], {"value": 0.6}, hass)
    await async_wait_recording_done(hass)

    # Then - the confirmation says exactly what will change, and the hour is
    # as it was
    assert confirm["step_id"] == "confirm"
    assert confirm["description_placeholders"] == {
        "sensor": METER,
        "when": "2026-10-14 20:00",
        "recorded": "11041.00 kWh",
        "value": "0.60 kWh",
        "difference": "-11040.40 kWh",
    }
    assert _hour_now(hass) == pytest.approx(11041.0)
    assert _issue(hass) is not None


@pytest.mark.usefixtures("recorder_mock")
async def test_confirming_corrects_the_hour_and_says_how_to_undo_it(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    # Given
    _record_fortnight(hass, 11041.0)
    entry = await _set_up(hass)
    await impossible_hours.async_check(hass, entry)
    opened = await _open(hass)
    confirm = await _answer(opened["flow_id"], {"value": 0.6}, hass)

    # When
    with caplog.at_level(logging.WARNING):
        done = await _answer(confirm["flow_id"], {}, hass)
    await async_wait_recording_done(hass)

    # Then - that hour corrected, the hours after it untouched, the Repair gone,
    # and the change written down with the value to set back
    assert done["type"] == "create_entry"
    assert _hour_now(hass) == pytest.approx(0.6)
    assert _hour_now(hass, at=FAULT + timedelta(hours=1)) == pytest.approx(
        ORDINARY_HOUR
    )
    assert _issue(hass) is None
    assert "set the same hour back to 11041.00 kWh" in caplog.text


@pytest.mark.usefixtures("recorder_mock")
async def test_a_correction_found_in_five_minutes_is_made_there(
    hass: HomeAssistant,
) -> None:
    # Given - the jump in the five minutes from 20:35
    windows = dict.fromkeys(range(0, 60, 5), 0.04) | {35: 11040.6}
    _record_fortnight(hass, sum(windows.values()))
    _record_five_minutes(hass, windows)
    entry = await _set_up(hass)
    await impossible_hours.async_check(hass, entry)
    opened = await _open(hass)
    confirm = await _answer(opened["flow_id"], {"value": 0.48}, hass)

    # When
    await _answer(confirm["flow_id"], {}, hass)
    await async_wait_recording_done(hass)

    # Then - the hour and the five minutes that carried the jump, both
    assert _hour_now(hass) == pytest.approx(0.48)
    assert _hour_now(
        hass, "5minute", at=FAULT + timedelta(minutes=35)
    ) == pytest.approx(0.04)
    assert _hour_now(hass, "5minute", at=FAULT + timedelta(minutes=30)) == (
        pytest.approx(0.04)
    )
