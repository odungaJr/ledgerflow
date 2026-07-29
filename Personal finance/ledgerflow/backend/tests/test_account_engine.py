import uuid
from datetime import date
from decimal import Decimal

from app.models.models import Account, Transaction, TransactionType
from app.services.account_engine import compute_balance


def _make_account(db_session, **kwargs):
    account = Account(id=uuid.uuid4(), name="Test", bank="CRDB", **kwargs)
    db_session.add(account)
    db_session.commit()
    return account


def _make_txn(db_session, account, txn_date, balance_after):
    txn = Transaction(
        id=uuid.uuid4(), account_id=account.id, date=txn_date, description="x",
        amount=1000, type=TransactionType.debit, balance_after=balance_after,
        fingerprint=str(uuid.uuid4()),
    )
    db_session.add(txn)
    db_session.commit()


def test_no_data_returns_none(db_session):
    account = _make_account(db_session)
    result = compute_balance(account)
    assert result == {"current_balance": None, "balance_as_of": None, "balance_source": None}


def test_uses_latest_transaction_balance(db_session):
    account = _make_account(db_session)
    _make_txn(db_session, account, date(2026, 1, 1), Decimal("100000"))
    _make_txn(db_session, account, date(2026, 3, 1), Decimal("80000"))
    db_session.refresh(account)

    result = compute_balance(account)
    assert result["current_balance"] == 80000.0
    assert result["balance_as_of"] == date(2026, 3, 1)
    assert result["balance_source"] == "transaction"


def test_uses_manual_balance_when_no_transactions(db_session):
    account = _make_account(
        db_session, manual_balance=Decimal("500000"), manual_balance_date=date(2026, 6, 1),
    )
    result = compute_balance(account)
    assert result["current_balance"] == 500000.0
    assert result["balance_source"] == "manual"


def test_manual_balance_wins_when_more_recent_than_transactions(db_session):
    account = _make_account(
        db_session, manual_balance=Decimal("500000"), manual_balance_date=date(2026, 6, 1),
    )
    _make_txn(db_session, account, date(2026, 1, 1), Decimal("100000"))
    db_session.refresh(account)

    result = compute_balance(account)
    assert result["current_balance"] == 500000.0
    assert result["balance_source"] == "manual"


def test_transaction_wins_when_more_recent_than_manual_balance(db_session):
    account = _make_account(
        db_session, manual_balance=Decimal("500000"), manual_balance_date=date(2026, 1, 1),
    )
    _make_txn(db_session, account, date(2026, 6, 1), Decimal("80000"))
    db_session.refresh(account)

    result = compute_balance(account)
    assert result["current_balance"] == 80000.0
    assert result["balance_source"] == "transaction"
