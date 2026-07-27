from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    DeviceTotals,
    SourceRole,
    Totals,
)
from custom_components.home_energy_advisor.engine.energy_source import (
    DecisionReason,
)

# A 5-minute-aligned instant; readings are placed at whole-minute offsets from it.
BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
PEAK = Decimal("0.30")


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _total_actual(result: Totals) -> Decimal:
    return sum(
        (d.actual_cost for d in result.devices.values()),
        start=result.untracked.actual_cost,
    )


def test_source_diagnostics_snapshots_every_observed_meter() -> None:
    # Given — a home with a grid meter and one tracked device, each seen twice
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))

    # When — the per-source diagnostics are read
    diagnostics = acc.source_diagnostics()

    # Then — every observed meter is keyed by its entity id with its last reading
    # and gating log exposed for the diagnostics download
    assert set(diagnostics) == {"sensor.grid_import", "sensor.guest_energy"}
    guest = diagnostics["sensor.guest_energy"]
    assert guest.last_value == Decimal("0.6")
    assert guest.last_at == at(5)
    assert guest.recent_decisions[-1].reason is DecisionReason.COUNTED


def test_consecutive_overdrawn_buckets_are_counted_for_the_remainder_repair() -> None:
    # Given — a home whose tracked device is (implausibly) drawing more than the
    # house imports, bucket after bucket: the double-counting the remainder clamp
    # hides and the Repair must surface (HEA-24 / HEA-36)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — across three intervals the house imports 0.1 kWh each but the device
    # reports drawing 0.5 kWh each
    buckets = ((5, "0.1", "0.5"), (10, "0.2", "1.0"), (15, "0.3", "1.5"))
    for minute, grid, device in buckets:
        acc.observe("sensor.grid_import", at(minute), Decimal(grid))
        acc.observe("sensor.guest_energy", at(minute), Decimal(device))
    acc.finalize(at(60))

    # Then — every over-drawn bucket is counted, so the coordinator can raise the
    # persistent-negative-remainder Repair once the run is long enough
    assert acc.consecutive_overdrawn_buckets() == 3


def test_overdrawn_run_resets_when_consumption_catches_up() -> None:
    # Given — a device that over-draws for a bucket, then behaves
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — one over-drawn bucket is followed by a healthy one (import ≥ draw)
    acc.observe("sensor.grid_import", at(5), Decimal("0.1"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_import", at(10), Decimal("1.1"))
    acc.observe("sensor.guest_energy", at(10), Decimal("0.6"))
    acc.finalize(at(60))

    # Then — the run resets to zero; the mismatch was transient, not persistent
    assert acc.consecutive_overdrawn_buckets() == 0


def test_import_only_prices_a_device_at_the_import_rate() -> None:
    # Given — a tariff-only home: one grid meter, one tracked device, one price
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — over one 5-minute interval the house imports 1 kWh, the device 0.6
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # Then — the device is priced at the import rate, the rest is Untracked, and
    # the parts sum to the real grid cost
    result = acc.totals()
    guest = result.devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.18")
    assert guest.naive_cost == Decimal("0.18")
    assert guest.cost_savings == Decimal(0)
    assert result.untracked.energy_kwh == Decimal("0.4")
    assert _total_actual(result) == Decimal("0.30")


def test_full_balance_solar_makes_a_device_cheaper_than_grid() -> None:
    # Given — a solar home configured with generation + export (full-balance)
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.SOLAR: "sensor.solar",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    for entity in (
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.solar",
        "sensor.guest_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When — the interval imports 1 kWh, generates 2 kWh solar, exports 1 kWh
    # (so solar-to-house = 2 - 0 - 1 = 1 kWh); consumption = 1 grid + 1 solar = 2 kWh
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.solar", at(5), Decimal("2.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("2.0"))
    acc.finalize(at(30))

    # Then — the device drew all 2 kWh at the blended €0.15/kWh (€0.30 grid over
    # 2 kWh consumed); naive values it at the €0.30 import rate, so solar saved half
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("2.0")
    assert guest.actual_cost == Decimal("0.30")
    assert guest.naive_cost == Decimal("0.60")
    assert guest.cost_savings == Decimal("0.30")


def test_battery_discharge_is_priced_at_its_stored_cost() -> None:
    # Given — a home that charged its battery from the grid overnight (cheap),
    # now discharging it at peak
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), Decimal("0.10"))
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.guest_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When — interval 1: import 2 kWh, all of it charging the battery (grid-charge),
    # house load 0
    acc.observe("sensor.grid_import", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.guest_energy", at(5), Decimal(0))
    # interval 2 (price now peak): battery discharges 2 kWh to serve the device
    acc.record_price(at(5), PEAK)
    acc.observe("sensor.grid_import", at(10), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(10), Decimal("2.0"))
    acc.observe("sensor.house_load", at(10), Decimal("2.0"))
    acc.observe("sensor.guest_energy", at(10), Decimal("2.0"))
    acc.finalize(at(40))

    # Then — the device's 2 kWh is priced at the €0.10 the battery stored, not the
    # €0.30 peak; naive values it at peak, so the saving is the gap
    result = acc.totals()
    guest = result.devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("2.0")
    assert guest.actual_cost == Decimal("0.20")
    assert guest.naive_cost == Decimal("0.60")
    # And the total allocated equals the real grid bill (2 kWh imported at €0.10
    # to charge) — the battery deferred the cost rather than double-counting it
    assert _total_actual(result) == Decimal("0.20")


def test_charge_split_attributes_charging_to_grid_up_to_what_was_imported() -> None:
    # Given — a solar+battery home on the residual model
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), Decimal("0.10"))
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.guest_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When — interval 1: charge 4 kWh but only import 1 kWh (3 kWh from solar);
    # so grid-charge = min(4, 1) = 1 kWh at €0.10, solar-charge = 3 kWh free
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("4.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.guest_energy", at(5), Decimal(0))
    # interval 2: discharge all 4 kWh to the device
    acc.record_price(at(5), PEAK)
    acc.observe("sensor.grid_import", at(10), Decimal("1.0"))
    acc.observe("sensor.battery_discharge", at(10), Decimal("4.0"))
    acc.observe("sensor.house_load", at(10), Decimal("4.0"))
    acc.observe("sensor.guest_energy", at(10), Decimal("4.0"))
    acc.finalize(at(40))

    # Then — stored cost is €0.10 over 4 kWh = €0.025/kWh; the device's 4 kWh
    # costs just the €0.10 that charged it from the grid
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.actual_cost == Decimal("0.10")


def test_buckets_are_not_finalised_until_past_the_lateness_margin() -> None:
    # Given — an interval's readings are in
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))

    # When — we finalise only 6 minutes after the interval ended (< 15 min margin)
    acc.finalize(at(11))

    # Then — nothing has been allocated yet
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal(0)


def test_a_late_delta_into_a_retained_bucket_is_reallocated_not_dropped() -> None:
    # Given — bucket at(0) is finalised while the device stayed silent through it;
    # the retention ring still holds that bucket's context (HEA-48)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.finalize(at(30))  # bucket at(0) finalised; watermark = at(0)

    # When — the coarse device finally reports, its delta spanning the finalised
    # (but still retained) bucket
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(40))

    # Then — the energy is reclaimed by re-running that bucket's allocation with its
    # retained prices: the device is credited, and exactly that value moves out of
    # the Untracked remainder rather than being silently lost
    result = acc.totals()
    guest = result.devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.18")
    assert result.untracked.energy_kwh == Decimal("0.4")
    assert result.whole_home.energy_kwh == Decimal("1.0")
    assert _total_actual(result) == Decimal("0.30")


def test_progressive_finalisation_loses_no_coarse_device_energy() -> None:
    # Given — the founding use case: a a cycle-resetting counter aircon reporting 0.25 kWh steps at
    # the real guest-bedroom cadence (21/22/31/37/44-minute gaps), while the house
    # imports steadily and the coordinator finalises every minute (HEA-48 §1)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    steps = {21: "0.25", 43: "0.50", 74: "0.75", 111: "1.00", 155: "1.25"}

    # When — readings arrive on that cadence and every minute triggers a finalise,
    # so each coarse step spans buckets long since past the watermark
    for minute in range(1, 200):
        if minute % 5 == 0:
            acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
        if minute in steps:
            acc.observe("sensor.guest_energy", at(minute), Decimal(steps[minute]))
        acc.finalize(at(minute))

    # Then — every kWh the aircon reported is accounted to it, none reattributed to
    # Untracked. The old watermark-drop lost 30-50 % here; the residual now is pure
    # Decimal-context rounding from summing time-proportional portions — 1e-27 kWh,
    # zero at any observable precision — while the aggregate split still reconciles
    # exactly (Untracked is derived from the whole home minus the devices).
    result = acc.totals()
    guest = result.devices["coarse_step_aircon"]
    assert guest.energy_kwh.quantize(Decimal("0.000000001")) == Decimal("1.250000000")
    reconciled = guest.energy_kwh + result.untracked.energy_kwh
    assert reconciled == result.whole_home.energy_kwh


def test_a_late_correction_moves_value_only_from_untracked_to_that_device() -> None:
    # Given — two devices; A drew in bucket at(0), B was silent, and the bucket is
    # finalised with A and Untracked recorded
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={
            "device_a": "sensor.a_energy",
            "device_b": "sensor.b_energy",
        },
    )
    acc.record_price(at(0), PEAK)
    for entity in ("sensor.grid_import", "sensor.a_energy", "sensor.b_energy"):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.a_energy", at(5), Decimal("0.2"))
    acc.finalize(at(30))  # bucket at(0) finalised; A=0.2, Untracked=0.8

    before_a = acc.totals().devices["device_a"]

    # When — device B reports late, its delta spanning the finalised bucket
    acc.observe("sensor.b_energy", at(5), Decimal("0.3"))
    acc.finalize(at(40))

    # Then — B gains its share, exactly that value leaves Untracked, and device A's
    # published figures are never revised
    result = acc.totals()
    assert result.devices["device_a"] == before_a
    assert result.devices["device_b"].energy_kwh == Decimal("0.3")
    assert result.devices["device_b"].actual_cost == Decimal("0.09")
    assert result.untracked.energy_kwh == Decimal("0.5")
    assert result.untracked.actual_cost == Decimal("0.15")
    assert result.whole_home.energy_kwh == Decimal("1.0")
    assert _total_actual(result) == Decimal("0.30")


def test_an_overdrawing_late_device_is_capped_at_the_untracked_headroom() -> None:
    # Given — bucket at(0) finalised with device A taking almost all the house
    # consumption, leaving only 0.1 kWh of Untracked headroom
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={
            "device_a": "sensor.a_energy",
            "device_b": "sensor.b_energy",
        },
    )
    acc.record_price(at(0), PEAK)
    for entity in ("sensor.grid_import", "sensor.a_energy", "sensor.b_energy"):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.a_energy", at(5), Decimal("0.9"))
    acc.finalize(at(30))

    before_a = acc.totals().devices["device_a"]

    # When — device B reports 0.4 kWh late, overdrawing the bucket (0.9 + 0.4 > 1.0)
    acc.observe("sensor.b_energy", at(5), Decimal("0.4"))
    acc.finalize(at(40))

    # Then — B keeps all its real energy, but its cost gain is capped at the €0.03
    # of headroom Untracked held; A is untouched; the real bill is still fully split
    result = acc.totals()
    b = result.devices["device_b"]
    assert result.devices["device_a"] == before_a
    assert b.energy_kwh == Decimal("0.4")
    assert b.actual_cost == Decimal("0.03")
    assert result.untracked.actual_cost == Decimal(0)
    assert result.untracked.energy_kwh == Decimal(0)
    assert result.whole_home.actual_cost == Decimal("0.30")
    assert _total_actual(result) == Decimal("0.30")


def test_a_delta_older_than_the_retention_ring_is_dropped_and_logged() -> None:
    # Given — a short 30-minute retention ring, and a house that runs long enough
    # for bucket at(0) to be evicted from the ring
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
        retention=timedelta(minutes=30),
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    for minute in range(5, 135, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
    acc.finalize(at(150))  # watermark ~ at(125); bucket at(0) evicted (< 125-30)

    # When — the device finally reports a step spanning the long-evicted bucket
    acc.observe("sensor.guest_energy", at(5), Decimal("0.25"))
    acc.finalize(at(160))

    # Then — the energy is genuinely dropped (beyond the ring), but never silently:
    # a DROPPED_LATE decision is logged so diagnostics can prove it
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal(0)
    decisions = acc.source_diagnostics()["sensor.guest_energy"].recent_decisions
    dropped = [d for d in decisions if d.reason is DecisionReason.DROPPED_LATE]
    assert len(dropped) == 1
    assert dropped[0].kwh == Decimal("0.25")


def test_unavailable_reading_produces_no_phantom_delta() -> None:
    # Given — a device that goes unavailable then recovers
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal("2.75"))

    # When — the device reports unavailable, then recovers unchanged
    acc.observe("sensor.guest_energy", at(2), None)
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("2.75"))
    acc.finalize(at(30))

    # Then — the recovery is not read as fresh consumption
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal(0)


def test_totals_start_empty() -> None:
    # Given / When — a fresh accountant with a tracked device
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )

    # Then — every figure is zero, including the Untracked remainder
    result = acc.totals()
    assert result.devices["coarse_step_aircon"] == DeviceTotals(
        energy_kwh=Decimal(0),
        actual_cost=Decimal(0),
        naive_cost=Decimal(0),
        cost_savings=Decimal(0),
    )
    assert result.untracked.energy_kwh == Decimal(0)


def test_import_without_a_known_price_is_tracked_but_costs_nothing() -> None:
    # Given — grid import and a device, but no price has ever been recorded
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — an interval passes
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # Then — energy is still tracked, but with no price it is costed at zero
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal(0)


def test_readings_from_unconfigured_entities_are_ignored() -> None:
    # Given — an accountant that knows nothing about a stray entity
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)

    # When — a reading arrives for an entity that is neither a source nor a device
    acc.observe("sensor.random", at(0), Decimal(0))
    acc.observe("sensor.random", at(5), Decimal(99))
    acc.finalize(at(30))

    # Then — it is ignored, adding no phantom energy anywhere
    assert acc.totals().untracked.energy_kwh == Decimal(0)
