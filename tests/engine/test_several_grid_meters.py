"""A household whose import comes through more than one meter (HEA-221).

The common case is a dual-rate meter publishing a peak and an off-peak counter,
only one of which moves at a time, each priced separately; Home Assistant's
Energy Dashboard holds it as two grid sources. Each interval's import is priced
register by register and summed, so the grid price an interval settles at is
the blend of what each register carried (ADR-0032).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
    SourceRole,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
PEAK = Decimal("0.30")
OFF_PEAK = Decimal("0.10")

DAY = "sensor.day_register"
NIGHT = "sensor.night_register"
GENERATION = "sensor.generation"
EXPORT = "sensor.grid_export"
PUMP = "sensor.pump_energy"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _dual_rate_home() -> Accountant:
    """Two import registers and one tracked device, and nothing else.

    No quiet span: a register that sat still while the other ran would
    otherwise have its first step spread back across that stillness, which is
    right for a coarse counter and beside the point here.
    """
    return Accountant(
        house_sources={SourceRole.GRID_IMPORT: (DAY, NIGHT)},
        device_energy_entities={"pump": PUMP},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )


def _priced(acc: Accountant) -> None:
    acc.record_price(at(0), PEAK, meter=DAY)
    acc.record_price(at(0), OFF_PEAK, meter=NIGHT)
    for entity in (DAY, NIGHT, PUMP):
        acc.observe(entity, at(0), Decimal(0))


def test_each_interval_is_priced_at_the_register_that_carried_it() -> None:
    # Given - a dual-rate home with a price on each register
    acc = _dual_rate_home()
    _priced(acc)

    # When - the night register carries the first interval and the day register
    # the second, with the pump drawing all of it. Each register reports every
    # interval, still or not, as a real meter does, so neither step is spread
    # back across a quiet span
    acc.observe(NIGHT, at(5), Decimal(2))
    acc.observe(DAY, at(5), Decimal(0))
    acc.observe(PUMP, at(5), Decimal(2))
    acc.observe(DAY, at(10), Decimal(1))
    acc.observe(NIGHT, at(10), Decimal(2))
    acc.observe(PUMP, at(10), Decimal(3))
    acc.finalize(at(40))

    # Then - 2 kWh at the night rate and 1 at the day rate. One price for both
    # registers would have put 0.90 or 0.30 here
    pump = acc.totals().devices["pump"]
    assert pump.energy_kwh == Decimal(3)
    assert pump.actual_cost == Decimal("0.50")
    assert pump.naive_cost == Decimal("0.50")


def test_an_interval_both_registers_carried_is_priced_at_their_blend() -> None:
    # Given
    acc = _dual_rate_home()
    _priced(acc)

    # When - the meter switches register part-way through one interval: 1 kWh
    # on the day register and 3 on the night one
    acc.observe(DAY, at(5), Decimal(1))
    acc.observe(NIGHT, at(5), Decimal(3))
    acc.observe(PUMP, at(5), Decimal(4))
    acc.finalize(at(35))

    # Then - each register's energy at its own rate, 0.30 + 0.30
    assert acc.totals().devices["pump"].actual_cost == Decimal("0.60")


def test_an_interval_nothing_imported_in_is_priced_at_the_registers_average() -> None:
    # Given - a dual-rate home with solar, whose house uses only what it makes
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: (DAY, NIGHT),
            SourceRole.GRID_EXPORT: EXPORT,
            SourceRole.GENERATION: GENERATION,
        },
        device_energy_entities={},
    )
    _priced(acc)
    acc.observe(EXPORT, at(0), Decimal(0))
    acc.observe(GENERATION, at(0), Decimal(0))

    # When - 2 kWh of generation, all used at home, and neither register moves
    acc.observe(GENERATION, at(5), Decimal(2))
    acc.observe(EXPORT, at(5), Decimal(0))
    acc.observe(DAY, at(5), Decimal(0))
    acc.observe(NIGHT, at(5), Decimal(0))
    acc.finalize(at(35))

    # Then - it cost nothing, and what it would have cost from the grid is priced
    # at the plain average of the two rates. With no import to weight by, no
    # register has a better claim than the other
    untracked = acc.totals().untracked
    assert untracked.actual_cost == Decimal(0)
    assert untracked.naive_cost == Decimal("0.40")


def test_a_single_register_is_priced_exactly_as_before() -> None:
    # Given - a household with one import meter, priced as every household was
    # before there could be several, at a rate that does not divide evenly
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: DAY},
        device_energy_entities={"pump": PUMP},
    )
    rate = Decimal("0.2345")
    acc.record_price(at(0), rate)
    acc.observe(DAY, at(0), Decimal(0))
    acc.observe(PUMP, at(0), Decimal(0))

    # When - an awkward amount is imported and drawn
    acc.observe(DAY, at(5), Decimal("0.333"))
    acc.observe(PUMP, at(5), Decimal("0.333"))
    acc.finalize(at(35))

    # Then - the rate itself, not a blend that round-trips through a division
    # and lands a digit off
    assert acc.totals().devices["pump"].actual_cost == Decimal("0.333") * rate


def test_a_snapshot_from_before_several_registers_keeps_its_price() -> None:
    # Given - a single-register snapshot written before prices were kept per
    # register: the one list, and no record of which register each interval's
    # import came through
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: DAY},
        device_energy_entities={"pump": PUMP},
    )
    acc.record_price(at(0), PEAK)
    acc.observe(DAY, at(0), Decimal(0))
    acc.observe(PUMP, at(0), Decimal(0))
    acc.observe(DAY, at(5), Decimal(1))
    acc.observe(PUMP, at(5), Decimal(1))
    carried = json.loads(json.dumps(acc.snapshot()))
    carried["prices"] = carried.pop("import_prices")[0]["prices"]
    del carried["raw_import"]

    # When - it is restored, and the open interval closes
    restored = Accountant(
        house_sources={SourceRole.GRID_IMPORT: DAY},
        device_energy_entities={"pump": PUMP},
    )
    restored.restore(carried)
    restored.finalize(at(35))

    # Then - the interval is priced at the rate the household was on, not at
    # nothing
    assert restored.totals().devices["pump"].actual_cost == PEAK
