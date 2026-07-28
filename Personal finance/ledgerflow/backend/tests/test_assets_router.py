def _create(client, **overrides):
    body = {
        "name": "CRDB shares",
        "asset_type": "stocks",
        "quantity": 100,
        "value_date": "2026-01-01",
        "total_value": 1_000_000,
        "unit_value": 10_000,
    }
    body.update(overrides)
    return client.post("/assets", json=body)


def test_create_asset_with_initial_value(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "CRDB shares"
    assert body["current_value"] == 1_000_000
    assert body["change_amount"] == 0


def test_create_asset_rejects_unknown_type(client):
    resp = _create(client, asset_type="crypto")
    assert resp.status_code == 422


def test_list_assets_only_returns_active(client):
    created = _create(client).json()
    _create(client, name="Treasury bond", asset_type="bonds")

    client.patch(f"/assets/{created['id']}", json={"is_active": False})

    resp = client.get("/assets")
    names = [a["name"] for a in resp.json()]
    assert "CRDB shares" not in names
    assert "Treasury bond" in names


def test_patch_asset_updates_fields(client):
    created = _create(client).json()
    resp = client.patch(f"/assets/{created['id']}", json={"name": "Renamed", "quantity": 200})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["quantity"] == 200


def test_add_asset_value_updates_current_value(client):
    created = _create(client).json()
    resp = client.post(f"/assets/{created['id']}/values", json={
        "value_date": "2026-06-01",
        "total_value": 1_500_000,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["current_value"] == 1_500_000
    assert body["change_amount"] == 500_000


def test_asset_history_lists_all_snapshots(client):
    created = _create(client).json()
    client.post(f"/assets/{created['id']}/values", json={"value_date": "2026-06-01", "total_value": 1_500_000})

    resp = client.get(f"/assets/{created['id']}/history")
    assert resp.status_code == 200
    dates = [v["value_date"] for v in resp.json()]
    assert dates == ["2026-01-01", "2026-06-01"]


def test_delete_asset_removes_it(client):
    created = _create(client).json()
    resp = client.delete(f"/assets/{created['id']}")
    assert resp.status_code == 200
    assert client.get("/assets").json() == []


def test_assets_summary_endpoint(client):
    _create(client)
    resp = client.get("/assets/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_value"] == 1_000_000
    assert len(body["breakdown"]) == 1
