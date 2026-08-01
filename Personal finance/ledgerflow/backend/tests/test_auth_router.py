def test_status_false_before_any_account_exists(unauthenticated_client):
    resp = unauthenticated_client.get("/auth/status")
    assert resp.status_code == 200
    assert resp.json() == {"initialized": False}


def test_register_creates_bootstrap_account_and_sets_cookie(unauthenticated_client):
    resp = unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    assert resp.status_code == 201
    assert resp.json() == {"username": "moses"}
    assert "session_token" in resp.cookies

    assert unauthenticated_client.get("/auth/status").json() == {"initialized": True}


def test_register_rejects_short_password(unauthenticated_client):
    resp = unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "short"})
    assert resp.status_code == 422


def test_register_allows_a_second_user_with_a_different_username(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post("/auth/register", json={"username": "anyone", "password": "correct-horse"})
    assert resp.status_code == 201
    assert resp.json() == {"username": "anyone"}


def test_register_rejects_a_duplicate_username(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    unauthenticated_client.post("/auth/logout")
    resp = unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "another-password"})
    assert resp.status_code == 409


def test_fresh_registration_gets_its_own_seeded_categories(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    categories = unauthenticated_client.get("/categories").json()
    assert len(categories) == 23
    assert any(c["name"] == "Food & Dining" for c in categories)


def test_second_user_gets_their_own_empty_dataset(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    unauthenticated_client.post("/accounts", json={"name": "Moses's account", "bank": "CRDB"})
    unauthenticated_client.post("/auth/logout")

    unauthenticated_client.post("/auth/register", json={"username": "second", "password": "correct-horse"})
    resp = unauthenticated_client.get("/accounts")
    assert resp.status_code == 200
    assert resp.json() == []

    # Second user's own categories exist and are separate rows from moses's.
    second_categories = {c["id"] for c in unauthenticated_client.get("/categories").json()}

    unauthenticated_client.post("/auth/logout")
    unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "correct-horse"})
    moses_categories = {c["id"] for c in unauthenticated_client.get("/categories").json()}
    moses_accounts = unauthenticated_client.get("/accounts").json()

    assert second_categories.isdisjoint(moses_categories)
    assert len(moses_accounts) == 1
    assert moses_accounts[0]["name"] == "Moses's account"


def test_login_succeeds_with_correct_credentials(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "correct-horse"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "moses"}


def test_login_rejects_wrong_password(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "wrong-password"})
    assert resp.status_code == 401


def test_login_rejects_unknown_username(unauthenticated_client):
    resp = unauthenticated_client.post("/auth/login", json={"username": "ghost", "password": "whatever1"})
    assert resp.status_code == 401


def test_me_requires_authentication(unauthenticated_client):
    resp = unauthenticated_client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_username_once_logged_in(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"username": "moses"}


def test_logout_revokes_the_session(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    assert unauthenticated_client.get("/auth/me").status_code == 200

    resp = unauthenticated_client.post("/auth/logout")
    assert resp.status_code == 200

    assert unauthenticated_client.get("/auth/me").status_code == 401


def test_protected_route_401s_without_a_session(unauthenticated_client):
    resp = unauthenticated_client.get("/accounts")
    assert resp.status_code == 401


def test_protected_route_works_once_logged_in(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.get("/accounts")
    assert resp.status_code == 200


def test_repeated_failed_logins_lock_the_account(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    unauthenticated_client.post("/auth/logout")

    for _ in range(5):
        resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "wrong"})
        assert resp.status_code == 401

    # 6th attempt (even with the correct password) is now locked out.
    resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "correct-horse"})
    assert resp.status_code == 423


def test_successful_login_resets_the_failed_attempt_counter(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    unauthenticated_client.post("/auth/logout")

    for _ in range(3):
        unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "wrong"})

    resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "correct-horse"})
    assert resp.status_code == 200

    # Counter reset — three more wrong attempts alone shouldn't lock it.
    for _ in range(3):
        resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "wrong"})
        assert resp.status_code == 401


def test_change_password_requires_correct_current_password(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post(
        "/auth/change-password",
        json={"current_password": "wrong", "new_password": "new-password-123"},
    )
    assert resp.status_code == 401


def test_change_password_rejects_short_new_password(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post(
        "/auth/change-password",
        json={"current_password": "correct-horse", "new_password": "short"},
    )
    assert resp.status_code == 422


def test_change_password_succeeds_and_new_password_works(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post(
        "/auth/change-password",
        json={"current_password": "correct-horse", "new_password": "new-password-123"},
    )
    assert resp.status_code == 200

    unauthenticated_client.post("/auth/logout")
    resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "new-password-123"})
    assert resp.status_code == 200


def test_login_is_rate_limited_per_ip(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    unauthenticated_client.post("/auth/logout")

    # First 10 requests in the window go through to the normal auth logic
    # (account lockout kicks in partway through and starts returning 423
    # instead of 401 — either is fine here, this test is about the 11th
    # request getting rate-limited, not about lockout behaviour).
    for _ in range(10):
        resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "wrong"})
        assert resp.status_code in (401, 423)

    resp = unauthenticated_client.post("/auth/login", json={"username": "moses", "password": "wrong"})
    assert resp.status_code == 429


def test_register_is_rate_limited_per_ip(unauthenticated_client):
    for i in range(5):
        resp = unauthenticated_client.post("/auth/register", json={"username": f"user{i}", "password": "correct-horse"})
        assert resp.status_code == 201

    resp = unauthenticated_client.post("/auth/register", json={"username": "user5", "password": "correct-horse"})
    assert resp.status_code == 429
