def test_create_one_off_income_entry(client):
    resp = client.post("/income", json={
        "source": "Freelance client X",
        "expected_amount": 250_000,
        "expected_date": "2026-03-10",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "Freelance client X"
    assert body["status"] == "overdue" or body["status"] == "pending"
    assert body["pending_amount"] == 250_000
    assert body["is_recurring"] is False


def test_create_recurring_entry_sets_series_id(client):
    resp = client.post("/income", json={
        "source": "Salary",
        "expected_amount": 500_000,
        "expected_date": "2026-01-15",
        "is_recurring": True,
        "recurrence_period": "monthly",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_recurring"] is True
    assert body["series_id"] == body["id"]


def test_create_recurring_entry_requires_period(client):
    resp = client.post("/income", json={
        "source": "Salary",
        "expected_amount": 500_000,
        "expected_date": "2026-01-15",
        "is_recurring": True,
    })
    assert resp.status_code == 422


def test_create_entry_with_unknown_category_404s(client):
    resp = client.post("/income", json={
        "source": "Salary",
        "expected_amount": 500_000,
        "expected_date": "2026-01-15",
        "category_name": "Nonexistent Category",
    })
    assert resp.status_code == 404


def test_list_income_entries_generates_recurring_occurrences(client):
    client.post("/income", json={
        "source": "Salary",
        "expected_amount": 500_000,
        "expected_date": "2026-01-15",
        "is_recurring": True,
        "recurrence_period": "monthly",
    })

    resp = client.get("/income", params={"year": 2026, "month": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["expected_date"] == "2026-03-15"


def test_income_summary_endpoint_matches_get_income_summary(client):
    client.post("/income", json={
        "source": "Salary",
        "expected_amount": 500_000,
        "expected_date": "2026-05-05",
    })

    resp = client.get("/income/summary", params={"year": 2026, "month": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_expected"] == 500_000
    assert body["total_received"] == 0
    assert body["total_pending"] == 500_000


def test_income_summary_all_time_spans_periods(client):
    client.post("/income", json={
        "source": "Salary Jan",
        "expected_amount": 500_000,
        "expected_date": "2026-01-05",
    })
    entry = client.post("/income", json={
        "source": "Salary Feb",
        "expected_amount": 500_000,
        "expected_date": "2026-02-05",
    }).json()
    client.patch(f"/income/{entry['id']}", json={"received_amount": 500_000})

    resp = client.get("/income/summary/all-time")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_expected"] == 1_000_000
    assert body["total_received"] == 500_000
    assert body["total_pending"] == 500_000


def test_patch_income_entry_records_received_amount(client):
    created = client.post("/income", json={
        "source": "Freelance",
        "expected_amount": 100_000,
        "expected_date": "2026-01-01",
    }).json()

    resp = client.patch(f"/income/{created['id']}", json={
        "received_amount": 100_000,
        "received_date": "2026-01-02",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "received"
    assert body["pending_amount"] == 0


def test_patch_income_entry_not_found(client):
    resp = client.patch("/income/11111111-1111-1111-1111-111111111111", json={"received_amount": 1})
    assert resp.status_code == 404


def test_delete_income_entry(client):
    created = client.post("/income", json={
        "source": "One-off",
        "expected_amount": 10_000,
        "expected_date": "2026-01-01",
    }).json()

    resp = client.delete(f"/income/{created['id']}")
    assert resp.status_code == 200

    resp = client.get("/income", params={"year": 2026, "month": 1})
    assert resp.json() == []


def test_delete_recurring_template_removes_whole_series(client):
    created = client.post("/income", json={
        "source": "Salary",
        "expected_amount": 500_000,
        "expected_date": "2026-01-15",
        "is_recurring": True,
        "recurrence_period": "monthly",
    }).json()

    # Generates March and other in-between occurrences that reference the template via series_id.
    client.get("/income", params={"year": 2026, "month": 3})

    resp = client.delete(f"/income/{created['id']}")
    assert resp.status_code == 200

    resp = client.get("/income", params={"year": 2026, "month": 3})
    assert resp.json() == []
