"""Several batteries, accounted as one pool, each with its share of the loss.

Home Assistant's Energy Dashboard holds each battery as its own battery system
and weights their levels by capacity into one state of charge. The engine does
the same: the batteries' meters add up into the house balance, their contents
add up into one level, there is one stored-cost ledger, and the loss is measured
for the pool exactly as it is for one battery (ADR-0031).

What one battery cannot need is a share. With two or more, each published loss
is split across them by their own bound since the measurement's anchor - charge
less discharge less gain, every term from that battery's own meters and level -
and priced at the pool's cost. It is an apportionment of a measured figure, not a
measurement of its own.

The scenario is the single-battery loss test's (HEA-182) with the charge divided
between two batteries, so the pooled figure has to come out the same.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)
from custom_components.home_energy_advisor.engine.battery_shares import BatteryMeters

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
OVERNIGHT = Decimal("0.093")
# What export pays throughout. Grid charge forgoes none of it, so the figures the
# scenario was written for are unchanged by it (ADR-0027).
EXPORT = Decimal("0.10")
# How long a loss has to have been allowed before it is published (HEA-213).
A_DAY = timedelta(hours=24)

TWO_BATTERIES = {
    "anker": BatteryMeters(
        charge=("sensor.anker_charge",), discharge=("sensor.anker_discharge",)
    ),
    "growatt": BatteryMeters(
        charge=("sensor.growatt_charge",), discharge=("sensor.growatt_discharge",)
    ),
}
ONE_BATTERY = {"anker": TWO_BATTERIES["anker"]}


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _q(value: Decimal) -> Decimal:
    """To a billionth, past the engine's division residue in the 27th place."""
    return value.quantize(Decimal("1e-9"))


def _home(batteries: dict[str, BatteryMeters]) -> Accountant:
    """A fully metered house whose battery meters are those of `batteries`."""
    acc = Accountant(
        house_sources=_house_sources(batteries),
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
        batteries=batteries,
    )
    acc.record_price(at(0), OVERNIGHT)
    acc.record_export_price(at(0), EXPORT)
    for meter in _meters(batteries):
        acc.observe(meter, at(0), Decimal(0))
    acc.finalize(at(40))
    return acc


def _meters(batteries: dict[str, BatteryMeters]) -> list[str]:
    house = [
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.generation",
        "sensor.house_load",
    ]
    return house + [
        meter
        for battery in batteries.values()
        for meter in (*battery.charge, *battery.discharge)
    ]


def _observe(acc: Accountant, when: datetime, readings: dict[str, str]) -> None:
    for meter, value in readings.items():
        acc.observe(meter, when, Decimal(value))


def _baseline(
    acc: Accountant, *, anker: str, growatt: str | None, sunny: bool = False
) -> None:
    """4 kWh imported, 3 into one battery and 1 into the other, then a level.

    The first level only anchors the measurement, so nothing before it counts.
    `sunny` makes the same 4 kWh the panels' instead of the grid's.
    """
    supply = "sensor.generation" if sunny else "sensor.grid_import"
    readings = {supply: "4.0", "sensor.house_load": "1.0"}
    readings["sensor.anker_charge"] = "3.0" if growatt is not None else "4.0"
    if growatt is not None:
        readings["sensor.growatt_charge"] = "1.0"
    _observe(acc, at(45), readings)
    acc.finalize(at(85))
    _reconcile(acc, at(85), anker=anker, growatt=growatt)


def _span(acc: Accountant, *, two: bool, sunny: bool = False) -> None:
    """2 kWh more imported, all into the batteries, and 0.5 more used by the house.

    The house's meters cannot account for 1.5 kWh of that, and the pool gained
    1.2, so 0.3 went to heat - the single-battery test's figures exactly.
    `sunny` makes it generation, as in the baseline.
    """
    supply = "sensor.generation" if sunny else "sensor.grid_import"
    readings = {supply: "6.0", "sensor.house_load": "1.5"}
    if two:
        readings["sensor.anker_charge"] = "4.5"
        readings["sensor.growatt_charge"] = "1.5"
    else:
        readings["sensor.anker_charge"] = "6.0"
    _observe(acc, at(90), readings)
    acc.finalize(at(130))


def _reconcile(
    acc: Accountant, when: datetime, *, anker: str, growatt: str | None
) -> None:
    levels = {"anker": Decimal(anker)}
    if growatt is not None:
        levels["growatt"] = Decimal(growatt)
    acc.reconcile_battery(sum(levels.values(), Decimal(0)), when, levels=levels)


def _settle(acc: Accountant) -> None:
    """The span's levels, then again a day on, when the loss is published."""
    _reconcile(acc, at(130), anker="3.2", growatt="0.5")
    _reconcile(acc, at(130) + A_DAY, anker="3.2", growatt="0.5")


def test_the_pool_loses_what_one_battery_would() -> None:
    # Given / When - the charge split 1.5 / 0.5 between two batteries
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _settle(acc)

    # Then - the combined Battery Losses is the single-battery figure, priced at
    # the overnight rate every kWh in the pool was bought at
    battery = acc.totals().battery
    assert _q(battery.energy_kwh) == Decimal("0.300000000")
    assert _q(battery.actual_cost) == _q(Decimal("0.3") * OVERNIGHT)


def test_each_battery_takes_the_loss_its_own_meters_leave_room_for() -> None:
    # Given / When - one battery took 1.5 kWh and gained 1.2, the other took 0.5
    # and gained nothing. Their bounds are 0.3 and 0.5 of the pool's 0.8
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _settle(acc)

    # Then - the 0.3 kWh lost is split 3:5, each priced at the pool's cost
    shares = acc.totals().batteries
    assert _q(shares["anker"].energy_kwh) == Decimal("0.112500000")
    assert _q(shares["growatt"].energy_kwh) == Decimal("0.187500000")
    assert _q(shares["anker"].actual_cost) == _q(Decimal("0.1125") * OVERNIGHT)
    assert _q(shares["growatt"].actual_cost) == _q(Decimal("0.1875") * OVERNIGHT)
    # and a share is a loss that really was bought, so it shows no saving
    assert shares["anker"].naive_cost == shares["anker"].actual_cost
    assert shares["anker"].cost_savings == Decimal(0)


def test_a_household_with_one_battery_has_no_shares() -> None:
    # Given / When - the same span through a single battery
    acc = _home(ONE_BATTERY)
    _baseline(acc, anker="2.5", growatt=None)
    _span(acc, two=False)
    _reconcile(acc, at(130), anker="3.7", growatt=None)
    _reconcile(acc, at(130) + A_DAY, anker="3.7", growatt=None)

    # Then - its figures are exactly what they were, and nothing is split
    totals = acc.totals()
    assert _q(totals.battery.energy_kwh) == Decimal("0.300000000")
    assert totals.batteries == {}


def test_the_shares_survive_a_restart() -> None:
    # Given - a restart between the span and the day it is published on
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _reconcile(acc, at(130), anker="3.2", growatt="0.5")
    restarted = Accountant(
        house_sources=_house_sources(TWO_BATTERIES),
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
        batteries=TWO_BATTERIES,
    )
    restarted.restore(acc.snapshot())

    # When
    _reconcile(restarted, at(130) + A_DAY, anker="3.2", growatt="0.5")

    # Then - the same split as a run that never stopped
    shares = restarted.totals().batteries
    assert _q(shares["anker"].energy_kwh) == Decimal("0.112500000")
    assert _q(shares["growatt"].energy_kwh) == Decimal("0.187500000")


def test_an_upgraded_household_splits_evenly_until_it_can_say_more() -> None:
    # Given - a snapshot from before batteries were told apart, mid-span: the
    # pooled measurement is anchored, the split never was
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _reconcile(acc, at(130), anker="3.2", growatt="0.5")
    snapshot: dict[str, Any] = acc.snapshot()
    del snapshot["battery_shares"]
    restarted = Accountant(
        house_sources=_house_sources(TWO_BATTERIES),
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
        batteries=TWO_BATTERIES,
    )
    restarted.restore(snapshot)

    # When - the loss measured before the upgrade is published
    _reconcile(restarted, at(130) + A_DAY, anker="3.2", growatt="0.5")

    # Then - the pool is exactly right, and with nothing measured since the
    # split began, neither battery is blamed more than the other
    totals = restarted.totals()
    assert _q(totals.battery.energy_kwh) == Decimal("0.300000000")
    assert _q(totals.batteries["anker"].energy_kwh) == Decimal("0.150000000")
    assert _q(totals.batteries["growatt"].energy_kwh) == Decimal("0.150000000")


def test_reset_totals_rebases_each_batterys_share() -> None:
    # Given - shares already published
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _settle(acc)

    # When
    acc.reset_totals()

    # Then - each starts again with the combined figure
    totals = acc.totals()
    assert totals.battery.energy_kwh == Decimal(0)
    assert totals.batteries["anker"].energy_kwh == Decimal(0)
    assert totals.batteries["growatt"].energy_kwh == Decimal(0)


def _house_sources(batteries: dict[str, BatteryMeters]) -> dict[SourceRole, Any]:
    return {
        SourceRole.GRID_IMPORT: "sensor.grid_import",
        SourceRole.GRID_EXPORT: "sensor.grid_export",
        SourceRole.GENERATION: "sensor.generation",
        SourceRole.BATTERY_CHARGE: tuple(
            meter for battery in batteries.values() for meter in battery.charge
        ),
        SourceRole.BATTERY_DISCHARGE: tuple(
            meter for battery in batteries.values() for meter in battery.discharge
        ),
        SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
    }


def test_the_download_shows_each_batterys_bound_and_share() -> None:
    # Given / When - the split above
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _settle(acc)

    # Then - what each battery's meters carried, the bound its share was split
    # by, and the share, so a household can see why one battery lost more
    batteries = acc.battery_diagnostics()["batteries"]
    assert Decimal(batteries["anker"]["charged"]) == Decimal("4.5")
    assert Decimal(batteries["anker"]["bound_since_anchor"]) == Decimal("0.3")
    assert Decimal(batteries["growatt"]["bound_since_anchor"]) == Decimal("0.5")
    assert _q(Decimal(batteries["growatt"]["loss_kwh"])) == Decimal("0.187500000")


def test_the_download_of_a_single_battery_is_unchanged() -> None:
    # Given / When - one battery, which is the pool
    acc = _home(ONE_BATTERY)
    _baseline(acc, anker="2.5", growatt=None)

    # Then - nothing about shares appears
    assert "batteries" not in acc.battery_diagnostics()


def _a_sunny_loss(batteries: dict[str, BatteryMeters]) -> Accountant:
    """The same span charged by the panels, so every stored kWh gave up export."""
    acc = _home(batteries)
    two = len(batteries) > 1
    if two:
        _baseline(acc, anker="2.0", growatt="0.5", sunny=True)
        _span(acc, two=True, sunny=True)
        _settle(acc)
    else:
        _baseline(acc, anker="2.5", growatt=None, sunny=True)
        _span(acc, two=False, sunny=True)
        _reconcile(acc, at(130), anker="3.7", growatt=None)
        _reconcile(acc, at(130) + A_DAY, anker="3.7", growatt=None)
    return acc


def test_sunshine_lost_in_the_battery_could_have_been_earned() -> None:
    """HEA-229: the export a lost kWh gave up, at the blend it was stored at.

    The ledger already carries what its stored sunshine forwent (ADR-0027), and a
    loss takes its share of that out with its cost. Lost energy never reached a
    device, so before this the value left the books and nobody was shown it.
    """
    # Given / When - a battery charged only by the panels loses 0.3 kWh
    battery = _a_sunny_loss(ONE_BATTERY).totals().battery

    # Then - it was paid nothing for, and could have earned the export rate
    assert _q(battery.energy_kwh) == Decimal("0.300000000")
    assert _q(battery.actual_cost) == Decimal("0E-9")
    assert _q(battery.forgone_export) == _q(Decimal("0.3") * EXPORT)


def test_grid_charge_lost_in_the_battery_forgoes_nothing() -> None:
    # Given / When - the original scenario, charged from the grid with export
    # priced throughout
    acc = _home(TWO_BATTERIES)
    _baseline(acc, anker="2.0", growatt="0.5")
    _span(acc, two=True)
    _settle(acc)

    # Then - bought energy was bought: the loss cost money and gave up no export
    totals = acc.totals()
    assert _q(totals.battery.actual_cost) == _q(Decimal("0.3") * OVERNIGHT)
    assert totals.battery.forgone_export == Decimal(0)
    assert totals.batteries["anker"].forgone_export == Decimal(0)


def test_each_battery_could_have_earned_its_share() -> None:
    # Given / When - the sunny span split 3:5 between two batteries
    shares = _a_sunny_loss(TWO_BATTERIES).totals().batteries

    # Then - what was forgone follows the energy, as the cost does
    assert _q(shares["anker"].forgone_export) == _q(Decimal("0.1125") * EXPORT)
    assert _q(shares["growatt"].forgone_export) == _q(Decimal("0.1875") * EXPORT)


def test_what_the_loss_could_have_earned_reaches_the_whole_home() -> None:
    """Σ devices + Untracked + Battery Losses == Whole Home, for this figure too.

    The house used 1.5 kWh of sunshine directly, which Untracked carries as it
    always has; the 0.3 kWh lost is added to the whole home beside it, so the
    remainder is not moved by it.
    """
    # Given / When
    totals = _a_sunny_loss(TWO_BATTERIES).totals()

    # Then
    assert _q(totals.untracked.forgone_export) == _q(Decimal("1.5") * EXPORT)
    assert _q(totals.whole_home.forgone_export) == _q(Decimal("1.8") * EXPORT)


def test_what_a_loss_could_have_earned_survives_a_restart() -> None:
    # Given - a published sunny loss
    acc = _a_sunny_loss(TWO_BATTERIES)
    restarted = Accountant(
        house_sources=_house_sources(TWO_BATTERIES),
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
        batteries=TWO_BATTERIES,
    )

    # When
    restarted.restore(acc.snapshot())

    # Then - the pool and each share carry on from where they stood
    totals = restarted.totals()
    assert _q(totals.battery.forgone_export) == _q(Decimal("0.3") * EXPORT)
    assert _q(totals.batteries["growatt"].forgone_export) == _q(
        Decimal("0.1875") * EXPORT
    )


def test_a_snapshot_from_before_a_loss_could_have_earned_restores_as_nothing() -> None:
    # Given - a snapshot as 0.13.0b2 wrote it, with no forgone figure for the
    # loss or its shares
    acc = _a_sunny_loss(TWO_BATTERIES)
    snapshot: dict[str, Any] = acc.snapshot()
    del snapshot["battery_loss"]["forgone"]
    for share in snapshot["battery_shares"].values():
        share["loss"] = share["loss"][:2]
    restarted = Accountant(
        house_sources=_house_sources(TWO_BATTERIES),
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
        batteries=TWO_BATTERIES,
    )

    # When
    restarted.restore(snapshot)

    # Then - it restores, the energy and cost kept, and nothing forgone yet
    totals = restarted.totals()
    assert _q(totals.battery.energy_kwh) == Decimal("0.300000000")
    assert totals.battery.forgone_export == Decimal(0)
    assert _q(totals.batteries["growatt"].energy_kwh) == Decimal("0.187500000")
    assert totals.batteries["growatt"].forgone_export == Decimal(0)


def test_reset_totals_rebases_what_a_loss_could_have_earned() -> None:
    # Given - a published sunny loss
    acc = _a_sunny_loss(TWO_BATTERIES)

    # When
    acc.reset_totals()

    # Then
    totals = acc.totals()
    assert totals.battery.forgone_export == Decimal(0)
    assert totals.batteries["anker"].forgone_export == Decimal(0)
