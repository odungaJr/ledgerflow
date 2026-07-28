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
