"""Booking the cost of energy the battery never gave back (HEA-178).

The ledger's inventory is inferred, not measured, and two things leave a battery
by a door it does not subtract from: round-trip losses, and any discharge its
configured meter does not count. So it drifts upwards for ever - 15.69 kWh on the
books of a 5 kWh battery on the reference instance - and because its only
self-correction is being drained to empty, the drift is what prevents the
correction.

Reconciling against what the battery really holds fixes the inventory, and that
is what these tests are about. Discharge is priced from the ledger and from
nothing else, so a ledger carrying energy the battery does not have prices every
discharge against a blend that was never there.

**Nothing the write-down releases is published** (HEA-182). It knows what was
wrongly on the books but not why, and the two causes want opposite treatment: a
round-trip loss is energy the household paid for and never got back, while a
discharge the configured meter did not count reached the house and was billed
there already. Publishing both as consumption double-counts the second, and on a
battery carrying months of drift it does so all at once - measured on the
reference instance at four times its own house meter, for hours.

So the correction stays inside the ledger. What belongs in the household's total
is the loss alone, measured per interval against what the battery's level
actually did, and that is HEA-182's subject.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
OVERNIGHT = Decimal("0.093")
PEAK = Decimal("0.234")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _home_with_a_charged_battery() -> Accountant:
    """A household that charged 4 kWh from the grid overnight and used 2 of it."""
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.battery_discharge", "0"),
        ("sensor.house_load", "0"),
        ("sensor.coarse_step_energy", "0"),
    ):
        acc.observe(entity, at(5), Decimal(value))
    acc.record_price(at(5), PEAK)
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.battery_discharge", "2.0"),
        ("sensor.house_load", "2.0"),
        ("sensor.coarse_step_energy", "2.0"),
    ):
        acc.observe(entity, at(10), Decimal(value))
    acc.finalize(at(40))
    return acc


def test_the_write_down_corrects_the_ledger_and_publishes_nothing() -> None:
    """What the reconcile is for, and what it deliberately stops short of.

    Correcting the inventory is the point: discharge is priced from the ledger
    and from nothing else, so a ledger holding energy the battery does not have
    prices every discharge against a blend that was never there.

    Publishing the correction is a separate claim, and one the write-down cannot
    support - it knows what was wrongly on the books, not why (HEA-182).
    """
    # Given - a household whose ledger holds 2 kWh that is not in the battery
    acc = _home_with_a_charged_battery()

    # When - the battery reports itself flat
    acc.reconcile_battery(Decimal(0))

    # Then - the books agree with the battery, and the household's row is silent
    assert Decimal(acc.battery_diagnostics()["stored_kwh"]) == Decimal(0)
    totals = acc.totals()
    assert totals.battery.energy_kwh == Decimal(0)
    assert totals.battery.actual_cost == Decimal(0)


def test_the_battery_is_not_swept_into_untracked() -> None:
    # Given - a household with a tracked device and a remainder
    acc = _home_with_a_charged_battery()
    untracked_before = acc.totals().untracked.actual_cost

    # When - the battery's loss is written off
    acc.reconcile_battery(Decimal(0))

    # Then - Untracked is untouched. It means "energy you have not tracked yet",
    # and a household acting on it by adding devices can never reduce this
    assert acc.totals().untracked.actual_cost == untracked_before


def test_the_three_terms_still_account_for_the_whole_house() -> None:
    # Given / When - a household whose battery has lost something
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal(0))

    # Then - devices, remainder and battery add up to the house exactly. This is
    # ADR-0002's exhaustiveness with a third term rather than an exception to it:
    # the cards sum these rows to get a household total, so a figure outside the
    # sum would make every card disagree with Whole Home
    totals = acc.totals()
    tracked_energy = sum(
        (d.energy_kwh for d in totals.devices.values()), start=Decimal(0)
    )
    tracked_cost = sum(
        (d.actual_cost for d in totals.devices.values()), start=Decimal(0)
    )
    assert (
        tracked_energy + totals.untracked.energy_kwh + totals.battery.energy_kwh
        == totals.whole_home.energy_kwh
    )
    assert (
        tracked_cost + totals.untracked.actual_cost + totals.battery.actual_cost
        == totals.whole_home.actual_cost
    )


def test_a_loss_the_house_meters_cannot_explain_is_refused() -> None:
    """The ceiling, and the misconfiguration it exists for.

    `discharged` is meant to be the battery's whole output. A household who
    points it at a meter counting only what reached the *house* leaves everything
    the battery sent to the grid looking like a loss - and publishing that as
    energy the household used would claim more than the house drew, which is the
    one thing physics will not allow.

    The house's own meters settle it without reference to the battery at all:
    `import + generation - export - house` is whatever the battery gained plus
    whatever it lost, so nothing above that can honestly be called a loss.
    """
    # Given - a household that meters everything, imports 4 kWh, charges all of
    # it, and whose house drew 1 kWh of that. Its own meters can therefore
    # account for 3 kWh of gain-plus-loss in the battery and no more
    acc = _fully_metered_home()

    # When - the battery claims to be empty, which would mean all 4 kWh it was
    # given vanished - one more than the house's meters can explain
    acc.reconcile_battery(Decimal(0))

    # Then - only the explainable 3 is written off, and the fourth stays on the
    # books as the honest "we cannot tell". The ceiling still governs what may
    # leave the ledger even now that nothing leaving it is published: it is what
    # keeps a mis-pointed discharge meter from emptying the inventory and pricing
    # every later discharge against a blend built from nothing
    assert Decimal(acc.battery_diagnostics()["stored_kwh"]) == Decimal("1.0")


def _fully_metered_home() -> Accountant:
    """A household metering import, export, generation and its own load."""
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: "sensor.generation",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    entities = (
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.generation",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
    )
    for entity in entities:
        acc.observe(entity, at(0), Decimal(0))
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.grid_export", "0"),
        ("sensor.generation", "0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.battery_discharge", "0"),
        ("sensor.house_load", "1.0"),
    ):
        acc.observe(entity, at(5), Decimal(value))
    acc.finalize(at(40))
    return acc


def _metered_home_at_rest() -> Accountant:
    """A fully metered home with every counter at zero and one interval closed."""
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: "sensor.generation",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.generation",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
    ):
        acc.observe(entity, at(0), Decimal(0))
    # Far enough past the lateness margin that the opening interval really
    # closes, so the balance headroom exists before anything is measured.
    acc.finalize(at(40))
    return acc


def test_the_batterys_loss_is_what_the_meters_cannot_explain_less_what_it_gained() -> (
    None
):
    """The measurement HEA-182 asked for, with no efficiency constant in it.

    `import + generation - export - house` is, by physics, whatever the battery
    gained plus whatever it lost. Knowing how full the battery is supplies the
    gain, so the loss is the remainder - both halves metered, nothing assumed
    about the hardware.
    """
    # Given - a home that has run a while and then had its battery level filled
    # in, so the first reading is a baseline and nothing before it is claimed
    acc = _metered_home_at_rest()
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.house_load", "1.0"),
    ):
        acc.observe(entity, at(45), Decimal(value))
    acc.finalize(at(85))
    acc.reconcile_battery(Decimal("2.5"))
    assert acc.totals().battery.energy_kwh == Decimal(0)

    # When - it imports 2 kWh more, puts all of it into the battery, and the
    # house draws another 0.5. Its meters cannot account for 1.5 kWh of that
    # span, and the battery itself gained only 1.2, so 0.3 went to heat
    for entity, value in (
        ("sensor.grid_import", "6.0"),
        ("sensor.battery_charge", "6.0"),
        ("sensor.house_load", "1.5"),
    ):
        acc.observe(entity, at(90), Decimal(value))
    acc.finalize(at(130))
    acc.reconcile_battery(Decimal("3.7"))

    # Then - the loss is published as the battery's own consumption, and it is
    # the span's figure rather than anything accumulated before the baseline
    assert acc.totals().battery.energy_kwh.quantize(Decimal("0.001")) == Decimal(
        "0.300"
    )


def test_the_first_measurement_establishes_a_baseline_and_publishes_nothing() -> None:
    """The trap this ticket exists for, arriving by the other door.

    `_balance_headroom` accumulates from the household's first interval, so a
    first measurement taken against it would publish the whole history as one
    loss - which is exactly what HEA-182 was raised to stop.
    """
    # Given - a home that has been running, unexplained energy already behind it
    acc = _metered_home_at_rest()
    for entity, value in (
        ("sensor.grid_import", "4.0"),
        ("sensor.battery_charge", "4.0"),
        ("sensor.house_load", "1.0"),
    ):
        acc.observe(entity, at(45), Decimal(value))
    acc.finalize(at(85))

    # When - the household fills in the battery level for the first time
    acc.reconcile_battery(Decimal("2.5"))

    # Then - nothing is published. The history before the first reading is not a
    # loss anybody measured, and claiming it would repeat the fault
    assert acc.totals().battery.energy_kwh == Decimal(0)


def test_a_household_that_meters_too_little_is_not_capped() -> None:
    # Given - a household with no generation or export meter, so the balance
    # cannot be computed at all
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
        },
        device_energy_entities={},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), OVERNIGHT)
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
    ):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("4.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("4.0"))
    acc.finalize(at(40))

    # When - the battery reports itself empty
    acc.reconcile_battery(Decimal(0))

    # Then - the write-down happens anyway. A ceiling nobody can calculate is not
    # a reason to refuse the figure underneath it, and this household's ledger
    # drifts exactly as much as anyone else's
    assert Decimal(acc.battery_diagnostics()["stored_kwh"]) == Decimal(0)


def test_the_write_off_publishes_no_cost() -> None:
    # Given - a household whose ledger believes it holds 2 kWh at the overnight
    # rate, when the battery is actually empty
    acc = _home_with_a_charged_battery()
    before = acc.totals().whole_home.actual_cost
    assert Decimal(acc.battery_diagnostics()["stored_kwh"]) == Decimal("2.0")

    # When - the battery reports itself flat
    acc.reconcile_battery(Decimal(0))

    # Then - nothing is added to the bill. The money is real, but a write-down
    # cannot say whether it paid for a round-trip loss or for a discharge the
    # meter missed, and the second was already billed when the house used it
    assert acc.totals().whole_home.actual_cost == before


def test_the_write_off_invents_no_energy_the_house_never_used() -> None:
    # Given - a household with a drifted ledger
    acc = _home_with_a_charged_battery()
    energy_before = acc.totals().whole_home.energy_kwh

    # When - the inventory is written down
    acc.reconcile_battery(Decimal(0))

    # Then - the published total does not move. A ledger correction is a
    # statement about what we wrongly believed, not about what the house drew,
    # and publishing it put the reference instance at four times its own house
    # meter for hours (HEA-182)
    assert acc.totals().whole_home.energy_kwh == energy_before


def test_the_write_off_leaves_cost_savings_alone() -> None:
    # Given - a household with a drifted ledger
    acc = _home_with_a_charged_battery()
    savings_before = acc.totals().whole_home.cost_savings

    # When - the inventory is written down
    acc.reconcile_battery(Decimal(0))

    # Then - unchanged, because the counterfactual moves with the cost: this
    # energy *was* bought from the grid, so what it would have cost from the grid
    # is what it cost. Whether a round-trip loss should reduce what the battery
    # saved is a separate question, and a figure that answers it by accident is
    # worse than one that does not answer it at all (HEA-174)
    assert acc.totals().whole_home.cost_savings == savings_before


def test_the_write_off_charges_no_device_for_it() -> None:
    # Given - a household with one tracked device carrying real cost
    acc = _home_with_a_charged_battery()
    device_before = acc.totals().devices["coarse_step_aircon"].actual_cost
    assert device_before > 0

    # When - the inventory is written down
    acc.reconcile_battery(Decimal(0))

    # Then - the device is untouched. No appliance ran on the energy the battery
    # lost, so charging one for it would move money between households' devices
    # to fix a figure about the battery
    assert acc.totals().devices["coarse_step_aircon"].actual_cost == device_before


def test_a_battery_holding_what_the_ledger_thinks_books_nothing() -> None:
    # Given - a household whose ledger agrees with its battery
    acc = _home_with_a_charged_battery()
    before = acc.totals().whole_home.actual_cost

    # When - the battery confirms the 2 kWh on the books
    acc.reconcile_battery(Decimal("2.0"))

    # Then - nothing is booked. The ordinary case has to cost nothing, or every
    # interval would publish a write-off it invented
    assert acc.totals().whole_home.actual_cost == before


def test_the_written_off_cost_is_explainable_from_the_diagnostics() -> None:
    # Given / When - a household whose ledger is written down twice
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal("1.0"))
    acc.reconcile_battery(Decimal(0))

    # Then - the running total is in the download. A cost that appears in the
    # household's total with nothing anywhere explaining it is exactly the kind of
    # figure this project's diagnostics exist to account for
    assert Decimal(acc.battery_diagnostics()["written_off_cost"]) == Decimal("0.186")


def test_the_written_off_total_survives_a_restart() -> None:
    # Given - a household that has written some off
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal(0))
    snapshot = acc.snapshot()

    # When - the engine is rebuilt from the snapshot
    resumed = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    resumed.restore(snapshot)

    # Then - it is carried, so the diagnostics still explain a cost the household
    # is still being shown
    assert Decimal(resumed.battery_diagnostics()["written_off_cost"]) == Decimal(
        "0.186"
    )


def test_the_energy_written_off_is_the_loss_the_household_can_be_shown() -> None:
    """What HEA-174 publishes, and why it is measured rather than subtracted.

    `charged - discharged` over a window is the obvious way to get a round-trip
    loss and it is wrong by whatever the battery's level did over that window,
    plus any discharge the configured meter does not see: on the reference
    instance it read 84.1 % efficiency against a true 87.7 %. The write-off is the
    same quantity reconciled against what the battery actually holds, every
    interval, so the level cancels instead of confounding.
    """
    # Given - a household whose ledger holds the 2 kWh it saw charged
    acc = _home_with_a_charged_battery()

    # When - the battery turns out to be holding half of that
    acc.reconcile_battery(Decimal("1.0"))

    # Then - the kilowatt-hours are reported beside the money, because "your
    # battery lost this much" and "that cost you this much" answer different
    # halves of the same question (HEA-174)
    assert acc.battery_losses() == (Decimal("1.0"), Decimal("0.093"))


def test_battery_losses_accumulate_across_reconciliations() -> None:
    # Given / When - a household reconciled twice, as every interval does
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal("1.5"))
    acc.reconcile_battery(Decimal("0.5"))

    # Then - both figures are running totals, so a period's loss is the change
    # across it the way every other figure here works (ADR-0008)
    assert acc.battery_losses() == (Decimal("1.5"), Decimal("0.1395"))


def test_a_battery_that_holds_what_we_think_loses_nothing() -> None:
    # Given / When - the ordinary interval, where the books already agree
    acc = _home_with_a_charged_battery()
    acc.reconcile_battery(Decimal("2.0"))

    # Then - nothing accrues. A loss figure that ticked up when nothing was lost
    # would be worse than none, because it is the kind of number a household
    # checks once and then stops believing
    assert acc.battery_losses() == (Decimal(0), Decimal(0))


def test_a_snapshot_written_before_this_existed_still_restores() -> None:
    # Given - a snapshot as the released version wrote it, with no such figure
    acc = _home_with_a_charged_battery()
    snapshot = acc.snapshot()
    del snapshot["battery"]["written_off_cost"]

    # When / Then - it restores, reading the absent total as nothing rather than
    # refusing. Refusing would cold-start every installed household and throw away
    # the very ledger this ticket is about (ADR-0021)
    resumed = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={},
    )
    resumed.restore(snapshot)
    assert Decimal(resumed.battery_diagnostics()["written_off_cost"]) == Decimal(0)
