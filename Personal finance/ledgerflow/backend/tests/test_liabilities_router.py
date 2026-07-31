def _create(client, **overrides):
    body = {
        "name": "NMB Car Loan",
        "liability_type": "loan",
        "value_date": "2026-01-01",
        "total_value": 5_000_000,
    }
    body.update(overrides)
    return client.post("/liabilities", json=body)


def test_create_liability_with_initial_value(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "NMB Car Loan"
    assert body["current_value"] == 5_000_000
    assert body["change_amount"] == 0


def test_create_liability_rejects_unknown_type(client):
    resp = _create(client, liability_type="student_loan")
    assert resp.status_code == 422


def test_list_liabilities_only_returns_active(client):
    created = _create(client).json()
    _create(client, name="Visa Card", liability_type="credit_card")

    client.patch(f"/liabilities/{created['id']}", json={"is_active": False})

    resp = client.get("/liabilities")
    names = [l["name"] for l in resp.json()]
    assert "NMB Car Loan" not in names
    assert "Visa Card" in names


def test_patch_liability_updates_fields(client):
    created = _create(client).json()
    resp = client.patch(f"/liabilities/{created['id']}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


def test_add_liability_value_updates_current_value(client):
    created = _create(client).json()
    resp = client.post(f"/liabilities/{created['id']}/values", json={
        "value_date": "2026-06-01",
        "total_value": 4_200_000,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["current_value"] == 4_200_000
    assert body["change_amount"] == -800_000


def test_liability_history_lists_all_snapshots(client):
    created = _create(client).json()
    client.post(f"/liabilities/{created['id']}/values", json={"value_date": "2026-06-01", "total_value": 4_200_000})

    resp = client.get(f"/liabilities/{created['id']}/history")
    assert resp.status_code == 200
    dates = [v["value_date"] for v in resp.json()]
    assert dates == ["2026-01-01", "2026-06-01"]


def test_delete_liability_removes_it(client):
    created = _create(client).json()
    resp = client.delete(f"/liabilities/{created['id']}")
    assert resp.status_code == 200
    assert client.get("/liabilities").json() == []


def test_liabilities_summary_endpoint(client):
    _create(client)
    resp = client.get("/liabilities/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_value"] == 5_000_000
    assert len(body["breakdown"]) == 1
