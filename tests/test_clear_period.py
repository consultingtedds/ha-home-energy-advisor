"""Clearing a household's figures for a chosen period (HEA-272).

Run against the real recorder and the real statistics compiler, as the reset's
tests are: the obligation is what Home Assistant records, and a double written
from our own reading of the compiler would agree with us whatever it did.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import restore_state
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
    do_adhoc_statistics,
    statistics_during_period,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_CYCLE_DAILY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SERVICE_CLEAR_PERIOD,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}

START = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)
_HOUR = timedelta(hours=1)

_COST = "sensor.whole_home_actual_cost"
_ENERGY_USED = "sensor.whole_home_energy_used"
_AIRCON_COST = "sensor.coarse_step_aircon_actual_cost"
_AIRCON_COST_DAILY = "sensor.coarse_step_aircon_actual_cost_daily"
_AIRCON_ENERGY_DAILY = "sensor.coarse_step_aircon_energy_used_daily"


def _entry(options: dict[str, bool] | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        options=options or {},
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="Coarse Step Aircon",
                data={
                    CONF_NAME: "Coarse Step Aircon",
                    CONF_ENERGY_ENTITY: "sensor.coarse_step_energy",
                },
                unique_id=None,
            )
        ],
    )


async def _compile_hour(hass: HomeAssistant, hour: datetime) -> None:
    """Compile an hour's five-minute windows, then the hour, as the recorder does."""
    await async_wait_recording_done(hass)
    for window in range(12):
        do_adhoc_statistics(hass, start=hour + timedelta(minutes=5 * window))
        await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, period="hour", start=hour)
    await async_wait_recording_done(hass)


async def _run_hour(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hour: datetime, kwh: float
) -> None:
    """One hour of use: the meters step early in it and the figures publish."""
    grid = float(_published(hass, "sensor.grid_import")) + kwh
    device = float(_published(hass, "sensor.coarse_step_energy")) + kwh / 2
    freezer.move_to(hour + timedelta(minutes=5))
    hass.states.async_set("sensor.grid_import", str(grid), _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", str(device), _ENERGY)
    await hass.async_block_till_done()
    # Fired at the time rather than firing everything, which would also run the
    # cycle meters' midnight reset every hour.
    freezer.move_to(hour + timedelta(minutes=40))
    async_fire_time_changed(hass, hour + timedelta(minutes=40))
    await hass.async_block_till_done()


async def _household_with_four_hours(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    options: dict[str, bool] | None = None,
) -> MockConfigEntry:
    """A household with four compiled hours: 1, 2, 3 and 4 kWh at 0.30."""
    freezer.move_to(START - _HOUR)
    await restore_state.async_load(hass)
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry(options)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _compile_hour(hass, START - _HOUR)
    for index, kwh in enumerate((1.0, 2.0, 3.0, 4.0)):
        hour = START + index * _HOUR
        await _run_hour(hass, freezer, hour, kwh)
        await _compile_hour(hass, hour)
    freezer.move_to(START + 4 * _HOUR + timedelta(minutes=2))
    return entry


def _hourly(hass: HomeAssistant, entity_id: str, kind: str) -> list[float]:
    rows = statistics_during_period(
        hass, START, None, {entity_id}, "hour", None, {kind}
    )
    return [round(row[kind], 6) for row in rows.get(entity_id, [])]


def _published(hass: HomeAssistant, entity_id: str) -> Decimal:
    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} is not present"
    return Decimal(state.state)


async def _clear(
    hass: HomeAssistant, entry: MockConfigEntry, start: datetime, end: datetime
) -> dict[str, float]:
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_PERIOD,
        {"config_entry_id": entry.entry_id, "start": start, "end": end},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    assert isinstance(response, dict)
    removed = response["removed"]
    assert isinstance(removed, dict)
    return {key: float(str(value)) for key, value in removed.items()}


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cleared_hour_shows_no_change_and_later_hours_drop_by_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - four compiled hours costing 0.30, 0.60, 0.90 and 1.20
    entry = await _household_with_four_hours(hass, freezer)
    assert _hourly(hass, _COST, "change") == [0.3, 0.6, 0.9, 1.2]
    assert _hourly(hass, _ENERGY_USED, "change") == [1.0, 2.0, 3.0, 4.0]

    # When - the second hour is cleared
    removed = await _clear(hass, entry, START + _HOUR, START + 2 * _HOUR)

    # Then - it shows no change, money and energy alike, and the hours after it
    # carry on from where the hour before it ended
    assert _hourly(hass, _COST, "change") == [0.3, 0.0, 0.9, 1.2]
    assert _hourly(hass, _COST, "sum") == [0.3, 0.3, 1.2, 2.4]
    assert _hourly(hass, _ENERGY_USED, "change") == [1.0, 0.0, 3.0, 4.0]
    assert _hourly(hass, _ENERGY_USED, "sum") == [1.0, 1.0, 4.0, 8.0]
    # ...and the household is told what went
    assert removed == {
        "energy_used": 2.0,
        "actual_cost": pytest.approx(0.6),
        "cost_savings": 0.0,
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_money_totals_drop_by_the_period_and_energy_totals_keep_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household 3.00 of cost and 10 kWh into its lifetime
    entry = await _household_with_four_hours(hass, freezer)
    assert _published(hass, _COST) == Decimal("3.00")
    assert _published(hass, _ENERGY_USED) == Decimal("10.000")
    aircon = _published(hass, _AIRCON_COST)

    # When - the second hour is cleared
    await _clear(hass, entry, START + _HOUR, START + 2 * _HOUR)

    # Then - cost to date has lost that hour's 0.60, the device's its share, and
    # the energy counter, which Home Assistant only lets rise, has kept it
    assert _published(hass, _COST) == Decimal("2.40")
    assert _published(hass, _AIRCON_COST) == aircon - Decimal("0.30")
    assert _published(hass, _ENERGY_USED) == Decimal("10.000")


@pytest.mark.usefixtures("recorder_mock")
async def test_the_fall_is_booked_once_and_the_next_hour_carries_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household whose second hour has been cleared
    entry = await _household_with_four_hours(hass, freezer)
    await _clear(hass, entry, START + _HOUR, START + 2 * _HOUR)

    # When - the hour the clear was made in is used and compiled
    hour = START + 4 * _HOUR
    await _run_hour(hass, freezer, hour, 5.0)
    await _compile_hour(hass, hour)

    # Then - that hour shows only what it used. The money figure fell when the
    # clear lowered it, and the history had already been lowered for it, so a
    # fall booked again would show here as 1.50 less 0.60.
    assert _hourly(hass, _COST, "change") == [0.3, 0.0, 0.9, 1.2, 1.5]
    assert _hourly(hass, _COST, "sum")[-1] == 3.9
    assert _hourly(hass, _ENERGY_USED, "change") == [1.0, 0.0, 3.0, 4.0, 5.0]
    assert _hourly(hass, _ENERGY_USED, "sum")[-1] == 13.0


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cost_cycle_meter_loses_a_period_inside_its_cycle(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - daily totals on, with the second hour inside today
    await hass.config.async_set_time_zone("UTC")
    entry = await _household_with_four_hours(hass, freezer, {CONF_CYCLE_DAILY: True})
    cost_today = _published(hass, _AIRCON_COST_DAILY)
    energy_today = _published(hass, _AIRCON_ENERGY_DAILY)
    assert cost_today >= Decimal("0.30")

    # When - the second hour is cleared
    await _clear(hass, entry, START + _HOUR, START + 2 * _HOUR)

    # Then - today's cost loses that hour's 0.30 once, not twice, and today's
    # energy, like the lifetime energy it follows, keeps it
    assert _published(hass, _AIRCON_COST_DAILY) == cost_today - Decimal("0.30")
    assert _published(hass, _AIRCON_ENERGY_DAILY) == energy_today


@pytest.mark.usefixtures("recorder_mock")
async def test_a_cost_cycle_meter_keeps_its_cycle_when_the_period_is_before_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - daily totals on, in a zone where today began at 02:00 UTC, so the
    # first two hours belong to yesterday
    await hass.config.async_set_time_zone("Etc/GMT+2")
    entry = await _household_with_four_hours(hass, freezer, {CONF_CYCLE_DAILY: True})
    today = _published(hass, _AIRCON_COST_DAILY)

    # When - the second hour, yesterday, is cleared
    await _clear(hass, entry, START + _HOUR, START + 2 * _HOUR)

    # Then - today's total is untouched, while cost to date has lost it
    assert _published(hass, _AIRCON_COST_DAILY) == today
    assert _published(hass, _COST) == Decimal("2.40")


@pytest.mark.usefixtures("recorder_mock")
async def test_a_period_still_being_counted_is_refused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a running household, two minutes into an hour
    entry = await _household_with_four_hours(hass, freezer)

    # When / Then - a period reaching into this hour is refused, and nothing moves
    with pytest.raises(ServiceValidationError) as refused:
        await _clear(hass, entry, START + 3 * _HOUR, START + 4 * _HOUR + _HOUR)
    assert refused.value.translation_key == "clear_period_unfinished"
    assert _published(hass, _COST) == Decimal("3.00")


@pytest.mark.usefixtures("recorder_mock")
async def test_a_period_ending_before_it_starts_is_refused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _household_with_four_hours(hass, freezer)
    with pytest.raises(ServiceValidationError) as refused:
        await _clear(hass, entry, START + 2 * _HOUR, START + _HOUR)
    assert refused.value.translation_key == "clear_period_order"


@pytest.mark.usefixtures("recorder_mock")
async def test_configure_shows_what_will_go_then_clears_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household in UTC, so the picker's times are UTC too
    await hass.config.async_set_time_zone("UTC")
    entry = await _household_with_four_hours(hass, freezer)

    # When - Configure is asked to clear the second hour
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "clear_period"}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {"start": "2026-07-08 01:00:00", "end": "2026-07-08 02:00:00"},
    )

    # Then - it shows the amounts before anything changes
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "clear_period_confirm"
    assert flow["description_placeholders"] == {
        "start": "2026-07-08 01:00",
        "end": "2026-07-08 02:00",
        "energy": "2.00 kWh",
        "cost": "0.60 EUR",
        "savings": "0.00 EUR",
    }
    assert _published(hass, _COST) == Decimal("3.00")

    # ...and only submitting clears them
    flow = await hass.config_entries.options.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    assert flow["type"] is FlowResultType.ABORT
    assert flow["reason"] == "clear_period_done"
    assert _published(hass, _COST) == Decimal("2.40")


@pytest.mark.usefixtures("recorder_mock")
async def test_configure_refuses_an_end_before_the_start(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _household_with_four_hours(hass, freezer)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "clear_period"}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {"start": "2026-07-08 02:00:00", "end": "2026-07-08 01:00:00"},
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["errors"] == {"base": "clear_period_order"}
