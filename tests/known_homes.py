"""The known homes every change is tested against (HEA-316).

Each is an invented home with the shape of one met in a discussion: which price
sensors it has and whether they keep statistics, which kinds of plan it weighs,
what its current plan held under the last release. Never a household's names,
prices or recorded data (docs/CRITICAL_INSTRUCTIONS.md, Privacy).

Code right for the reference home and wrong for one shaped differently broke
real installs twice: a freeze on a home with years of statistics (HEA-310), and
the current plan unpriced where price sensors kept no statistics (HEA-311).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_NAME
from homeassistant.core import ServiceCall, ServiceResponse, SupportsResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_energy_advisor.const import (
    CONF_BAND_DAYS,
    CONF_BAND_END,
    CONF_BAND_IMPORT_PRICE,
    CONF_BAND_START,
    CONF_BANDS,
    CONF_CURRENCY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_HOUSE_CONSUMPTION_ENTITY,
    CONF_PLAN_DAILY_CHARGE,
    CONF_PLAN_DAILY_CHARGE_ENTITY,
    CONF_PLAN_DEMAND_CHARGE_ENTITY,
    CONF_PLAN_EXPORT_CAP,
    CONF_PLAN_EXPORT_PRICE,
    CONF_PLAN_EXPORT_PRICE_ENTITY,
    CONF_PLAN_FOLLOWS,
    CONF_PLAN_HOLIDAYS,
    CONF_PLAN_IMPORT_PRICE_ADD,
    CONF_PLAN_IMPORT_PRICE_ENTITY,
    CONF_PRICE_ENTITY,
    DOMAIN,
    SUBENTRY_TYPE_GRID,
    SUBENTRY_TYPE_PLAN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CURRENT = "current"
_GRID_IMPORT = "sensor.grid_import"
_GRID_EXPORT = "sensor.grid_export"


@dataclass(frozen=True)
class KnownHome:
    """One shape of home, as an invented household with that shape.

    `prices` are the price sensors that keep statistics, each hour's mean by
    local hour of the recorded day; `without_statistics` exist with no state
    class, so keep none. `current` is the current plan as the last release
    stored it, to be upgraded on setup.
    """

    name: str
    time_zone: str
    currency: str
    grid: dict[str, Any]
    plans: dict[str, dict[str, Any]]
    current: dict[str, Any]
    imported: dict[int, float]
    exported: dict[int, float] = field(default_factory=dict)
    prices: dict[str, dict[int, float]] = field(default_factory=dict)
    without_statistics: tuple[str, ...] = ()
    export_price_entity: str | None = None
    # A sensor giving the daily charge per day, each hour's mean by local hour.
    daily_charges: dict[int, float] = field(default_factory=dict)
    # A sensor giving a demand or capacity charge per day, the same way.
    demand_charges: dict[int, float] = field(default_factory=dict)
    # The house's own settings, beside its currency: its house meter, say.
    house: dict[str, Any] = field(default_factory=dict)
    # What the home should see.
    periods_after_upgrade: list[dict[str, str]] = field(default_factory=list)
    current_lacks: list[str] = field(default_factory=list)
    left_out: bool = False
    current_daily_rate: float | None = None
    demand_rate: float | None = None

    @property
    def day(self) -> datetime:
        """The recorded day, a Wednesday, from local midnight."""
        return datetime(2026, 10, 14, tzinfo=ZoneInfo(self.time_zone))


def _flat(name: str, price: float, daily: float, export: float) -> dict[str, Any]:
    return {
        CONF_NAME: name,
        CONF_PLAN_DAILY_CHARGE: daily,
        CONF_PLAN_EXPORT_PRICE: export,
        CONF_BANDS: [
            {
                CONF_BAND_DAYS: "every_day",
                CONF_BAND_START: 0,
                CONF_BAND_END: 24,
                CONF_BAND_IMPORT_PRICE: price,
            }
        ],
    }


def _all_day(price: float) -> dict[int, float]:
    return dict.fromkeys(range(24), price)


# The reference home's shape: a time-of-use price sensor with statistics, the
# Energy Dashboard's export price, banded plans with public holidays, and the
# current plan as 1.7.1 left it, reading its price history from one plan.
SPANISH_TIME_OF_USE = KnownHome(
    name="spanish_time_of_use",
    time_zone="Europe/Madrid",
    currency="EUR",
    grid={
        CONF_NAME: "Grid",
        CONF_GRID_IMPORT_ENTITY: _GRID_IMPORT,
        CONF_GRID_EXPORT_ENTITY: _GRID_EXPORT,
        CONF_PRICE_ENTITY: "sensor.time_of_use_price",
    },
    plans={
        "three_periods": {
            CONF_NAME: "Three periods",
            CONF_PLAN_DAILY_CHARGE: 1.47,
            CONF_PLAN_EXPORT_PRICE: 0.05,
            CONF_PLAN_EXPORT_CAP: "monthly",
            CONF_PLAN_HOLIDAYS: "calendar.public_holidays",
            CONF_BANDS: [
                {
                    CONF_BAND_DAYS: "weekdays",
                    CONF_BAND_START: 8,
                    CONF_BAND_END: 22,
                    CONF_BAND_IMPORT_PRICE: 0.245,
                },
                {
                    CONF_BAND_DAYS: "weekdays",
                    CONF_BAND_START: 22,
                    CONF_BAND_END: 8,
                    CONF_BAND_IMPORT_PRICE: 0.098,
                },
                {
                    CONF_BAND_DAYS: "rest_days",
                    CONF_BAND_START: 0,
                    CONF_BAND_END: 24,
                    CONF_BAND_IMPORT_PRICE: 0.098,
                },
            ],
        },
        "flat_offer": _flat("Flat offer", 0.18, 2.27, 0.089),
    },
    current={
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 1.47,
        CONF_PLAN_EXPORT_CAP: "carried",
        "price_history_from": "three_periods",
    },
    imported={7: 1.0, 12: 0.5, 20: 1.0},
    exported={12: 2.0},
    prices={
        "sensor.time_of_use_price": {
            hour: 0.245 if 8 <= hour < 22 else 0.098 for hour in range(24)
        },
        "sensor.export_price": _all_day(0.05),
    },
    export_price_entity="sensor.export_price",
    periods_after_upgrade=[{"plan": "three_periods"}],
)

# Discussion 58's first home: grid and export price sensors with no state class,
# so no statistics; plans importing and exporting at market sensors; and the
# current plan answered under 1.7.0, with no plan for its price history.
AUSTRALIAN_MARKET = KnownHome(
    name="australian_market",
    time_zone="Australia/Sydney",
    currency="AUD",
    grid={
        CONF_NAME: "Grid",
        CONF_GRID_IMPORT_ENTITY: _GRID_IMPORT,
        CONF_GRID_EXPORT_ENTITY: _GRID_EXPORT,
        CONF_PRICE_ENTITY: "sensor.grid_buy_price",
    },
    plans={
        "wholesale_a": {
            CONF_NAME: "Wholesale A",
            CONF_PLAN_DAILY_CHARGE: 1.1,
            CONF_PLAN_EXPORT_PRICE: 0.0,
            CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.market_import",
            CONF_PLAN_EXPORT_PRICE_ENTITY: "sensor.market_export",
        },
        "wholesale_b": {
            CONF_NAME: "Wholesale B",
            CONF_PLAN_DAILY_CHARGE: 0.95,
            CONF_PLAN_EXPORT_PRICE: 0.0,
            CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.market_import",
            CONF_PLAN_IMPORT_PRICE_ADD: 0.02,
            CONF_PLAN_EXPORT_PRICE_ENTITY: "sensor.market_export",
        },
        "flat_retail": _flat("Flat retail", 0.31, 1.2, 0.04),
    },
    current={
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 1.1,
        CONF_PLAN_EXPORT_CAP: "none",
    },
    imported={7: 1.5, 18: 2.0},
    exported={11: 4.0, 13: 3.0},
    prices={
        "sensor.market_import": _all_day(0.21),
        "sensor.market_export": _all_day(0.03),
    },
    without_statistics=("sensor.grid_buy_price", "sensor.grid_sell_price"),
    export_price_entity="sensor.grid_sell_price",
    current_lacks=["sensor.grid_buy_price", "sensor.grid_sell_price"],
)

# Discussion 58's second home: the grid meter's price sensor recorded from
# midday only, and followed also by a market plan; no export price in the Energy
# Dashboard; the current plan answered, with no plan for its price history.
AUSTRALIAN_SHARED_SENSOR = KnownHome(
    name="australian_shared_sensor",
    time_zone="Australia/Perth",
    currency="AUD",
    grid={
        CONF_NAME: "Grid",
        CONF_GRID_IMPORT_ENTITY: _GRID_IMPORT,
        CONF_GRID_EXPORT_ENTITY: _GRID_EXPORT,
        CONF_PRICE_ENTITY: "sensor.electricity_price",
    },
    plans={
        "ev_add_on": {
            CONF_NAME: "EV add-on",
            CONF_PLAN_DAILY_CHARGE: 1.3,
            CONF_PLAN_EXPORT_PRICE: 0.02,
            CONF_PLAN_IMPORT_PRICE_ENTITY: "sensor.electricity_price",
        },
        "home_plan": _flat("Home plan", 0.32, 1.15, 0.02),
    },
    current={
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 1.15,
        CONF_PLAN_EXPORT_CAP: "none",
    },
    imported={7: 1.0, 14: 0.5, 19: 1.5},
    exported={12: 3.0},
    prices={"sensor.electricity_price": dict.fromkeys(range(12, 24), 0.30)},
    # Shared with a typed plan, so the morning the sensor has no statistics is
    # left out for every plan (ADR-0043).
    left_out=True,
)

# Discussion 55's home: the grid alone, priced by a sensor; no generation,
# battery or export; no plans entered beside the current one.
GRID_ONLY = KnownHome(
    name="grid_only",
    time_zone="Pacific/Auckland",
    currency="NZD",
    grid={
        CONF_NAME: "Grid",
        CONF_GRID_IMPORT_ENTITY: _GRID_IMPORT,
        CONF_PRICE_ENTITY: "sensor.power_price",
    },
    plans={},
    current={
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 2.86,
        CONF_PLAN_EXPORT_CAP: "none",
    },
    imported={7: 1.2, 12: 0.8, 19: 2.0},
    prices={"sensor.power_price": _all_day(0.27)},
)

# Discussion 65's home: the same, its daily charge followed from a sensor its
# supplier's integration publishes, which changed at midday (HEA-317).
DAILY_CHARGE_SENSOR = "sensor.daily_charge"
GRID_ONLY_DAILY_CHARGE_SENSOR = KnownHome(
    name="grid_only_daily_charge_sensor",
    time_zone="Pacific/Auckland",
    currency="NZD",
    grid=GRID_ONLY.grid,
    plans={},
    current={
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE_ENTITY: DAILY_CHARGE_SENSOR,
        CONF_PLAN_EXPORT_CAP: "none",
    },
    imported=GRID_ONLY.imported,
    prices=GRID_ONLY.prices,
    daily_charges={hour: 2.70 if hour < 12 else 3.02 for hour in range(24)},
    current_daily_rate=2.86,
)

# GitHub 66's home: the same, its grid meter named as its house consumption
# too, since on the grid alone they are the same energy.
GRID_ONLY_HOUSE_IS_GRID = KnownHome(
    name="grid_only_house_is_grid",
    time_zone="Pacific/Auckland",
    currency="NZD",
    grid=GRID_ONLY.grid,
    plans={},
    current=GRID_ONLY.current,
    imported=GRID_ONLY.imported,
    prices=GRID_ONLY.prices,
    house={CONF_HOUSE_CONSUMPTION_ENTITY: _GRID_IMPORT},
)

# Discussion 67's home: a capacity charge on the measured monthly peak, worked
# out per day by the household's own template, on its current plan and on one
# offer but not the other; export priced by the Energy Dashboard (HEA-322).
DEMAND_CHARGE_SENSOR = "sensor.capacity_charge_per_day"
CAPACITY_CHARGE = KnownHome(
    name="capacity_charge",
    time_zone="Europe/Brussels",
    currency="EUR",
    grid={
        CONF_NAME: "Grid",
        CONF_GRID_IMPORT_ENTITY: _GRID_IMPORT,
        CONF_GRID_EXPORT_ENTITY: _GRID_EXPORT,
        CONF_PRICE_ENTITY: "sensor.dynamic_price",
    },
    plans={
        "fixed_offer": {
            **_flat("Fixed offer", 0.29, 0.31, 0.03),
            CONF_PLAN_DEMAND_CHARGE_ENTITY: DEMAND_CHARGE_SENSOR,
        },
        "offer_without_it": _flat("Offer without it", 0.27, 0.31, 0.02),
    },
    current={
        CONF_NAME: "Your current plan",
        CONF_PLAN_FOLLOWS: True,
        CONF_PLAN_DAILY_CHARGE: 0.31,
        CONF_PLAN_DEMAND_CHARGE_ENTITY: DEMAND_CHARGE_SENSOR,
        CONF_PLAN_EXPORT_CAP: "none",
    },
    imported={7: 0.8, 18: 1.6, 21: 0.6},
    exported={13: 2.4},
    prices={"sensor.dynamic_price": _all_day(0.26)},
    demand_charges=_all_day(0.47),
    demand_rate=0.47,
)

KNOWN_HOMES = (
    SPANISH_TIME_OF_USE,
    AUSTRALIAN_MARKET,
    AUSTRALIAN_SHARED_SENSOR,
    GRID_ONLY,
    GRID_ONLY_DAILY_CHARGE_SENSOR,
    GRID_ONLY_HOUSE_IS_GRID,
    CAPACITY_CHARGE,
)


def entry_of(home: KnownHome) -> MockConfigEntry:
    """The home's config entry, as the last release stored it."""
    subentries = [
        ConfigSubentryDataWithId(
            subentry_id="grid",
            subentry_type=SUBENTRY_TYPE_GRID,
            title=home.grid[CONF_NAME],
            data=home.grid,
            unique_id=None,
        ),
        *(
            ConfigSubentryDataWithId(
                subentry_id=plan_id,
                subentry_type=SUBENTRY_TYPE_PLAN,
                title=plan[CONF_NAME],
                data=plan,
                unique_id=None,
            )
            for plan_id, plan in home.plans.items()
        ),
        ConfigSubentryDataWithId(
            subentry_id=CURRENT,
            subentry_type=SUBENTRY_TYPE_PLAN,
            title=home.current[CONF_NAME],
            data=home.current,
            unique_id=None,
        ),
    ]
    return MockConfigEntry(
        domain=DOMAIN,
        version=8,
        data={CONF_CURRENCY: home.currency, **home.house},
        subentries_data=subentries,
    )


async def record(hass: HomeAssistant, home: KnownHome) -> None:
    """The home's recorded day, its Energy Dashboard, and its calendar."""
    await hass.config.async_set_time_zone(home.time_zone)
    _record_meter(hass, home, _GRID_IMPORT, home.imported)
    if CONF_GRID_EXPORT_ENTITY in home.grid:
        _record_meter(hass, home, _GRID_EXPORT, home.exported)
    unit = f"{home.currency}/kWh"
    for entity, hours in home.prices.items():
        _record_prices(hass, home, entity, hours, unit)
    if home.daily_charges:
        _record_prices(
            hass, home, DAILY_CHARGE_SENSOR, home.daily_charges, f"{home.currency}/day"
        )
    if home.demand_charges:
        per_day = f"{home.currency}/day"
        _record_prices(hass, home, DEMAND_CHARGE_SENSOR, home.demand_charges, per_day)
    for entity in home.without_statistics:
        # No state class: Home Assistant keeps no statistics for it.
        hass.states.async_set(entity, "0.3", {"unit_of_measurement": unit})
    await _energy_dashboard(hass, home)
    _no_holidays(hass)


def _record_meter(
    hass: HomeAssistant, home: KnownHome, statistic_id: str, hours: dict[int, float]
) -> None:
    total = 0.0
    rows = []
    for hour in range(24):
        total += hours.get(hour, 0.0)
        start = (home.day + timedelta(hours=hour)).astimezone(UTC)
        rows.append(StatisticData(start=start, state=total, sum=total))
    async_import_statistics(
        hass,
        StatisticMetaData(
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=None,
            source="recorder",
            statistic_id=statistic_id,
            unit_class="energy",
            unit_of_measurement="kWh",
        ),
        rows,
    )


def _record_prices(
    hass: HomeAssistant,
    home: KnownHome,
    statistic_id: str,
    hours: dict[int, float],
    unit: str,
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
            StatisticData(
                start=(home.day + timedelta(hours=hour)).astimezone(UTC),
                mean=price,
                min=price,
                max=price,
            )
            for hour, price in hours.items()
        ],
    )
    hass.states.async_set(statistic_id, "0", {"unit_of_measurement": unit})


async def _energy_dashboard(hass: HomeAssistant, home: KnownHome) -> None:
    source: dict[str, Any] = {"type": "grid", "stat_energy_from": _GRID_IMPORT}
    if CONF_GRID_EXPORT_ENTITY in home.grid:
        source["stat_energy_to"] = _GRID_EXPORT
        source["entity_energy_price_export"] = home.export_price_entity
        source["number_energy_price_export"] = None
    manager = await async_get_manager(hass)
    update: Any = {"energy_sources": [source]}
    await manager.async_update(update)
    await hass.async_block_till_done()


def _no_holidays(hass: HomeAssistant) -> None:
    """A calendar with no public holiday on the recorded day."""

    async def get_events(call: ServiceCall) -> ServiceResponse:
        asked = call.data["entity_id"]
        entity_ids = [asked] if isinstance(asked, str) else asked
        return {entity_id: {"events": []} for entity_id in entity_ids}

    hass.services.async_register(
        "calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY
    )
