"""Golden-master regression guard: the delta/pricing path against real capture.

Runs the real ``CumulativeEnergySource`` over raw recorder history captured from
the reference instance (July 2026 exploration; provenance in the fixtures
README) and reproduces the hand-verified published figures.

Scope is deliberately narrow — this guards delta extraction (resets, unavailable
spans, mid-sequence gaps) and price lookup against messy real data, the paths
where real behaviour has surprised us before. It does **not** validate the cost
allocation model: that invariant is proven synthetically in ``test_allocation``
and against the live instance in dogfooding (HEA-28). Naive cost here replicates
the exploration's device-level method (each delta priced at the rate active when
it landed); the product prices per 5-minute bucket.

The whole module skips when the fixture directory is absent, so the public CI
stays green while the full suite runs locally — the capture is gitignored
because it carries household occupancy patterns.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_energy_advisor.engine.energy_source import (
    CumulativeEnergySource,
    EnergyDelta,
    Reading,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "exploration_2026_07"
MADRID = ZoneInfo("Europe/Madrid")
_UNAVAILABLE = {"unavailable", "unknown"}
_GUEST = "sensor.guest_bedroom_aircon_energy_usage_cycle"
_LIVING_ROOM = "sensor.living_room_aircon_energy_usage_cycle"

pytestmark = pytest.mark.skipif(
    not FIXTURES.exists(),
    reason="golden-master fixtures absent (local-only capture; see HEA-19)",
)


def _states(filename: str, entity_id: str) -> list[dict[str, str]]:
    payload = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    for entity in payload["data"]["entities"]:
        if entity["entity_id"] == entity_id:
            states: list[dict[str, str]] = entity["states"]
            return states
    pytest.fail(f"entity {entity_id} not found in {filename}")


def _reading(state: dict[str, str]) -> Reading:
    raw = state["state"]
    value = None if raw in _UNAVAILABLE else Decimal(raw)
    return Reading(at=datetime.fromisoformat(state["last_changed"]), value=value)


def _deltas(filename: str, entity_id: str) -> list[EnergyDelta]:
    source = CumulativeEnergySource()
    return [
        delta
        for state in _states(filename, entity_id)
        if (delta := source.observe(_reading(state))) is not None
    ]


def _price_points() -> list[tuple[datetime, Decimal]]:
    states = _states("price_import_raw.json", "sensor.electricity_price_import")
    points = [
        (datetime.fromisoformat(s["last_changed"]), Decimal(s["state"]))
        for s in states
        if s["state"] not in _UNAVAILABLE
    ]
    points.sort(key=lambda point: point[0])
    return points


def _price_at(points: list[tuple[datetime, Decimal]], when: datetime) -> Decimal:
    price = points[0][1]
    for moment, value in points:
        if moment > when:
            break
        price = value
    return price


def _within(delta: EnergyDelta, day: int) -> bool:
    start = datetime(2026, 7, day, tzinfo=MADRID)
    end = datetime(2026, 7, day + 1, tzinfo=MADRID)
    return start <= delta.end < end


def test_guest_bedroom_energy_reproduces_the_published_complete_days() -> None:
    # Given — the guest bedroom's raw counter run through the real delta pipeline
    deltas = _deltas("aircon_raw_batch1.json", _GUEST)

    # When — energy is summed over each fully captured day (Jul 11 is excluded:
    # the published table snapshotted it mid-day, the fixture has the whole day)
    daily = {
        day: sum((d.kwh for d in deltas if _within(d, day)), start=Decimal(0))
        for day in (8, 9, 10)
    }

    # Then — it matches the hand-verified figures exactly, through real resets and
    # scores of unavailable flaps
    assert daily == {8: Decimal("3.25"), 9: Decimal("3.25"), 10: Decimal("2.75")}


def test_guest_bedroom_naive_cost_reproduces_the_published_complete_days() -> None:
    # Given — the same deltas and the exact TOU price step function
    deltas = _deltas("aircon_raw_batch1.json", _GUEST)
    points = _price_points()

    # When — each delta is priced at the rate active when it landed and summed to
    # cents per complete day
    daily = {
        day: sum(
            (d.kwh * _price_at(points, d.end) for d in deltas if _within(d, day)),
            start=Decimal(0),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for day in (8, 9, 10)
    }

    # Then — it reproduces the published euro figures
    assert daily == {8: Decimal("0.58"), 9: Decimal("0.52"), 10: Decimal("0.41")}


def test_living_room_attributes_the_full_delta_across_an_unavailable_gap() -> None:
    # Given — the living room counter reads 1.0, drops to unavailable for ~2 hours,
    # then recovers at 2.5 (the documented Jul 9 real-data edge)
    deltas = _deltas("aircon_raw_batch2.json", _LIVING_ROOM)

    # When — the delta that recovers the gap is located
    recovery = datetime.fromisoformat("2026-07-09T16:51:01.375342+02:00")
    spanning = next(d for d in deltas if d.end == recovery)

    # Then — the full 1.5 kWh is attributed, spanning from the last good reading to
    # recovery, neither lost nor lumped at the recovery instant
    assert spanning.kwh == Decimal("1.5")
    assert spanning.start == datetime.fromisoformat("2026-07-09T14:47:06.817417+02:00")
