from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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


# Every figure a device carries, at zero — what a fresh or freshly-rebased
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


def test_overdrawn_buckets_are_counted_for_the_remainder_repair() -> None:
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
    # persistent-negative-remainder Repair once enough of them accumulate
    assert acc.overdrawn_buckets_in_window() == 3


def test_intermittent_overdraw_stays_visible_across_healthy_buckets() -> None:
    # Given — a device that over-draws every other bucket, which is what a coarse
    # counter reporting in lumps actually looks like
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_energy"},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_energy", at(0), Decimal(0))

    # When — over-drawn and healthy buckets alternate
    readings = ((5, "0.1", "0.5"), (10, "1.1", "0.6"), (15, "1.2", "1.1"))
    for minute, grid, device in readings:
        acc.observe("sensor.grid_import", at(minute), Decimal(grid))
        acc.observe("sensor.coarse_energy", at(minute), Decimal(device))
    acc.finalize(at(60))

    # Then — both over-drawn buckets are still counted. Counting only *consecutive*
    # runs meant an intermittent lump reset the tally every time, so the Repair
    # stayed silent for weeks while the mismatch was continuous (HEA-74)
    assert acc.overdrawn_buckets_in_window() == 2


def test_overdraw_ages_out_of_the_window_once_the_house_recovers() -> None:
    # Given — a single over-drawn bucket followed by a full window of healthy ones
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.coarse_energy"},
        windows=AccountingWindows(max_quiet_span=timedelta(0)),
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.coarse_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("0.1"))
    acc.observe("sensor.coarse_energy", at(5), Decimal("0.5"))

    # When — twelve clean buckets follow, the house importing well above the draw
    grid = Decimal("0.1")
    device = Decimal("0.5")
    for minute in range(10, 70, 5):
        grid += Decimal("2.0")
        device += Decimal("0.1")
        acc.observe("sensor.grid_import", at(minute), grid)
        acc.observe("sensor.coarse_energy", at(minute), device)
    acc.finalize(at(120))

    # Then — the window has moved past it; a transient mismatch does not keep a
    # Repair standing once the evidence for it has aged out
    assert acc.overdrawn_buckets_in_window() == 0


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
            SourceRole.GENERATION: "sensor.solar",
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


def test_an_overdrawing_late_device_pays_import_for_what_untracked_cannot_fund() -> (
    None
):
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

    # Then — B keeps all its real energy. It takes the €0.03 of headroom Untracked
    # held at the bucket's blended rate, and buys the remaining 0.3 kWh at the
    # import rate: leaving that excess free, as the shipped engine did, is what
    # let a device's published cost fall far below the tariff. A is untouched.
    result = acc.totals()
    b = result.devices["device_b"]
    assert result.devices["device_a"] == before_a
    assert b.energy_kwh == Decimal("0.4")
    assert b.actual_cost == Decimal("0.12")
    assert result.untracked.actual_cost == Decimal(0)
    assert result.untracked.energy_kwh == Decimal(0)
    assert result.whole_home.actual_cost == Decimal("0.39")
    assert _total_actual(result) == Decimal("0.39")


def test_a_late_correction_buys_its_excess_at_import_not_at_a_free_blend() -> None:
    # Given — a finalised bucket served half by grid and half by generation, so its
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

    # When — the coarse counter reports 1 kWh late into that same bucket, with no
    # Untracked headroom left to fund it
    acc.observe("sensor.cloud_polled_energy", at(5), Decimal("1.0"))
    acc.finalize(at(40))

    # Then — the late kWh costs the full import rate, not the €0.15 blended rate
    # the bucket happened to settle at: generation that was already consumed
    # cannot supply it a second time
    pump = acc.totals().devices["cloud_polled_pump"]
    assert pump.energy_kwh == Decimal("1.0")
    assert pump.actual_cost == PEAK


def test_a_delta_older_than_the_retention_ring_is_dropped_and_logged() -> None:
    # Given — a short 30-minute retention ring, and a house that runs long enough
    # for bucket at(0) to be evicted from the ring
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
        windows=AccountingWindows(retention=timedelta(minutes=30)),
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
    assert result.devices["coarse_step_aircon"] == ZERO_TOTALS
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


def test_finalising_prunes_superseded_prices_but_keeps_costs_correct() -> None:
    # Given — the import price changes once, an hour into a steady run; left
    # unpruned the price list would grow without bound and be rescanned from index
    # zero on every finalised bucket (HEA-53)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), Decimal("0.10"))
    acc.record_price(at(60), Decimal("0.30"))
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — two hours of readings (house 1 kWh/interval, device 0.5) are finalised
    # well past the second price change
    for minute in range(5, 125, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
        acc.observe("sensor.guest_energy", at(minute), Decimal(minute) / 10)
    acc.finalize(at(150))

    # Then — the superseded first price is pruned (only the price active at the
    # watermark and any later survive), yet the accounting still reflects both
    # tariffs: 12 intervals of 0.5 kWh at 0.10 then 12 more at 0.30
    assert len(acc._prices) == 1  # noqa: SLF001
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("12.0")
    assert guest.actual_cost == Decimal("2.4")


def test_flush_finalises_in_flight_buckets_so_they_can_be_banked() -> None:
    # Given — an interval's readings are in but not yet past the lateness margin,
    # so nothing has been finalised (a reload here would drop them)
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(11))  # < margin: still nothing allocated
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal(0)

    # When — the accountant is flushed, as the coordinator does on unload
    acc.flush(at(11))

    # Then — the in-flight interval is sealed and banked, so the sensors' restore
    # baseline captures it instead of losing ~20 min of accounting (HEA-53)
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal("0.18")


def test_a_bucket_finalised_before_any_price_is_logged_as_zero_priced() -> None:
    # Given — grid import and a device, but no price has ever been recorded
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — an interval is finalised while the price list is still empty
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))

    # Then — energy is still tracked and costed at zero (unchanged), but the era is
    # now explainable: a ZERO_PRICED decision is logged on the import source so the
    # diagnostics download accounts for the zero-cost early bucket (HEA-53)
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.6")
    assert guest.actual_cost == Decimal(0)
    decisions = acc.source_diagnostics()["sensor.grid_import"].recent_decisions
    assert [d.reason for d in decisions].count(DecisionReason.ZERO_PRICED) == 1


def test_zero_priced_is_logged_once_then_never_after_a_price_arrives() -> None:
    # Given — a home that finalises several buckets before its first price
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    for minute in range(5, 30, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
    acc.finalize(at(40))  # several zero-priced buckets in one go

    # When — a price finally arrives and the run continues
    acc.record_price(at(40), PEAK)
    for minute in range(30, 60, 5):
        acc.observe("sensor.grid_import", at(minute), Decimal(minute) / 5)
    acc.finalize(at(90))

    # Then — the cold-start era is marked exactly once, not once per bucket, and not
    # again once pricing is known
    decisions = acc.source_diagnostics()["sensor.grid_import"].recent_decisions
    assert [d.reason for d in decisions].count(DecisionReason.ZERO_PRICED) == 1


def test_reset_totals_rebases_every_running_total_to_zero() -> None:
    # Given — a home that has accumulated real cost across a finalised interval
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))
    assert acc.totals().whole_home.energy_kwh == Decimal("1.0")

    # When — the totals are rebased
    acc.reset_totals()

    # Then — every published figure starts from zero: the tracked device, the
    # derived Untracked remainder, and the whole-home aggregate alike
    result = acc.totals()
    assert result.devices["coarse_step_aircon"] == ZERO_TOTALS
    assert result.untracked == ZERO_TOTALS
    assert result.whole_home == ZERO_TOTALS


def test_reset_totals_keeps_meter_tracking_so_the_next_delta_is_not_a_phantom() -> None:
    # Given — a home whose meters have been read up to 1.0 kWh, then rebased
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))
    acc.finalize(at(30))
    acc.reset_totals()

    # When — the counters climb again after the rebase
    acc.observe("sensor.grid_import", at(35), Decimal("2.0"))
    acc.observe("sensor.guest_energy", at(35), Decimal("1.0"))
    acc.finalize(at(70))

    # Then — only the energy that arrived after the rebase is counted. The reset
    # keeps each meter's last reading, so a climbing counter is read neither as a
    # fresh start (dropping the delta) nor as a climb from zero (re-counting the
    # pre-reset kWh)
    result = acc.totals()
    assert result.whole_home.energy_kwh == Decimal("1.0")
    assert result.devices["coarse_step_aircon"].energy_kwh == Decimal("0.4")


def test_reset_totals_discards_pre_reset_energy_still_in_flight() -> None:
    # Given — a home whose most recent interval has been observed but not yet
    # finalised, so its energy is still held in the in-flight buckets
    acc = Accountant(
        house_sources={SourceRole.GRID_IMPORT: "sensor.grid_import"},
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("1.0"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.6"))

    # When — the totals are rebased and accounting runs on past the lateness margin
    acc.reset_totals()
    acc.finalize(at(40))

    # Then — the pre-reset energy is gone rather than banked into the new era: a
    # rebase is a hard boundary, so nothing earned before it lands after it
    result = acc.totals()
    assert result.whole_home.energy_kwh == Decimal(0)
    assert result.devices["coarse_step_aircon"].energy_kwh == Decimal(0)


def test_reset_totals_keeps_the_battery_stored_cost_ledger() -> None:
    # Given — a home that charged its battery from the grid at €0.10, and rebased
    # its totals before discharging
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.BATTERY_CHARGE: "sensor.battery_charge",
            SourceRole.BATTERY_DISCHARGE: "sensor.battery_discharge",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
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
        "sensor.guest_energy",
    ):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(5), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(5), Decimal(0))
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.guest_energy", at(5), Decimal(0))
    acc.finalize(at(40))
    acc.reset_totals()

    # When — the stored energy is discharged to serve the device at peak price.
    # The meters re-report unchanged at at(40) first, as a polled source does, so
    # the discharge delta falls wholly inside the peak-priced bucket
    acc.record_price(at(40), PEAK)
    acc.observe("sensor.grid_import", at(40), Decimal("2.0"))
    acc.observe("sensor.battery_charge", at(40), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(40), Decimal(0))
    acc.observe("sensor.house_load", at(40), Decimal(0))
    acc.observe("sensor.guest_energy", at(40), Decimal(0))
    acc.observe("sensor.grid_import", at(45), Decimal("2.0"))
    acc.observe("sensor.battery_discharge", at(45), Decimal("2.0"))
    acc.observe("sensor.house_load", at(45), Decimal("2.0"))
    acc.observe("sensor.guest_energy", at(45), Decimal("2.0"))
    acc.finalize(at(80))

    # Then — the discharge is still priced at the €0.10 the battery stored, not
    # given away free: a rebase clears accumulated totals, never the physical state
    # of the battery's stored-cost ledger
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("2.0")
    assert guest.actual_cost == Decimal("0.20")
    assert guest.naive_cost == Decimal("0.60")


def _solar_home() -> Accountant:
    """A home with grid, solar and export meters — the full-balance decomposition."""
    return Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.GENERATION: "sensor.solar",
            SourceRole.GRID_EXPORT: "sensor.grid_export",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )


def _seed_solar_home(acc: Accountant) -> None:
    acc.record_price(at(0), PEAK)
    for entity in ("sensor.grid_import", "sensor.solar", "sensor.grid_export"):
        acc.observe(entity, at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))


def _by_source_sum(totals: DeviceTotals) -> Decimal:
    return (
        totals.energy_from_grid
        + totals.energy_from_generation
        + totals.energy_from_battery
    )


def test_running_totals_carry_each_devices_energy_by_source() -> None:
    # Given — a solar home where 0.4 kWh was imported and 0.3 kWh of generation was
    # self-consumed (0.5 generated, 0.2 exported), so the house was served 0.7 kWh
    acc = _solar_home()
    _seed_solar_home(acc)

    # When — the device draws 0.5 kWh of that interval and it is finalised
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.5"))
    acc.finalize(at(30))

    # Then — the device's energy is split in the mix that served the bucket, so a
    # self-sufficiency share can be read straight off the totals (HEA-51)
    guest = acc.totals().devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.5")
    assert guest.energy_from_grid == Decimal("0.2857142857142857142857142857")
    assert guest.energy_from_generation == Decimal("0.2142857142857142857142857143")
    assert guest.energy_from_battery == Decimal(0)
    assert _by_source_sum(guest) == guest.energy_kwh


def test_untracked_by_source_derives_so_the_split_reconciles() -> None:
    # Given — the same solar interval, part of it drawn by the tracked device
    acc = _solar_home()
    _seed_solar_home(acc)
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.5"))

    # When — the interval is finalised
    acc.finalize(at(30))

    # Then — device plus Untracked equal the whole home for every source, just as
    # they do for energy and cost: Untracked is derived, never accumulated
    result = acc.totals()
    guest = result.devices["coarse_step_aircon"]
    assert guest.energy_from_grid + result.untracked.energy_from_grid == (
        result.whole_home.energy_from_grid
    )
    assert guest.energy_from_generation + result.untracked.energy_from_generation == (
        result.whole_home.energy_from_generation
    )
    # And the home's own split still sums to its energy, and to what was served
    assert _by_source_sum(result.whole_home) == result.whole_home.energy_kwh
    assert result.whole_home.energy_from_grid == Decimal("0.4")
    assert result.whole_home.energy_from_generation == Decimal("0.3")


def test_a_late_correction_carries_the_retained_buckets_source_mix() -> None:
    # Given — a solar bucket finalised while the coarse device stayed silent, its
    # context still held in the retention ring (ADR-0006)
    acc = _solar_home()
    _seed_solar_home(acc)
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.finalize(at(30))  # bucket at(0) finalised; watermark = at(0)

    # When — the device reports late into that finalised, still-retained bucket
    acc.observe("sensor.guest_energy", at(5), Decimal("0.5"))
    acc.finalize(at(40))

    # Then — the reclaimed energy is attributed in that bucket's own source mix,
    # not the current one, and still sums to the device's energy
    result = acc.totals()
    guest = result.devices["coarse_step_aircon"]
    assert guest.energy_kwh == Decimal("0.5")
    assert guest.energy_from_grid == Decimal("0.2857142857142857142857142857")
    assert guest.energy_from_generation == Decimal("0.2142857142857142857142857143")
    assert _by_source_sum(guest) == guest.energy_kwh
    # And Untracked gives back exactly what the device gained, per source
    assert result.untracked.energy_from_grid == Decimal("0.4") - (
        guest.energy_from_grid
    )


def test_reset_totals_rebases_the_by_source_totals_too() -> None:
    # Given — a solar home with accumulated by-source energy
    acc = _solar_home()
    _seed_solar_home(acc)
    acc.observe("sensor.grid_import", at(5), Decimal("0.4"))
    acc.observe("sensor.solar", at(5), Decimal("0.5"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.2"))
    acc.observe("sensor.guest_energy", at(5), Decimal("0.5"))
    acc.finalize(at(30))
    assert _by_source_sum(acc.totals().devices["coarse_step_aircon"]) > 0

    # When — the household's totals are rebased (HEA-57)
    acc.reset_totals()

    # Then — the by-source figures start from zero alongside every other total;
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
    """A home with a house-consumption meter — the residual decomposition."""
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
    # Given — a home using 0.15 kWh per 5-minute bucket, and a device whose
    # counter claims 1.5 kWh in each of them. That is the utility plug's real failure
    # mode: a source that lies is indistinguishable from a huge load, except that
    # no single device can use more than the house (HEA-60)
    acc = _metered_home()

    # When — a full hour of that runs through the ledger
    _run_buckets(acc, buckets=14, house_step="0.15", device_step="1.5")

    # Then — the device is judged implausible and its energy stops being booked,
    # so the lie stops corrupting the ledger
    assert "utility_plug" in acc.implausible_devices()
    pump = acc.totals().devices["utility_plug"]
    assert pump.energy_kwh < Decimal(14) * Decimal("1.5")

    # And — the rejection is explained rather than silent, on the source's own log
    decisions = acc.source_diagnostics()["sensor.utility_plug_total"].recent_decisions
    assert any(d.reason is DecisionReason.IMPLAUSIBLE for d in decisions)


def test_a_coarse_device_overdrawing_one_bucket_is_still_booked() -> None:
    # Given — the founding case the guard must not break: a a cycle-resetting counter aircon reporting
    # a 0.25 kWh step that lands in a single bucket the house only consumed 0.15 in.
    # Over one bucket it "exceeds the house"; over the hour it plainly does not
    acc = Accountant(
        house_sources={
            SourceRole.GRID_IMPORT: "sensor.grid_import",
            SourceRole.HOUSE_CONSUMPTION: "sensor.house_load",
        },
        device_energy_entities={"coarse_step_aircon": "sensor.guest_energy"},
    )
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.house_load", at(0), Decimal(0))
    acc.observe("sensor.guest_energy", at(0), Decimal(0))

    # When — the house ticks along and the aircon steps once, coarsely
    house = Decimal(0)
    for index in range(14):
        minute = 5 + index * 5
        house += Decimal("0.15")
        acc.observe("sensor.grid_import", at(minute), house)
        acc.observe("sensor.house_load", at(minute), house)
        if index == 3:
            acc.observe("sensor.guest_energy", at(minute), Decimal("0.25"))
        acc.finalize(at(minute + 25))

    # Then — nothing is flagged and the step is booked in full. Judging a single
    # bucket would have rejected it; the window is what tells timing from lying
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["coarse_step_aircon"].energy_kwh == Decimal("0.25")


def test_the_guard_stays_quiet_when_the_house_reports_nothing() -> None:
    # Given — a household whose house-level meter is dead flat while a device draws
    # normally. Every device then "exceeds" a house total of zero
    acc = _metered_home()
    acc.record_price(at(0), PEAK)
    acc.observe("sensor.grid_import", at(0), Decimal(0))
    acc.observe("sensor.house_load", at(0), Decimal(0))
    acc.observe("sensor.utility_plug_total", at(0), Decimal(0))

    # When — a full window passes with house consumption never moving
    device = Decimal(0)
    for index in range(14):
        minute = 5 + index * 5
        device += Decimal("0.05")
        acc.observe("sensor.utility_plug_total", at(minute), device)
        acc.finalize(at(minute + 25))

    # Then — no device is condemned on the strength of a missing input. A silent
    # house meter is its own fault, surfaced elsewhere; it is not evidence that a
    # device is lying
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["utility_plug"].energy_kwh > 0


def test_a_flagged_device_recovers_once_its_source_reads_sanely_again() -> None:
    # Given — a device already judged implausible after an hour of lying
    acc = _metered_home()
    _run_buckets(acc, buckets=14, house_step="0.15", device_step="1.5")
    assert "utility_plug" in acc.implausible_devices()
    banked = acc.totals().devices["utility_plug"].energy_kwh

    # When — the source is repointed and starts reporting honestly, for long
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

    # Then — the guard lets go and accounting resumes. A device is never condemned
    # permanently on past behaviour
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["utility_plug"].energy_kwh > banked


def test_implausible_energy_is_refused_on_the_late_correction_path_too() -> None:
    # Given — a device already judged implausible. This is the path that matters
    # most for the real failure: the utility plug was cloud-polled every ~30 minutes,
    # so most of each delta landed past the finalisation watermark and reached the
    # retained ring, never the in-flight buckets (ADR-0006)
    acc = _metered_home()
    _run_buckets(acc, buckets=14, house_step="0.15", device_step="1.5")
    assert "utility_plug" in acc.implausible_devices()
    banked = acc.totals().devices["utility_plug"].energy_kwh
    untracked = acc.totals().untracked.energy_kwh

    # When — another inflated reading arrives spanning a bucket already finalised
    acc.observe("sensor.utility_plug_total", at(75), Decimal(14) * Decimal("1.5") + 8)
    acc.finalize(at(100))

    # Then — the correction is refused, so no value is moved out of the Untracked
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
    # Given — a fully metered home
    acc = _fully_metered_home()
    _baseline(acc)

    # When — over one bucket the house meter is unavailable, while generation,
    # export and import all report normally
    acc.observe("sensor.house_load", at(5), None)
    acc.observe("sensor.grid_import", at(5), Decimal("0.2"))
    acc.observe("sensor.generation", at(5), Decimal("1.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.3"))
    acc.finalize(at(30))

    # Then — consumption is grid + (generation less export) = 0.2 + 0.7. Reading the
    # dead meter as a zero would have collapsed it to 0.2, silently losing the
    # whole generation component (HEA-67)
    assert acc.totals().untracked.energy_kwh == Decimal("0.9")


def test_a_house_meter_that_does_not_move_keeps_the_residual_model() -> None:
    # Given — the same fully metered home
    acc = _fully_metered_home()
    _baseline(acc)

    # When — the house meter reports but is unchanged, which is what a quiet house
    # on a coarse counter looks like, while generation and export both move
    acc.observe("sensor.house_load", at(5), Decimal(0))
    acc.observe("sensor.grid_import", at(5), Decimal(0))
    acc.observe("sensor.generation", at(5), Decimal("1.0"))
    acc.observe("sensor.grid_export", at(5), Decimal("0.3"))
    acc.finalize(at(30))

    # Then — the house consumed nothing and the residual model says so. This is
    # the case that makes "no reading in the bucket" the wrong signal to fall back
    # on: full-balance would book 0.7 kWh of generation that in fact went to
    # export, every quiet bucket, on a perfectly healthy meter
    assert acc.totals().untracked.energy_kwh == Decimal(0)


def test_the_plausibility_guard_is_suspended_while_a_house_source_is_down() -> None:
    # Given — a device drawing honestly, with a full window of evidence behind it
    acc = _metered_home()
    _run_buckets(acc, buckets=12, house_step="1.0", device_step="0.5")
    assert acc.implausible_devices() == frozenset()
    banked = acc.totals().devices["utility_plug"].energy_kwh

    # When — the house meter fails while the grid meter keeps reporting, so the
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

    # Then — no device is condemned on the strength of a *house* input failure,
    # and its energy is still booked. Blaming the device would name the wrong
    # fault to the user and, worse, quietly move real consumption into Untracked
    assert acc.implausible_devices() == frozenset()
    assert acc.totals().devices["utility_plug"].energy_kwh > banked
