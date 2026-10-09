"""What a device's share of self-consumed generation gave up (ADR-0026, HEA-38).

Energy the panels made and the house used is priced at zero, which is right for
what left the bank account and wrong for what the energy was worth: that kilowatt
hour could have been exported and earned the export rate. ADR-0002 priced it at
zero and said openly that the saving figure was optimistic because of it.

So the forgone revenue is published **beside** the cost rather than inside it. No
device's `actual_cost` moves, the reconciliation identity is untouched, and a
household can read either question - what they paid, or what the energy was worth.

**The rate at the time, never an average over the period.** That is the whole
reason this is accumulated in the engine instead of multiplied on a card: the
export rate moves on a dynamic tariff, and total generation times a mean rate is
a different number wearing the right name. The first test below is built so that
the naive product gets a visibly wrong answer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)

GRID = "sensor.grid_import"
GENERATION = "sensor.generation"
HOUSE = "sensor.house_consumption"
AIRCON = "sensor.aircon_energy"

IMPORT_PRICE = Decimal("0.30")
# Two export rates far enough apart that an average cannot be mistaken for
# either, which is what makes the first test able to fail.
EARLY_EXPORT = Decimal("0.05")
LATE_EXPORT = Decimal("0.20")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_solar_home() -> Accountant:
    """A home whose house meter is served entirely by its panels.

    The grid meter is present and never moves. A counter reporting an unchanged
    reading has its next step spread back over the quiet run (HEA-74), but a
    counter that never moves again has no next step, so nothing is smeared and
    each interval's blend is exactly the sun.
    """
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.GENERATION: GENERATION,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        device_energy_entities={"aircon": AIRCON},
    )


def test_the_forgone_revenue_uses_the_rate_in_force_not_an_average() -> None:
    """The figure this exists for, and the one a card could not compute.

    Two intervals, both served entirely by the sun, at export rates four times
    apart. The device uses twice as much generation in the cheap interval as in
    the dear one, so weighting by when it ran is not the same as weighting by how
    much it used.
    """
    # Given - a solar home, and an export rate that quadruples part way through
    acc = a_solar_home()
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), EARLY_EXPORT)
    acc.record_export_price(at(5), LATE_EXPORT)
    for entity in (GRID, GENERATION, HOUSE, AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When - the sun serves 1 kWh of house load in each interval, and the aircon
    # takes 0.4 kWh of the first and 0.2 kWh of the second
    acc.observe(GRID, at(5), Decimal(0))
    acc.observe(GENERATION, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    acc.observe(AIRCON, at(5), Decimal("0.4"))
    acc.observe(GRID, at(10), Decimal(0))
    acc.observe(GENERATION, at(10), Decimal("2.0"))
    acc.observe(HOUSE, at(10), Decimal("2.0"))
    acc.observe(AIRCON, at(10), Decimal("0.6"))
    acc.finalize(at(45))

    aircon = acc.totals().devices["aircon"]

    # Then - 0.4 at five cents plus 0.2 at twenty, which is 0.06
    assert aircon.energy_from_generation == Decimal("0.6")
    assert (
        aircon.forgone_export
        == Decimal("0.4") * EARLY_EXPORT + Decimal("0.2") * LATE_EXPORT
    )
    assert aircon.forgone_export == Decimal("0.060")

    # And - the naive answer a card could reach from published statistics is
    # 0.6 kWh at the mean of the two rates, which is 0.075. If this assertion
    # ever fails, the figure has stopped being worth computing in the engine.
    naive = Decimal("0.6") * (EARLY_EXPORT + LATE_EXPORT) / 2
    assert naive == Decimal("0.075")
    assert aircon.forgone_export != naive


def test_what_the_household_paid_is_untouched_by_the_forgone_figure() -> None:
    """A sibling, not a re-pricing (ADR-0026 decision 1, HEA-97's constraint).

    The moment this entered `actual_cost`, ADR-0002's reconciliation would stop
    meaning what it says and "Actual Cost is the cost of metered energy at the
    price at the time" would stop being true.
    """
    # Given - a solar home with an export rate configured
    acc = a_solar_home()
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), EARLY_EXPORT)
    for entity in (GRID, GENERATION, HOUSE, AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When - the sun serves the whole house and the aircon takes half a kWh
    acc.observe(GRID, at(5), Decimal(0))
    acc.observe(GENERATION, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    acc.observe(AIRCON, at(5), Decimal("0.5"))
    acc.finalize(at(40))

    # Then - it cost nothing, as it always did, and the forgone revenue sits
    # beside that rather than in it
    aircon = acc.totals().devices["aircon"]
    assert aircon.actual_cost == Decimal(0)
    assert aircon.forgone_export == Decimal("0.5") * EARLY_EXPORT
    assert aircon.forgone_export == Decimal("0.025")


def test_a_household_with_no_export_rate_sees_nothing_new() -> None:
    """Today's behaviour exactly, for a household who export nothing.

    A home with no export arrangement has no rate to read, and for them
    self-consumed generation genuinely is free. ADR-0026 promises them no figure
    and no control rather than a guessed one.
    """
    # Given - the same solar home, with no export price ever recorded
    acc = a_solar_home()
    acc.record_price(at(0), IMPORT_PRICE)
    for entity in (GRID, GENERATION, HOUSE, AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When - the sun serves the house and the aircon runs on it
    acc.observe(GRID, at(5), Decimal(0))
    acc.observe(GENERATION, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    acc.observe(AIRCON, at(5), Decimal("0.5"))
    acc.finalize(at(40))

    # Then - the energy was served by the sun, and nothing was forgone
    aircon = acc.totals().devices["aircon"]
    assert aircon.energy_from_generation == Decimal("0.5")
    assert aircon.forgone_export == Decimal(0)


def test_grid_energy_forgoes_nothing() -> None:
    """Only generation the house consumed could have been exported instead."""
    # Given - a home running entirely off the meter, with an export rate set
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: GRID},
        device_energy_entities={"aircon": AIRCON},
    )
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), LATE_EXPORT)
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(AIRCON, at(0), Decimal(0))

    # When - a kilowatt hour off the grid, half of it the aircon's
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(AIRCON, at(5), Decimal("0.5"))
    acc.finalize(at(40))

    # Then - it was paid for, and gave up nothing
    aircon = acc.totals().devices["aircon"]
    assert aircon.actual_cost == Decimal("0.5") * IMPORT_PRICE
    assert aircon.energy_from_generation == Decimal(0)
    assert aircon.forgone_export == Decimal(0)


def test_the_forgone_figure_sums_to_the_whole_home() -> None:
    """A sibling figure still has to reconcile, like every other one.

    Σ tracked devices + untracked == whole home. A figure that drifted from that
    would be a second opinion about the same energy, which ADR-0015 rules out.
    """
    # Given - a solar home with two devices and an untracked remainder
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.GENERATION: GENERATION,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        device_energy_entities={"aircon": AIRCON, "pump": "sensor.pump_energy"},
    )
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), EARLY_EXPORT)
    acc.record_export_price(at(5), LATE_EXPORT)
    for entity in (GRID, GENERATION, HOUSE, AIRCON, "sensor.pump_energy"):
        acc.observe(entity, at(0), Decimal(0))

    # When - two intervals of sun, both devices drawing, and the house drawing
    # more than the two of them together so a remainder exists
    acc.observe(GRID, at(5), Decimal(0))
    acc.observe(GENERATION, at(5), Decimal("2.0"))
    acc.observe(HOUSE, at(5), Decimal("2.0"))
    acc.observe(AIRCON, at(5), Decimal("0.4"))
    acc.observe("sensor.pump_energy", at(5), Decimal("0.3"))
    acc.observe(GRID, at(10), Decimal(0))
    acc.observe(GENERATION, at(10), Decimal("4.0"))
    acc.observe(HOUSE, at(10), Decimal("4.0"))
    acc.observe(AIRCON, at(10), Decimal("0.6"))
    acc.observe("sensor.pump_energy", at(10), Decimal("0.5"))
    acc.finalize(at(45))

    # Then - the parts account for the whole, exactly
    totals = acc.totals()
    parts = sum(
        (device.forgone_export for device in totals.devices.values()),
        totals.untracked.forgone_export,
    )
    assert parts == totals.whole_home.forgone_export

    # And - the whole home gave up its entire generation at the two rates: 2 kWh
    # in the five-cent interval and 2 in the twenty-cent one
    assert (
        totals.whole_home.forgone_export
        == Decimal("2.0") * EARLY_EXPORT + Decimal("2.0") * LATE_EXPORT
    )
    assert totals.whole_home.forgone_export == Decimal("0.500")


BATTERY_CHARGE = "sensor.battery_charge"
BATTERY_DISCHARGE = "sensor.battery_discharge"
EXPORT = "sensor.grid_export"


def a_solar_home_with_a_battery() -> Accountant:
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.GRID_EXPORT: EXPORT,
            SourceRole.GENERATION: GENERATION,
            SourceRole.BATTERY_CHARGE: BATTERY_CHARGE,
            SourceRole.BATTERY_DISCHARGE: BATTERY_DISCHARGE,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        device_energy_entities={"aircon": AIRCON},
    )


def test_sunshine_stored_in_the_battery_still_carries_what_it_gave_up() -> None:
    """ADR-0027, and the half the question came from.

    A device running on battery-stored sunshine was given a free ride: the
    generation was valued at nothing going in, so the discharge inherited
    nothing. That is the half h227's figures turn on, because it is what decides
    whether storing sunshine or storing cheap import is the better move.
    """
    # Given - a solar home with a battery, exporting at ten cents
    acc = a_solar_home_with_a_battery()
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), Decimal("0.10"))
    for entity in (
        GRID,
        EXPORT,
        GENERATION,
        BATTERY_CHARGE,
        BATTERY_DISCHARGE,
        HOUSE,
        AIRCON,
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When - the sun makes 2 kWh: one serves the house and the aircon takes it,
    # and the other is stored
    acc.observe(GENERATION, at(5), Decimal("2.0"))
    acc.observe(BATTERY_CHARGE, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    acc.observe(AIRCON, at(5), Decimal("1.0"))

    # And - later the battery gives that kilowatt hour back, and the aircon
    # takes that too
    acc.observe(BATTERY_DISCHARGE, at(10), Decimal("1.0"))
    acc.observe(HOUSE, at(10), Decimal("2.0"))
    acc.observe(AIRCON, at(10), Decimal("2.0"))
    acc.finalize(at(50))

    aircon = acc.totals().devices["aircon"]

    # Then - both kilowatt hours gave up ten cents of export, the one used
    # directly and the one that went round through the battery
    assert aircon.energy_from_generation == Decimal("1.0")
    assert aircon.energy_from_battery == Decimal("1.0")
    assert aircon.forgone_export == Decimal("0.20")


def test_stored_sunshine_is_valued_when_it_was_stored_not_when_it_is_used() -> None:
    """The rate that was actually forgone, which is the one at charge time.

    A household who charged at noon and discharged at midnight did not give up
    the midnight rate. Valuing the discharge at whatever export pays when the
    battery is emptied would be simpler and wrong.
    """
    # Given - the same home, storing sunshine while export pays ten cents
    acc = a_solar_home_with_a_battery()
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), Decimal("0.10"))
    for entity in (
        GRID,
        EXPORT,
        GENERATION,
        BATTERY_CHARGE,
        BATTERY_DISCHARGE,
        HOUSE,
        AIRCON,
    ):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe(GENERATION, at(5), Decimal("1.0"))
    acc.observe(BATTERY_CHARGE, at(5), Decimal("1.0"))

    # When - export becomes five times dearer *after* it was stored, and only
    # then is the battery drawn on
    acc.record_export_price(at(6), Decimal("0.50"))
    acc.observe(BATTERY_DISCHARGE, at(10), Decimal("1.0"))
    acc.observe(HOUSE, at(10), Decimal("1.0"))
    acc.observe(AIRCON, at(10), Decimal("1.0"))
    acc.finalize(at(50))

    # Then - ten cents, the revenue actually given up. Fifty would be a rate
    # this household was never offered for that energy.
    aircon = acc.totals().devices["aircon"]
    assert aircon.energy_from_battery == Decimal("1.0")
    assert aircon.forgone_export == Decimal("0.10")


def test_a_battery_charged_from_the_grid_gives_up_nothing() -> None:
    """Only sunshine forgoes export; bought energy was bought."""
    # Given - a home that fills its battery from cheap overnight import, with
    # export priced
    acc = a_solar_home_with_a_battery()
    acc.record_price(at(0), IMPORT_PRICE)
    acc.record_export_price(at(0), Decimal("0.50"))
    for entity in (
        GRID,
        EXPORT,
        GENERATION,
        BATTERY_CHARGE,
        BATTERY_DISCHARGE,
        HOUSE,
        AIRCON,
    ):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(BATTERY_CHARGE, at(5), Decimal("1.0"))

    # When - the aircon runs off it later
    acc.observe(BATTERY_DISCHARGE, at(10), Decimal("1.0"))
    acc.observe(HOUSE, at(10), Decimal("1.0"))
    acc.observe(AIRCON, at(10), Decimal("1.0"))
    acc.finalize(at(50))

    # Then - it was paid for, and gave up no export at all
    aircon = acc.totals().devices["aircon"]
    assert aircon.energy_from_battery == Decimal("1.0")
    assert aircon.forgone_export == Decimal(0)
