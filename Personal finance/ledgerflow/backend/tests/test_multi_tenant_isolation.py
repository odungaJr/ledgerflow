"""
Cross-user data isolation
==========================
The actual point of the multi-tenant migration: two different logged-in
users must never see, modify, or accidentally reference each other's data.
`client` acts as `test_user`; `other_client` acts as `second_user` — both
fixtures share the same in-memory `db_session`, so these tests exercise real
cross-tenant boundaries rather than two disconnected databases.
"""
import uuid
from datetime import date


# ── Accounts ─────────────────────────────────────────────────────────────────

def test_accounts_are_not_visible_across_users(client, other_client):
    created = client.post("/accounts", json={"name": "My Account", "bank": "CRDB"}).json()

    assert other_client.get("/accounts").json() == []
    assert other_client.get(f"/accounts/{created['id']}").status_code == 404
    assert other_client.patch(f"/accounts/{created['id']}", json={"name": "Hijacked"}).status_code == 404
    assert other_client.delete(f"/accounts/{created['id']}").status_code == 404

    # The original owner still has it, untouched.
    assert client.get(f"/accounts/{created['id']}").json()["name"] == "My Account"


# ── Categories ───────────────────────────────────────────────────────────────

def test_categories_are_private_per_user(client, other_client):
    mine = client.post("/categories", json={"name": "Side Hustle"}).json()

    assert all(c["id"] != mine["id"] for c in other_client.get("/categories").json())
    assert other_client.patch(f"/categories/{mine['id']}", json={"name": "Hijacked"}).status_code == 404
    assert other_client.delete(f"/categories/{mine['id']}").status_code == 404


def test_same_category_name_is_allowed_across_different_users(client, other_client):
    """Two users can each have their own "Food & Dining" — names are unique per user, not globally."""
    mine = client.post("/categories", json={"name": "Food & Dining"}).json()
    theirs = other_client.post("/categories", json={"name": "Food & Dining"}).json()

    assert mine["id"] != theirs["id"]
    assert client.post("/categories", json={"name": "Food & Dining"}).status_code == 409


# ── Budgets: the gap-2 cross-tenant FK bug ──────────────────────────────────

def test_budget_creation_resolves_the_callers_own_category_only(client, other_client):
    client.post("/categories", json={"name": "Food & Dining"})
    theirs = other_client.post("/categories", json={"name": "Food & Dining"}).json()

    resp = other_client.post("/budgets", json={
        "category_name": "Food & Dining", "limit_amount": 100_000, "start_date": "2026-01-01",
    })
    assert resp.status_code == 201

    # The budget must be scoped to their own "Food & Dining" — not mine, and not visible to me.
    assert other_client.get("/budgets").json()[0]["category_name"] == "Food & Dining"
    assert client.get("/budgets").json() == []


def test_budget_creation_404s_for_a_category_only_another_user_owns(client, other_client):
    client.post("/categories", json={"name": "Only Mine"})
    resp = other_client.post("/budgets", json={
        "category_name": "Only Mine", "limit_amount": 50_000, "start_date": "2026-01-01",
    })
    assert resp.status_code == 404


def test_budgets_are_not_visible_or_editable_across_users(client, other_client):
    client.post("/categories", json={"name": "Food & Dining"})
    created = client.post("/budgets", json={
        "category_name": "Food & Dining", "limit_amount": 100_000, "start_date": "2026-01-01",
    }).json()

    assert other_client.get("/budgets") .json() == []
    assert other_client.patch(f"/budgets/{created['id']}", json={"limit_amount": 1}).status_code == 404
    assert other_client.delete(f"/budgets/{created['id']}").status_code == 404


# ── Income: the same gap-2 pattern ──────────────────────────────────────────

def test_income_entry_creation_resolves_the_callers_own_category_only(client, other_client):
    client.post("/categories", json={"name": "Salary", "is_income": True})
    other_client.post("/categories", json={"name": "Salary", "is_income": True})

    resp = other_client.post("/income", json={
        "source": "Job", "expected_amount": 500_000, "expected_date": "2026-01-01", "category_name": "Salary",
    })
    assert resp.status_code == 201
    assert client.get("/income").json() == []


def test_income_entries_are_not_visible_or_editable_across_users(client, other_client):
    created = client.post("/income", json={
        "source": "Job", "expected_amount": 500_000, "expected_date": "2026-01-01",
    }).json()

    assert other_client.get("/income").json() == []
    assert other_client.patch(f"/income/{created['id']}", json={"received_amount": 500_000}).status_code == 404
    assert other_client.delete(f"/income/{created['id']}").status_code == 404


# ── Assets / Liabilities ─────────────────────────────────────────────────────

def test_assets_are_not_visible_or_editable_across_users(client, other_client):
    created = client.post("/assets", json={
        "name": "Shares", "asset_type": "stocks", "value_date": "2026-01-01", "total_value": 1_000_000,
    }).json()

    assert other_client.get("/assets").json() == []
    assert other_client.patch(f"/assets/{created['id']}", json={"name": "Hijacked"}).status_code == 404
    assert other_client.post(f"/assets/{created['id']}/values", json={
        "value_date": "2026-02-01", "total_value": 2_000_000,
    }).status_code == 404
    assert other_client.get(f"/assets/{created['id']}/history").status_code == 404
    assert other_client.delete(f"/assets/{created['id']}").status_code == 404

    # Untouched from my side.
    assert client.get("/assets").json()[0]["current_value"] == 1_000_000


def test_liabilities_are_not_visible_or_editable_across_users(client, other_client):
    created = client.post("/liabilities", json={
        "name": "Loan", "liability_type": "loan", "value_date": "2026-01-01", "total_value": 5_000_000,
    }).json()

    assert other_client.get("/liabilities").json() == []
    assert other_client.patch(f"/liabilities/{created['id']}", json={"name": "Hijacked"}).status_code == 404
    assert other_client.post(f"/liabilities/{created['id']}/values", json={
        "value_date": "2026-02-01", "total_value": 4_000_000,
    }).status_code == 404
    assert other_client.delete(f"/liabilities/{created['id']}").status_code == 404


# ── Transactions ─────────────────────────────────────────────────────────────

def _seed_account_and_transaction(db_session, user):
    from app.models.models import Account, Transaction, TransactionType

    account = Account(id=uuid.uuid4(), user_id=user.id, name="Acct", bank="CRDB")
    db_session.add(account)
    db_session.commit()
    txn = Transaction(
        id=uuid.uuid4(), user_id=user.id, account_id=account.id, date=date(2026, 1, 1),
        description="Test txn", amount=10_000, type=TransactionType.debit,
        fingerprint=str(uuid.uuid4()),
    )
    db_session.add(txn)
    db_session.commit()
    return account, txn


def test_transactions_are_not_visible_or_editable_across_users(client, other_client, db_session, test_user):
    account, txn = _seed_account_and_transaction(db_session, test_user)

    assert other_client.get("/transactions").json() == []
    assert other_client.patch(f"/transactions/{txn.id}", json={"notes": "hijacked"}).status_code == 404
    assert other_client.delete(f"/transactions/{txn.id}").status_code == 404

    # A bulk patch targeting my transaction ID from another user's session must not touch it.
    resp = other_client.post("/categories", json={"name": "Whatever"})
    other_client.patch("/transactions/bulk", json={
        "transaction_ids": [str(txn.id)], "category_name": "Whatever",
    })
    assert client.get(f"/transactions").json()[0]["category"] is None


def test_transaction_patch_never_resolves_another_users_category(client, other_client, db_session, test_user, second_user):
    client.post("/categories", json={"name": "Food & Dining"})
    _, my_txn = _seed_account_and_transaction(db_session, test_user)
    _, their_txn = _seed_account_and_transaction(db_session, second_user)

    # My own patch, with my own category, works.
    assert client.patch(f"/transactions/{my_txn.id}", json={"category_name": "Food & Dining"}).status_code == 200

    # The other user has no category by that name (only I do) — patching
    # their own transaction with it must 404, never silently attach to mine.
    resp = other_client.patch(f"/transactions/{their_txn.id}", json={"category_name": "Food & Dining"})
    assert resp.status_code == 404


def test_delete_all_transactions_only_deletes_the_callers_own(client, other_client, db_session, test_user, second_user):
    _seed_account_and_transaction(db_session, test_user)
    _seed_account_and_transaction(db_session, second_user)

    resp = client.delete("/transactions/all")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1

    assert client.get("/transactions").json() == []
    assert len(other_client.get("/transactions").json()) == 1


# ── Dashboard / Reports ──────────────────────────────────────────────────────

def test_dashboard_summary_is_scoped_per_user(client, other_client, db_session, test_user):
    _seed_account_and_transaction(db_session, test_user)  # dated 2026-01-01, see the helper

    params = {"year": 2026, "month": 1}
    mine = client.get("/dashboard/summary", params=params).json()
    theirs = other_client.get("/dashboard/summary", params=params).json()

    assert mine["summary"]["total_expenses"] == 10_000
    assert theirs["summary"]["total_expenses"] == 0


def test_pnl_report_is_scoped_per_user(client, other_client, db_session, test_user):
    _seed_account_and_transaction(db_session, test_user)

    params = {"from_date": "2026-01-01", "to_date": "2026-01-31"}
    assert client.get("/reports/pnl", params=params).json()["total_expenses"] == 10_000
    assert other_client.get("/reports/pnl", params=params).json()["total_expenses"] == 0
