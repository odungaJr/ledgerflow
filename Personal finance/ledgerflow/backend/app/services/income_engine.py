"""
Income Engine
=============
Manual income tracking: expected vs. received amounts, recurring-series
generation, and per-period summaries for the dashboard.

A recurring series is a chain of IncomeEntry rows sharing the same
`series_id`. The first row in a series has `series_id == id` (it is its
own root). `ensure_recurring_occurrences` lazily fills in any missing
future occurrences up to a given date — there is no scheduler/cron.
"""
import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.models import IncomeEntry, RecurrencePeriod


def _advance(d: date, period: RecurrencePeriod) -> date:
    """Return the next occurrence date after `d` for the given recurrence period."""
    if period == RecurrencePeriod.weekly:
        return d + timedelta(days=7)

    # monthly: same day-of-month next month, clamped to that month's length
    year, month = d.year, d.month + 1
    if month > 12:
        month = 1
        year += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def ensure_recurring_occurrences(db: Session, through_date: date) -> None:
    """
    For every recurring income series, make sure an occurrence exists for
    every period up to and including `through_date`. Idempotent — safe to
    call on every read.
    """
    templates = (
        db.query(IncomeEntry)
        .filter(IncomeEntry.is_recurring == True, IncomeEntry.series_id == IncomeEntry.id)
        .all()
    )

    created = False
    for template in templates:
        latest = (
            db.query(IncomeEntry)
            .filter(IncomeEntry.series_id == template.id)
            .order_by(IncomeEntry.expected_date.desc())
            .first()
        )
        next_date = _advance(latest.expected_date, template.recurrence_period)
        while next_date <= through_date:
            db.add(IncomeEntry(
                id                = uuid.uuid4(),
                series_id         = template.id,
                category_id       = template.category_id,
                source            = template.source,
                expected_amount   = latest.expected_amount,
                expected_date     = next_date,
                received_amount   = Decimal(0),
                is_recurring      = True,
                recurrence_period = template.recurrence_period,
            ))
            created = True
            next_date = _advance(next_date, template.recurrence_period)

    if created:
        db.commit()


def entry_status(entry: IncomeEntry) -> dict:
    """Compute the derived pending amount and status for a single entry."""
    pending_amount = entry.expected_amount - entry.received_amount

    if entry.received_amount >= entry.expected_amount:
        status = "received"
    elif entry.received_amount > 0:
        status = "partial"
    elif entry.expected_date < date.today():
        status = "overdue"
    else:
        status = "pending"

    return {"status": status, "pending_amount": pending_amount}


def _period_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def list_entries(db: Session, year: int | None = None, month: int | None = None) -> list[IncomeEntry]:
    """List income entries, generating any due recurring occurrences first."""
    if year and month:
        _, end = _period_bounds(year, month)
        ensure_recurring_occurrences(db, end - timedelta(days=1))
    else:
        ensure_recurring_occurrences(db, date.today())

    q = db.query(IncomeEntry)
    if year and month:
        start, end = _period_bounds(year, month)
        q = q.filter(IncomeEntry.expected_date >= start, IncomeEntry.expected_date < end)
    return q.order_by(IncomeEntry.expected_date).all()


def _summarise(entries: list[IncomeEntry]) -> dict:
    statuses = [entry_status(e)["status"] for e in entries]

    total_expected = sum((e.expected_amount for e in entries), Decimal(0))
    total_received = sum((e.received_amount for e in entries), Decimal(0))

    return {
        "total_expected": float(total_expected),
        "total_received": float(total_received),
        "total_pending":  float(total_expected - total_received),
        "pending_count":  sum(1 for s in statuses if s in ("pending", "overdue", "partial")),
        "overdue_count":  statuses.count("overdue"),
    }


def get_income_summary(db: Session, year: int, month: int) -> dict:
    """Aggregate expected/received/pending income for a given month."""
    return _summarise(list_entries(db, year, month))


def get_income_summary_all_time(db: Session) -> dict:
    """
    Lifetime expected/received/pending totals "to date" — entries whose
    expected_date has actually arrived. Excludes not-yet-due future
    occurrences (e.g. previewed by navigating a recurring series' period
    forward), which would otherwise inflate "expected to date" with income
    that hasn't come due yet.
    """
    entries = [e for e in list_entries(db) if e.expected_date <= date.today()]
    return _summarise(entries)
