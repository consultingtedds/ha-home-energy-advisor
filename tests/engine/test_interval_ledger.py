from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from custom_components.home_energy_advisor.engine.energy_source import EnergyDelta
from custom_components.home_energy_advisor.engine.interval_ledger import (
    IntervalLedger,
    SourceKind,
    spread_energy,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from custom_components.home_energy_advisor.engine.interval_ledger import (
        BucketPortion,
    )

MADRID = ZoneInfo("Europe/Madrid")


def moment(at: str, day: str = "2026-07-11") -> datetime:
    return datetime.fromisoformat(f"{day}T{at}:00").replace(tzinfo=MADRID)


def delta(start: str, end: str, kwh: str, day: str = "2026-07-11") -> EnergyDelta:
    return EnergyDelta(kwh=Decimal(kwh), start=moment(start, day), end=moment(end, day))


def total(portions: Iterable[BucketPortion]) -> Decimal:
    return sum((p.kwh for p in portions), start=Decimal(0))


def test_spread_energy_within_one_bucket_stays_whole() -> None:
    # Given — a 0.25 kWh delta entirely inside the 02:15-02:20 bucket
    # When — it is spread
    portions = spread_energy(delta(start="02:16", end="02:19", kwh="0.25"))

    # Then — all of it lands in that single bucket
    assert len(portions) == 1
    assert portions[0].start == moment("02:15")
    assert portions[0].kwh == Decimal("0.25")


def test_spread_energy_aligned_to_a_boundary_fills_exactly_one_bucket() -> None:
    # Given — a delta spanning exactly the 02:15-02:20 bucket
    # When — it is spread
    portions = spread_energy(delta(start="02:15", end="02:20", kwh="0.30"))

    # Then — one bucket holds it all
    assert len(portions) == 1
    assert portions[0].start == moment("02:15")
    assert portions[0].kwh == Decimal("0.30")


def test_spread_energy_across_a_boundary_splits_by_time_overlap() -> None:
    # Given — a 5-minute delta straddling the 02:15 boundary: 1 min before, 4 after
    # When — it is spread
    portions = spread_energy(delta(start="02:14", end="02:19", kwh="0.25"))

    # Then — energy divides in proportion to the time in each bucket
    assert [(p.start, p.kwh) for p in portions] == [
        (moment("02:10"), Decimal("0.05")),
        (moment("02:15"), Decimal("0.20")),
    ]


def test_spread_energy_conserves_energy_when_the_share_does_not_terminate() -> None:
    # Given — 1 kWh across three whole buckets, a share of 1/3 that has no exact
    # decimal form — the canary for float contamination in the time arithmetic
    # When — it is spread
    portions = spread_energy(delta(start="02:00", end="02:15", kwh="1"))

    # Then — the parts still sum to exactly the original delta
    assert len(portions) == 3
    assert total(portions) == Decimal(1)


def test_spread_energy_across_a_long_outage_conserves_and_spans_every_bucket() -> None:
    # Given — the pool pump's counter jumps 50 kWh over a three-day outage
    # When — the recovered delta is spread
    portions = spread_energy(
        EnergyDelta(
            kwh=Decimal("50.00"),
            start=moment("22:00", day="2026-07-08"),
            end=moment("22:00", day="2026-07-11"),
        )
    )

    # Then — it covers every 5-minute bucket in the outage and loses nothing
    assert len(portions) == 3 * 24 * 12
    assert total(portions) == Decimal("50.00")
    assert portions[0].start == moment("22:00", day="2026-07-08")


def test_spread_energy_across_spring_dst_uses_real_elapsed_time() -> None:
    # Given — a delta from 01:30 to 03:30 on the 2026 Madrid spring-forward night,
    # when local clocks jump 02:00→03:00, so only one real hour elapses
    # When — it is spread
    portions = spread_energy(
        EnergyDelta(
            kwh=Decimal("0.60"),
            start=moment("01:30", day="2026-03-29"),
            end=moment("03:30", day="2026-03-29"),
        )
    )

    # Then — twelve buckets, not twenty-four: bucketing follows real time, and
    # energy is conserved across the discontinuity
    assert len(portions) == 12
    assert total(portions) == Decimal("0.60")


def test_ledger_accumulates_repeated_source_deltas_in_the_same_bucket() -> None:
    # Given — two grid-import deltas landing in the 02:15 bucket
    ledger = IntervalLedger()
    ledger.add_source(SourceKind.IMPORT, delta(start="02:15", end="02:18", kwh="0.30"))
    ledger.add_source(SourceKind.IMPORT, delta(start="02:18", end="02:20", kwh="0.20"))

    # When — the buckets are read back
    buckets = ledger.buckets()

    # Then — the bucket holds their sum for that source
    assert len(buckets) == 1
    assert buckets[0].sources[SourceKind.IMPORT] == Decimal("0.50")


def test_ledger_keeps_house_sources_separate() -> None:
    # Given — import and solar both feeding the 02:15 bucket
    ledger = IntervalLedger()
    ledger.add_source(SourceKind.IMPORT, delta(start="02:15", end="02:20", kwh="0.40"))
    ledger.add_source(SourceKind.SOLAR, delta(start="02:15", end="02:20", kwh="0.10"))

    # When / Then — each source is tallied under its own kind
    sources = ledger.buckets()[0].sources
    assert sources[SourceKind.IMPORT] == Decimal("0.40")
    assert sources[SourceKind.SOLAR] == Decimal("0.10")


def test_ledger_without_solar_or_battery_records_import_only() -> None:
    # Given — a household with no solar or battery configured
    ledger = IntervalLedger()
    ledger.add_source(SourceKind.IMPORT, delta(start="02:15", end="02:20", kwh="0.40"))

    # When / Then — the balance collapses to the import source alone
    sources = ledger.buckets()[0].sources
    assert set(sources) == {SourceKind.IMPORT}


def test_ledger_keeps_device_draws_separate_from_each_other() -> None:
    # Given — two tracked devices drawing in the 02:15 bucket
    ledger = IntervalLedger()
    ledger.add_device(
        "guest_bedroom_aircon", delta(start="02:15", end="02:20", kwh="0.25")
    )
    ledger.add_device("kitchen_aircon", delta(start="02:15", end="02:20", kwh="0.15"))

    # When / Then — each device is tallied under its own id
    draws = ledger.buckets()[0].device_draws
    assert draws["guest_bedroom_aircon"] == Decimal("0.25")
    assert draws["kitchen_aircon"] == Decimal("0.15")


def test_ledger_returns_buckets_in_chronological_order() -> None:
    # Given — deltas added out of order across three buckets
    ledger = IntervalLedger()
    ledger.add_device(
        "guest_bedroom_aircon", delta(start="02:25", end="02:30", kwh="1")
    )
    ledger.add_device(
        "guest_bedroom_aircon", delta(start="02:05", end="02:10", kwh="1")
    )
    ledger.add_device(
        "guest_bedroom_aircon", delta(start="02:15", end="02:20", kwh="1")
    )

    # When — the buckets are read back
    starts = [bucket.start for bucket in ledger.buckets()]

    # Then — they come out earliest first, regardless of insertion order
    assert starts == [moment("02:05"), moment("02:15"), moment("02:25")]


def test_ledger_spreads_a_device_delta_across_the_buckets_it_spans() -> None:
    # Given — a device delta straddling the 02:15 boundary
    ledger = IntervalLedger()
    ledger.add_device(
        "guest_bedroom_aircon", delta(start="02:14", end="02:19", kwh="0.25")
    )

    # When — the buckets are read back
    buckets = ledger.buckets()

    # Then — the draw is split across both buckets by time overlap
    assert buckets[0].device_draws["guest_bedroom_aircon"] == Decimal("0.05")
    assert buckets[1].device_draws["guest_bedroom_aircon"] == Decimal("0.20")
