"""What the household can check against their own meter and their own bill.

The remainder is derived by subtraction, and the two streams it subtracts are
sampled thousands of times apart: a house meter reports every few seconds, a
cycle-resetting counter every 30-90 minutes. Within one 5-minute bucket the
device draw regularly exceeds the metered consumption, and flooring the
remainder at zero there rectifies a zero-mean signal into a bias that never
cancels (ADR-0015).

These tests assert the two figures a user can verify without trusting anything:
published energy against the meter, and published cost against the real cost of
that energy. Both hold over a period rather than over a single bucket - a bucket
that overdraws is charged for energy the meters have not yet reported, and the
bucket that repays gives it back at the price it was charged.

Figures are chosen to divide exactly, so every expectation below is arithmetic a
reader can do by hand rather than a number copied out of a previous run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
TARIFF = Decimal("0.30")

GRID = "sensor.grid_import"
GENERATION = "sensor.generation"
HOUSE = "sensor.house_consumption"
COARSE_STEP_AIRCON = "sensor.coarse_step_energy"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_home(**sources: str) -> Accountant:
    """A home metering its import, tracking one coarse-stepping device."""
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: GRID, **_roles(sources)},
        device_energy_entities={"coarse_step_aircon": COARSE_STEP_AIRCON},
    )
    acc.record_price(at(0), TARIFF)
    return acc


def _roles(sources: dict[str, str]) -> dict[SourceRole, str]:
    return {SourceRole(role): entity for role, entity in sources.items()}


def overdraw_then_repay(acc: Accountant) -> None:
    """One bucket where the counter overshoots the meter, then one where it catches up.

    The house draws 0.1 kWh and then 0.5 kWh - 0.6 kWh altogether. The device's
    counter reveals a 0.4 kWh step in the first bucket and holds still through
    the second, which is exactly how a counter that reports every half hour
    behaves against a meter that reports every few seconds. Nothing here is
    faulty: the device really did draw 0.4 kWh, and the house really did consume
    0.6 kWh.
    """
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))
    acc.observe(GRID, at(10), Decimal("0.6"))
    acc.observe(COARSE_STEP_AIRCON, at(10), Decimal("0.4"))
    acc.finalize(at(40))


def test_published_energy_equals_the_metered_house_over_the_period() -> None:
    # Given - a counter that overshoots one bucket and is quiet the next
    acc = a_home()

    # When
    overdraw_then_repay(acc)

    # Then - the house consumed 0.6 kWh and that is what is published. Clamping
    # each bucket at zero would publish max(0.1, 0.4) + max(0.5, 0) = 0.9.
    assert acc.totals().whole_home.energy_kwh == Decimal("0.6")


def test_published_cost_equals_the_real_cost_of_that_energy() -> None:
    # Given / When
    acc = a_home()
    overdraw_then_repay(acc)

    # Then - 0.6 kWh at the 0.30 tariff is 0.18. Charging the overdraw without
    # ever giving it back bills 0.12 + 0.15 = 0.27, half again over the meter.
    assert acc.totals().whole_home.actual_cost == Decimal("0.18")


def test_the_device_still_pays_the_tariff_for_what_it_drew() -> None:
    # Given - reconciling the total must not be done by quietly discounting the
    # device, which is the dilution HEA-74 fixed
    acc = a_home()

    # When
    overdraw_then_repay(acc)

    # Then - 0.4 kWh at 0.30
    assert acc.totals().devices["coarse_step_aircon"].actual_cost == Decimal("0.12")


def test_the_remainder_absorbs_the_correction_and_never_goes_negative() -> None:
    # Given / When
    acc = a_home()
    overdraw_then_repay(acc)

    # Then - the remainder carries what is left: 0.2 kWh for 0.06, and it is the
    # only label that moves. Published figures stay non-negative however deep the
    # internal balance went (ADR-0015 decision 2).
    untracked = acc.totals().untracked
    assert untracked.energy_kwh == Decimal("0.2")
    assert untracked.actual_cost == Decimal("0.06")


def test_reconciliation_survives_a_blend_the_debt_was_not_charged_at() -> None:
    # Given - a home whose generation serves part of the second bucket, so the
    # blend there is cheaper than the import rate the debt was charged at. A debt
    # repaid at the later bucket's blend would leave the period short.
    acc = a_home(generation=GENERATION, house_consumption=HOUSE)
    for entity in (GRID, GENERATION, HOUSE, COARSE_STEP_AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When - the house consumes 0.1 kWh off the grid, then 0.5 kWh of which 0.3
    # is generated; the device reveals 0.4 kWh in the first bucket
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(GENERATION, at(5), Decimal(0))
    acc.observe(HOUSE, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))
    acc.observe(GRID, at(10), Decimal("0.3"))
    acc.observe(GENERATION, at(10), Decimal("0.3"))
    acc.observe(HOUSE, at(10), Decimal("0.6"))
    acc.observe(COARSE_STEP_AIRCON, at(10), Decimal("0.4"))
    acc.finalize(at(40))

    # Then - 0.6 kWh consumed, of which 0.3 came off the meter at 0.30 and 0.3
    # was generated at nothing. The bill is 0.09, and the energy still ties out.
    totals = acc.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal("0.09")


def test_the_device_is_refunded_when_its_overdraw_turns_out_to_be_generated() -> None:
    # Given - the same pair, where the meter later reveals the second bucket was
    # half generation. The device was charged the import rate for energy the
    # meters had not yet reported (ADR-0014), and that turns out to have been an
    # over-estimate.
    acc = a_home(generation=GENERATION, house_consumption=HOUSE)
    for entity in (GRID, GENERATION, HOUSE, COARSE_STEP_AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(GENERATION, at(5), Decimal(0))
    acc.observe(HOUSE, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))
    acc.observe(GRID, at(10), Decimal("0.3"))
    acc.observe(GENERATION, at(10), Decimal("0.3"))
    acc.observe(HOUSE, at(10), Decimal("0.6"))
    acc.observe(COARSE_STEP_AIRCON, at(10), Decimal("0.4"))
    acc.finalize(at(40))

    # Then - the refund goes to the device that drew the energy, not to the
    # remainder. Its 0.3 kWh of debt is repriced from the import rate it was
    # charged (0.090) to the blend that actually served it (0.036), so 0.054
    # comes back and it pays 0.066. The remainder keeps 0.2 kWh at that same
    # blend, and stays positive.
    totals = acc.totals()
    assert totals.devices["coarse_step_aircon"].actual_cost == Decimal("0.066")
    assert totals.untracked.actual_cost == Decimal("0.024")
    assert totals.untracked.energy_kwh == Decimal("0.2")

    # And the saving lands on the device that used the sun, not on Untracked
    assert totals.devices["coarse_step_aircon"].cost_savings == Decimal("0.054")


def test_a_debt_the_house_never_repays_is_forgiven_not_carried_forever() -> None:
    # Given - a counter claiming more than the house ever consumes. This is not
    # timing, it is a source that cannot be telling the truth, and absorbing it
    # indefinitely would suppress the remainder to zero for good while hiding the
    # fault (ADR-0015 decision 6).
    acc = a_home()
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))

    # When - the house keeps metering, and never draws enough to repay the debt
    for minute in range(10, 60 * 5, 5):
        acc.observe(GRID, at(minute), Decimal("0.1") + Decimal("0.01") * (minute // 5))
    acc.finalize(at(60 * 6))

    # Then - the debt expires after the quiet span rather than eating every
    # later bucket's remainder, and the energy it stood for is surfaced
    assert acc.unreconciled_energy() > 0
    assert acc.totals().untracked.energy_kwh > 0


def test_unreconciled_energy_is_exactly_the_gap_against_the_meter() -> None:
    # Given - a counter claiming more than the house ever consumes, so its debt
    # can never be repaid
    acc = a_home()
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))

    # When - the house trickles along for four hours, never metering enough to
    # repay the 0.3 kWh the device claimed beyond it
    metered = reading = Decimal("0.1")
    for minute in range(10, 60 * 4, 5):
        reading += Decimal("0.001")
        metered += Decimal("0.001")
        acc.observe(GRID, at(minute), reading)
    acc.finalize(at(60 * 5))

    # Then - since the carry landed, forgiven debt is the only thing that can
    # inflate the whole-home figure. So this number is not a diagnostic *about*
    # the gap against the household's own meter: it is that gap, in kWh.
    published = acc.totals().whole_home.energy_kwh
    assert acc.unreconciled_energy() > 0
    assert published - metered == acc.unreconciled_energy()


def test_the_unreconciled_share_is_that_gap_as_a_fraction_of_the_total() -> None:
    # Given / When - a house whose meters reconcile
    acc = a_home()
    overdraw_then_repay(acc)

    # Then - nothing forgiven, so nothing unreconciled. This is what a healthy
    # install reads, which is what makes any other reading worth acting on.
    assert acc.unreconciled_energy() == Decimal(0)
    assert acc.unreconciled_share() == Decimal(0)


def test_an_accountant_that_has_published_nothing_reports_no_share() -> None:
    # Given / When / Then - a share of nothing is not an error to divide by
    assert a_home().unreconciled_share() == Decimal(0)


CIRCUIT = "sensor.kitchen_circuit_energy"
APPLIANCE = "sensor.coarse_step_aircon_energy"


def _nested(devices: dict[str, str], nesting: dict[str, str]) -> Accountant:
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: GRID,
            SourceRole.HOUSE_CONSUMPTION: HOUSE,
        },
        device_energy_entities=devices,
        nested_devices=nesting,
    )
    acc.record_price(at(0), TARIFF)
    return acc


def test_a_nested_device_is_not_counted_twice_against_its_circuit() -> None:
    # Given - a house that used 1.0 kWh, of which a circuit clamp carried 0.6
    # and the aircon on that circuit used 0.4. The clamp's 0.6 *includes* the
    # aircon, because that is what measuring a breaker means - so counted
    # naively the two claim 1.0 between them and Untracked reads zero
    acc = _nested(
        {"kitchen_circuit": CIRCUIT, "aircon": APPLIANCE},
        {"aircon": "kitchen_circuit"},
    )
    for entity in (GRID, HOUSE, CIRCUIT, APPLIANCE):
        acc.observe(entity, at(0), Decimal(0))

    # When
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    acc.observe(CIRCUIT, at(5), Decimal("0.6"))
    acc.observe(APPLIANCE, at(5), Decimal("0.4"))
    acc.finalize(at(60))

    # Then - the circuit is booked for what it used itself, 0.6 - 0.4 = 0.2,
    # and the aircon keeps its own 0.4
    totals = acc.totals()
    assert totals.devices["kitchen_circuit"].energy_kwh == Decimal("0.2")
    assert totals.devices["aircon"].energy_kwh == Decimal("0.4")
    # And the 0.4 the house drew off other circuits is Untracked rather than
    # swallowed by the double count, which is what it read before nesting
    assert totals.untracked.energy_kwh == Decimal("0.4")
    assert totals.whole_home.energy_kwh == Decimal("1.0")


def test_nesting_telescopes_through_a_chain_of_any_depth() -> None:
    # Given - breaker -> fuse -> smart plug -> the appliance's own counter.
    # Four levels, each physically containing the next, which is unusual but
    # buildable. A rule that only subtracted one level would pass the test
    # above and be wrong here, so the depth is the point
    acc = _nested(
        {
            "breaker": "sensor.breaker_energy",
            "fuse": "sensor.fuse_energy",
            "plug": "sensor.plug_energy",
            "appliance": "sensor.appliance_energy",
        },
        {"fuse": "breaker", "plug": "fuse", "appliance": "plug"},
    )
    meters = {
        "sensor.breaker_energy": Decimal("1.0"),
        "sensor.fuse_energy": Decimal("0.6"),
        "sensor.plug_energy": Decimal("0.4"),
        "sensor.appliance_energy": Decimal("0.3"),
    }
    for entity in (GRID, HOUSE, *meters):
        acc.observe(entity, at(0), Decimal(0))

    # When - the house used 1.0, all of it through the breaker
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    for entity, reading in meters.items():
        acc.observe(entity, at(5), reading)
    acc.finalize(at(60))

    # Then - each level keeps only what it did not pass on. The intermediate
    # terms cancel in pairs, so the four sum to the breaker's own 1.0 and
    # nothing is left over for Untracked
    totals = acc.totals()
    assert totals.devices["breaker"].energy_kwh == Decimal("0.4")
    assert totals.devices["fuse"].energy_kwh == Decimal("0.2")
    assert totals.devices["plug"].energy_kwh == Decimal("0.1")
    assert totals.devices["appliance"].energy_kwh == Decimal("0.3")
    assert totals.untracked.energy_kwh == Decimal(0)
    assert totals.whole_home.energy_kwh == Decimal("1.0")


def test_a_parent_subtracts_its_children_gross_not_their_net() -> None:
    # Given / When - the same chain, asserted as the one arithmetic that
    # distinguishes a correct implementation from a plausible wrong one.
    # Netting a parent against its child's *net* would give the breaker
    # 1.0 - (0.6 - 0.4) = 0.8 instead of 0.4, and the four would sum to 1.6
    acc = _nested(
        {
            "breaker": "sensor.breaker_energy",
            "fuse": "sensor.fuse_energy",
            "plug": "sensor.plug_energy",
            "appliance": "sensor.appliance_energy",
        },
        {"fuse": "breaker", "plug": "fuse", "appliance": "plug"},
    )
    meters = {
        "sensor.breaker_energy": Decimal("1.0"),
        "sensor.fuse_energy": Decimal("0.6"),
        "sensor.plug_energy": Decimal("0.4"),
        "sensor.appliance_energy": Decimal("0.3"),
    }
    for entity in (GRID, HOUSE, *meters):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    for entity, reading in meters.items():
        acc.observe(entity, at(5), reading)
    acc.finalize(at(60))

    # Then - the devices and the remainder still sum to the metered house,
    # exactly, which is the invariant ADR-0002 will not trade for anything
    totals = acc.totals()
    booked = sum(
        (device.energy_kwh for device in totals.devices.values()),
        start=totals.untracked.energy_kwh,
    )
    assert booked == totals.whole_home.energy_kwh == Decimal("1.0")


def test_a_parent_outrun_by_a_coarse_child_publishes_zero_not_a_negative() -> None:
    # Given - a circuit clamp reporting every bucket, and a coarse counter on
    # that circuit reporting once for a span it covered. Over the span the
    # clamp necessarily read at least what the appliance did; inside a single
    # bucket it need not, because the coarse step is spread evenly while the
    # clamp's own reading is not (ADR-0006). This is ordinary, not a fault
    acc = _nested(
        {"kitchen_circuit": CIRCUIT, "aircon": APPLIANCE},
        {"aircon": "kitchen_circuit"},
    )
    for entity in (GRID, HOUSE, CIRCUIT, APPLIANCE):
        acc.observe(entity, at(0), Decimal(0))

    # When - the house and the circuit move 0.1 in the first bucket and 0.5 in
    # the second, while the aircon reports 0.4 all at once against the first
    acc.observe(GRID, at(5), Decimal("0.6"))
    acc.observe(HOUSE, at(5), Decimal("0.6"))
    acc.observe(CIRCUIT, at(5), Decimal("0.1"))
    acc.observe(APPLIANCE, at(5), Decimal("0.4"))
    acc.observe(GRID, at(10), Decimal("0.6"))
    acc.observe(HOUSE, at(10), Decimal("0.6"))
    acc.observe(CIRCUIT, at(10), Decimal("0.6"))
    acc.observe(APPLIANCE, at(10), Decimal("0.4"))
    acc.finalize(at(60))

    # Then - the circuit is never published below zero. Its first bucket owed
    # 0.3 more than it drew; that is carried and taken out of the bucket where
    # its own counter catches up, so across the span it books 0.6 - 0.4 = 0.2
    totals = acc.totals()
    assert totals.devices["kitchen_circuit"].energy_kwh == Decimal("0.2")
    assert totals.devices["kitchen_circuit"].actual_cost >= Decimal(0)
    assert totals.devices["aircon"].energy_kwh == Decimal("0.4")

    # And the invariant holds over the span, which is the level ADR-0015 says
    # it is owed at - a bucket that overdraws is settled by the one that repays
    booked = sum(
        (device.energy_kwh for device in totals.devices.values()),
        start=totals.untracked.energy_kwh,
    )
    assert booked == totals.whole_home.energy_kwh


def test_a_carry_the_parent_never_repays_expires_instead_of_lasting_for_ever() -> None:
    # Given - a child declared under a parent it is not actually on, which is
    # what a wrong upstream link looks like from here: the child reports and the
    # parent never accounts for it, so the debt is never repaid
    acc = _nested(
        {"kitchen_circuit": CIRCUIT, "aircon": APPLIANCE},
        {"aircon": "kitchen_circuit"},
    )
    for entity in (GRID, HOUSE, CIRCUIT, APPLIANCE):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.5"))
    acc.observe(HOUSE, at(5), Decimal("0.5"))
    acc.observe(CIRCUIT, at(5), Decimal("0.1"))
    acc.observe(APPLIANCE, at(5), Decimal("0.4"))

    # When - the parent reports again only after the carry's span has passed.
    # `MAX_QUIET_SPAN` is the same window ADR-0015 gives the remainder's
    # deficit, for the same reason: a gap caused by spreading clears inside it,
    # and one that does not is a claim that was wrong
    late = 60 * 5
    acc.observe(GRID, at(late), Decimal("1.0"))
    acc.observe(HOUSE, at(late), Decimal("1.0"))
    acc.observe(CIRCUIT, at(late), Decimal("0.6"))
    acc.finalize(at(late + 120))

    # Then - what it still owed is forgiven rather than chased for ever, and
    # the parent is never published below zero on the way there. Forgiving errs
    # towards a figure that is too high, never towards losing energy
    circuit = acc.totals().devices["kitchen_circuit"]
    assert circuit.energy_kwh > Decimal("0.2")
    assert circuit.actual_cost >= Decimal(0)


def test_a_carry_survives_a_restart_and_is_still_repaid() -> None:
    # Given - a parent outrun by its coarse child, snapshotted mid-debt. This is
    # the restart that used to re-introduce the double count the carry removes:
    # forget what the parent owed and its catch-up bucket books the lot
    acc = _nested(
        {"kitchen_circuit": CIRCUIT, "aircon": APPLIANCE},
        {"aircon": "kitchen_circuit"},
    )
    for entity in (GRID, HOUSE, CIRCUIT, APPLIANCE):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.6"))
    acc.observe(HOUSE, at(5), Decimal("0.6"))
    acc.observe(CIRCUIT, at(5), Decimal("0.1"))
    acc.observe(APPLIANCE, at(5), Decimal("0.4"))
    # Far enough on for that bucket to finalise - nothing is netted until one
    # does, so a snapshot taken sooner would have no debt in it to lose
    acc.finalize(at(40))
    carried = acc.snapshot()
    assert carried["nesting_carry"], "the parent should owe its child here"

    # When - the host restarts and the parent's counter catches up afterwards
    resumed = _nested(
        {"kitchen_circuit": CIRCUIT, "aircon": APPLIANCE},
        {"aircon": "kitchen_circuit"},
    )
    resumed.restore(carried)
    resumed.observe(GRID, at(45), Decimal("1.2"))
    resumed.observe(HOUSE, at(45), Decimal("1.2"))
    resumed.observe(CIRCUIT, at(45), Decimal("0.6"))
    resumed.observe(APPLIANCE, at(45), Decimal("0.4"))
    resumed.finalize(at(90))

    # Then - the debt is still taken out of the catch-up bucket, so the circuit
    # books what it used itself rather than its child's energy a second time
    circuit = resumed.totals().devices["kitchen_circuit"]
    assert circuit.energy_kwh == Decimal("0.2")
    assert circuit.actual_cost >= Decimal(0)


def test_a_fleet_with_no_nesting_never_carries_anything() -> None:
    # Given / When - the path every existing household is on
    acc = a_home()
    overdraw_then_repay(acc)

    # Then - netting is not merely a no-op, it is never reached, so a snapshot
    # taken here has no nesting state to restore
    assert acc.snapshot()["nesting_carry"] == []
