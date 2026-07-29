def test_list_categories_returns_seeded_categories_sorted_by_name(client, seed_categories):
    resp = client.get("/categories")
    assert resp.status_code == 200
    body = resp.json()
    names = [c["name"] for c in body]
    assert names == sorted(names)
    assert "Food & Dining" in names
    assert all({"id", "name", "icon", "is_income"} <= c.keys() for c in body)


def test_list_categories_empty_when_none_seeded(client):
    resp = client.get("/categories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_category_defaults_to_non_system(client):
    resp = client.post("/categories", json={"name": "Pet Care", "icon": "🐾"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Pet Care"
    assert body["icon"] == "🐾"
    assert body["is_income"] is False
    assert body["is_system"] is False


def test_create_category_rejects_duplicate_name(client, seed_categories):
    resp = client.post("/categories", json={"name": "Food & Dining"})
    assert resp.status_code == 409


def test_create_category_rejects_blank_name(client):
    resp = client.post("/categories", json={"name": "   "})
    assert resp.status_code == 422


def test_patch_category_renames_it(client):
    created = client.post("/categories", json={"name": "Pet Care"}).json()
    resp = client.patch(f"/categories/{created['id']}", json={"name": "Pets", "icon": "🐶"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Pets"
    assert body["icon"] == "🐶"


def test_delete_system_category_is_blocked(client, seed_categories):
    cat = seed_categories["Food & Dining"]
    resp = client.delete(f"/categories/{cat.id}")
    assert resp.status_code == 409


def test_delete_unused_custom_category_succeeds(client):
    created = client.post("/categories", json={"name": "Pet Care"}).json()
    resp = client.delete(f"/categories/{created['id']}")
    assert resp.status_code == 200

    remaining = [c["name"] for c in client.get("/categories").json()]
    assert "Pet Care" not in remaining


def test_delete_category_in_use_is_blocked(client, db_session):
    import uuid
    from datetime import date
    from app.models.models import Account, Transaction, TransactionType

    created = client.post("/categories", json={"name": "Pet Care"}).json()
    account = Account(id=uuid.uuid4(), name="Test Account", bank="CRDB")
    db_session.add(account)
    db_session.commit()
    txn = Transaction(
        id=uuid.uuid4(), account_id=account.id, category_id=uuid.UUID(created["id"]),
        date=date(2026, 7, 1), description="VET BILL", amount=10000,
        type=TransactionType.debit, fingerprint=str(uuid.uuid4()),
    )
    db_session.add(txn)
    db_session.commit()

    resp = client.delete(f"/categories/{created['id']}")
    assert resp.status_code == 409
