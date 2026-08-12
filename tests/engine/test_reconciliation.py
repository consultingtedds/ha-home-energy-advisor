"""What the household can check against their own meter and their own bill.

The remainder is derived by subtraction, and the two streams it subtracts are
sampled thousands of times apart: a house meter reports every few seconds, a
cycle-resetting counter every 30-90 minutes. Within one 5-minute bucket the
device draw regularly exceeds the metered consumption, and flooring the
remainder at zero there rectifies a zero-mean signal into a bias that never
cancels (ADR-0015).

These tests assert the two figures a user can verify without trusting anything:
published energy against the meter, and published cost against the real cost of
that energy. Both hold over a period rather than over a single bucket — a bucket
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

    The house draws 0.1 kWh and then 0.5 kWh — 0.6 kWh altogether. The device's
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
    # Given — a counter that overshoots one bucket and is quiet the next
    acc = a_home()

    # When
    overdraw_then_repay(acc)

    # Then — the house consumed 0.6 kWh and that is what is published. Clamping
    # each bucket at zero would publish max(0.1, 0.4) + max(0.5, 0) = 0.9.
    assert acc.totals().whole_home.energy_kwh == Decimal("0.6")


def test_published_cost_equals_the_real_cost_of_that_energy() -> None:
    # Given / When
    acc = a_home()
    overdraw_then_repay(acc)

    # Then — 0.6 kWh at the 0.30 tariff is 0.18. Charging the overdraw without
    # ever giving it back bills 0.12 + 0.15 = 0.27, half again over the meter.
    assert acc.totals().whole_home.actual_cost == Decimal("0.18")


def test_the_device_still_pays_the_tariff_for_what_it_drew() -> None:
    # Given — reconciling the total must not be done by quietly discounting the
    # device, which is the dilution HEA-74 fixed
    acc = a_home()

    # When
    overdraw_then_repay(acc)

    # Then — 0.4 kWh at 0.30
    assert acc.totals().devices["coarse_step_aircon"].actual_cost == Decimal("0.12")


def test_the_remainder_absorbs_the_correction_and_never_goes_negative() -> None:
    # Given / When
    acc = a_home()
    overdraw_then_repay(acc)

    # Then — the remainder carries what is left: 0.2 kWh for 0.06, and it is the
    # only label that moves. Published figures stay non-negative however deep the
    # internal balance went (ADR-0015 decision 2).
    untracked = acc.totals().untracked
    assert untracked.energy_kwh == Decimal("0.2")
    assert untracked.actual_cost == Decimal("0.06")


def test_reconciliation_survives_a_blend_the_debt_was_not_charged_at() -> None:
    # Given — a home whose generation serves part of the second bucket, so the
    # blend there is cheaper than the import rate the debt was charged at. A debt
    # repaid at the later bucket's blend would leave the period short.
    acc = a_home(generation=GENERATION, house_consumption=HOUSE)
    for entity in (GRID, GENERATION, HOUSE, COARSE_STEP_AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When — the house consumes 0.1 kWh off the grid, then 0.5 kWh of which 0.3
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

    # Then — 0.6 kWh consumed, of which 0.3 came off the meter at 0.30 and 0.3
    # was generated at nothing. The bill is 0.09, and the energy still ties out.
    totals = acc.totals()
    assert totals.whole_home.energy_kwh == Decimal("0.6")
    assert totals.whole_home.actual_cost == Decimal("0.09")


def test_the_device_is_refunded_when_its_overdraw_turns_out_to_be_generated() -> None:
    # Given — the same pair, where the meter later reveals the second bucket was
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

    # Then — the refund goes to the device that drew the energy, not to the
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
    # Given — a counter claiming more than the house ever consumes. This is not
    # timing, it is a source that cannot be telling the truth, and absorbing it
    # indefinitely would suppress the remainder to zero for good while hiding the
    # fault (ADR-0015 decision 6).
    acc = a_home()
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    acc.observe(GRID, at(5), Decimal("0.1"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.4"))

    # When — the house keeps metering, and never draws enough to repay the debt
    for minute in range(10, 60 * 5, 5):
        acc.observe(GRID, at(minute), Decimal("0.1") + Decimal("0.01") * (minute // 5))
    acc.finalize(at(60 * 6))

    # Then — the debt expires after the quiet span rather than eating every
    # later bucket's remainder, and the energy it stood for is surfaced
    assert acc.unreconciled_energy() > 0
    assert acc.totals().untracked.energy_kwh > 0
