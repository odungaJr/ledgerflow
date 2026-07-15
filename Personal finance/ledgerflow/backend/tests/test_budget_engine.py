import uuid
from datetime import date

from app.models.models import Account, Budget, BudgetPeriod, Transaction, TransactionType
from app.services.budget_engine import _period_start, get_budget_status, get_monthly_summary


def _make_account(db_session):
    account = Account(id=uuid.uuid4(), name="Test Account", bank="Test Bank")
    db_session.add(account)
    db_session.commit()
    return account


def _make_txn(db_session, account, category, txn_date, amount, txn_type):
    txn = Transaction(
        id=uuid.uuid4(),
        account_id=account.id,
        category_id=category.id,
        date=txn_date,
        description="test txn",
        amount=amount,
        type=txn_type,
        fingerprint=str(uuid.uuid4()),
    )
    db_session.add(txn)
    db_session.commit()
    return txn


# ── _period_start ────────────────────────────────────────────────────────────

def test_period_start_monthly_returns_first_of_month():
    assert _period_start(BudgetPeriod.monthly, date(2024, 4, 15)) == date(2024, 4, 1)


def test_period_start_weekly_returns_monday_of_current_week():
    ref = date(2024, 4, 17)  # a Wednesday
    start = _period_start(BudgetPeriod.weekly, ref)
    assert start.weekday() == 0
    assert start <= ref
    assert (ref - start).days < 7


# ── get_budget_status ────────────────────────────────────────────────────────

def test_budget_status_ok_warning_breached(db_session, seed_categories):
    account = _make_account(db_session)
    food = seed_categories["Food & Dining"]
    ref_date = date(2024, 4, 20)

    budget = Budget(
        id=uuid.uuid4(),
        category_id=food.id,
        period=BudgetPeriod.monthly,
        limit_amount=100_000,
        start_date=date(2024, 4, 1),
        is_active=True,
    )
    db_session.add(budget)
    db_session.commit()

    _make_txn(db_session, account, food, date(2024, 4, 5), 50_000, TransactionType.debit)

    status = get_budget_status(db_session, ref_date)[0]
    assert status["spent"] == 50_000.0
    assert status["pct_used"] == 0.5
    assert status["is_warning"] is False
    assert status["is_breached"] is False

    # Push spend into the warning band (80-100%)
    _make_txn(db_session, account, food, date(2024, 4, 10), 35_000, TransactionType.debit)
    status = get_budget_status(db_session, ref_date)[0]
    assert status["pct_used"] == 0.85
    assert status["is_warning"] is True
    assert status["is_breached"] is False

    # Push spend past the limit
    _make_txn(db_session, account, food, date(2024, 4, 12), 30_000, TransactionType.debit)
    status = get_budget_status(db_session, ref_date)[0]
    assert status["is_breached"] is True
    assert status["is_warning"] is False


def test_budget_status_ignores_transactions_outside_period(db_session, seed_categories):
    account = _make_account(db_session)
    food = seed_categories["Food & Dining"]
    budget = Budget(
        id=uuid.uuid4(),
        category_id=food.id,
        period=BudgetPeriod.monthly,
        limit_amount=100_000,
        start_date=date(2024, 4, 1),
        is_active=True,
    )
    db_session.add(budget)
    db_session.commit()

    # Previous month — should not count
    _make_txn(db_session, account, food, date(2024, 3, 25), 90_000, TransactionType.debit)

    status = get_budget_status(db_session, date(2024, 4, 20))[0]
    assert status["spent"] == 0.0


def test_budget_status_excludes_inactive_budgets(db_session, seed_categories):
    food = seed_categories["Food & Dining"]
    budget = Budget(
        id=uuid.uuid4(),
        category_id=food.id,
        period=BudgetPeriod.monthly,
        limit_amount=100_000,
        start_date=date(2024, 4, 1),
        is_active=False,
    )
    db_session.add(budget)
    db_session.commit()

    assert get_budget_status(db_session, date(2024, 4, 20)) == []


# ── get_monthly_summary ──────────────────────────────────────────────────────

def test_monthly_summary_totals_and_top_categories(db_session, seed_categories):
    account = _make_account(db_session)
    food = seed_categories["Food & Dining"]
    transport = seed_categories["Transport"]
    salary = seed_categories["Salary & Wages"]

    _make_txn(db_session, account, salary, date(2024, 4, 3), 1_000_000, TransactionType.credit)
    _make_txn(db_session, account, food, date(2024, 4, 5), 60_000, TransactionType.debit)
    _make_txn(db_session, account, transport, date(2024, 4, 6), 20_000, TransactionType.debit)

    # Outside the target month — must not be counted
    _make_txn(db_session, account, food, date(2024, 3, 20), 999_999, TransactionType.debit)

    summary = get_monthly_summary(db_session, 2024, 4)

    assert summary["period"] == "April 2024"
    assert summary["total_income"] == 1_000_000.0
    assert summary["total_expenses"] == 80_000.0
    assert summary["net"] == 920_000.0

    names = [c["name"] for c in summary["top_categories"]]
    assert names[0] == "Food & Dining"  # highest spend first
    assert "Transport" in names


def test_monthly_summary_with_no_transactions_returns_zeros(db_session, seed_categories):
    summary = get_monthly_summary(db_session, 2024, 4)
    assert summary["total_income"] == 0.0
    assert summary["total_expenses"] == 0.0
    assert summary["net"] == 0.0
    assert summary["top_categories"] == []
