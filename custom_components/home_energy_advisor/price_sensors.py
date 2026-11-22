"""The price sensors this integration provides for the household (ADR-0048).

Created only where the household ticks "Provide my price sensors" on its current
plan. Each follows the typed plan of the period in force today: its band's price
at this local hour, a public holiday priced as the plan prices holidays, or a
market plan's market price adjusted as the plan adjusts it. The next period
takes over from the start of its day.

They read the plans as they stand on every update, so editing a plan changes
them at once, with no reload (HEA-255). A plan with an allowance charges by how
much has been used, which they cannot follow yet, so it feeds no price (HEA-309).

The daily charge comes as a running cost and a meter rising 0.001 kWh a day, so
the Energy Dashboard can carry it as a grid source of its own while adding next
to nothing to the grid totals. Both build up hour by hour over each real day, a
23- or 25-hour day charging exactly one day's charge, and carry on across a
restart, catching up the hours missed, never starting again from zero.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .current_plan import plan_on
from .engine.plan_schedule import export_price_at, follows_the_clock, import_price_at
from .plan_comparison import async_holidays, price_per_kwh

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo

    from .tariff_plans import TariffPlan

IMPORT_PRICE = "import_price"
EXPORT_PRICE = "export_price"
DAILY_CHARGE_COST = "daily_charge_cost"
DAILY_CHARGE_METER = "daily_charge_meter"
_KEYS = (IMPORT_PRICE, EXPORT_PRICE, DAILY_CHARGE_COST, DAILY_CHARGE_METER)
# What the meter rises a day: next to nothing in the grid totals.
_METER_KWH_A_DAY = Decimal("0.001")
_ACCRUED_UNTIL = "accrued_until"


def _unique_id(entry: ConfigEntry, key: str) -> str:
    return f"{entry.entry_id}_current_plan_{key}"


def price_sensors(
    entry: ConfigEntry, currency: str, device_info: DeviceInfo
) -> list[SensorEntity]:
    """The price and daily charge sensors, for a household that asked for them."""
    return [
        CurrentPlanPrice(entry, IMPORT_PRICE, currency, device_info),
        CurrentPlanPrice(entry, EXPORT_PRICE, currency, device_info),
        DailyChargeCost(entry, currency, device_info),
        DailyChargeMeter(entry, device_info),
    ]


@callback
def forget_price_sensors(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the price sensors of a household that no longer asks for them.

    Removed rather than left unavailable, which would read as a fault.
    """
    registry = er.async_get(hass)
    for key in _KEYS:
        if entity_id := registry.async_get_entity_id(
            "sensor", DOMAIN, _unique_id(entry, key)
        ):
            registry.async_remove(entity_id)


class CurrentPlanPrice(SensorEntity):
    """The price per kWh of the plan the household is on now, import or export.

    Recorded as a mean, as the Energy Dashboard reads a price. Unavailable while
    no period has started yet, or its plan cannot be read by the clock.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4

    def __init__(
        self, entry: ConfigEntry, key: str, currency: str, device_info: DeviceInfo
    ) -> None:
        """One of the current plan's prices."""
        self._entry = entry
        self._key = key
        self._attr_translation_key = f"current_plan_{key}"
        self._attr_unique_id = _unique_id(entry, key)
        self._attr_native_unit_of_measurement = f"{currency}/kWh"
        self._attr_device_info = device_info
        self._attr_available = False
        self._holidays: tuple[str, date, frozenset[date]] | None = None
        self._market: str | None = None
        self._unfollow_market: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Follow the clock at every hour, and the entry as it is edited."""
        self.async_on_remove(
            async_track_time_change(self.hass, self._at_the_hour, minute=0, second=0)
        )
        self.async_on_remove(self._entry.add_update_listener(self._entry_changed))
        self.async_on_remove(self._stop_following_the_market)
        await self._refresh()

    async def _at_the_hour(self, _now: datetime) -> None:
        await self._refresh()

    async def _entry_changed(self, _hass: HomeAssistant, _entry: ConfigEntry) -> None:
        await self._refresh()

    async def _refresh(self) -> None:
        now = dt_util.now()
        tariff = plan_on(self._entry, now.date())
        if tariff is None or not follows_the_clock(tariff.plan):
            self._follow_market(None)
            self._attr_available = False
            self.async_write_ha_state()
            return
        market = (
            tariff.import_entity if self._key == IMPORT_PRICE else tariff.export_entity
        )
        self._follow_market(market)
        if market:
            self._set_market_price(tariff, market)
        else:
            holidays = await self._holidays_on(tariff, now.date())
            at = import_price_at if self._key == IMPORT_PRICE else export_price_at
            self._set(at(tariff.plan, now, holidays))
        self.async_write_ha_state()

    def _set(self, price: Decimal | None) -> None:
        if price is None:
            self._attr_available = False
            return
        self._attr_native_value = float(price)
        self._attr_available = True

    def _set_market_price(self, tariff: TariffPlan, market: str) -> None:
        """The market's price, adjusted as the plan adjusts it.

        A missing one keeps the last, as a zero would be taken as a real price.
        """
        state = self.hass.states.get(market)
        try:
            raw = Decimal(state.state) if state is not None else None
        except InvalidOperation:
            raw = None
        if raw is None:
            return
        price = raw * price_per_kwh(self.hass, market)
        adjustment = (
            tariff.plan.import_adjustment
            if self._key == IMPORT_PRICE
            else tariff.plan.export_adjustment
        )
        self._set(adjustment.apply(price))

    def _follow_market(self, market: str | None) -> None:
        if market == self._market:
            return
        self._stop_following_the_market()
        self._market = market
        if market:
            self._unfollow_market = async_track_state_change_event(
                self.hass, market, self._market_changed
            )

    @callback
    def _stop_following_the_market(self) -> None:
        if self._unfollow_market is not None:
            self._unfollow_market()
            self._unfollow_market = None

    @callback
    def _market_changed(self, _event: Event[EventStateChangedData]) -> None:
        tariff = plan_on(self._entry, dt_util.now().date())
        if tariff is not None and self._market:
            self._set_market_price(tariff, self._market)
            self.async_write_ha_state()

    async def _holidays_on(self, tariff: TariffPlan, day: date) -> frozenset[date]:
        """Today's holidays in the plan's calendar, asked once a day."""
        if not tariff.holidays:
            return frozenset()
        if self._holidays and self._holidays[:2] == (tariff.holidays, day):
            return self._holidays[2]
        start = dt_util.start_of_local_day(day)
        found = await async_holidays(
            self.hass, tariff.holidays, start, start + timedelta(days=1)
        )
        self._holidays = (tariff.holidays, day, found)
        return found


class _DailyAccrual(RestoreSensor):
    """A running total that rises by `_per_day` over each local day, by the hour.

    Each stretch of a day adds its share of that day's amount, the share taken
    over the day's real length, so a day of 23 or 25 hours adds exactly one day.
    The total and the moment it was built up to are restored after a restart,
    and the hours since are caught up: never reset, never counted twice.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str, device_info: DeviceInfo) -> None:
        """One of the daily charge's running totals."""
        self._entry = entry
        self._attr_translation_key = f"current_plan_{key}"
        self._attr_unique_id = _unique_id(entry, key)
        self._attr_device_info = device_info
        self._total = Decimal(0)
        self._until: datetime | None = None

    def _per_day(self, day: date) -> Decimal | None:
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Carry on from what was restored, then rise at every hour."""
        last = await self.async_get_last_state()
        if last is not None and last.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            until = dt_util.parse_datetime(str(last.attributes.get(_ACCRUED_UNTIL)))
            try:
                total = Decimal(last.state)
            except InvalidOperation:
                total = None
            if total is not None and until is not None:
                self._total, self._until = total, until
        self.async_on_remove(
            async_track_time_change(self.hass, self._at_the_hour, minute=0, second=0)
        )
        self.async_on_remove(self._entry.add_update_listener(self._entry_changed))
        self._accrue(dt_util.now())

    @callback
    def _at_the_hour(self, now: datetime) -> None:
        # The hour itself: the callback can arrive a moment after it.
        self._accrue(now.replace(minute=0, second=0, microsecond=0))

    async def _entry_changed(self, _hass: HomeAssistant, _entry: ConfigEntry) -> None:
        self._accrue(dt_util.now())

    @callback
    def _accrue(self, now: datetime) -> None:
        moment = self._until or now
        while moment < now:
            day = dt_util.as_local(moment).date()
            start = dt_util.start_of_local_day(day)
            next_day = dt_util.start_of_local_day(day + timedelta(days=1))
            end = min(now, next_day)
            if (amount := self._per_day(day)) is not None:
                share = Decimal(str((end - moment).total_seconds())) / Decimal(
                    str((next_day - start).total_seconds())
                )
                self._total += amount * share
            moment = end
        self._until = max(now, self._until or now)
        self._attr_native_value = float(self._total)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The moment the total is built up to, which a restart carries on from."""
        return {_ACCRUED_UNTIL: self._until.isoformat()} if self._until else {}


class DailyChargeCost(_DailyAccrual):
    """What the plan the household is on has charged by the day, in money.

    The Energy Dashboard takes it as the cost of the daily charge meter's grid
    source. The rate in force today is shown beside it.
    """

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    def __init__(
        self, entry: ConfigEntry, currency: str, device_info: DeviceInfo
    ) -> None:
        """The daily charge's running cost."""
        super().__init__(entry, DAILY_CHARGE_COST, device_info)
        self._attr_native_unit_of_measurement = currency

    def _per_day(self, day: date) -> Decimal | None:
        tariff = plan_on(self._entry, day)
        return tariff.plan.daily_charge if tariff is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Also the daily charge in force today, where a plan is."""
        rate = self._per_day(dt_util.now().date())
        return super().extra_state_attributes | (
            {"daily_charge": float(rate)} if rate is not None else {}
        )


class DailyChargeMeter(_DailyAccrual):
    """A meter rising 0.001 kWh a day, for the daily charge's grid source.

    The Energy Dashboard needs energy to hang a cost on; this adds next to
    nothing to the grid totals, never resets, and rises whether or not a plan
    is in force.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 3

    def __init__(self, entry: ConfigEntry, device_info: DeviceInfo) -> None:
        """The daily charge's meter."""
        super().__init__(entry, DAILY_CHARGE_METER, device_info)

    def _per_day(self, day: date) -> Decimal | None:  # noqa: ARG002 - every day alike
        return _METER_KWH_A_DAY
