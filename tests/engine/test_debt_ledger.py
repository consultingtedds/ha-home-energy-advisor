"""The carried deficit, in isolation from the accounting it corrects.

When tracked devices report drawing more than the house meters recorded, the
excess is energy the meters have not reported *yet*. Its energy is published so
the period reconciles; its money is not, because the import rate is only a guess
about where unmetered energy came from and the next few buckets usually overturn
it (ADR-0014, ADR-0015, HEA-85).

So the charge waits here and falls due once, when a later bucket's surplus repays
the debt at the price that interval really was — or at the import rate if nothing
ever repays it, because then nothing better was learned. A settlement carries the
two figures separately: what the energy cost, and what buying it off the meter
would have cost, so Cost Savings moves by exactly their difference.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.debt_ledger import (
    DebtLedger,
    Settlement,
)

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
TARIFF = Decimal("0.30")
EXPIRY = timedelta(hours=2)

AIRCON = "coarse_step_aircon"
PUMP = "cloud_polled_pump"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_ledger() -> DebtLedger:
    return DebtLedger(expiry=EXPIRY)


def saving(settlement: Settlement, device: str) -> Decimal:
    """What the household saved on this device's share — naive less actual."""
    return settlement.naive.get(device, Decimal(0)) - settlement.actual.get(
        device, Decimal(0)
    )


def test_a_debt_is_repaid_by_a_later_surplus() -> None:
    # Given — 0.3 kWh drawn that the meters had not yet reported, recorded at the
    # rate the grid would have sold it at but not charged to anyone
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When — a later interval meters 0.5 kWh the devices did not claim, priced at
    # the same rate the debt was recorded at
    settlement = ledger.repay(Decimal("0.5"), TARIFF)

    # Then — the whole debt clears and the charge falls due at exactly what it was
    # recorded at, so the household saved nothing on it
    assert settlement.kwh == Decimal("0.3")
    assert settlement.actual[AIRCON] == Decimal("0.09")
    assert saving(settlement, AIRCON) == Decimal(0)
    assert ledger.outstanding_kwh() == Decimal(0)


def test_a_surplus_smaller_than_the_debt_repays_what_it_can() -> None:
    # Given / When
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})
    settlement = ledger.repay(Decimal("0.1"), TARIFF)

    # Then — the rest stays owed rather than being written off early
    assert settlement.kwh == Decimal("0.1")
    assert ledger.outstanding_kwh() == Decimal("0.2")


def test_the_charge_falls_due_at_what_the_energy_really_cost() -> None:
    # Given — a debt recorded at the import rate on the assumption the energy came
    # off the grid
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When — the interval that repays it was served at a blended 0.12/kWh, because
    # generation covered most of it
    settlement = ledger.repay(Decimal("0.5"), Decimal("0.12"))

    # Then — the 0.3 kWh is charged the 0.036 it really cost, never the 0.09.
    # Publishing 0.09 first and handing 0.054 back is what made an hour read as
    # costing less than nothing.
    assert settlement.actual[AIRCON] == Decimal("0.036")
    assert settlement.naive[AIRCON] == Decimal("0.09")
    assert saving(settlement, AIRCON) == Decimal("0.054")


def test_a_dearer_repaying_interval_charges_the_device_more() -> None:
    # Given — the battery discharging energy stored when import was expensive can
    # price an interval above the import rate the debt was recorded at (HEA-39)
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When
    settlement = ledger.repay(Decimal("0.5"), Decimal("0.40"))

    # Then — the charge is the 0.12 it really cost, and the saving is negative:
    # a real loss, shown rather than floored at zero
    assert settlement.actual[AIRCON] == Decimal("0.12")
    assert saving(settlement, AIRCON) == Decimal("-0.03")


def test_a_charge_is_split_across_the_devices_that_overdrew() -> None:
    # Given — two devices overshot the same interval, three quarters of the draw
    # to one of them
    ledger = a_ledger()
    ledger.owe(
        at(0),
        Decimal("0.4"),
        Decimal("0.12"),
        {AIRCON: Decimal("0.6"), PUMP: Decimal("0.2")},
    )

    # When — the repaying interval was free, so the energy turns out to have cost
    # nothing at all
    settlement = ledger.repay(Decimal("0.4"), Decimal(0))

    # Then — nothing to pay, and the whole counterfactual becomes saving, split in
    # proportion to what each drew. The sun belongs to whoever used it.
    assert settlement.actual == {AIRCON: Decimal(0), PUMP: Decimal(0)}
    assert saving(settlement, AIRCON) == Decimal("0.09")
    assert saving(settlement, PUMP) == Decimal("0.03")


def test_the_oldest_debt_is_repaid_first() -> None:
    # Given — two debts, the older one from a different device
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.2"), Decimal("0.06"), {AIRCON: Decimal("0.2")})
    ledger.owe(at(30), Decimal("0.2"), Decimal("0.06"), {PUMP: Decimal("0.2")})

    # When — only enough surplus to clear one
    settlement = ledger.repay(Decimal("0.2"), Decimal(0))

    # Then — the oldest, so a debt cannot be starved into expiring while newer
    # ones are settled around it
    assert settlement.naive == {AIRCON: Decimal("0.06")}
    assert ledger.outstanding_kwh() == Decimal("0.2")


def test_a_debt_older_than_the_expiry_is_charged_at_import() -> None:
    # Given — a debt the house never repays, which is a source claiming more than
    # the house ever consumed rather than a counter reporting late
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When — the expiry passes
    settlement = ledger.expire(at(0) + EXPIRY)

    # Then — the *energy* is written off, because the meters never accounted for
    # it and it can no longer be reconciled. The money still falls due: nothing
    # better than the import rate was ever learned, so that is what it costs, and
    # the counterfactual matches it, leaving no saving.
    assert settlement.kwh == Decimal("0.3")
    assert settlement.actual[AIRCON] == Decimal("0.09")
    assert saving(settlement, AIRCON) == Decimal(0)
    assert ledger.outstanding_kwh() == Decimal(0)
    assert ledger.forgiven_kwh() == Decimal("0.3")


def test_a_debt_within_the_expiry_is_kept() -> None:
    # Given / When — one minute short of the window
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})
    settlement = ledger.expire(at(0) + EXPIRY - timedelta(minutes=1))

    # Then — still waiting, so nothing is published for it yet
    assert settlement.kwh == Decimal(0)
    assert settlement.actual == {}
    assert ledger.outstanding_kwh() == Decimal("0.3")


def test_an_expired_debt_is_not_charged_twice() -> None:
    # Given — a debt already charged at import because nothing ever repaid it
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})
    ledger.expire(at(0) + EXPIRY)

    # When — a surplus arrives afterwards
    settlement = ledger.repay(Decimal("0.5"), Decimal(0))

    # Then — nothing left to settle. Re-pricing it now would credit the device for
    # energy the house was never metered as consuming.
    assert settlement.kwh == Decimal(0)
    assert settlement.actual == {}
    assert settlement.naive == {}


def test_nothing_owed_means_nothing_withheld() -> None:
    # Given / When — the ordinary case, where the devices did not overshoot
    settlement = a_ledger().repay(Decimal("0.5"), TARIFF)

    # Then — the remainder keeps its whole surplus
    assert settlement.kwh == Decimal(0)
    assert settlement.actual == {}
