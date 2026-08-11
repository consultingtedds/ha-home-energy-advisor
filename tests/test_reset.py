"""The supported reset of a household's accumulated totals (HEA-57).

Deleting and re-adding the integration cannot clear HEA's figures: Home
Assistant keeps `restore_state` and long-term statistics keyed by entity id, so
a fresh add re-adopts the old baselines. The only alternative was filesystem
surgery on a running instance, which is not something a user can be asked to do.

These tests pin the three things the reset has to do together — rebase the
sensors, zero the cycle meters HEA created, and clear HEA's own statistics —
and, just as importantly, what it must not touch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SERVICE_RESET_TOTALS,
    SUBENTRY_TYPE_DEVICE,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
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


async def _running_household(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """A set-up household that has accounted one interval of real cost."""
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    return entry


def _state(hass: HomeAssistant, entity_id: str) -> Decimal:
    state = hass.states.get(entity_id)
    assert state is not None
    return Decimal(state.state)


async def test_the_action_rebases_the_household_to_zero(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a household with real accumulated cost across its figures
    entry = await _running_household(hass, freezer)
    assert _state(hass, "sensor.coarse_step_aircon_energy_used") == Decimal("0.6")
    assert _state(hass, "sensor.whole_home_actual_cost") > 0

    # When — the reset action is called for that config entry
    with patch(
        "custom_components.home_energy_advisor.reset.get_instance",
        return_value=MagicMock(),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_TOTALS,
            {"config_entry_id": entry.entry_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    # Then — every figure starts again from zero: the tracked device, the
    # Untracked remainder and the whole-home aggregate alike
    assert _state(hass, "sensor.coarse_step_aircon_energy_used") == Decimal(0)
    assert _state(hass, "sensor.coarse_step_aircon_actual_cost") == Decimal(0)
    assert _state(hass, "sensor.untracked_energy_devices_energy_used") == Decimal(0)
    assert _state(hass, "sensor.whole_home_actual_cost") == Decimal(0)


async def test_the_action_clears_only_heas_own_statistics(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running household, alongside a statistic that is nothing to do
    # with this integration
    entry = await _running_household(hass, freezer)
    hass.states.async_set("sensor.next_door_meter", "5.0", _ENERGY)

    # When — the reset action runs
    recorder = MagicMock()
    with patch(
        "custom_components.home_energy_advisor.reset.get_instance",
        return_value=recorder,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_TOTALS,
            {"config_entry_id": entry.entry_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    # Then — statistics are cleared for HEA's own sensors and the cycle meters it
    # created, and for nothing else. A blanket recorder purge would take out the
    # rest of the user's home
    recorder.async_clear_statistics.assert_called_once()
    cleared = set(recorder.async_clear_statistics.call_args.args[0])
    assert "sensor.coarse_step_aircon_energy_used" in cleared
    assert "sensor.whole_home_actual_cost" in cleared
    assert "sensor.coarse_step_aircon_energy_used_daily" in cleared
    assert "sensor.next_door_meter" not in cleared
    assert all(stat.startswith("sensor.") for stat in cleared)


async def test_the_options_flow_offers_a_confirmed_reset(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a household with accumulated figures, and a user in Configure
    entry = await _running_household(hass, freezer)
    assert _state(hass, "sensor.coarse_step_aircon_energy_used") == Decimal("0.6")
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    assert menu["type"] is FlowResultType.MENU
    assert "reset_totals" in menu["menu_options"]

    # When — they choose the reset branch and confirm it
    form = await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "reset_totals"}
    )
    assert form["type"] is FlowResultType.FORM
    with patch(
        "custom_components.home_energy_advisor.reset.get_instance",
        return_value=MagicMock(),
    ):
        done = await hass.config_entries.options.async_configure(form["flow_id"], {})
    await hass.async_block_till_done()

    # Then — the household is rebased, and the flow closes without rewriting the
    # options (which would reload the entry for no reason)
    assert done["type"] is FlowResultType.ABORT
    assert _state(hass, "sensor.coarse_step_aircon_energy_used") == Decimal(0)


async def test_the_reset_branch_does_nothing_until_it_is_confirmed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a household with accumulated figures
    entry = await _running_household(hass, freezer)

    # When — the user opens the reset branch but goes no further
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "reset_totals"}
    )
    await hass.async_block_till_done()

    # Then — nothing has been destroyed: showing the confirmation is not the
    # confirmation
    assert _state(hass, "sensor.coarse_step_aircon_energy_used") == Decimal("0.6")


async def test_the_action_rejects_an_unknown_config_entry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running household
    await _running_household(hass, freezer)

    # When / Then — asking to reset an entry that does not exist is refused with a
    # translated error, not a traceback
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_TOTALS,
            {"config_entry_id": "not-a-real-entry"},
            blocking=True,
        )
