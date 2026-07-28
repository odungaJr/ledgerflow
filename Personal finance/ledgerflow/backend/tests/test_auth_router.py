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


def test_register_conflicts_once_initialized(unauthenticated_client):
    unauthenticated_client.post("/auth/register", json={"username": "moses", "password": "correct-horse"})
    resp = unauthenticated_client.post("/auth/register", json={"username": "anyone", "password": "correct-horse"})
    assert resp.status_code == 409


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
