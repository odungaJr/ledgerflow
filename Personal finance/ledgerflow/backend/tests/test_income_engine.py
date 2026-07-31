import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.models.models import IncomeEntry, RecurrencePeriod
from app.services.income_engine import (
    _advance,
    ensure_recurring_occurrences,
    entry_status,
    get_income_summary,
    get_income_summary_all_time,
)


def _make_template(db_session, user_id, expected_date, period=RecurrencePeriod.monthly, amount=500_000):
    entry = IncomeEntry(
        id=uuid.uuid4(),
        user_id=user_id,
        source="Salary",
        expected_amount=amount,
        expected_date=expected_date,
        received_amount=0,
        is_recurring=True,
        recurrence_period=period,
    )
    db_session.add(entry)
    db_session.flush()
    entry.series_id = entry.id
    db_session.commit()
    return entry


# ── _advance ─────────────────────────────────────────────────────────────────

def test_advance_monthly_moves_to_next_month_same_day():
    assert _advance(date(2026, 1, 15), RecurrencePeriod.monthly) == date(2026, 2, 15)


def test_advance_monthly_clamps_to_shorter_month():
    assert _advance(date(2026, 1, 31), RecurrencePeriod.monthly) == date(2026, 2, 28)


def test_advance_monthly_rolls_over_year():
    assert _advance(date(2026, 12, 5), RecurrencePeriod.monthly) == date(2027, 1, 5)


def test_advance_weekly_adds_seven_days():
    assert _advance(date(2026, 1, 1), RecurrencePeriod.weekly) == date(2026, 1, 8)


# ── ensure_recurring_occurrences ─────────────────────────────────────────────

def test_ensure_recurring_occurrences_fills_missing_months(db_session, test_user):
    _make_template(db_session, test_user.id, date(2026, 1, 15))

    ensure_recurring_occurrences(db_session, test_user.id, date(2026, 4, 30))

    entries = db_session.query(IncomeEntry).order_by(IncomeEntry.expected_date).all()
    dates = [e.expected_date for e in entries]
    assert dates == [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)]


def test_ensure_recurring_occurrences_is_idempotent(db_session, test_user):
    _make_template(db_session, test_user.id, date(2026, 1, 15))

    ensure_recurring_occurrences(db_session, test_user.id, date(2026, 3, 31))
    first_count = db_session.query(IncomeEntry).count()

    ensure_recurring_occurrences(db_session, test_user.id, date(2026, 3, 31))
    second_count = db_session.query(IncomeEntry).count()

    assert first_count == second_count == 3


def test_ensure_recurring_occurrences_ignores_one_off_entries(db_session, test_user):
    entry = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Freelance", expected_amount=100_000,
        expected_date=date(2026, 1, 1), received_amount=0, is_recurring=False,
    )
    db_session.add(entry)
    db_session.commit()

    ensure_recurring_occurrences(db_session, test_user.id, date(2026, 6, 1))

    assert db_session.query(IncomeEntry).count() == 1


def test_ensure_recurring_occurrences_only_affects_this_user(db_session, test_user, second_user):
    _make_template(db_session, second_user.id, date(2026, 1, 15))

    ensure_recurring_occurrences(db_session, test_user.id, date(2026, 4, 30))

    # Only the template itself exists — nothing generated for a series that isn't mine.
    assert db_session.query(IncomeEntry).count() == 1


# ── entry_status ─────────────────────────────────────────────────────────────

def test_entry_status_received():
    entry = IncomeEntry(expected_amount=Decimal("100"), received_amount=Decimal("100"), expected_date=date(2020, 1, 1))
    result = entry_status(entry)
    assert result["status"] == "received"
    assert result["pending_amount"] == 0


def test_entry_status_partial():
    entry = IncomeEntry(expected_amount=Decimal("100"), received_amount=Decimal("40"), expected_date=date(2020, 1, 1))
    result = entry_status(entry)
    assert result["status"] == "partial"
    assert result["pending_amount"] == 60


def test_entry_status_overdue():
    entry = IncomeEntry(expected_amount=Decimal("100"), received_amount=Decimal("0"), expected_date=date(2020, 1, 1))
    assert entry_status(entry)["status"] == "overdue"


def test_entry_status_pending_when_future():
    entry = IncomeEntry(expected_amount=Decimal("100"), received_amount=Decimal("0"), expected_date=date(2099, 1, 1))
    assert entry_status(entry)["status"] == "pending"


# ── get_income_summary ───────────────────────────────────────────────────────

def test_get_income_summary_aggregates_period(db_session, test_user):
    e1 = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Salary", expected_amount=500_000,
        expected_date=date(2026, 3, 5), received_amount=500_000, received_date=date(2026, 3, 5),
    )
    e2 = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Side hustle", expected_amount=100_000,
        expected_date=date(2026, 3, 20), received_amount=40_000,
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    summary = get_income_summary(db_session, test_user.id, 2026, 3)
    assert summary["total_expected"] == 600_000
    assert summary["total_received"] == 540_000
    assert summary["total_pending"] == 60_000


# ── get_income_summary_all_time ──────────────────────────────────────────────

def test_get_income_summary_all_time_spans_every_period(db_session, test_user):
    e1 = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Salary Jan", expected_amount=500_000,
        expected_date=date(2026, 1, 5), received_amount=500_000, received_date=date(2026, 1, 5),
    )
    e2 = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Salary Mar", expected_amount=500_000,
        expected_date=date(2026, 3, 5), received_amount=300_000,
    )
    e3 = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Freelance", expected_amount=200_000,
        expected_date=date(2020, 6, 1), received_amount=0,
    )
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    summary = get_income_summary_all_time(db_session, test_user.id)
    assert summary["total_expected"] == 1_200_000
    assert summary["total_received"] == 800_000
    assert summary["total_pending"] == 400_000
    assert summary["overdue_count"] == 1
    assert summary["pending_count"] == 2  # e2 (partial) + e3 (overdue)


def test_get_income_summary_all_time_excludes_not_yet_due_entries(db_session, test_user):
    """
    Regression test: navigating a recurring series' period forward (e.g. to
    preview next month) generates that future occurrence in the DB via
    ensure_recurring_occurrences — it must not then get counted as "expected
    to date" before it's actually due.
    """
    due = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Salary this month", expected_amount=2_000_000,
        expected_date=date.today(), received_amount=2_000_000, received_date=date.today(),
    )
    not_yet_due = IncomeEntry(
        id=uuid.uuid4(), user_id=test_user.id, source="Salary next month", expected_amount=2_000_000,
        expected_date=date.today() + timedelta(days=30), received_amount=0,
    )
    db_session.add_all([due, not_yet_due])
    db_session.commit()

    summary = get_income_summary_all_time(db_session, test_user.id)
    assert summary["total_expected"] == 2_000_000
    assert summary["total_received"] == 2_000_000
    assert summary["total_pending"] == 0
