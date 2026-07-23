"""Per-device cost sensors — the four figures ADR-0003 fixes.

For every tracked device and the Untracked remainder this platform publishes
Energy Used, Actual Cost, Cost Without Solar and Cost Savings, grouped one Home
Assistant device per tracked device. The identities here (``unique_id``,
``device_class``, ``state_class``, ``translation_key``, unit) are effectively
permanent — changing them after release orphans long-term statistics — so they
follow ADR-0003 exactly.

The accounting runtime keeps *since-startup* running totals and resets to zero on
restart (see ``engine/accountant.py``). Each sensor is therefore a
``RestoreSensor``: on startup it restores its last published value as a baseline
and adds the runtime's running total on top, so ``total_increasing`` stays
continuous across restarts without the engine persisting anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CURRENCY, DEFAULT_CURRENCY, DOMAIN, SUBENTRY_TYPE_DEVICE

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import HeaConfigEntry, HeaCoordinator
    from .engine.accountant import DeviceTotals

# Device key for the Untracked remainder; real devices are keyed by subentry id
# (a UUID), so this literal cannot collide with one.
_UNTRACKED_KEY = "untracked"


@dataclass(frozen=True, kw_only=True)
class HeaSensorDescription(SensorEntityDescription):
    """A cost-sensor concept plus how to read it from a device's totals."""

    value_fn: Callable[[DeviceTotals], Decimal]


_CONCEPTS: tuple[HeaSensorDescription, ...] = (
    HeaSensorDescription(
        key="energy_used",
        translation_key="energy_used",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda totals: totals.energy_kwh,
    ),
    HeaSensorDescription(
        key="actual_cost",
        translation_key="actual_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda totals: totals.actual_cost,
    ),
    HeaSensorDescription(
        key="cost_without_solar",
        translation_key="cost_without_solar",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda totals: totals.naive_cost,
    ),
    HeaSensorDescription(
        key="cost_savings",
        translation_key="cost_savings",
        device_class=SensorDeviceClass.MONETARY,
        # `total`, not `total_increasing`: battery arbitrage can make a period's
        # saving negative, and the lifetime accumulator dip with it (ADR-0003).
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda totals: totals.cost_savings,
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
        for concept in _CONCEPTS
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
        self._attr_unique_id = f"{entry.entry_id}_{device_key}_{description.key}"
        if description.device_class == SensorDeviceClass.MONETARY:
            self._attr_native_unit_of_measurement = currency
        self._baseline = Decimal(0)

    async def async_added_to_hass(self) -> None:
        """Restore the pre-restart total as the baseline for the running figure."""
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, Decimal):
            self._baseline = last.native_value

    @property
    def native_value(self) -> Decimal:
        """The restored baseline plus the runtime's since-startup running total."""
        totals = self._device_totals()
        running = self.entity_description.value_fn(totals) if totals else Decimal(0)
        return self._baseline + running

    def _device_totals(self) -> DeviceTotals | None:
        data = self.coordinator.data
        if self._device_key == _UNTRACKED_KEY:
            return data.untracked
        return data.devices.get(self._device_key)
