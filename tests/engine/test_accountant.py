from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from custom_components.home_energy_advisor.engine.accountant import (
    Accountant,
    AccountingWindows,
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


# Every figure a device carries, at zero - what a fresh or freshly-rebased
# accountant must publish. Spelled out rather than defaulted so that adding a
# concept to DeviceTotals fails here until it is deliberately accounted for.
ZERO_TOTALS = DeviceTotals(
    energy_kwh=Decimal(0),
    actual_cost=Decimal(0),
    naive_cost=Decimal(0),
    cost_savings=Decimal(0),
    energy_from_grid=Decimal(0),
    energy_from_generation=Decimal(0),
    energy_from_battery=Decimal(0),
    cost_floor=Decimal(0),
    cost_ceiling=Decimal(0),
)


def test_source_diagnostics_snapshots_every_observed_meter() -> None:
    # Given - a home with a grid meter and one tracked device, each seen twice
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))

    # When - the per-source diagnostics are read
    diagnostics = acc.source_diagnostics()

    # Then - every observed meter is keyed by its entity id with its last reading
    # and gating log exposed for the diagnostics download
    assert set(diagnostics) == {"sensor.grid_import", "sensor.coarse_step_energy"}
    aircon = diagnostics["sensor.coarse_step_energy"]
    assert aircon.last_value == Decimal("0.6")
    assert aircon.last_at == at(5)
    assert aircon.recent_decisions[-1].reason is DecisionReason.COUNTED


def test_import_only_prices_a_device_at_the_import_rate() -> None:
    # Given - a tariff-only home: one grid meter, one tracked device, one price
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))

    # When - over one 5-minute interval the house imports 1 kWh, the device 0.6
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # Then - the device is priced at the import rate, the rest is Untracked, and
    # the parts sum to the real grid cost
    result = acc.totals()
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.6")
    assert aircon.actual_cost == Decimal("0.18")
    assert aircon.naive_cost == Decimal("0.18")
    assert aircon.cost_savings == Decimal(0)
    assert result.untracked.energy_kwh == Decimal("0.4")
    assert _total_actual(result) == Decimal("0.30")


def test_full_balance_solar_makes_a_device_cheaper_than_grid() -> None:
    # Given - a solar home configured with generation + export (full-balance)
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: "sensor.solar",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    for entity in (
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.solar",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When - the interval imports 1 kWh, generates 2 kWh solar, exports 1 kWh
    # (so solar-to-house = 2 - 0 - 1 = 1 kWh); consumption = 1 grid + 1 solar = 2 kWh
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.solar", at(5), Decimal("2.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("2.0"))
    acc.finalize(at(30))

    # Then - the device drew all 2 kWh at the blended €0.15/kWh (€0.30 grid over
    # 2 kWh consumed); naive values it at the €0.30 import rate, so solar saved half
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("2.0")
    assert aircon.actual_cost == Decimal("0.30")
    assert aircon.naive_cost == Decimal("0.60")
    assert aircon.cost_savings == Decimal("0.30")


def test_battery_discharge_is_priced_at_its_stored_cost() -> None:
    # Given - a home that charged its battery from the grid overnight (cheap),
    # now discharging it at peak
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        # Isolate the battery ledger from quiet-run spreading (HEA-74): these
        # meters sit unchanged and then jump by design here, which the spreading
        # rule would legitimately smear back across earlier intervals. That rule
        # has its own tests; this one is about what a stored kWh costs.
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), Decimal("0.10"))
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When - interval 1: import 2 kWh, all of it charging the battery (grid-charge),
    # house load 0
    acc.observe("sensor.grid_import", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal(0))
    # interval 2 (price now peak): battery discharges 2 kWh to serve the device
    acc.record_price(at(5), PEAK)
    acc.observe("sensor.grid_import", at(10), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(10), Decimal("2.0"))
    acc.observe("sensor.house_load", at(10), Decimal("2.0"))
    acc.observe("sensor.coarse_step_energy", at(10), Decimal("2.0"))
    acc.finalize(at(40))

    # Then - the device's 2 kWh is priced at the €0.10 the battery stored, not the
    # €0.30 peak; naive values it at peak, so the saving is the gap
    result = acc.totals()
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("2.0")
    assert aircon.actual_cost == Decimal("0.20")
    assert aircon.naive_cost == Decimal("0.60")
    # And the total allocated equals the real grid bill (2 kWh imported at €0.10
    # to charge) - the battery deferred the cost rather than double-counting it
    assert _total_actual(result) == Decimal("0.20")


def test_charge_split_attributes_charging_to_grid_up_to_what_was_imported() -> None:
    # Given - a solar+battery home on the residual model
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), Decimal("0.10"))
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))

    # When - interval 1: charge 4 kWh but only import 1 kWh (3 kWh from solar);
    # so grid-charge = min(4, 1) = 1 kWh at €0.10, solar-charge = 3 kWh free
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("4.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal(0))
    # interval 2: discharge all 4 kWh to the device
    acc.record_price(at(5), PEAK)
    acc.observe("sensor.grid_import", at(10), Decimal("1.0"))
    acc.observe("sensor.battery_discharge", at(10), Decimal("4.0"))
    acc.observe("sensor.house_load", at(10), Decimal("4.0"))
    acc.observe("sensor.coarse_step_energy", at(10), Decimal("4.0"))
    acc.finalize(at(40))

    # Then - stored cost is €0.10 over 4 kWh = €0.025/kWh; the device's 4 kWh
    # costs just the €0.10 that charged it from the grid
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.actual_cost == Decimal("0.10")


def test_buckets_are_not_finalised_until_past_the_lateness_margin() -> None:
    # Given - an interval's readings are in
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))

    # When - we finalise only 6 minutes after the interval ended (< 15 min margin)
    acc.finalize(at(11))

    # Then - nothing has been allocated yet
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal(0)


def test_a_late_delta_into_a_retained_bucket_is_reallocated_not_dropped() -> None:
    # Given - bucket at(0) is finalised while the device stayed silent through it;
    # the retention ring still holds that bucket's context (HEA-48)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.finalize(at(30))  # bucket at(0) finalised; watermark = at(0)

    # When - the coarse device finally reports, its delta spanning the finalised
    # (but still retained) bucket, and the house consumes on so the remainder can
    # afford to hand the value over without printing an hour that went backwards
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.observe("sensor.grid_import", at(10), Decimal("2.0"))
    acc.finalize(at(40))

    # Then - the energy is reclaimed by re-running that bucket's allocation with its
    # retained prices: the device is credited, and exactly that value moves out of
    # the Untracked remainder rather than being silently lost
    result = acc.totals()
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.6")
    assert aircon.actual_cost == Decimal("0.18")
    assert result.untracked.energy_kwh == Decimal("1.4")
    assert result.whole_home.energy_kwh == Decimal("2.0")
    assert _total_actual(result) == Decimal("0.60")


def test_progressive_finalisation_loses_no_coarse_device_energy() -> None:
    # Given - the founding use case: a cycle-resetting aircon reporting 0.25 kWh
    # steps at
    # the real coarse-step cadence (21/22/31/37/44-minute gaps), while the house
    # imports steadily and the coordinator finalises every minute (HEA-48 §1)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    steps = {21: "0.25", 43: "0.50", 74: "0.75", 111: "1.00", 155: "1.25"}

    # When - readings arrive on that cadence and every minute triggers a finalise,
    # so each coarse step spans buckets long since past the watermark
    for minute in range(1, 200):
        if minute % 5 == 0:
            acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
        if minute in steps:
            acc.observe("sensor.coarse_step_energy", at(minute), Decimal(steps[minute]))
        acc.finalize(at(minute))

    # Then - every kWh the aircon reported is accounted to it, none reattributed to
    # Untracked. The old watermark-drop lost 30-50 % here; the residual now is pure
    # Decimal-context rounding from summing time-proportional portions - 1e-27 kWh,
    # zero at any observable precision - while the aggregate split still reconciles
    # exactly (Untracked is derived from the whole home minus the devices).
    result = acc.totals()
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh.quantize(Decimal("0.000000001")) == Decimal("1.250000000")
    reconciled = aircon.energy_kwh + result.untracked.energy_kwh
    assert reconciled == result.whole_home.energy_kwh


def test_a_late_correction_moves_value_only_from_untracked_to_that_device() -> None:
    # Given - two devices; A drew in bucket at(0), B was silent, and the bucket is
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

    # When - device B reports late, its delta spanning the finalised bucket, and
    # the house consumes on so the remainder can fund the handover
    acc.observe("sensor.b_energy", at(5), Decimal("0.3"))
    acc.observe("sensor.grid_import", at(10), Decimal("2.0"))
    acc.finalize(at(40))

    # Then - B gains its share, exactly that value leaves Untracked, and device A's
    # published figures are never revised
    result = acc.totals()
    assert result.devices["device_a"] == before_a
    assert result.devices["device_b"].energy_kwh == Decimal("0.3")
    assert result.devices["device_b"].actual_cost == Decimal("0.09")
    assert result.untracked.energy_kwh == Decimal("1.5")
    assert result.untracked.actual_cost == Decimal("0.45")
    assert result.whole_home.energy_kwh == Decimal("2.0")
    assert _total_actual(result) == Decimal("0.60")


def test_an_overdrawing_late_device_pays_import_for_what_untracked_cannot_fund() -> (
    None
):
    # Given - bucket at(0) finalised with device A taking almost all the house
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

    # When - device B reports 0.4 kWh late, overdrawing the bucket (0.9 + 0.4 > 1.0)
    acc.observe("sensor.b_energy", at(5), Decimal("0.4"))
    acc.finalize(at(40))

    # Then - B keeps the 0.3 kWh no meter reading backs, which is its outright and
    # takes nothing from anyone. The €0.03 of headroom Untracked holds is B's too,
    # but it *comes out of* the remainder, so it waits for a bucket whose remainder
    # can afford to hand it over - nothing has consumed since, so nothing moves
    # yet. Neither published figure has gone backwards, and A is untouched.
    result = acc.totals()
    b = result.devices["device_b"]
    assert result.devices["device_a"] == before_a
    assert b.energy_kwh == Decimal("0.3")
    assert b.actual_cost == Decimal(0)
    assert result.untracked.actual_cost == Decimal("0.03")
    assert result.untracked.energy_kwh == Decimal("0.1")
    assert result.whole_home.actual_cost == Decimal("0.30")
    assert _total_actual(result) == Decimal("0.30")

    # And both waits are deferrals, not forgiveness. With no surplus ever arriving,
    # the quiet span ends: the suspended overdraw costs the import rate after all,
    # and the held headroom is handed over rather than stranding B short for good
    acc.finalize(at(200))
    settled = acc.totals()
    assert settled.devices["device_b"].energy_kwh == Decimal("0.4")
    assert settled.devices["device_b"].actual_cost == Decimal("0.12")
    assert settled.untracked.actual_cost == Decimal(0)
    assert settled.whole_home.actual_cost == Decimal("0.39")
    assert _total_actual(settled) == settled.whole_home.actual_cost


def test_a_late_correction_buys_its_excess_at_import_not_at_a_free_blend() -> None:
    # Given - a finalised bucket served half by grid and half by generation, so its
    # blended rate is half the import rate, with the tracked device already taking
    # all of the consumption
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GENERATION: "sensor.solar",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
        },
        device_energy_entities={
            "steady_load": "sensor.steady_energy",
            "cloud_polled_pump": "sensor.cloud_polled_energy",
        },
    )
    acc.record_price(at(0), PEAK)
    for entity in (
        "sensor.grid_import",
        "sensor.solar",
        "sensor.grid_export",
        "sensor.steady_energy",
        "sensor.cloud_polled_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.solar", at(5), Decimal("1.0"))
    acc.observe("sensor.steady_energy", at(5), Decimal("2.0"))
    acc.finalize(at(30))

    # When - the coarse counter reports 1 kWh late into that same bucket, with no
    # Untracked headroom left to fund it
    acc.observe("sensor.cloud_polled_energy", at(5), Decimal("1.0"))
    acc.finalize(at(40))

    # Then - the late kWh keeps its energy but carries no charge yet: there was no
    # Untracked headroom to fund any of it, and generation already consumed cannot
    # supply it a second time, so nothing about its price is known until the debt
    # settles (HEA-85).
    pump = acc.totals().devices["cloud_polled_pump"]
    assert pump.energy_kwh == Decimal("1.0")
    assert pump.actual_cost == Decimal(0)

    # And when nothing ever repays it, it costs the full import rate - never the
    # €0.15 blend the bucket happened to settle at (ADR-0014)
    acc.finalize(at(200))
    assert acc.totals().devices["cloud_polled_pump"].actual_cost == PEAK


def test_a_delta_older_than_the_retention_ring_is_dropped_and_logged() -> None:
    # Given - a short 30-minute retention ring, and a house that runs long enough
    # for bucket at(0) to be evicted from the ring
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        windows=AccountingWindows(retention=timedelta(minutes=30)),
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    for minute in range(5, 135, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
    acc.finalize(at(150))  # watermark ~ at(125); bucket at(0) evicted (< 125-30)

    # When - the device finally reports a step spanning the long-evicted bucket
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.25"))
    acc.finalize(at(160))

    # Then - the energy is genuinely dropped (beyond the ring), but never silently:
    # a DROPPED_LATE decision is logged so diagnostics can prove it
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal(0)
    decisions = acc.source_diagnostics()["sensor.coarse_step_energy"].recent_decisions
    dropped = [d for d in decisions if d.reason is DecisionReason.DROPPED_LATE]
    assert len(dropped) == 1
    assert dropped[0].kwh == Decimal("0.25")


def test_unavailable_reading_produces_no_phantom_delta() -> None:
    # Given - a device that goes unavailable then recovers
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal("2.75"))

    # When - the device reports unavailable, then recovers unchanged
    acc.observe("sensor.coarse_step_energy", at(2), None)
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("2.75"))
    acc.finalize(at(30))

    # Then - the recovery is not read as fresh consumption
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal(0)


def test_totals_start_empty() -> None:
    # Given / When - a fresh accountant with a tracked device
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )

    # Then - every figure is zero, including the Untracked remainder
    result = acc.totals()
    assert result.devices["coarse_step_aircon"] == ZERO_TOTALS
    assert result.untracked.energy_kwh == Decimal(0)


def test_import_without_a_known_price_is_tracked_but_costs_nothing() -> None:
    # Given - grid import and a device, but no price has ever been recorded
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))

    # When - an interval passes
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # Then - energy is still tracked, but with no price it is costed at zero
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.6")
    assert aircon.actual_cost == Decimal(0)


def test_readings_from_unconfigured_entities_are_ignored() -> None:
    # Given - an accountant that knows nothing about a stray entity
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)

    # When - a reading arrives for an entity that is neither a source nor a device
    acc.observe("sensor.random", at(0), Decimal(0))
    acc.observe("sensor.random", at(5), Decimal(99))
    acc.finalize(at(30))

    # Then - it is ignored, adding no phantom energy anywhere
    assert acc.totals().untracked.energy_kwh == Decimal(0)


def test_finalising_prunes_superseded_prices_but_keeps_costs_correct() -> None:
    # Given - the import price changes once, an hour into a steady run; left
    # unpruned the price list would grow without bound and be rescanned from index
    # zero on every finalised bucket (HEA-53)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), Decimal("0.10"))
    acc.record_price(at(60), Decimal("0.30"))
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))

    # When - two hours of readings (house 1 kWh/interval, device 0.5) are finalised
    # well past the second price change
    for minute in range(5, 125, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
        acc.observe("sensor.coarse_step_energy", at(minute), Decimal(minute) / 10)
    acc.finalize(at(150))

    # Then - the superseded first price is pruned (only the price active at the
    # watermark and any later survive), yet the accounting still reflects both
    # tariffs: 12 intervals of 0.5 kWh at 0.10 then 12 more at 0.30
    assert len(acc._prices) == 1  # noqa: SLF001
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("12.0")
    assert aircon.actual_cost == Decimal("2.4")


def test_flush_finalises_in_flight_buckets_so_they_can_be_banked() -> None:
    # Given - an interval's readings are in but not yet past the lateness margin,
    # so nothing has been finalised (a reload here would drop them)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(11))  # < margin: still nothing allocated
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal(0)

    # When - the accountant is flushed, as the coordinator does on unload
    acc.flush(at(11))

    # Then - the in-flight interval is sealed and banked, so the sensors' restore
    # baseline captures it instead of losing ~20 min of accounting (HEA-53)
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.6")
    assert aircon.actual_cost == Decimal("0.18")


def test_a_bucket_finalised_before_any_price_is_logged_as_zero_priced() -> None:
    # Given - grid import and a device, but no price has ever been recorded
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))

    # When - an interval is finalised while the price list is still empty
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # Then - energy is still tracked and costed at zero (unchanged), but the era is
    # now explainable: a ZERO_PRICED decision is logged on the import source so the
    # diagnostics download accounts for the zero-cost early bucket (HEA-53)
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.6")
    assert aircon.actual_cost == Decimal(0)
    decisions = acc.source_diagnostics()["sensor.grid_import"].recent_decisions
    assert [d.reason for d in decisions].count(DecisionReason.ZERO_PRICED) == 1


def test_zero_priced_is_logged_once_then_never_after_a_price_arrives() -> None:
    # Given - a home that finalises several buckets before its first price
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    for minute in range(5, 30, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
    acc.finalize(at(40))  # several zero-priced buckets in one go

    # When - a price finally arrives and the run continues
    acc.record_price(at(40), PEAK)
    for minute in range(30, 60, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
    acc.finalize(at(90))

    # Then - the cold-start era is marked exactly once, not once per bucket, and not
    # again once pricing is known
    decisions = acc.source_diagnostics()["sensor.grid_import"].recent_decisions
    assert [d.reason for d in decisions].count(DecisionReason.ZERO_PRICED) == 1


def test_reset_totals_rebases_every_running_total_to_zero() -> None:
    # Given - a home that has accumulated real cost across a finalised interval
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))
    assert acc.totals().whole_home.energy_kwh == Decimal("1.0")

    # When - the totals are rebased
    acc.reset_totals()

    # Then - every published figure starts from zero: the tracked device, the
    # derived Untracked remainder, and the whole-home aggregate alike
    result = acc.totals()
    assert result.devices["coarse_step_aircon"] == ZERO_TOTALS
    assert result.untracked == ZERO_TOTALS
    assert result.whole_home == ZERO_TOTALS


def test_reset_totals_keeps_meter_tracking_so_the_next_delta_is_not_a_phantom() -> None:
    # Given - a home whose meters have been read up to 1.0 kWh, then rebased
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))
    acc.reset_totals()

    # When - the counters climb again after the rebase
    acc.observe("sensor.grid_import", at(35), Decimal("2.0"))
    acc.observe("sensor.coarse_step_energy", at(35), Decimal("1.0"))
    acc.finalize(at(70))

    # Then - only the energy that arrived after the rebase is counted. The reset
    # keeps each meter's last reading, so a climbing counter is read neither as a
    # fresh start (dropping the delta) nor as a climb from zero (re-counting the
    # pre-reset kWh)
    result = acc.totals()
    assert result.whole_home.energy_kwh == Decimal("1.0")
    assert result.devices["coarse_step_aircon"].energy_kwh == Decimal("0.4")


def test_reset_totals_discards_pre_reset_energy_still_in_flight() -> None:
    # Given - a home whose most recent interval has been observed but not yet
    # finalised, so its energy is still held in the in-flight buckets
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))

    # When - the totals are rebased and accounting runs on past the lateness margin
    acc.reset_totals()
    acc.finalize(at(40))

    # Then - the pre-reset energy is gone rather than banked into the new era: a
    # rebase is a hard boundary, so nothing earned before it lands after it
    result = acc.totals()
    assert result.whole_home.energy_kwh == Decimal(0)
    assert result.devices["coarse_step_aircon"].energy_kwh == Decimal(0)


def test_reset_totals_keeps_the_battery_stored_cost_ledger() -> None:
    # Given - a home that charged its battery from the grid at €0.10, and rebased
    # its totals before discharging
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
        # As above: this test is about the ledger surviving a rebase, not about
        # how a quiet counter's energy is spread (HEA-74).
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), Decimal("0.10"))
    for entity in (
        "sensor.grid_import",
        "sensor.battery_charge",
        "sensor.battery_discharge",
        "sensor.house_load",
        "sensor.coarse_step_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal(0))
    acc.finalize(at(40))
    acc.reset_totals()

    # When - the stored energy is discharged to serve the device at peak price.
    # The meters re-report unchanged at at(40) first, as a polled source does, so
    # the discharge delta falls wholly inside the peak-priced bucket
    acc.record_price(at(40), PEAK)
    acc.observe("sensor.grid_import", at(40), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(40), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(40), Decimal(0))
    acc.observe("sensor.house_load", at(40), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(40), Decimal(0))
    acc.observe("sensor.grid_import", at(45), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(45), Decimal("2.0"))
    acc.observe("sensor.house_load", at(45), Decimal("2.0"))
    acc.observe("sensor.coarse_step_energy", at(45), Decimal("2.0"))
    acc.finalize(at(80))

    # Then - the discharge is still priced at the €0.10 the battery stored, not
    # given away free: a rebase clears accumulated totals, never the physical state
    # of the battery's stored-cost ledger
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("2.0")
    assert aircon.actual_cost == Decimal("0.20")
    assert aircon.naive_cost == Decimal("0.60")


def _solar_home() -> Accountant:
    """A home with grid, solar and export meters - the full-balance decomposition."""
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GENERATION: "sensor.solar",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )


def _seed_solar_home(acc: Accountant) -> None:
    acc.record_price(at(0), PEAK)
    for entity in ("sensor.grid_import", "sensor.solar", "sensor.grid_export"):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))


def _by_source_sum(totals: DeviceTotals) -> Decimal:
    return (
        totals.energy_from_grid
        + totals.energy_from_generation
        + totals.energy_from_battery
    )


def test_running_totals_carry_each_devices_energy_by_source() -> None:
    # Given - a solar home where 0.4 kWh was imported and 0.3 kWh of generation was
    # self-consumed (0.5 generated, 0.2 exported), so the house was served 0.7 kWh
    acc = _solar_home()
    _seed_solar_home(acc)

    # When - the device draws 0.5 kWh of that interval and it is finalised
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.5"))
    acc.finalize(at(30))

    # Then - the device's energy is split in the mix that served the bucket, so a
    # self-sufficiency share can be read straight off the totals (HEA-51)
    aircon = acc.totals().devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.5")
    assert aircon.energy_from_grid == Decimal("0.2857142857142857142857142857")
    assert aircon.energy_from_generation == Decimal("0.2142857142857142857142857143")
    assert aircon.energy_from_battery == Decimal(0)
    assert _by_source_sum(aircon) == aircon.energy_kwh


def test_untracked_by_source_derives_so_the_split_reconciles() -> None:
    # Given - the same solar interval, part of it drawn by the tracked device
    acc = _solar_home()
    _seed_solar_home(acc)
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.5"))

    # When - the interval is finalised
    acc.finalize(at(30))

    # Then - device plus Untracked equal the whole home for every source, just as
    # they do for energy and cost: Untracked is derived, never accumulated
    result = acc.totals()
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_from_grid + result.untracked.energy_from_grid == (
        result.whole_home.energy_from_grid
    )
    assert aircon.energy_from_generation + result.untracked.energy_from_generation == (
        result.whole_home.energy_from_generation
    )
    # And the home's own split still sums to its energy, and to what was served
    assert _by_source_sum(result.whole_home) == result.whole_home.energy_kwh
    assert result.whole_home.energy_from_grid == Decimal("0.4")
    assert result.whole_home.energy_from_generation == Decimal("0.3")


def test_a_late_correction_carries_the_retained_buckets_source_mix() -> None:
    # Given - a solar bucket finalised while the coarse device stayed silent, its
    # context still held in the retention ring (ADR-0006)
    acc = _solar_home()
    _seed_solar_home(acc)
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.finalize(at(30))  # bucket at(0) finalised; watermark = at(0)

    # When - the device reports late into that finalised, still-retained bucket,
    # and the house runs another identical interval so the remainder can afford to
    # hand the reclaimed energy over
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_import", at(10), Decimal("0.8"))
    acc.observe("sensor.solar", at(10), Decimal("1.0"))
    acc.observe("sensor.grid_export", at(10), Decimal("0.4"))
    acc.finalize(at(40))

    # Then - the reclaimed energy is attributed in that bucket's own source mix,
    # not the current one, and still sums to the device's energy. The mix is the
    # first bucket's even though it was handed over during the second, which is
    # the whole point of retaining the context
    result = acc.totals()
    aircon = result.devices["coarse_step_aircon"]
    assert aircon.energy_kwh == Decimal("0.5")
    assert aircon.energy_from_grid == Decimal("0.2857142857142857142857142857")
    assert aircon.energy_from_generation == Decimal("0.2142857142857142857142857143")
    assert _by_source_sum(aircon) == aircon.energy_kwh
    # And Untracked gives back exactly what the device gained, per source
    assert result.untracked.energy_from_grid == Decimal("0.8") - (
        aircon.energy_from_grid
    )


def test_reset_totals_rebases_the_by_source_totals_too() -> None:
    # Given - a solar home with accumulated by-source energy
    acc = _solar_home()
    _seed_solar_home(acc)
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.5"))
    acc.finalize(at(30))
    assert _by_source_sum(acc.totals().devices["coarse_step_aircon"]) > 0

    # When - the household's totals are rebased (HEA-57)
    acc.reset_totals()

    # Then - the by-source figures start from zero alongside every other total;
    # they are new accumulators that cannot be back-seeded, which is why they must
    # be installed before the reset rather than after it (HEA-51)
    result = acc.totals()
    for totals in (
        result.devices["coarse_step_aircon"],
        result.untracked,
        result.whole_home,
    ):
        assert _by_source_sum(totals) == Decimal(0)


def _metered_home() -> Accountant:
    """A home with a house-consumption meter - the residual decomposition."""
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"utility_plug": "sensor.utility_plug_total"},
    )


def _run_buckets(
    acc: Accountant, *, buckets: int, house_step: str, device_step: str, first: int = 5
) -> None:
    """Climb both counters once per 5-minute bucket, finalising as we go."""
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.house_load", at(0), Decimal(0))
    acc.observe("sensor.utility_plug_total", at(0), Decimal(0))
    house = Decimal(0)
    device = Decimal(0)
    for index in range(buckets):
        minute = first + index * 5
        house += Decimal(house_step)
        device += Decimal(device_step)
        acc.observe("sensor.grid_import", at(minute), house)
        acc.observe("sensor.house_load", at(minute), house)
        acc.observe("sensor.utility_plug_total", at(minute), device)
        acc.finalize(at(minute + 25))


def test_a_device_claiming_more_energy_than_the_whole_house_is_not_booked() -> None:
    # Given - a home using 0.15 kWh per 5-minute bucket, and a device whose
    # counter claims 1.5 kWh in each of them. That is the utility plug's real failure
    # mode: a source that lies is indistinguishable from a huge load, except that
    # no single device can use more than the house (HEA-60)
    acc = _metered_home()

    # When - a full hour of that runs through the ledger
    _run_buckets(acc, buckets=14, house_step="0.15", device_step="1.5")

    # Then - the device is judged implausible and its energy stops being booked,
    # so the lie stops corrupting the ledger
    assert "utility_plug" in acc.implausible_devices()
    pump = acc.totals().devices["utility_plug"]
    assert pump.energy_kwh < Decimal(14) * Decimal("1.5")

    # And - the rejection is explained rather than silent, on the source's own log
    decisions = acc.source_diagnostics()["sensor.utility_plug_total"].recent_decisions
    assert any(d.reason is DecisionReason.IMPLAUSIBLE for d in decisions)


def test_a_coarse_device_overdrawing_one_bucket_is_still_booked() -> None:
    # Given - the founding case the guard must not break: a cycle-resetting
    # aircon reporting
    # a 0.25 kWh step that lands in a single bucket the house only consumed 0.15 in.
    # Over one bucket it "exceeds the house"; over the hour it plainly does not
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.house_load", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))

    # When - the house ticks along and the aircon steps once, coarsely
    house = Decimal(0)
    for index in range(14):
        minute = 5 + index * 5
        house += Decimal("0.15")
        acc.observe("sensor.grid_import", at(minute), house)
        acc.observe("sensor.house_load", at(minute), house)
        if index == 3:
            acc.observe("sensor.coarse_step_energy", at(minute), Decimal("0.25"))
        acc.finalize(at(minute + 25))

    # Then - nothing is flagged and the step is booked in full. Judging a single
    # bucket would have rejected it; the window is what tells timing from lying
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal("0.25")


def test_the_guard_stays_quiet_when_the_house_reports_nothing() -> None:
    # Given - a household whose house-level meter is dead flat while a device draws
    # normally. Every device then "exceeds" a house total of zero
    acc = _metered_home()
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.house_load", at(0), Decimal(0))
    acc.observe("sensor.utility_plug_total", at(0), Decimal(0))

    # When - a full window passes with house consumption never moving
    device = Decimal(0)
    for index in range(14):
        minute = 5 + index * 5
        device += Decimal("0.05")
        acc.observe("sensor.utility_plug_total", at(minute), device)
        acc.finalize(at(minute + 25))

    # Then - no device is condemned on the strength of a missing input. A silent
    # house meter is its own fault, surfaced elsewhere; it is not evidence that a
    # device is lying
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["utility_plug"].energy_kwh > 0


def test_a_flagged_device_recovers_once_its_source_reads_sanely_again() -> None:
    # Given - a device already judged implausible after an hour of lying
    acc = _metered_home()
    _run_buckets(acc, buckets=14, house_step="0.15", device_step="1.5")
    assert "utility_plug" in acc.implausible_devices()
    banked = acc.totals().devices["utility_plug"].energy_kwh

    # When - the source is repointed and starts reporting honestly, for long
    # enough to refill the window
    device = Decimal(14) * Decimal("1.5")
    house = Decimal(14) * Decimal("0.15")
    for index in range(14):
        minute = 75 + index * 5
        house += Decimal("0.15")
        device += Decimal("0.01")
        acc.observe("sensor.grid_import", at(minute), house)
        acc.observe("sensor.house_load", at(minute), house)
        acc.observe("sensor.utility_plug_total", at(minute), device)
        acc.finalize(at(minute + 25))

    # Then - the guard lets go and accounting resumes. A device is never condemned
    # permanently on past behaviour
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["utility_plug"].energy_kwh > banked


def test_implausible_energy_is_refused_on_the_late_correction_path_too() -> None:
    # Given - a device already judged implausible. This is the path that matters
    # most for the real failure: the utility plug was cloud-polled every ~30 minutes,
    # so most of each delta landed past the finalisation watermark and reached the
    # retained ring, never the in-flight buckets (ADR-0006)
    acc = _metered_home()
    _run_buckets(acc, buckets=14, house_step="0.15", device_step="1.5")
    assert "utility_plug" in acc.implausible_devices()
    banked = acc.totals().devices["utility_plug"].energy_kwh
    untracked = acc.totals().untracked.energy_kwh

    # When - another inflated reading arrives spanning a bucket already finalised
    acc.observe("sensor.utility_plug_total", at(75), Decimal(14) * Decimal("1.5") + 8)
    acc.finalize(at(100))

    # Then - the correction is refused, so no value is moved out of the Untracked
    # remainder into a device whose source cannot be telling the truth
    assert acc.totals().devices["utility_plug"].energy_kwh == banked
    assert acc.totals().untracked.energy_kwh == untracked
    decisions = acc.source_diagnostics()["sensor.utility_plug_total"].recent_decisions
    assert any(d.reason is DecisionReason.IMPLAUSIBLE for d in decisions)


def _fully_metered_home() -> Accountant:
    """A home with a house meter *and* the generation and export meters.

    The combination that matters for HEA-67: when the house meter fails there is
    a complete second model available to fall back to.
    """
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
            SourceRole.GENERATION: "sensor.generation",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={},
    )


def _baseline(acc: Accountant) -> None:
    """Establish a zero baseline on every house meter, and a price."""
    acc.record_price(at(0), PEAK)
    for entity in (
        "sensor.grid_import",
        "sensor.grid_export",
        "sensor.generation",
        "sensor.house_load",
    ):
        acc.observe(entity, at(0), Decimal(0))


def test_a_failed_house_meter_falls_back_to_the_full_balance_model() -> None:
    # Given - a fully metered home
    acc = _fully_metered_home()
    _baseline(acc)

    # When - over one bucket the house meter is unavailable, while generation,
    # export and import all report normally
    acc.observe("sensor.house_load", at(5), None)
    acc.observe("sensor.grid_import", at(5), Decimal("0.2"))
    acc.observe("sensor.generation", at(5), Decimal("1.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.3"))
    acc.finalize(at(30))

    # Then - consumption is grid + (generation less export) = 0.2 + 0.7. Reading the
    # dead meter as a zero would have collapsed it to 0.2, silently losing the
    # whole generation component (HEA-67)
    assert acc.totals().untracked.energy_kwh == Decimal("0.9")


def test_a_house_meter_that_does_not_move_keeps_the_residual_model() -> None:
    # Given - the same fully metered home
    acc = _fully_metered_home()
    _baseline(acc)

    # When - the house meter reports but is unchanged, which is what a quiet house
    # on a coarse counter looks like, while generation and export both move
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal(0))
    acc.observe("sensor.generation", at(5), Decimal("1.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.3"))
    acc.finalize(at(30))

    # Then - the house consumed nothing and the residual model says so. This is
    # the case that makes "no reading in the bucket" the wrong signal to fall back
    # on: full-balance would book 0.7 kWh of generation that in fact went to
    # export, every quiet bucket, on a perfectly healthy meter
    assert acc.totals().untracked.energy_kwh == Decimal(0)


def test_the_plausibility_guard_is_suspended_while_a_house_source_is_down() -> None:
    # Given - a device drawing honestly, with a full window of evidence behind it
    acc = _metered_home()
    _run_buckets(acc, buckets=12, house_step="1.0", device_step="0.5")
    assert acc.implausible_devices() == frozenset()
    banked = acc.totals().devices["utility_plug"].energy_kwh

    # When - the house meter fails while the grid meter keeps reporting, so the
    # house total collapses to a trickle and the device now "exceeds" it
    grid = Decimal(12)
    device = Decimal(6)
    for index in range(12):
        minute = 65 + index * 5
        grid += Decimal("0.1")
        device += Decimal("0.5")
        acc.observe("sensor.house_load", at(minute), None)
        acc.observe("sensor.grid_import", at(minute), grid)
        acc.observe("sensor.utility_plug_total", at(minute), device)
        acc.finalize(at(minute + 25))

    # Then - no device is condemned on the strength of a *house* input failure,
    # and its energy is still booked. Blaming the device would name the wrong
    # fault to the user and, worse, quietly move real consumption into Untracked
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["utility_plug"].energy_kwh > banked


def test_a_fresh_accountant_has_finalised_nothing() -> None:
    # Given - a home configured but not yet observed
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )

    # When / Then - nothing has closed, so there is nothing to publish yet
    assert acc.has_finalised() is False


def test_readings_alone_do_not_close_an_interval() -> None:
    # Given - a home metering normally from its first minute
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))

    # When - a tick arrives before the lateness margin has elapsed
    acc.finalize(at(10))

    # Then - still nothing closed. This is the ~20 minutes a first install spends
    # reading zero while the engine is in fact counting correctly, and it is the
    # gap the warming-up signal exists to explain rather than shorten: the margin
    # is what lets a coarse device's delta land before its bucket seals (HEA-48,
    # ADR-0006), so it serves correctness and is not a knob to turn down (HEA-47)
    assert acc.has_finalised() is False
    assert acc.totals().devices["coarse_step_aircon"].actual_cost == Decimal(0)


def test_the_first_closed_interval_ends_the_wait() -> None:
    # Given - the same home, with an interval's worth of readings behind it
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))

    # When - a tick arrives past the margin, closing the interval
    acc.finalize(at(30))

    # Then - the wait is over, and it stays over: the signal tracks whether the
    # engine has ever produced a figure, not whether the last tick happened to
    # close one, so a quiet house does not read as a fresh install
    assert acc.has_finalised() is True
    acc.finalize(at(35))
    assert acc.has_finalised() is True


def _home_with_a_late_reporting_device() -> Accountant:
    """A house importing steadily, and one device whose counter reports late.

    The house meter is fine-grained and the device silent through the bucket it
    actually drew in, which is the coarse-counter shape the retention ring exists
    for (ADR-0006).
    """
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.finalize(at(30))
    return acc


def test_a_late_correction_never_pulls_the_remainder_down() -> None:
    # Given - a finalised bucket whose whole 1 kWh went to Untracked, because the
    # device that actually drew 0.6 of it had not reported yet
    acc = _home_with_a_late_reporting_device()
    before = acc.totals().untracked

    # When - the device reports late, claiming energy Untracked was credited with
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(40))

    # Then - the remainder does not go backwards. Taking the value out where it
    # was discovered would land the correction in whichever hour the counter
    # happened to report, and a cumulative sensor can only be corrected in its
    # current bucket - the same wrong-hour retraction HEA-85 removed from the
    # overdraw charge, arriving by the other path (ADR-0006, HEA-85)
    after = acc.totals().untracked
    assert after.actual_cost >= before.actual_cost
    assert after.energy_kwh >= before.energy_kwh


def test_a_late_correction_reaches_the_device_as_the_remainder_earns_it() -> None:
    # Given - the same late correction, held rather than taken
    acc = _home_with_a_late_reporting_device()
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(40))
    assert acc.totals().devices["coarse_step_aircon"].actual_cost < Decimal("0.18")

    # When - the house goes on consuming, so the remainder accrues afresh and can
    # fund what it owes without any published figure falling
    for minute in range(10, 60, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(1) + Decimal(minute) / 10)
        acc.finalize(at(minute + 25))

    # Then - the device ends up with exactly what the retained bucket priced it at,
    # having climbed to it rather than jumped. A device figure only ever rises
    assert acc.totals().devices["coarse_step_aircon"].actual_cost == Decimal("0.18")
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal("0.6")


def test_no_published_figure_falls_while_a_correction_is_releasing() -> None:
    # Given - the same home, and the correction outstanding
    acc = _home_with_a_late_reporting_device()
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))

    # When - the house consumes on, tick by tick, while the release plays out
    seen = [acc.totals()]
    for minute in range(10, 60, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(1) + Decimal(minute) / 10)
        acc.finalize(at(minute + 25))
        seen.append(acc.totals())

    # Then - at no point does any published total step backwards, and the split
    # reconciles to the whole home at *every* point, not merely once it settles.
    # Releasing only what the remainder has just earned is what buys both: the
    # money moves device-ward without ever exceeding what is there to move
    for earlier, later in pairwise(seen):
        assert later.untracked.actual_cost >= earlier.untracked.actual_cost
        assert later.untracked.energy_kwh >= earlier.untracked.energy_kwh
        assert (
            later.devices["coarse_step_aircon"].actual_cost
            >= earlier.devices["coarse_step_aircon"].actual_cost
        )
    for result in seen:
        assert _total_actual(result) == result.whole_home.actual_cost
        assert (
            result.untracked.energy_kwh
            + result.devices["coarse_step_aircon"].energy_kwh
            == result.whole_home.energy_kwh
        )


def test_a_rebase_does_not_reopen_the_wait() -> None:
    # Given - an established home that has been publishing figures
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_step_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_step_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.coarse_step_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # When - the household rebases its totals to zero (HEA-57)
    acc.reset_totals()

    # Then - the figures are zero but the engine has not forgotten that it works.
    # A reset drops the sensors' baselines too, so were this to reopen the wait,
    # both halves of the warming-up condition would be true at once and a working
    # installation would announce itself as a fresh one
    assert acc.totals().devices["coarse_step_aircon"] == ZERO_TOTALS
    assert acc.has_finalised() is True
