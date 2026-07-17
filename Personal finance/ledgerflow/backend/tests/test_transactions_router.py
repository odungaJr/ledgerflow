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
