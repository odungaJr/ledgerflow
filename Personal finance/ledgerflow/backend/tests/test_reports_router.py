import uuid
from datetime import date

from app.models.models import Account, Transaction, TransactionType


def _make_account(db_session, user_id):
    account = Account(id=uuid.uuid4(), user_id=user_id, name="Test Account", bank="CRDB")
    db_session.add(account)
    db_session.commit()
    return account


def _make_txn(db_session, account, txn_date, description, amount, txn_type, category=None):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=account.user_id,
        account_id=account.id,
        category_id=category.id if category else None,
        date=txn_date,
        description=description,
        amount=amount,
        type=txn_type,
        fingerprint=str(uuid.uuid4()),
    )
    db_session.add(txn)
    db_session.commit()
    return txn


def test_pnl_totals_and_net(client, db_session, test_user, seed_categories):
    account = _make_account(db_session, test_user.id)
    _make_txn(db_session, account, date(2026, 7, 1), "SALARY", 500000, TransactionType.credit,
              seed_categories["Salary & Wages"])
    _make_txn(db_session, account, date(2026, 7, 5), "GROCERIES", 150000, TransactionType.debit,
              seed_categories["Food & Dining"])
    _make_txn(db_session, account, date(2026, 7, 6), "BUS FARE", 20000, TransactionType.debit,
              seed_categories["Transport"])
    # Outside the requested range — must not be counted.
    _make_txn(db_session, account, date(2026, 6, 1), "JUNE SALARY", 500000, TransactionType.credit,
              seed_categories["Salary & Wages"])

    resp = client.get("/reports/pnl", params={"from_date": "2026-07-01", "to_date": "2026-07-31"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_income"] == 500000
    assert body["total_expenses"] == 170000
    assert body["net_income"] == 330000
    assert {r["name"]: r["total"] for r in body["income"]} == {"Salary & Wages": 500000}
    assert {r["name"]: r["total"] for r in body["expenses"]} == {
        "Food & Dining": 150000, "Transport": 20000,
    }


def test_pnl_groups_uncategorised_transactions(client, db_session, test_user):
    account = _make_account(db_session, test_user.id)
    _make_txn(db_session, account, date(2026, 7, 1), "UNKNOWN DEBIT", 5000, TransactionType.debit)

    resp = client.get("/reports/pnl", params={"from_date": "2026-07-01", "to_date": "2026-07-31"})
    assert resp.status_code == 200
    expenses = resp.json()["expenses"]
    assert expenses == [{"name": "Uncategorised", "icon": "❓", "total": 5000}]


def test_pnl_rejects_inverted_date_range(client):
    resp = client.get("/reports/pnl", params={"from_date": "2026-07-31", "to_date": "2026-07-01"})
    assert resp.status_code == 422


def test_pnl_empty_range_returns_zeros(client):
    resp = client.get("/reports/pnl", params={"from_date": "2026-07-01", "to_date": "2026-07-31"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_income"] == 0
    assert body["total_expenses"] == 0
    assert body["net_income"] == 0
    assert body["income"] == []
    assert body["expenses"] == []
