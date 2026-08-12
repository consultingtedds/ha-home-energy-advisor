"""What a device's cost is knowable to, given how rarely its counter reports.

A coarse counter reveals a step that accrued somewhere inside a 30-90 minute
span, and nothing in the data says where inside it. The engine spreads the step
evenly and prices each 5-minute slice at that slice's own blend, which is the
best available answer and still an estimate.

So each figure has a floor and a ceiling: what it would have cost had all of that
energy landed in the cheapest slice of its span, and in the dearest. On a house
with generation those can be far apart — a span may hold a slice served by the
sun and a slice served entirely by the meter — and saying so is the point
(ADR-0016).

These are outer bounds, not a confidence interval. They assume every kWh landed
in the single worst slice, which is why they are published as money and rendered
as a range: a percentage of a near-zero cost is meaningless (HEA-75).
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
COARSE_STEP_AIRCON = "sensor.coarse_step_energy"
CHEAP = Decimal("0.10")
DEAR = Decimal("0.30")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_home(*, generation: bool = False) -> Accountant:
    sources = {SourceRole.GRID_IMPORT: GRID}
    if generation:
        sources[SourceRole.GENERATION] = GENERATION
        sources[SourceRole.HOUSE_CONSUMPTION] = HOUSE
    return Accountant(
        house_sources=sources,
        device_energy_entities={"coarse_step_aircon": COARSE_STEP_AIRCON},
    )


def test_a_step_reported_within_one_slice_is_known_exactly() -> None:
    # Given — a counter that moves every interval, so there is nowhere else its
    # energy could have been
    acc = a_home()
    acc.record_price(at(0), DEAR)
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))

    # When
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.5"))
    acc.finalize(at(40))

    # Then — floor and ceiling meet at what was charged: no span, no doubt
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.cost_floor == aircon.actual_cost
    assert aircon.cost_ceiling == aircon.actual_cost


def test_a_step_spanning_a_tariff_change_is_bounded_by_both_rates() -> None:
    # Given — a counter that holds still across a tariff change and then reveals
    # 0.6 kWh, so the energy may have accrued before the change, after it, or
    # anywhere between
    acc = a_home()
    acc.record_price(at(0), CHEAP)
    acc.record_price(at(10), DEAR)
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    for minute in (5, 10, 15):
        acc.observe(GRID, at(minute), Decimal("0.5") * (minute // 5))
        acc.observe(COARSE_STEP_AIRCON, at(minute), Decimal(0))

    # When — the step finally lands, covering four slices at two different rates
    acc.observe(GRID, at(20), Decimal("2.0"))
    acc.observe(COARSE_STEP_AIRCON, at(20), Decimal("0.6"))
    acc.finalize(at(60))

    # Then — all of it at the cheap rate, or all of it at the dear one
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.cost_floor == Decimal("0.6") * CHEAP
    assert aircon.cost_ceiling == Decimal("0.6") * DEAR
    assert aircon.cost_floor <= aircon.actual_cost <= aircon.cost_ceiling


def test_generation_makes_the_band_much_wider_than_the_tariff_does() -> None:
    # Given — a house where the sun serves one slice completely and none of the
    # next, at an unchanging tariff. The tariff says the cost is certain; the
    # blend says it is anything but (ADR-0016).
    acc = a_home(generation=True)
    acc.record_price(at(0), DEAR)
    for entity in (GRID, GENERATION, HOUSE, COARSE_STEP_AIRCON):
        acc.observe(entity, at(0), Decimal(0))

    # When — the sun serves all but a thousandth of the first slice and none of
    # the second, and the device's counter spans both before revealing 0.4 kWh.
    # The grid meter has to keep moving: a counter that reports an unchanged
    # reading has its next step spread back over the quiet run (HEA-74), which
    # would smear the two slices into the same blend.
    acc.observe(GRID, at(5), Decimal("0.001"))
    acc.observe(GENERATION, at(5), Decimal("1.0"))
    acc.observe(HOUSE, at(5), Decimal("1.0"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal(0))
    acc.observe(GRID, at(10), Decimal("1.001"))
    acc.observe(GENERATION, at(10), Decimal("1.0"))
    acc.observe(HOUSE, at(10), Decimal("2.0"))
    acc.observe(COARSE_STEP_AIRCON, at(10), Decimal("0.4"))
    acc.finalize(at(45))

    # Then — a thousandth of the tariff if it ran on the sun, the whole tariff if
    # it did not: a band a thousand times wide, on an unchanging price. This is
    # what a percentage cannot express once the floor approaches zero.
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.cost_floor == Decimal("0.4") * Decimal("0.001") * DEAR
    assert aircon.cost_ceiling == Decimal("0.4") * DEAR
    assert aircon.cost_floor <= aircon.actual_cost <= aircon.cost_ceiling


def test_the_remainder_carries_no_doubt_of_its_own() -> None:
    # Given — Untracked is derived per slice from meters that reported for that
    # slice, so unlike a coarse counter it has no span to be uncertain about
    acc = a_home()
    acc.record_price(at(0), DEAR)
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))

    # When
    acc.observe(GRID, at(5), Decimal("1.0"))
    acc.observe(COARSE_STEP_AIRCON, at(5), Decimal("0.5"))
    acc.finalize(at(40))

    # Then
    untracked = acc.totals().untracked
    assert untracked.cost_floor == untracked.actual_cost
    assert untracked.cost_ceiling == untracked.actual_cost


def test_the_whole_home_bounds_are_the_sum_of_what_they_bound() -> None:
    # Given / When — the same interval, read at the top
    acc = a_home()
    acc.record_price(at(0), CHEAP)
    acc.record_price(at(10), DEAR)
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    for minute in (5, 10, 15, 20):
        acc.observe(GRID, at(minute), Decimal("0.5") * (minute // 5))
    acc.observe(COARSE_STEP_AIRCON, at(20), Decimal("0.6"))
    acc.finalize(at(60))

    # Then — the household's bounds reconcile the way its costs do, so a card can
    # show a range for any subset and have the parts add up
    totals = acc.totals()
    devices = list(totals.devices.values())
    assert totals.whole_home.cost_floor == sum(
        (d.cost_floor for d in devices), start=totals.untracked.cost_floor
    )
    assert totals.whole_home.cost_ceiling == sum(
        (d.cost_ceiling for d in devices), start=totals.untracked.cost_ceiling
    )
    assert (
        totals.whole_home.cost_floor
        <= totals.whole_home.actual_cost
        <= totals.whole_home.cost_ceiling
    )


def test_late_energy_is_bounded_by_the_slices_it_belongs_to() -> None:
    # Given — a counter reporting every 40 minutes, so most of its step lands in
    # buckets the accountant has already finalised. That path carries the bulk of
    # a coarse counter's energy, and bounds that stop there stop qualifying the
    # figure they exist for (ADR-0016).
    acc = a_home()
    acc.record_price(at(0), CHEAP)
    acc.record_price(at(10), DEAR)
    acc.observe(GRID, at(0), Decimal(0))
    acc.observe(COARSE_STEP_AIRCON, at(0), Decimal(0))
    for minute in range(5, 45, 5):
        acc.observe(GRID, at(minute), Decimal("0.5") * (minute // 5))
    acc.finalize(at(40))

    # When — the step arrives for a span whose buckets are mostly already closed
    acc.observe(COARSE_STEP_AIRCON, at(40), Decimal("0.8"))
    acc.finalize(at(75))

    # Then — still bracketed, at the rates of the slices it really spanned
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.cost_floor == Decimal("0.8") * CHEAP
    assert aircon.cost_ceiling == Decimal("0.8") * DEAR
    assert aircon.cost_floor <= aircon.actual_cost <= aircon.cost_ceiling
