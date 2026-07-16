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
