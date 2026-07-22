from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.home_energy_advisor.const import (
    CONF_CURRENCY,
    CONF_ENERGY_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from custom_components.home_energy_advisor.issues import (
    ISSUE_NEGATIVE_REMAINDER,
    ISSUE_PRICE_UNAVAILABLE,
    source_removed_issue_id,
    source_unavailable_issue_id,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant

_ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
_POWER = {"unit_of_measurement": "W", "device_class": "power"}


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
                title="Guest Bedroom Aircon",
                data={
                    CONF_NAME: "Guest Bedroom Aircon",
                    CONF_ENERGY_ENTITY: "sensor.guest_energy",
                },
                unique_id=None,
            )
        ],
    )


async def test_coordinator_accounts_for_a_device_over_an_interval(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a configured home with a grid meter, a tracked device, and a price,
    # all reading zero at the top of a 5-minute interval
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — over the interval the house imports 1 kWh and the device draws 0.6
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()

    # ...and the finalisation timer fires well past the lateness margin
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — the coordinator has priced the device at the import rate
    coordinator = entry.runtime_data
    subentry_id = next(iter(entry.subentries))
    guest = coordinator.data.devices[subentry_id]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.18")
    assert coordinator.data.untracked.energy_kwh == Decimal("0.4")


async def test_setup_creates_the_coordinator_and_unload_tears_it_down(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a configured, running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Then — the coordinator is attached and holds initial (zero) totals
    subentry_id = next(iter(entry.subentries))
    assert entry.runtime_data.data.devices[subentry_id].energy_kwh == Decimal(0)

    # When / Then — the entry unloads cleanly, tearing down its listeners and timer
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_price_changes_and_bad_readings_are_handled(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running integration
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.10")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the price changes, then briefly goes unavailable, and the grid meter
    # reports a garbage value before the real reading lands
    freezer.move_to(datetime(2026, 7, 8, 22, 1, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.price", "unavailable")
    hass.states.async_set("sensor.grid_import", "not-a-number", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — accounting carries on through the noise; the bucket is priced at the
    # rate active at its start (€0.10), the mid-bucket change and outages ignored
    coordinator = entry.runtime_data
    subentry_id = next(iter(entry.subentries))
    guest = coordinator.data.devices[subentry_id]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.06")


async def test_coordinator_diagnostics_reports_config_sources_and_totals(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running home that has accounted for one interval
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0.6", _ENERGY)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # When — a diagnostics snapshot is built
    diagnostics = entry.runtime_data.diagnostics()

    # Then — the config records the house inputs as redaction-friendly records
    subentry_id = next(iter(entry.subentries))
    config = diagnostics["config"]
    assert config["currency"] == "EUR"
    assert {"role": "grid_import", "entity": "sensor.grid_import"} in config[
        "house_sources"
    ]

    # ...each observed meter is labelled and carries a JSON-safe decision log
    by_entity = {source["entity_id"]: source for source in diagnostics["sources"]}
    guest = by_entity["sensor.guest_energy"]
    assert guest["device"] == "Guest Bedroom Aircon"
    assert guest["device_id"] == subentry_id
    assert guest["last_value"] == "0.6"
    assert guest["decisions"][-1]["reason"] == "counted"
    assert by_entity["sensor.grid_import"]["role"] == "grid_import"

    # ...and the running totals are stringified, never raw Decimals
    assert diagnostics["totals"]["devices"][subentry_id]["energy_kwh"] == "0.6"
    assert diagnostics["totals"]["untracked"]["energy_kwh"] == "0.4"


def _has_issue(hass: HomeAssistant, issue_id: str) -> bool:
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: datetime
) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()


async def _setup_running_home(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "0", _ENERGY)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_critical_source_unavailable_past_the_grace_raises_and_clears(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running home whose grid meter then goes unavailable
    entry = await _setup_running_home(hass, freezer)
    issue_id = source_unavailable_issue_id("sensor.grid_import")
    freezer.move_to(datetime(2026, 7, 8, 22, 1, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "unavailable")
    await hass.async_block_till_done()

    # When — half an hour passes: still inside the one-hour grace
    await _tick(hass, freezer, datetime(2026, 7, 8, 22, 31, tzinfo=UTC))

    # Then — no Repair yet; brief outages and restarts must not nag
    assert not _has_issue(hass, issue_id)

    # When — the outage passes the one-hour grace
    await _tick(hass, freezer, datetime(2026, 7, 8, 23, 5, tzinfo=UTC))

    # Then — the Repair is raised
    assert _has_issue(hass, issue_id)

    # When — the meter recovers
    freezer.move_to(datetime(2026, 7, 8, 23, 10, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "5.0", _ENERGY)
    await hass.async_block_till_done()
    await _tick(hass, freezer, datetime(2026, 7, 8, 23, 11, tzinfo=UTC))

    # Then — the Repair clears itself
    assert not _has_issue(hass, issue_id)
    assert entry.state is ConfigEntryState.LOADED


async def test_price_entity_unavailable_past_the_grace_raises_its_own_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running home whose price entity goes unavailable
    await _setup_running_home(hass, freezer)
    freezer.move_to(datetime(2026, 7, 8, 22, 1, tzinfo=UTC))
    hass.states.async_set("sensor.price", "unavailable")
    await hass.async_block_till_done()

    # When — the outage passes the grace period
    await _tick(hass, freezer, datetime(2026, 7, 8, 23, 5, tzinfo=UTC))

    # Then — the dedicated price Repair is raised (tied to the unavailable-price
    # policy: accounting continues at the last known price)
    assert _has_issue(hass, ISSUE_PRICE_UNAVAILABLE)


async def test_a_device_sensor_going_unavailable_never_raises_a_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running home whose tracked device goes offline for the season
    await _setup_running_home(hass, freezer)
    freezer.move_to(datetime(2026, 7, 8, 22, 1, tzinfo=UTC))
    hass.states.async_set("sensor.guest_energy", "unavailable")
    await hass.async_block_till_done()

    # When — a full day passes with the device still unavailable
    await _tick(hass, freezer, datetime(2026, 7, 9, 22, 5, tzinfo=UTC))

    # Then — no Repair: a device unplugged out of season is expected, not a fault
    assert not _has_issue(hass, source_unavailable_issue_id("sensor.guest_energy"))
    assert not _has_issue(hass, source_removed_issue_id("sensor.guest_energy"))


async def test_a_configured_entity_removed_from_hass_raises_a_removed_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running home whose device sensor is deleted (or renamed away)
    await _setup_running_home(hass, freezer)
    freezer.move_to(datetime(2026, 7, 8, 22, 1, tzinfo=UTC))
    hass.states.async_remove("sensor.guest_energy")
    await hass.async_block_till_done()

    # When — the very next tick notices it is gone (a removed entity has no state,
    # so grace is measured from first sight), then an hour passes still gone
    await _tick(hass, freezer, datetime(2026, 7, 8, 22, 2, tzinfo=UTC))
    await _tick(hass, freezer, datetime(2026, 7, 8, 23, 5, tzinfo=UTC))

    # Then — a removed/renamed Repair is raised even for a device: a vanished
    # entity is a real misconfiguration, unlike mere unavailability
    assert _has_issue(hass, source_removed_issue_id("sensor.guest_energy"))


async def test_persistently_negative_remainder_raises_a_repair(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a running home where the device implausibly out-draws the house,
    # bucket after bucket (double-counting / bad inputs)
    entry = await _setup_running_home(hass, freezer)

    # When — across well over an hour, the grid imports a trickle while the device
    # reports drawing far more, then the finalisation timer processes every bucket
    start = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
    for minute in range(5, 80, 5):
        freezer.move_to(start + timedelta(minutes=minute))
        hass.states.async_set("sensor.grid_import", f"{minute * 0.001:.3f}", _ENERGY)
        hass.states.async_set("sensor.guest_energy", f"{minute * 0.1:.3f}", _ENERGY)
        await hass.async_block_till_done()
    await _tick(hass, freezer, start + timedelta(minutes=100))

    # Then — the persistent negative-remainder Repair is raised
    assert _has_issue(hass, ISSUE_NEGATIVE_REMAINDER)
    assert entry.state is ConfigEntryState.LOADED

    # When — the inputs recover: the grid now imports far more than the device draws
    freezer.move_to(start + timedelta(minutes=105))
    hass.states.async_set("sensor.grid_import", "10.000", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "7.600", _ENERGY)
    await hass.async_block_till_done()
    await _tick(hass, freezer, start + timedelta(minutes=140))

    # Then — the Repair clears itself; the over-draw was not permanent
    assert not _has_issue(hass, ISSUE_NEGATIVE_REMAINDER)


def _power_only_entry() -> MockConfigEntry:
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
                title="Living Room Wall Lights",
                data={
                    CONF_NAME: "Living Room Wall Lights",
                    CONF_POWER_ENTITY: "sensor.living_room_wall_lights_power",
                },
                unique_id=None,
            )
        ],
    )


async def test_a_power_only_device_is_costed_via_an_auto_created_helper(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a home whose only tracked device is power-only (WiZ wall lights),
    # holding a steady 600 W
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    hass.states.async_set("sensor.living_room_wall_lights_power", "600", _POWER)
    entry = _power_only_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — the house imports 1 kWh while the lights hold 600 W across the interval
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.living_room_wall_lights_power", "600", _POWER)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — the device is wired through the auto-created Integral helper: it
    # draws real energy (~0.1 kWh) and is costed against it. (Exact W->kWh accuracy
    # is the native helper's own concern, proven in test_integral_helper; per-bucket
    # source allocation is proven in the engine tests. This asserts the seam: a
    # power-only device is no longer stuck at zero.)
    coordinator = entry.runtime_data
    subentry_id = next(iter(entry.subentries))
    lights = coordinator.data.devices[subentry_id]
    assert lights.energy_kwh > Decimal(0)
    assert lights.naive_cost > Decimal(0)


async def test_a_watt_hour_device_is_normalised_to_kwh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    # Given — a device whose energy sensor reports in Wh, not kWh
    freezer.move_to(datetime(2026, 7, 8, 22, 0, tzinfo=UTC))
    hass.states.async_set("sensor.price", "0.30")
    hass.states.async_set("sensor.grid_import", "0", _ENERGY)
    watt_hours = {"unit_of_measurement": "Wh", "device_class": "energy"}
    hass.states.async_set("sensor.guest_energy", "0", watt_hours)
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # When — it climbs by 600 Wh over the interval
    freezer.move_to(datetime(2026, 7, 8, 22, 5, tzinfo=UTC))
    hass.states.async_set("sensor.grid_import", "1.0", _ENERGY)
    hass.states.async_set("sensor.guest_energy", "600", watt_hours)
    await hass.async_block_till_done()
    freezer.move_to(datetime(2026, 7, 8, 22, 30, tzinfo=UTC))
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Then — that is accounted as 0.6 kWh, not 600
    guest = entry.runtime_data.data.devices[next(iter(entry.subentries))]
    assert guest.energy_kwh == Decimal("0.6")
