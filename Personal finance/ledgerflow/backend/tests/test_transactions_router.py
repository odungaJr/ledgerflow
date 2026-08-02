import io

CSV_BYTES = (
    b"Date,Description,Debit,Credit,Balance\n"
    b"15/04/2024,ATM WITHDRAWAL KARIAKOO,50000.00,,2340500.00\n"
)


def _make_account(client):
    resp = client.post("/accounts", json={"name": "Test Account", "bank": "CRDB"})
    return resp.json()["id"]


def test_import_skips_ai_when_auto_categorise_false(client, monkeypatch):
    account_id = _make_account(client)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("categorise_batch should not be called when auto_categorise=false")

    monkeypatch.setattr("app.routers.transactions.categorise_batch", _fail_if_called)

    resp = client.post(
        "/transactions/import/csv",
        data={"account_id": account_id, "auto_categorise": "false"},
        files={"file": ("statement.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["categorised"] is False


def test_import_runs_ai_by_default(client, monkeypatch, seed_categories):
    account_id = _make_account(client)

    def _fake_categorise(payload):
        return [{"transaction_id": payload[0]["id"], "category": "Transport", "confidence": 0.9}]

    monkeypatch.setattr("app.routers.transactions.categorise_batch", _fake_categorise)

    resp = client.post(
        "/transactions/import/csv",
        data={"account_id": account_id},
        files={"file": ("statement.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["categorised"] is True

    txns = client.get("/transactions").json()
    assert txns[0]["category"] == "Transport"


def test_categorise_pending_reports_no_transactions_when_nothing_uncategorised(client):
    resp = client.post("/transactions/categorise-pending")
    assert resp.status_code == 200
    assert resp.json() == {"scanned": 0, "categorised": 0, "ai_available": True}


def test_categorise_pending_categorises_uncategorised_transactions(client, monkeypatch, seed_categories):
    account_id = _make_account(client)
    client.post(
        "/transactions/import/csv",
        data={"account_id": account_id, "auto_categorise": "false"},
        files={"file": ("statement.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    )

    def _fake_categorise(payload):
        return [{"transaction_id": payload[0]["id"], "category": "Transport", "confidence": 0.9}]

    monkeypatch.setattr("app.routers.transactions.categorise_batch", _fake_categorise)

    resp = client.post("/transactions/categorise-pending")
    assert resp.status_code == 200
    assert resp.json() == {"scanned": 1, "categorised": 1, "ai_available": True}

    txns = client.get("/transactions").json()
    assert txns[0]["category"] == "Transport"


def test_categorise_pending_reports_when_ai_service_fails(client, monkeypatch):
    account_id = _make_account(client)
    client.post(
        "/transactions/import/csv",
        data={"account_id": account_id, "auto_categorise": "false"},
        files={"file": ("statement.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    )

    def _raise(*args, **kwargs):
        raise ConnectionError("Ollama isn't running")

    monkeypatch.setattr("app.routers.transactions.categorise_batch", _raise)

    resp = client.post("/transactions/categorise-pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"scanned": 1, "categorised": 0, "ai_available": False}

    # Transaction is untouched, left for the user to categorise manually.
    txns = client.get("/transactions").json()
    assert txns[0]["category"] is None


def test_categorise_pending_leaves_already_categorised_transactions_alone(client, monkeypatch, seed_categories):
    account_id = _make_account(client)

    def _fake_categorise(payload):
        return [{"transaction_id": payload[0]["id"], "category": "Transport", "confidence": 0.9}]

    monkeypatch.setattr("app.routers.transactions.categorise_batch", _fake_categorise)

    client.post(
        "/transactions/import/csv",
        data={"account_id": account_id},
        files={"file": ("statement.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    )

    # Already categorised by the import above — nothing left to scan.
    resp = client.post("/transactions/categorise-pending")
    assert resp.status_code == 200
    assert resp.json() == {"scanned": 0, "categorised": 0, "ai_available": True}


CSV_TWO_ROWS = (
    b"Date,Description,Debit,Credit,Balance\n"
    b"15/04/2024,ATM WITHDRAWAL KARIAKOO,50000.00,,2340500.00\n"
    b"16/04/2024,SUPERMARKET,20000.00,,2320500.00\n"
)


def test_bulk_patch_applies_category_to_all_given_ids(client, seed_categories):
    account_id = _make_account(client)
    client.post(
        "/transactions/import/csv",
        data={"account_id": account_id, "auto_categorise": "false"},
        files={"file": ("statement.csv", io.BytesIO(CSV_TWO_ROWS), "text/csv")},
    )
    txns = client.get("/transactions").json()
    ids = [t["id"] for t in txns]

    resp = client.patch("/transactions/bulk", json={"transaction_ids": ids, "category_name": "Food & Dining"})
    assert resp.status_code == 200
    assert resp.json() == {"updated": 2}

    txns = client.get("/transactions").json()
    assert all(t["category"] == "Food & Dining" for t in txns)
    assert all(t["is_confirmed"] for t in txns)


def test_bulk_patch_unknown_category_404s(client):
    resp = client.patch("/transactions/bulk", json={"transaction_ids": [], "category_name": "Nonexistent"})
    assert resp.status_code == 404


def test_delete_all_transactions(client):
    account_id = _make_account(client)
    client.post(
        "/transactions/import/csv",
        data={"account_id": account_id, "auto_categorise": "false"},
        files={"file": ("statement.csv", io.BytesIO(CSV_TWO_ROWS), "text/csv")},
    )
    assert len(client.get("/transactions").json()) == 2

    resp = client.delete("/transactions/all")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}
    assert client.get("/transactions").json() == []


def test_delete_all_transactions_when_none_exist(client):
    resp = client.delete("/transactions/all")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 0}
