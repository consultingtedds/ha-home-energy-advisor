"""The carried deficit, in isolation from the accounting it corrects.

When tracked devices report drawing more than the house meters recorded, the
excess is energy the meters have not reported *yet* — so it is charged at the
import rate and remembered as a debt (ADR-0014, ADR-0015). A later bucket where
the meter runs ahead of the devices repays it.

Repayment is where the money moves. The debt was charged at the import rate on
the assumption the energy came off the grid; if the interval that repays it was
served partly by generation, the devices that overdrew are refunded the
difference. A debt nobody repays expires, because a source claiming more than
the house ever consumes is a fault to surface, not a deficit to absorb.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.home_energy_advisor.engine.debt_ledger import DebtLedger

BASE = datetime(2026, 7, 8, 22, 0, tzinfo=UTC)
TARIFF = Decimal("0.30")
EXPIRY = timedelta(hours=2)

AIRCON = "coarse_step_aircon"
PUMP = "cloud_polled_pump"


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def a_ledger() -> DebtLedger:
    return DebtLedger(expiry=EXPIRY)


def test_a_debt_is_repaid_by_a_later_surplus() -> None:
    # Given — 0.3 kWh drawn that the meters had not yet reported, charged at
    # the rate the grid would have sold it at
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When — a later interval meters 0.5 kWh the devices did not claim, priced
    # at the same rate the debt was charged at
    repayment = ledger.repay(Decimal("0.5"), TARIFF)

    # Then — the whole debt clears, and nothing is refunded because the energy
    # cost exactly what it was charged
    assert repayment.kwh == Decimal("0.3")
    assert repayment.refunds.get(AIRCON, Decimal(0)) == Decimal(0)
    assert ledger.outstanding_kwh() == Decimal(0)


def test_a_surplus_smaller_than_the_debt_repays_what_it_can() -> None:
    # Given / When
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})
    repayment = ledger.repay(Decimal("0.1"), TARIFF)

    # Then — the rest stays owed rather than being written off early
    assert repayment.kwh == Decimal("0.1")
    assert ledger.outstanding_kwh() == Decimal("0.2")


def test_the_device_is_refunded_when_the_repaying_energy_was_cheaper() -> None:
    # Given — a debt charged at the import rate on the assumption the energy came
    # off the grid
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When — the interval that repays it was served at a blended 0.12/kWh,
    # because generation covered most of it
    repayment = ledger.repay(Decimal("0.5"), Decimal("0.12"))

    # Then — the 0.3 kWh really cost 0.036, not the 0.09 charged, so 0.054 goes
    # back to the device that drew it rather than to the remainder
    assert repayment.refunds[AIRCON] == Decimal("0.054")


def test_a_dearer_repaying_interval_charges_the_device_more() -> None:
    # Given — the battery discharging energy stored when import was expensive can
    # price an interval above the import rate the debt was charged at (HEA-39)
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When
    repayment = ledger.repay(Decimal("0.5"), Decimal("0.40"))

    # Then — the refund is negative: the device underpaid and now settles up
    assert repayment.refunds[AIRCON] == Decimal("-0.03")


def test_a_refund_is_split_across_the_devices_that_overdrew() -> None:
    # Given — two devices overshot the same interval, three quarters of the draw
    # to one of them
    ledger = a_ledger()
    ledger.owe(
        at(0),
        Decimal("0.4"),
        Decimal("0.12"),
        {AIRCON: Decimal("0.6"), PUMP: Decimal("0.2")},
    )

    # When — the repaying interval was free, so the whole charge comes back
    repayment = ledger.repay(Decimal("0.4"), Decimal(0))

    # Then — in proportion to what each drew, summing to what was charged
    assert repayment.refunds[AIRCON] == Decimal("0.09")
    assert repayment.refunds[PUMP] == Decimal("0.03")


def test_the_oldest_debt_is_repaid_first() -> None:
    # Given — two debts, the older one from a different device
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.2"), Decimal("0.06"), {AIRCON: Decimal("0.2")})
    ledger.owe(at(30), Decimal("0.2"), Decimal("0.06"), {PUMP: Decimal("0.2")})

    # When — only enough surplus to clear one
    repayment = ledger.repay(Decimal("0.2"), Decimal(0))

    # Then — the oldest, so a debt cannot be starved into expiring while newer
    # ones are settled around it
    assert repayment.refunds == {AIRCON: Decimal("0.06")}
    assert ledger.outstanding_kwh() == Decimal("0.2")


def test_a_debt_older_than_the_expiry_is_forgiven() -> None:
    # Given — a debt the house never repays, which is a source claiming more than
    # the house ever consumed rather than a counter reporting late
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})

    # When — the expiry passes
    forgiven = ledger.expire(at(0) + EXPIRY)

    # Then — it stops suppressing every later remainder, and is counted so the
    # household can be told their meters disagree (HEA-82)
    assert forgiven == Decimal("0.3")
    assert ledger.outstanding_kwh() == Decimal(0)
    assert ledger.forgiven_kwh() == Decimal("0.3")


def test_a_debt_within_the_expiry_is_kept() -> None:
    # Given / When — one minute short of the window
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})
    forgiven = ledger.expire(at(0) + EXPIRY - timedelta(minutes=1))

    # Then
    assert forgiven == Decimal(0)
    assert ledger.outstanding_kwh() == Decimal("0.3")


def test_an_expired_debt_is_not_refunded_later() -> None:
    # Given — a debt forgiven because nothing ever repaid it
    ledger = a_ledger()
    ledger.owe(at(0), Decimal("0.3"), Decimal("0.09"), {AIRCON: Decimal("0.4")})
    ledger.expire(at(0) + EXPIRY)

    # When — a surplus arrives afterwards
    repayment = ledger.repay(Decimal("0.5"), Decimal(0))

    # Then — the charge stands. Refunding it would hand back money for energy the
    # house was never metered as consuming.
    assert repayment.kwh == Decimal(0)
    assert repayment.refunds == {}


def test_nothing_owed_means_nothing_withheld() -> None:
    # Given / When — the ordinary case, where the devices did not overshoot
    repayment = a_ledger().repay(Decimal("0.5"), TARIFF)

    # Then — the remainder keeps its whole surplus
    assert repayment.kwh == Decimal(0)
    assert repayment.refunds == {}
