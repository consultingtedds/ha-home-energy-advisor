from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.diagnostics import (
    async_get_config_entry_diagnostics,
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


async def test_diagnostics_name_the_entity_behind_every_figure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A masked sensor makes the file unactionable (HEA-147).

    The download exists to answer "which sensor produced this figure". Masking
    the answer leaves a maintainer asking the household to supply by hand the one
    thing the file was for - which is what happened on GitHub #22, where three
    devices were reported as condemned and nothing said which sensor each was.
    """
    # Given - a configured, running home
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the configuration names the entity behind each house input, and the
    # price entity, so a figure can be traced to the sensor it came from
    assert result["config"]["price_entity"] == "sensor.price"
    grid = next(
        source
        for source in result["config"]["house_sources"]
        if source["role"] == "grid_import"
    )
    assert grid["entity"] == "sensor.grid_import"

    # ...and each observed source carries its decision log alongside the entity
    # and the device name it belongs to, which is the pairing a report needs
    source = next(item for item in result["sources"] if item["device_id"] is not None)
    assert source["entity_id"] == "sensor.coarse_step_energy"
    assert source["device"] == "Coarse Step Aircon"
    assert source["role"] is None
    assert "decisions" in source


async def test_diagnostics_expose_the_battery_ledger(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a configured, running home
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the stored-cost ledger is in it. Discharge is priced from these two
    # figures and nothing else, so a household given a discharge costed below the
    # import rate can otherwise only infer why (HEA-112).
    assert result["battery"] == {
        "stored_kwh": "0",
        "stored_cost": "0",
        # What reconciliation has written off, because that money reaches the
        # household's own total and has to be accountable from here (HEA-178),
        # and the energy beside it is the round-trip loss published (HEA-174).
        "written_off_kwh": "0",
        "written_off_cost": "0",
        # What the battery's own meters would not let the house balance publish
        # as loss. It grows only where a household's meters disagree with each
        # other, which is the one thing the download could not say before: a
        # figure climbing here means their metering wants looking at, not that
        # the accounting is wrong (HEA-196).
        "loss_refused_kwh": "0",
    }

    # ...and it is the whole ledger, with nothing else smuggled in beside them
    assert set(result["battery"]) == {
        "stored_kwh",
        "stored_cost",
        "written_off_kwh",
        "written_off_cost",
        "loss_refused_kwh",
    }


async def test_diagnostics_say_why_the_previous_accounting_was_not_carried(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a first run on a household that has never written a snapshot
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - it records that the run began cold and why. A restart that silently
    # drops the battery ledger changes what discharge costs, so the download has
    # to explain the change rather than leave the figures unaccountable.
    assert result["snapshot"] == {"status": "absent", "age_seconds": None}


async def test_diagnostics_say_whether_new_entities_are_allowed_to_arrive(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The setting that decides whether anything reaches the household (HEA-189).

    Home Assistant lets a household switch off "Enable newly added entities" per
    integration. With it off, every entity created afterwards arrives disabled,
    so a device added later tracks nothing - which is exactly what was reported
    on GitHub 32, with a full diagnostics download attached that could not say
    so. The file carried what the engine knew and nothing about the entry the
    engine was running in.
    """
    # Given - a household who has switched off newly added entities
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, pref_disable_new_entities=True)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When - the diagnostics download is produced
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the file says so, rather than leaving a maintainer to ask the
    # household to go and read a menu
    assert result["entry"]["pref_disable_new_entities"] is True
    assert result["entry"]["disabled_by"] is None
    assert result["entry"]["state"] == "loaded"


async def test_diagnostics_report_new_entities_allowed_on_an_ordinary_household(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given - a household who has changed nothing, which is almost all of them
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then - the default is reported as the default, so the figure above means
    # something when it differs
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["pref_disable_new_entities"] is False


async def test_diagnostics_count_the_entities_a_household_has_switched_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The same question from the other side (HEA-189).

    `pref_disable_new_entities` explains entities disabled *on arrival*. It says
    nothing about ones switched off since, or disabled by an integration that is
    not us. Counting what is actually registered disabled answers "why is this
    figure missing" whatever put it that way.
    """
    # Given - a running household who has switched one figure off by hand
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    ours = er.async_entries_for_config_entry(registry, entry.entry_id)
    enabled_at_first = [item for item in ours if item.disabled_by is None]
    registry.async_update_entity(
        enabled_at_first[0].entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # When
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the file separates what we switched off from what they did. This
    # household is grid-only, so the integration has already disabled every
    # by-source and battery figure on purpose (HEA-175); reporting those beside
    # the household's own single choice as one number would read as alarming
    after = er.async_entries_for_config_entry(registry, entry.entry_id)
    by_us = [
        item
        for item in after
        if item.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    ]
    assert result["entry"]["entities"] == {
        "total": len(after),
        "disabled": len(by_us) + 1,
        "disabled_by": {"integration": len(by_us), "user": 1},
    }
