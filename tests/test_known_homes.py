"""Every known home set up, upgraded, compared and edited (HEA-316).

What runs for every household on an upgrade, and the paths each shape of home
takes, checked against each known home rather than the reference home alone.
A new feature adds what each home should see here.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)
from tests.known_homes import CURRENT, KNOWN_HOMES, KnownHome, entry_of, record

from custom_components.home_energy_advisor.const import (
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DEMAND_CHARGE_ENTITY,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_PERIODS,
    CONF_PLAN_PROVIDES_PRICES,
    DOMAIN,
    SUBENTRY_TYPE_PLAN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator

pytestmark = [
    pytest.mark.usefixtures("recorder_mock"),
    pytest.mark.parametrize("home", KNOWN_HOMES, ids=lambda home: home.name),
]

_PRICE_SENSORS = (
    "import_price",
    "export_price",
    "daily_charge_cost",
    "daily_charge_meter",
)


async def _set_up(hass: HomeAssistant, home: KnownHome) -> MockConfigEntry:
    await record(hass, home)
    await async_wait_recording_done(hass)
    entry = entry_of(home)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_it_sets_up_and_upgrades_from_the_last_release(
    hass: HomeAssistant, home: KnownHome
) -> None:
    # Given / When - its entry as the last release stored it
    entry = await _set_up(hass, home)

    # Then - loaded, and its current plan upgraded as this home's should be
    assert entry.state is ConfigEntryState.LOADED
    current = entry.subentries[CURRENT].data
    assert current.get(CONF_PLAN_PERIODS, []) == home.periods_after_upgrade
    assert "price_history_from" not in current


async def test_it_compares_its_recorded_day(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, home: KnownHome
) -> None:
    # Given
    await _set_up(hass, home)

    # When
    result = await _compare(hass, hass_ws_client, home)

    # Then - every plan it entered priced, its current plan priced or, where its
    # price sensors keep no statistics, listed unpriced naming them; and a gap
    # left out for every plan only where a plan shares the sensor
    rows = {row["name"]: row for row in result["plans"]}
    current = next(row for row in result["plans"] if row["current"])
    typed = {name: row for name, row in rows.items() if not row["current"]}
    assert set(typed) == {plan["name"] for plan in home.plans.values()}
    assert all("no_price" not in row for row in typed.values())
    if home.current_lacks:
        assert current["no_price"] is True
        assert current["no_price_entities"] == home.current_lacks
    else:
        assert "no_price" not in current
        assert current["energy"] > 0
    if home.current_daily_rate is not None:
        # each hour's daily charge, the morning's and the afternoon's
        assert current["breakdown"]["daily"]["rate"] == pytest.approx(
            home.current_daily_rate
        )
    # a demand charge on each plan that names a sensor for it, and only there
    plans = [*home.plans.values(), home.current]
    named = {
        "Your current plan" if plan.get(CONF_PLAN_FOLLOWS) else plan[CONF_NAME]
        for plan in plans
        if plan.get(CONF_PLAN_DEMAND_CHARGE_ENTITY)
    }
    assert {name for name, row in rows.items() if "demand_charges" in row} == named
    for name in named:
        assert rows[name]["breakdown"]["demand"]["rate"] == pytest.approx(
            home.demand_rate
        )
    assert bool(result["left_out"]) is home.left_out


async def test_its_current_plan_s_settings_open_and_save(
    hass: HomeAssistant, home: KnownHome
) -> None:
    # Given
    entry = await _set_up(hass, home)

    # When - the rules confirmed, and the plans been on saved as they are
    form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PLAN),
        context={"source": "reconfigure", "subentry_id": CURRENT},
    )
    assert form["step_id"] == "current"
    result = await _configure(
        hass,
        form["flow_id"],
        {CONF_PLAN_DAILY_CHARGE: 1.5, CONF_PLAN_EXPORT_CAP: "none"},
    )

    # Then
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[CURRENT].data[CONF_PLAN_DAILY_CHARGE] == 1.5


async def test_it_provides_its_price_sensors_when_asked(
    hass: HomeAssistant, home: KnownHome
) -> None:
    # Given
    entry = await _set_up(hass, home)

    # When - ticked
    current = entry.subentries[CURRENT]
    hass.config_entries.async_update_subentry(
        entry, current, data={**current.data, CONF_PLAN_PROVIDES_PRICES: True}
    )
    await hass.async_block_till_done()

    # Then - still loaded, every sensor made, and the import price priced where
    # a plan it has been on is in force, unavailable where none is yet
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    ids = {
        key: registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_current_plan_{key}"
        )
        for key in _PRICE_SENSORS
    }
    assert all(ids.values())
    state = hass.states.get(str(ids["import_price"]))
    assert state is not None
    if home.periods_after_upgrade:
        assert float(state.state) > 0
    else:
        assert state.state == STATE_UNAVAILABLE


async def _compare(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, home: KnownHome
) -> dict[str, Any]:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "home_energy_advisor/compare_plans",
            "start_time": home.day.isoformat(),
            "end_time": (home.day + timedelta(days=1)).isoformat(),
        }
    )
    response = await client.receive_json()
    assert response["success"], response
    result: dict[str, Any] = response["result"]
    return result


async def _configure(hass: HomeAssistant, flow_id: str, answer: dict[str, Any]) -> Any:  # noqa: ANN401 - a flow result
    """Answer a step, saving the plans been on as they stand where asked."""
    result = await hass.config_entries.subentries.async_configure(flow_id, answer)
    if result.get("step_id") == "periods":
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"action": "save"}
        )
    return result
