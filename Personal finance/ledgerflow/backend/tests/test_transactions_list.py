import uuid
from datetime import date

from app.models.models import Account, Transaction, TransactionType


def _make_account(db_session, user_id):
    account = Account(id=uuid.uuid4(), user_id=user_id, name="Test Account", bank="CRDB")
    db_session.add(account)
    db_session.commit()
    return account


def _make_txn(db_session, account, txn_date, description, amount, txn_type):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=account.user_id,
        account_id=account.id,
        date=txn_date,
        description=description,
        amount=amount,
        type=txn_type,
        fingerprint=str(uuid.uuid4()),
    )
    db_session.add(txn)
    db_session.commit()
    return txn


def test_search_filters_by_description_substring(client, db_session, test_user):
    account = _make_account(db_session, test_user.id)
    _make_txn(db_session, account, date(2026, 7, 1), "ATM WITHDRAWAL KARIAKOO", 50000, TransactionType.debit)
    _make_txn(db_session, account, date(2026, 7, 2), "SUPERMARKET SHOPPING", 20000, TransactionType.debit)

    resp = client.get("/transactions?search=atm")
    assert resp.status_code == 200
    descriptions = [t["description"] for t in resp.json()]
    assert descriptions == ["ATM WITHDRAWAL KARIAKOO"]


def test_date_range_filters(client, db_session, test_user):
    account = _make_account(db_session, test_user.id)
    _make_txn(db_session, account, date(2026, 6, 15), "JUNE TXN", 10000, TransactionType.debit)
    _make_txn(db_session, account, date(2026, 7, 15), "JULY TXN", 10000, TransactionType.debit)

    resp = client.get("/transactions?from_date=2026-07-01&to_date=2026-07-31")
    descriptions = [t["description"] for t in resp.json()]
    assert descriptions == ["JULY TXN"]


def test_txn_type_filter(client, db_session, test_user):
    account = _make_account(db_session, test_user.id)
    _make_txn(db_session, account, date(2026, 7, 1), "SALARY", 500000, TransactionType.credit)
    _make_txn(db_session, account, date(2026, 7, 2), "SHOPPING", 20000, TransactionType.debit)

    resp = client.get("/transactions?txn_type=credit")
    descriptions = [t["description"] for t in resp.json()]
    assert descriptions == ["SALARY"]


def test_pagination_limit_and_offset(client, db_session, test_user):
    account = _make_account(db_session, test_user.id)
    for i in range(5):
        _make_txn(db_session, account, date(2026, 7, i + 1), f"TXN {i}", 1000, TransactionType.debit)

    page1 = client.get("/transactions?limit=2&offset=0").json()
    page2 = client.get("/transactions?limit=2&offset=2").json()

    assert len(page1) == 2
    assert len(page2) == 2
    assert {t["id"] for t in page1}.isdisjoint({t["id"] for t in page2})


def test_list_transactions_excludes_other_users(client, db_session, test_user, second_user):
    other_account = _make_account(db_session, second_user.id)
    _make_txn(db_session, other_account, date(2026, 7, 1), "NOT MINE", 50000, TransactionType.debit)

    resp = client.get("/transactions")
    assert resp.status_code == 200
    assert resp.json() == []
