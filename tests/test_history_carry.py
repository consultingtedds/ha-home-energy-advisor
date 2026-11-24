"""Carrying the household's old price history into the sensors it opts into.

ADR-0048 decision 4: the household chooses the price sensors and the standing
charge it used before, and their recorded history is written behind the new
sensors: each hour's mean price for the prices, each hour's cost for the daily
charge, joined to the live rows without a step. Written up from zero and the
live rows lifted by its total, as proven on the reference home (HEA-308).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import get_instance
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.home_energy_advisor import history_carry
from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_PERIOD_PLAN,
    CONF_PLAN_CARRY_IN,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_PERIODS,
    CONF_PLAN_PROVIDES_PRICES,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

MADRID = ZoneInfo("Europe/Madrid")
# The new sensors' first recorded hour: where the history joins them.
JOIN = datetime(2026, 11, 19, 0, tzinfo=MADRID)
NOW = datetime(2026, 11, 20, 10, tzinfo=MADRID)

_FLAT = {
    CONF_NAME: "Flat",
    CONF_PLAN_DAILY_CHARGE: 0.9,
    CONF_PLAN_EXPORT_PRICE: 0.05,
    CONF_BANDS: [
        {
            CONF_BAND_DAYS: "every_day",
            CONF_BAND_START: 0,
            CONF_BAND_END: 24,
            CONF_BAND_IMPORT_PRICE: 0.18,
        }
    ],
}


def _house(
    *, provides: bool = True, carry_in: dict[str, str] | None = None
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=8,
        data={CONF_CURRENCY: "EUR"},
        subentries_data=[
            ConfigSubentryDataWithId(
                subentry_id="flat",
                subentry_type=SUBENTRY_TYPE_PLAN,
                title="Flat",
                data=_FLAT,
                unique_id=None,
            ),
            ConfigSubentryDataWithId(
                subentry_id="current",
                subentry_type=SUBENTRY_TYPE_PLAN,
                title="Your current plan",
                data={
                    CONF_NAME: "Your current plan",
                    CONF_PLAN_FOLLOWS: True,
                    CONF_PLAN_DAILY_CHARGE: 0.9,
                    CONF_PLAN_PERIODS: [{CONF_PERIOD_PLAN: "flat"}],
                    **({CONF_PLAN_PROVIDES_PRICES: True} if provides else {}),
                    **({CONF_PLAN_CARRY_IN: carry_in} if carry_in else {}),
                },
                unique_id=None,
            ),
        ],
    )


async def _set_up(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, entry: MockConfigEntry
) -> None:
    await hass.config.async_set_time_zone("Europe/Madrid")
    freezer.move_to(NOW)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _ours(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_current_plan_{key}"
    )
    assert entity_id is not None
    return entity_id


def _hours(start: datetime, end: datetime) -> list[datetime]:
    hours = []
    moment = start
    while moment < end:
        hours.append(moment)
        moment += timedelta(hours=1)
    return hours


def _record_means(
    hass: HomeAssistant, statistic_id: str, means: dict[datetime, float], unit: str
) -> None:
    async_import_statistics(
        hass,
        StatisticMetaData(
            has_sum=False,
            mean_type=StatisticMeanType.ARITHMETIC,
            name=None,
            source="recorder",
            statistic_id=statistic_id,
            unit_class=None,
            unit_of_measurement=unit,
        ),
        [
            StatisticData(start=at.astimezone(UTC), mean=mean, min=mean, max=mean)
            for at, mean in means.items()
        ],
    )


def _record_sums(
    hass: HomeAssistant, statistic_id: str, sums: dict[datetime, float]
) -> None:
    async_import_statistics(
        hass,
        StatisticMetaData(
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=None,
            source="recorder",
            statistic_id=statistic_id,
            unit_class=None,
            unit_of_measurement="EUR",
        ),
        [
            StatisticData(start=at.astimezone(UTC), state=total, sum=total)
            for at, total in sums.items()
        ],
    )


async def _read(
    hass: HomeAssistant, statistic_id: str, kind: str
) -> dict[datetime, float]:
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2020, 1, 1, tzinfo=UTC),
        NOW.astimezone(UTC),
        {statistic_id},
        "hour",
        None,
        {kind},
    )
    return {
        datetime.fromtimestamp(row["start"], UTC): float(str(dict(row)[kind]))
        for row in rows.get(statistic_id, ())
    }


async def _carry(hass: HomeAssistant, **data: Any) -> dict[str, Any]:  # noqa: ANN401 - the action's answer
    response = await hass.services.async_call(
        DOMAIN, "carry_in_history", data, blocking=True, return_response=True
    )
    await async_wait_recording_done(hass)
    assert isinstance(response, dict)
    return response


@pytest.mark.usefixtures("recorder_mock")
async def test_the_old_price_history_is_written_behind_the_new_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the old price sensor recorded from the 17th at 0.20, then 0.25,
    # and the new import price recording itself from the 19th at 0.18
    entry = _house()
    await _set_up(hass, freezer, entry)
    ours = _ours(hass, entry, "import_price")
    before = _hours(datetime(2026, 11, 17, tzinfo=MADRID), JOIN)
    _record_means(
        hass,
        "sensor.old_price",
        {at: 0.20 if at.day == 17 else 0.25 for at in _hours(before[0], NOW)},
        "EUR/kWh",
    )
    _record_means(hass, ours, dict.fromkeys(_hours(JOIN, NOW), 0.18), "EUR/kWh")
    await async_wait_recording_done(hass)

    # When
    answer = await _carry(hass, import_price_from="sensor.old_price")

    # Then - every hour before the join copied, nothing from it overwritten
    means = await _read(hass, ours, "mean")
    assert answer == {"import_price": len(before)}
    assert means[before[0].astimezone(UTC)] == pytest.approx(0.20)
    assert means[before[-1].astimezone(UTC)] == pytest.approx(0.25)
    assert means[JOIN.astimezone(UTC)] == pytest.approx(0.18)
    assert len(means) == len(_hours(before[0], NOW))


@pytest.mark.usefixtures("recorder_mock")
async def test_a_price_kept_per_mwh_is_carried_per_kwh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the old export price kept in EUR/MWh
    entry = _house()
    await _set_up(hass, freezer, entry)
    ours = _ours(hass, entry, "export_price")
    hass.states.async_set("sensor.old_export", "50", {"unit_of_measurement": "EUR/MWh"})
    day = _hours(datetime(2026, 11, 18, tzinfo=MADRID), JOIN)
    _record_means(hass, "sensor.old_export", dict.fromkeys(day, 50.0), "EUR/MWh")
    await async_wait_recording_done(hass)

    # When
    await _carry(hass, export_price_from="sensor.old_export")

    # Then - as the new sensor records it
    means = await _read(hass, ours, "mean")
    assert means[day[0].astimezone(UTC)] == pytest.approx(0.05)


@pytest.mark.usefixtures("recorder_mock")
async def test_the_old_daily_charge_joins_the_new_without_a_step(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the old standing charge cost 1.00 a day for the two days before
    # the join, and the new cost has run 0.0375 an hour since it
    entry = _house()
    await _set_up(hass, freezer, entry)
    ours = _ours(hass, entry, "daily_charge_cost")
    before = _hours(datetime(2026, 11, 17, tzinfo=MADRID), JOIN)
    _record_sums(
        hass,
        "sensor.old_standing_charge",
        {at: 1000 + (index + 1) / 24 for index, at in enumerate(before)},
    )
    after = _hours(JOIN, NOW)
    _record_sums(
        hass, ours, {at: (index + 1) * 0.0375 for index, at in enumerate(after)}
    )
    await async_wait_recording_done(hass)

    # When
    await _carry(hass, daily_charge_cost_from="sensor.old_standing_charge")

    # Then - written up from zero, each hour's cost as charged, and the live
    # rows lifted by what was carried in: one running total with no step. The
    # old statistic's first hour carries nothing: its running total before it
    # is not known, and taking that total as one hour's cost is HEA-308's step
    carried = 47 / 24
    sums = await _read(hass, ours, "sum")
    assert sums[before[0].astimezone(UTC)] == pytest.approx(0)
    assert sums[before[1].astimezone(UTC)] == pytest.approx(1 / 24)
    assert sums[before[-1].astimezone(UTC)] == pytest.approx(carried)
    assert sums[JOIN.astimezone(UTC)] == pytest.approx(carried + 0.0375)
    assert sums[after[-1].astimezone(UTC)] == pytest.approx(
        carried + len(after) * 0.0375
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_a_new_sensor_with_nothing_recorded_takes_the_history_to_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the new import price has recorded nothing yet
    entry = _house()
    await _set_up(hass, freezer, entry)
    ours = _ours(hass, entry, "import_price")
    hours = _hours(datetime(2026, 11, 18, tzinfo=MADRID), NOW)
    _record_means(hass, "sensor.old_price", dict.fromkeys(hours, 0.22), "EUR/kWh")
    await async_wait_recording_done(hass)

    # When
    answer = await _carry(hass, import_price_from="sensor.old_price")

    # Then - every whole hour before this one
    assert answer == {"import_price": len(hours)}
    assert len(await _read(hass, ours, "mean")) == len(hours)


@pytest.mark.usefixtures("recorder_mock")
async def test_it_can_be_aimed_at_a_spare_statistic_to_rehearse(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - not opted in: no sensors of ours, as on the reference home before
    # it moves (HEA-308)
    await _set_up(hass, freezer, _house(provides=False))
    day = _hours(datetime(2026, 11, 18, tzinfo=MADRID), JOIN)
    _record_means(hass, "sensor.old_price", dict.fromkeys(day, 0.22), "EUR/kWh")
    await async_wait_recording_done(hass)

    # When - aimed at a spare helper nothing reads
    answer = await _carry(
        hass, import_price_from="sensor.old_price", import_price_to="sensor.spare"
    )

    # Then
    assert answer == {"import_price": len(day)}
    assert len(await _read(hass, "sensor.spare", "mean")) == len(day)


@pytest.mark.usefixtures("recorder_mock")
async def test_with_no_sensor_of_ours_and_no_target_it_is_refused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - not opted in
    await _set_up(hass, freezer, _house(provides=False))

    # When / Then - there is nothing to write behind
    with pytest.raises(ServiceValidationError):
        await _carry(hass, import_price_from="sensor.old_price")


@pytest.mark.usefixtures("recorder_mock")
async def test_a_carry_in_chosen_in_the_form_runs_once_the_sensors_exist(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - the old price recorded, and the carry-in chosen when the box was
    # ticked, waiting for the sensors the reload makes
    day = _hours(datetime(2026, 11, 18, tzinfo=MADRID), JOIN)
    entry = _house(carry_in={"import_price": "sensor.old_price"})
    await hass.config.async_set_time_zone("Europe/Madrid")
    freezer.move_to(NOW)
    _record_means(hass, "sensor.old_price", dict.fromkeys(day, 0.22), "EUR/kWh")
    await async_wait_recording_done(hass)

    # When
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    # The carry-in runs as a background task once setup is done
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    # Then - carried into the new import price, and not waiting any more
    means = await _read(hass, _ours(hass, entry, "import_price"), "mean")
    assert len(means) == len(day)
    assert CONF_PLAN_CARRY_IN not in entry.subentries["current"].data


@pytest.mark.usefixtures("recorder_mock")
async def test_history_is_carried_a_window_at_a_time_and_joins_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given - windows of ten hours, so two days of the old standing charge
    # cross several of them, as years would cross many months (HEA-316)
    monkeypatch.setattr(history_carry, "_WINDOW", timedelta(hours=10))
    entry = _house()
    await _set_up(hass, freezer, entry)
    ours = _ours(hass, entry, "daily_charge_cost")
    before = _hours(datetime(2026, 11, 17, tzinfo=MADRID), JOIN)
    _record_sums(
        hass,
        "sensor.old_standing_charge",
        {at: 1000 + (index + 1) / 24 for index, at in enumerate(before)},
    )
    after = _hours(JOIN, NOW)
    _record_sums(
        hass, ours, {at: (index + 1) * 0.0375 for index, at in enumerate(after)}
    )
    await async_wait_recording_done(hass)

    # When
    answer = await _carry(hass, daily_charge_cost_from="sensor.old_standing_charge")

    # Then - every hour written once, one running total across the windows, and
    # the live rows lifted by it, exactly as read in one go
    carried = 47 / 24
    sums = await _read(hass, ours, "sum")
    assert answer == {"daily_charge_cost": len(before)}
    assert [sums[at.astimezone(UTC)] for at in before] == pytest.approx(
        [index / 24 for index in range(len(before))]
    )
    assert sums[JOIN.astimezone(UTC)] == pytest.approx(carried + 0.0375)
