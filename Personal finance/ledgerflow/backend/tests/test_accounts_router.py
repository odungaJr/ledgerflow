def test_create_account_defaults_currency_and_active(client):
    resp = client.post("/accounts", json={"name": "KCB Salary Account", "bank": "KCB"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "KCB Salary Account"
    assert body["bank"] == "KCB"
    assert body["currency"] == "TZS"
    assert body["is_active"] is True


def test_create_account_accepts_explicit_currency(client):
    resp = client.post("/accounts", json={"name": "USD Wallet", "bank": "CRDB", "currency": "USD"})
    assert resp.status_code == 201
    assert resp.json()["currency"] == "USD"


def test_list_accounts_excludes_inactive_by_default(client):
    active = client.post("/accounts", json={"name": "Active Acc", "bank": "NMB"}).json()
    inactive = client.post("/accounts", json={"name": "Inactive Acc", "bank": "NMB"}).json()
    client.patch(f"/accounts/{inactive['id']}", json={"is_active": False})

    resp = client.get("/accounts")
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert active["name"] in names
    assert inactive["name"] not in names

    resp_all = client.get("/accounts?include_inactive=true")
    names_all = [a["name"] for a in resp_all.json()]
    assert inactive["name"] in names_all


def test_get_account_by_id(client):
    created = client.post("/accounts", json={"name": "Test Acc", "bank": "CRDB"}).json()
    resp = client.get(f"/accounts/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_account_not_found(client):
    resp = client.get("/accounts/11111111-1111-1111-1111-111111111111")
    assert resp.status_code == 404


def test_update_account_fields(client):
    created = client.post("/accounts", json={"name": "Old Name", "bank": "CRDB"}).json()
    resp = client.patch(f"/accounts/{created['id']}", json={"name": "New Name", "is_active": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["is_active"] is False
    assert body["bank"] == "CRDB"  # untouched fields remain


def test_update_account_not_found(client):
    resp = client.patch("/accounts/11111111-1111-1111-1111-111111111111", json={"name": "X"})
    assert resp.status_code == 404


def test_delete_account(client):
    created = client.post("/accounts", json={"name": "To Delete", "bank": "CRDB"}).json()
    resp = client.delete(f"/accounts/{created['id']}")
    assert resp.status_code == 200
    assert client.get(f"/accounts/{created['id']}").status_code == 404


def test_delete_account_not_found(client):
    resp = client.delete("/accounts/11111111-1111-1111-1111-111111111111")
    assert resp.status_code == 404


def test_new_account_has_no_balance(client):
    created = client.post("/accounts", json={"name": "Fresh", "bank": "CRDB"}).json()
    assert created["current_balance"] is None
    assert created["balance_source"] is None


def test_set_manual_balance(client):
    created = client.post("/accounts", json={"name": "Fresh", "bank": "CRDB"}).json()
    resp = client.patch(f"/accounts/{created['id']}", json={
        "manual_balance": 250000, "manual_balance_date": "2026-07-01",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_balance"] == 250000
    assert body["balance_source"] == "manual"
    assert body["balance_as_of"] == "2026-07-01"


def test_balance_reflects_latest_transaction_import(client, seed_categories):
    import io
    created = client.post("/accounts", json={"name": "Fresh", "bank": "CRDB"}).json()
    csv_bytes = (
        b"Date,Description,Debit,Credit,Balance\n"
        b"01/07/2026,Salary,,500000.00,500000.00\n"
        b"05/07/2026,Groceries,50000.00,,450000.00\n"
    )
    client.post(
        "/transactions/import/csv",
        data={"account_id": created["id"], "auto_categorise": "false"},
        files={"file": ("statement.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    resp = client.get(f"/accounts/{created['id']}")
    body = resp.json()
    assert body["current_balance"] == 450000
    assert body["balance_source"] == "transaction"
    assert body["balance_as_of"] == "2026-07-05"
