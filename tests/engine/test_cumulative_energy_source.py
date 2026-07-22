from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_energy_advisor.engine.energy_source import (
    CumulativeEnergySource,
    Decision,
    DecisionReason,
    EnergyDelta,
    EnergyUnit,
    Reading,
)

MADRID = ZoneInfo("Europe/Madrid")


def reading(at: str, value: str | None, day: str = "2026-07-11") -> Reading:
    moment = datetime.fromisoformat(f"{day}T{at}:00").replace(tzinfo=MADRID)
    return Reading(at=moment, value=None if value is None else Decimal(value))


def moment(at: str, day: str = "2026-07-11") -> datetime:
    return datetime.fromisoformat(f"{day}T{at}:00").replace(tzinfo=MADRID)


def test_cumulative_source_first_reading_establishes_a_baseline_without_energy() -> (
    None
):
    # Given — a fresh source for the Guest Bedroom Aircon
    source = CumulativeEnergySource()

    # When — the very first reading arrives mid-cycle
    delta = source.observe(reading(at="02:14", value="2.75"))

    # Then — no energy is claimed; we cannot know when it accumulated
    assert delta is None


def test_cumulative_source_rising_counter_yields_the_increment() -> None:
    # Given — the counter has been seen at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When — it steps up by one 0.25 kWh increment
    delta = source.observe(reading(at="02:19", value="3.00"))

    # Then — the increment is the energy, spanning the two readings
    assert delta == EnergyDelta(
        kwh=Decimal("0.25"), start=moment("02:14"), end=moment("02:19")
    )


def test_cumulative_source_cycle_reset_treats_the_new_value_as_a_fresh_cycle() -> None:
    # Given — the WF-RAC counter is mid-cycle at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When — the compressor cycle ends and the counter restarts, already at 0.25
    delta = source.observe(reading(at="02:19", value="0.25"))

    # Then — the post-reset value is the energy, not a negative difference
    assert delta == EnergyDelta(
        kwh=Decimal("0.25"), start=moment("02:14"), end=moment("02:19")
    )


def test_cumulative_source_reset_to_zero_yields_no_energy() -> None:
    # Given — the counter is mid-cycle at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When — the cycle ends and the counter drops cleanly to zero
    delta = source.observe(reading(at="02:19", value="0"))

    # Then — the reset itself is not energy
    assert delta is None


def test_cumulative_source_unavailable_span_does_not_disturb_the_baseline() -> None:
    # Given — a counter at 2.75 kWh that then goes unavailable
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))
    skipped = source.observe(reading(at="02:19", value=None))

    # When — it recovers, having kept counting while unavailable
    delta = source.observe(reading(at="02:24", value="3.25"))

    # Then — the unavailable state yields nothing, and the delta spans the gap
    # back to the last known good reading rather than restarting from it
    assert skipped is None
    assert delta == EnergyDelta(
        kwh=Decimal("0.50"), start=moment("02:14"), end=moment("02:24")
    )


def test_cumulative_source_gap_spanning_downtime_attributes_the_whole_delta() -> None:
    # Given — the pool pump's lifetime counter at 3377.00 kWh before HA restarts
    source = CumulativeEnergySource()
    source.observe(reading(at="22:00", value="3377.00", day="2026-07-08"))

    # When — HA comes back three days later and the counter has moved on
    delta = source.observe(reading(at="22:00", value="3427.00", day="2026-07-11"))

    # Then — the full 50 kWh is attributed, spanning the outage, so the interval
    # ledger can spread it rather than lumping it at the restart instant
    assert delta == EnergyDelta(
        kwh=Decimal("50.00"),
        start=moment("22:00", day="2026-07-08"),
        end=moment("22:00", day="2026-07-11"),
    )


def test_cumulative_source_out_of_order_reading_is_ignored() -> None:
    # Given — readings observed up to 02:19
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))
    source.observe(reading(at="02:19", value="3.00"))

    # When — a stale reading arrives late, out of order
    delta = source.observe(reading(at="02:16", value="2.90"))

    # Then — it is discarded; rewinding the baseline would double-count energy
    assert delta is None


def test_cumulative_source_repeated_timestamp_is_ignored() -> None:
    # Given — a reading already observed at 02:19
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))
    source.observe(reading(at="02:19", value="3.00"))

    # When — another reading arrives bearing the same timestamp
    delta = source.observe(reading(at="02:19", value="3.25"))

    # Then — it is discarded; a delta spanning zero time cannot be allocated
    assert delta is None


def test_cumulative_source_watt_hour_counter_is_normalised_to_kilowatt_hours() -> None:
    # Given — a source whose sensor reports in Wh, not kWh
    source = CumulativeEnergySource(unit=EnergyUnit.WH)
    source.observe(reading(at="02:14", value="2750"))

    # When — the counter climbs by 250 Wh
    delta = source.observe(reading(at="02:19", value="3000"))

    # Then — the engine speaks only in kWh
    assert delta == EnergyDelta(
        kwh=Decimal("0.250"), start=moment("02:14"), end=moment("02:19")
    )


def test_cumulative_source_daily_counter_reset_at_midnight_spans_the_boundary() -> None:
    # Given — the well pump's Tuya daily counter, late in the day
    source = CumulativeEnergySource()
    source.observe(reading(at="23:58", value="4.20", day="2026-07-10"))

    # When — the device-side counter rolls over at midnight and polls back low
    delta = source.observe(reading(at="00:03", value="0.10", day="2026-07-11"))

    # Then — the reset rule applies and the delta still spans the midnight boundary
    assert delta == EnergyDelta(
        kwh=Decimal("0.10"),
        start=moment("23:58", day="2026-07-10"),
        end=moment("00:03", day="2026-07-11"),
    )


def test_cumulative_source_unchanged_counter_yields_no_energy() -> None:
    # Given — a counter at 3.00 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="3.00"))

    # When — the sensor reports the same value again
    delta = source.observe(reading(at="02:19", value="3.00"))

    # Then — nothing was consumed
    assert delta is None


def test_cumulative_source_negative_counter_value_is_rejected() -> None:
    # Given — a source for a total_increasing energy counter
    source = CumulativeEnergySource()

    # When / Then — a negative reading is not a reset; treating it as one would
    # mint negative energy and break the aggregate invariant
    with pytest.raises(ValueError, match="negative"):
        source.observe(reading(at="02:14", value="-1.00"))


# --- Diagnostics: the decision log (HEA-24) ------------------------------------
#
# The engine that makes each gating decision is the only place that can record it
# faithfully, so it keeps a bounded log the diagnostics download reads back. Each
# reading leaves exactly one Decision explaining what the engine did with it.


def test_cumulative_source_first_reading_is_logged_as_a_baseline_decision() -> None:
    # Given — a fresh source for the Guest Bedroom Aircon
    source = CumulativeEnergySource()

    # When — the very first reading arrives
    source.observe(reading(at="02:14", value="2.75"))

    # Then — it is logged as a baseline that claimed no energy
    assert source.recent_decisions() == (
        Decision(at=moment("02:14"), reason=DecisionReason.FIRST_READING, kwh=None),
    )


def test_cumulative_source_rising_counter_is_logged_as_counted_with_energy() -> None:
    # Given — the counter has been seen at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When — it steps up by one 0.25 kWh increment
    source.observe(reading(at="02:19", value="3.00"))

    # Then — the increment is logged as counted energy
    assert source.recent_decisions()[-1] == Decision(
        at=moment("02:19"), reason=DecisionReason.COUNTED, kwh=Decimal("0.25")
    )


def test_cumulative_source_cycle_reset_is_logged_as_a_reset_with_energy() -> None:
    # Given — the WF-RAC counter is mid-cycle at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When — the compressor cycle ends and the counter restarts at 0.25
    source.observe(reading(at="02:19", value="0.25"))

    # Then — the post-reset energy is logged, distinguished from a normal increment
    assert source.recent_decisions()[-1] == Decision(
        at=moment("02:19"), reason=DecisionReason.RESET, kwh=Decimal("0.25")
    )


def test_cumulative_source_unavailable_reading_is_logged_without_energy() -> None:
    # Given — a counter at 2.75 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))

    # When — the sensor goes unavailable
    source.observe(reading(at="02:19", value=None))

    # Then — the gap is logged as unavailable, claiming no energy
    assert source.recent_decisions()[-1] == Decision(
        at=moment("02:19"), reason=DecisionReason.UNAVAILABLE, kwh=None
    )


def test_cumulative_source_out_of_order_reading_is_logged_as_stale() -> None:
    # Given — readings observed up to 02:19
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="2.75"))
    source.observe(reading(at="02:19", value="3.00"))

    # When — a stale reading arrives late, out of order
    source.observe(reading(at="02:16", value="2.90"))

    # Then — it is logged as stale rather than silently dropped
    assert source.recent_decisions()[-1] == Decision(
        at=moment("02:16"), reason=DecisionReason.STALE, kwh=None
    )


def test_cumulative_source_unchanged_counter_is_logged_as_no_movement() -> None:
    # Given — a counter at 3.00 kWh
    source = CumulativeEnergySource()
    source.observe(reading(at="02:14", value="3.00"))

    # When — the sensor reports the same value again
    source.observe(reading(at="02:19", value="3.00"))

    # Then — the still counter is logged as no movement
    assert source.recent_decisions()[-1] == Decision(
        at=moment("02:19"), reason=DecisionReason.NO_MOVEMENT, kwh=None
    )


def test_cumulative_source_decision_log_keeps_only_the_most_recent_entries() -> None:
    # Given — a source fed far more readings than the log retains
    source = CumulativeEnergySource()
    for minute in range(30):
        source.observe(reading(at=f"03:{minute:02d}", value=str(Decimal(minute))))

    # When — the bounded log is read back
    decisions = source.recent_decisions()

    # Then — it retains only the last 20, newest last, oldest evicted
    assert len(decisions) == 20
    assert decisions[-1].at == moment("03:29")
    assert decisions[0].at == moment("03:10")


def test_cumulative_source_snapshot_exposes_last_reading_and_decisions() -> None:
    # Given — a Wh counter seen twice
    source = CumulativeEnergySource(unit=EnergyUnit.WH)
    source.observe(reading(at="02:14", value="2750"))
    source.observe(reading(at="02:19", value="3000"))

    # When — a diagnostics snapshot is taken
    snapshot = source.snapshot()

    # Then — it reports the unit, the last known reading, and the decision log
    assert snapshot.unit is EnergyUnit.WH
    assert snapshot.last_value == Decimal(3000)
    assert snapshot.last_at == moment("02:19")
    assert snapshot.recent_decisions == source.recent_decisions()


def test_cumulative_source_snapshot_before_any_reading_has_no_last_value() -> None:
    # Given — a source that has never observed a reading
    source = CumulativeEnergySource()

    # When — a snapshot is taken
    snapshot = source.snapshot()

    # Then — there is no last reading and the decision log is empty
    assert snapshot.last_value is None
    assert snapshot.last_at is None
    assert snapshot.recent_decisions == ()
