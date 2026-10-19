from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_CHARGE_ENTITY,
    CONF_BATTERY_DISCHARGE_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_BATTERY,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.diagnostics import (
    async_get_config_entry_diagnostics,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


def _entry(
    extra_data: dict[str, object] | None = None,
    battery: dict[str, object] | None = None,
) -> MockConfigEntry:
    subentries = [
        ConfigSubentryData(
            subentry_type=SUBENTRY_TYPE_DEVICE,
            title="Coarse Step Aircon",
            data={
                CONF_NAME: "Coarse Step Aircon",
                CONF_ENERGY_ENTITY: "sensor.coarse_step_energy",
            },
            unique_id=None,
        )
    ]
    if battery is not None:
        subentries.append(
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_BATTERY,
                title="Battery",
                data={CONF_NAME: "Battery", **battery},
                unique_id=None,
            )
        )
    return MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={
            CONF_PRICE_ENTITY: "sensor.price",
            CONF_CURRENCY: "EUR",
            CONF_GRID_IMPORT_ENTITY: "sensor.grid_import",
            **(extra_data or {}),
        },
        subentries_data=subentries,
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


async def test_diagnostics_say_which_rates_are_in_force(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Where the rate comes from, and what it is (HEA-210).

    The download named the price entities and never the rates, so "did my new
    export rate take?" could only be answered by waiting for generation to be
    used at it.
    """
    # Given - a household whose import price sensor reads 0.30, and who declare no
    # export price
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

    # Then - the import rate the engine holds and since when, beside the entity it
    # came from, and no export rate said as none rather than as zero
    assert result["config"]["price_entity"] == "sensor.price"
    assert result["config"]["rates_in_force"] == {
        "import": {"rate": "0.30", "since": "2026-07-08T22:00:00+00:00"},
        "export": None,
    }


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
        # How far the house meters disagree with the battery's own, with what
        # that means beside it - the only place it is visible at all (HEA-200).
        "meter_disagreement": {
            "kwh": "0",
            "means": (
                "How far the house meters claim more battery loss than the "
                "battery's own meters allow, since measuring began. Non-zero only "
                "where a household's meters disagree with each other; it never "
                "reaches a published figure."
            ),
        },
        # The loss measurement's own state, or none where nothing is being
        # measured - as here, with no battery level configured (HEA-212).
        "loss": None,
    }


async def test_diagnostics_say_which_battery_settings_are_set(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Absent should mean not set, and nothing else (HEA-212).

    The battery level and its capacity decide whether the loss can be measured
    at all, and the download carried neither. A triage once told a household they
    had set none, from their absence in the file - and was wrong.
    """
    # Given - a household with no battery level configured
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - said outright as no battery, and no readings to show
    assert result["config"]["batteries"] == []
    assert result["battery_level"] == []


async def test_diagnostics_carry_what_the_battery_level_read(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The history a household was asked to export by hand, three times (HEA-212).

    The level is read once a minute and is unchanged almost every time, so a
    reading is kept only when what was read, or what was made of it, changes.
    """
    # Given - a 5 kWh battery at 50%, then its level unavailable for two minutes,
    # then reading 150 - not a percentage at all - then 51%
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.coarse_step_energy", "0", _ENERGY)
    hass.states.async_set("sensor.battery_level", "50")
    hass.states.async_set("sensor.battery_charge", "0", _ENERGY)
    hass.states.async_set("sensor.battery_discharge", "0", _ENERGY)
    entry = _entry(
        battery={
            CONF_BATTERY_CHARGE_ENTITY: "sensor.battery_charge",
            CONF_BATTERY_DISCHARGE_ENTITY: "sensor.battery_discharge",
            CONF_BATTERY_SOC_ENTITY: "sensor.battery_level",
            CONF_BATTERY_CAPACITY_KWH: 5.0,
        }
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def a_minute_later(minute: int, level: str) -> None:
        hass.states.async_set("sensor.battery_level", level)
        freezer.move_to(datetime(2026, 7, 8, 22, minute, tzinfo=UTC))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    await a_minute_later(1, "50")
    await a_minute_later(2, "unavailable")
    await a_minute_later(3, "unavailable")
    await a_minute_later(4, "150")
    await a_minute_later(5, "51")

    # When
    result = await async_get_config_entry_diagnostics(hass, entry)

    # Then - the battery and its settings, and one reading per change, dated
    # when it began
    assert result["config"]["batteries"] == [
        {
            "name": "Battery",
            "charge": "sensor.battery_charge",
            "discharge": "sensor.battery_discharge",
            "level_entity": "sensor.battery_level",
            "capacity_kwh": "5.0",
        }
    ]
    assert result["battery_level"] == [
        {
            "battery": "Battery",
            "readings": [
                {
                    "at": "2026-07-08T22:01:00+00:00",
                    "state": "50",
                    "kwh": "2.5",
                    "reason": "used",
                },
                {
                    "at": "2026-07-08T22:02:00+00:00",
                    "state": "unavailable",
                    "kwh": None,
                    "reason": "unavailable",
                },
                {
                    "at": "2026-07-08T22:04:00+00:00",
                    "state": "150",
                    "kwh": None,
                    "reason": "not_a_percentage",
                },
                {
                    "at": "2026-07-08T22:05:00+00:00",
                    "state": "51",
                    "kwh": "2.55",
                    "reason": "used",
                },
            ],
        }
    ]


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
