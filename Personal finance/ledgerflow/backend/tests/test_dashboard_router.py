def test_dashboard_summary_includes_all_time_income(client):
    client.post("/income", json={
        "source": "Salary Jan",
        "expected_amount": 500_000,
        "expected_date": "2026-01-05",
    })
    entry = client.post("/income", json={
        "source": "Salary May",
        "expected_amount": 500_000,
        "expected_date": "2026-05-05",
    }).json()
    client.patch(f"/income/{entry['id']}", json={"received_amount": 500_000})

    # income_tracker is scoped to the requested month (January); income_all_time is not.
    resp = client.get("/dashboard/summary", params={"year": 2026, "month": 1})
    assert resp.status_code == 200
    body = resp.json()

    assert body["income_tracker"]["total_expected"] == 500_000
    assert body["income_all_time"]["total_expected"] == 1_000_000
    assert body["income_all_time"]["total_received"] == 500_000


def test_dashboard_summary_folds_in_net_worth(client):
    client.post("/assets", json={
        "name": "Shares", "asset_type": "stocks", "value_date": "2026-01-01", "total_value": 1_000_000,
    })
    client.post("/liabilities", json={
        "name": "Car Loan", "liability_type": "loan", "value_date": "2026-01-01", "total_value": 300_000,
    })

    resp = client.get("/dashboard/summary", params={"year": 2026, "month": 1})
    assert resp.status_code == 200
    body = resp.json()

    assert body["assets"]["total_value"] == 1_000_000
    assert body["liabilities"]["total_value"] == 300_000
    assert body["net_worth"]["total"] == 700_000
    assert body["net_worth"]["trend"][-1]["net_worth"] == 700_000


def test_dashboard_summary_includes_monthly_trend(client):
    resp = client.get("/dashboard/summary", params={"year": 2026, "month": 6})
    assert resp.status_code == 200
    trend = resp.json()["monthly_trend"]
    assert len(trend) == 6
    assert trend[-1]["period"] == "Jun 2026"


def test_insights_reports_a_clean_error_when_ai_is_unavailable(client, monkeypatch):
    def _raise(*args, **kwargs):
        raise ConnectionError("Ollama isn't running")

    monkeypatch.setattr("app.routers.dashboard.detect_anomalies", _raise)

    resp = client.get("/dashboard/insights", params={"year": 2026, "month": 6})
    assert resp.status_code == 503
    assert "Ollama" in resp.json()["detail"]
