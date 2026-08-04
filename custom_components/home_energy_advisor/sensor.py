"""Per-device cost sensors — the four figures ADR-0003 fixes.

For every tracked device and the Untracked remainder this platform publishes
Energy Used, Actual Cost, Cost at Grid Price and Cost Savings, grouped one Home
Assistant device per tracked device. The identities here (``unique_id``,
``device_class``, ``state_class``, ``translation_key``, unit) are effectively
permanent — changing them after release orphans long-term statistics — so they
follow ADR-0003 exactly.

The accounting runtime keeps *since-startup* running totals and resets to zero on
restart (see ``engine/accountant.py``). Each sensor is therefore a
``RestoreSensor``: on startup it restores its last published value as a baseline
and adds the runtime's running total on top, so ``total_increasing`` stays
continuous across restarts without the engine persisting anything.

This module is also where a figure stops being an accumulator and becomes a
recorded Home Assistant state, so it is where rounding belongs — see
``HeaCostSensor.native_value`` (HEA-59).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_CURRENCY,
    DEFAULT_CURRENCY,
    DOMAIN,
    SIGNAL_RESET_TOTALS,
    SUBENTRY_TYPE_DEVICE,
    WHOLE_HOME_KEY,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import HeaConfigEntry, HeaCoordinator
    from .engine.accountant import DeviceTotals

# Device keys for the two synthetic aggregates; real devices are keyed by subentry
# id (a UUID), so these literals cannot collide with one. The whole-home key is
# shared via const so cycle-meter creation can exclude it (HEA-48).
_UNTRACKED_KEY = "untracked"
_WHOLE_HOME_KEY = WHOLE_HOME_KEY

# Only Energy Used differs between a real device and the Untracked remainder: a
# late correction legitimately pulls Untracked's energy down, which HA statistics
# would misread as a meter reset under `total_increasing`, so Untracked's is
# `total` (HEA-48 / ADR-0006). The monetary costs are `total` for every device
# already (ADR-0007), so they need no per-key remap.
_UNTRACKED_TOTAL_CONCEPTS = frozenset(
    {
        "energy_used",
        "energy_from_grid",
        "energy_from_generation",
        "energy_from_battery",
    }
)

# Precision at which a figure becomes a Home Assistant state (HEA-59). Publishing
# the accumulator's full Decimal wrote 28-significant-digit strings to the recorder
# roughly once a minute, mirrored by every cycle meter. Both limits sit far below
# anything a reading can mean — 1 mWh, and a hundredth of a cent — and below the
# display precision above, so nothing a user sees changes. The engine's own
# accumulators keep full precision; this is only the presentation boundary.
_ENERGY_PRECISION = 6
_MONEY_PRECISION = 4


def _concepts_for(device_key: str) -> tuple[HeaSensorDescription, ...]:
    """The concept descriptions for a device key, remapping Untracked's to total."""
    if device_key != _UNTRACKED_KEY:
        return _CONCEPTS
    return tuple(
        replace(concept, state_class=SensorStateClass.TOTAL)
        if concept.key in _UNTRACKED_TOTAL_CONCEPTS
        else concept
        for concept in _CONCEPTS
    )


@dataclass(frozen=True, kw_only=True)
class HeaSensorDescription(SensorEntityDescription):
    """A cost-sensor concept plus how to read it from a device's totals."""

    value_fn: Callable[[DeviceTotals], Decimal]
    publish_precision: int


_CONCEPTS: tuple[HeaSensorDescription, ...] = (
    HeaSensorDescription(
        key="energy_used",
        translation_key="energy_used",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        publish_precision=_ENERGY_PRECISION,
        value_fn=lambda totals: totals.energy_kwh,
    ),
    # Monetary sensors are `total`, never `total_increasing`: Home Assistant
    # rejects `total_increasing` for the monetary device class (a currency total is
    # not a strictly-rising meter), and Cost Savings genuinely dips on battery
    # arbitrage. `total` models a monotonic accumulator too, so the actual/naive
    # costs use it as well — one consistent choice for all money (ADR-0007).
    HeaSensorDescription(
        key="actual_cost",
        translation_key="actual_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        publish_precision=_MONEY_PRECISION,
        value_fn=lambda totals: totals.actual_cost,
    ),
    HeaSensorDescription(
        key="cost_at_grid_price",
        translation_key="cost_at_grid_price",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        publish_precision=_MONEY_PRECISION,
        value_fn=lambda totals: totals.naive_cost,
    ),
    HeaSensorDescription(
        key="cost_savings",
        translation_key="cost_savings",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        publish_precision=_MONEY_PRECISION,
        value_fn=lambda totals: totals.cost_savings,
    ),
    # Energy Used split across the sources that served it, for energy
    # self-sufficiency — "how much of this device ran on the sun" (HEA-51). The
    # engine already computes the split per 5-minute bucket to price the energy;
    # publishing it is the only way to reach it, because unlike a period total
    # (derivable from statistics `change`) or the whole-home aggregate (derivable
    # as Σ siblings) it cannot be recovered retroactively from anything else.
    # Never cycle-metered — see ADR-0008 §3 and `cycle_meter._METERED_CONCEPTS`.
    HeaSensorDescription(
        key="energy_from_grid",
        translation_key="energy_from_grid",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        publish_precision=_ENERGY_PRECISION,
        value_fn=lambda totals: totals.energy_from_grid,
    ),
    HeaSensorDescription(
        key="energy_from_generation",
        translation_key="energy_from_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        publish_precision=_ENERGY_PRECISION,
        value_fn=lambda totals: totals.energy_from_generation,
    ),
    HeaSensorDescription(
        key="energy_from_battery",
        translation_key="energy_from_battery",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        publish_precision=_ENERGY_PRECISION,
        value_fn=lambda totals: totals.energy_from_battery,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 - HA platform signature; state is on the entry
    entry: HeaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the four sensors for the Untracked remainder and each device."""
    coordinator = entry.runtime_data
    currency = entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY)

    # One integration-level "hub" device carries the devices-registry sensor —
    # the authoritative list dashboards read to enumerate tracked devices without
    # hardcoding them (HEA-55); a natural home for future house-level sensors too.
    async_add_entities(
        [
            HeaDevicesSensor(
                coordinator,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, entry.entry_id)},
                    translation_key="hub",
                ),
            )
        ]
    )

    # A normal device (like the real tracked devices) whose display name is set by
    # the "untracked" translation key. It reads as a genuine entry rather than a
    # placeholder; the name — not a service-device flag — is what keeps it from
    # looking like a setup error (HEA-44).
    untracked_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{_UNTRACKED_KEY}")},
        translation_key="untracked",
    )
    async_add_entities(
        HeaCostSensor(
            coordinator,
            concept,
            device_key=_UNTRACKED_KEY,
            device_info=untracked_info,
            currency=currency,
        )
        for concept in _concepts_for(_UNTRACKED_KEY)
    )

    # The whole-home aggregate: the monotonic total the derived split rolls up to
    # (Σ devices + Untracked). A device of its own, carrying lifetime running totals
    # only — its period figures are derivable and duplicate the Energy Dashboard, so
    # it is excluded from cycle metering (HEA-48).
    whole_home_info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{_WHOLE_HOME_KEY}")},
        translation_key="whole_home",
    )
    async_add_entities(
        HeaCostSensor(
            coordinator,
            concept,
            device_key=_WHOLE_HOME_KEY,
            device_info=whole_home_info,
            currency=currency,
        )
        for concept in _concepts_for(_WHOLE_HOME_KEY)
    )

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_DEVICE:
            continue
        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{subentry_id}")},
            name=subentry.title,
        )
        async_add_entities(
            (
                HeaCostSensor(
                    coordinator,
                    concept,
                    device_key=subentry_id,
                    device_info=device_info,
                    currency=currency,
                )
                for concept in _CONCEPTS
            ),
            config_subentry_id=subentry_id,
        )


class HeaCostSensor(CoordinatorEntity["HeaCoordinator"], RestoreSensor):
    """One device's running figure: restored baseline plus the live total."""

    entity_description: HeaSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeaCoordinator,
        description: HeaSensorDescription,
        *,
        device_key: str,
        device_info: DeviceInfo,
        currency: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_key = device_key
        self._attr_device_info = device_info
        # The coordinator always has its config entry (passed to super().__init__).
        entry = cast("HeaConfigEntry", coordinator.config_entry)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_{device_key}_{description.key}"
        if description.device_class == SensorDeviceClass.MONETARY:
            self._attr_native_unit_of_measurement = currency
        self._quantum = Decimal(1).scaleb(-description.publish_precision)
        self._baseline = Decimal(0)

    async def async_added_to_hass(self) -> None:
        """Restore the pre-restart total as the baseline for the running figure."""
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, Decimal):
            self._baseline = last.native_value
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_RESET_TOTALS.format(entry_id=self._entry_id),
                self._handle_reset,
            )
        )

    @callback
    def _handle_reset(self) -> None:
        """Drop the restored baseline when the household's totals are rebased.

        The engine clears its running total in the same breath; the coordinator
        publishes straight after, so no state write is needed here (HEA-57).
        """
        self._baseline = Decimal(0)

    @property
    def native_value(self) -> Decimal:
        """The restored baseline plus the running total, rounded for publication.

        Rounding happens here and only here: an accumulator is kept at full
        Decimal precision (docs/CRITICAL_INSTRUCTIONS.md) and rounded when it is
        presented, and handing a value to Home Assistant *is* presentation — the
        state is recorded, roughly once a minute, for every HEA entity and every
        cycle meter mirroring one (HEA-59).

        Because this published state is also what a restart restores as the
        baseline, rounding bounds the error a restart can introduce to half an
        ulp — not cumulative within a run, and immaterial at 1 mWh. Rounding is
        half-even, so repeated restarts do not bias the total in either direction,
        and monotonic, so a `total_increasing` figure can never step backwards.
        """
        totals = self._device_totals()
        running = self.entity_description.value_fn(totals) if totals else Decimal(0)
        return (self._baseline + running).quantize(self._quantum)

    def _device_totals(self) -> DeviceTotals | None:
        data = self.coordinator.data
        if self._device_key == _UNTRACKED_KEY:
            return data.untracked
        if self._device_key == _WHOLE_HOME_KEY:
            return data.whole_home
        return data.devices.get(self._device_key)


class HeaDevicesSensor(CoordinatorEntity["HeaCoordinator"], SensorEntity):
    """The authoritative list of tracked devices, for dashboard lookups (HEA-55).

    State is the tracked-device count; the ``devices`` attribute is one row per
    tracked device plus the Untracked remainder, each carrying the device's entity
    slug (so a card can build ``sensor.<key>_<concept>``), its display name, its
    registry ``device_id``, and whether it is the Untracked remainder. Membership
    is the config subentries (so it follows device add/remove, which reload the
    entry); the names and slugs are resolved live from the registries.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "devices"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # The list can be long and rarely changes — keep it out of the recorder.
    _unrecorded_attributes = frozenset({"devices"})

    def __init__(self, coordinator: HeaCoordinator, *, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_device_info = device_info
        entry = cast("HeaConfigEntry", coordinator.config_entry)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_devices"

    @property
    def native_value(self) -> int:
        """The number of tracked devices (the Untracked remainder is excluded)."""
        return sum(1 for device in self._devices() if not device["untracked"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The authoritative tracked-device list for dashboards to enumerate."""
        return {"devices": self._devices()}

    def _devices(self) -> list[dict[str, Any]]:
        entry = cast("HeaConfigEntry", self.coordinator.config_entry)
        rows = [
            self._row(subentry_id, subentry.title, untracked=False)
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_TYPE_DEVICE
        ]
        rows.append(self._row(_UNTRACKED_KEY, None, untracked=True))
        rows.sort(key=lambda device: device["key"])
        return rows

    def _row(
        self, device_key: str, fallback_name: str | None, *, untracked: bool
    ) -> dict[str, Any]:
        device = dr.async_get(self.hass).async_get_device(
            identifiers={(DOMAIN, f"{self._entry_id}_{device_key}")}
        )
        # Derive the slug from the device's own Actual Cost entity so it matches
        # the real entity ids exactly (HA de-duplication, user renames), rather
        # than guessing it from the name; fall back to the name only in the brief
        # window before that entity has registered.
        actual_cost_id = er.async_get(self.hass).async_get_entity_id(
            "sensor", DOMAIN, f"{self._entry_id}_{device_key}_actual_cost"
        )
        key = (
            actual_cost_id.removeprefix("sensor.").removesuffix("_actual_cost")
            if actual_cost_id is not None
            else slugify(fallback_name or device_key)
        )
        name = (device and (device.name_by_user or device.name)) or fallback_name or key
        return {
            "key": key,
            "name": name,
            "device_id": device.id if device is not None else None,
            "untracked": untracked,
        }
