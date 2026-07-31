import uuid

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import Base, get_db
from app.models.models import Category, User

# Header used to pick which fake identity a request runs as. Needed because
# `app.dependency_overrides` is a single dict shared by the *app object*,
# not per-TestClient — two TestClients both hard-overriding
# get_current_user to a fixed user would silently stomp on each other (last
# fixture set up wins for BOTH clients). Reading identity from a header
# instead means the override itself is identity-agnostic; each TestClient
# just sends its own default header.
_TEST_USER_HEADER = "x-test-user-id"


@pytest.fixture()
def db_session():
    """An isolated in-memory SQLite session with all tables created.

    StaticPool + check_same_thread=False so the same connection can be shared
    with TestClient, which dispatches requests on a different thread.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_user(db_session):
    """A logged-in user row, used to fake authentication in the `client` fixture."""
    user = User(id=uuid.uuid4(), username="testuser", password_hash="unused-in-tests")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def second_user(db_session):
    """A second, distinct user row — for cross-user data-isolation tests."""
    user = User(id=uuid.uuid4(), username="otheruser", password_hash="unused-in-tests")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def seed_categories(db_session, test_user):
    """Seed a handful of categories, owned by `test_user`, used across budget/transaction tests."""
    names = ["Food & Dining", "Transport", "Salary & Wages", "Other"]
    categories = {}
    for name in names:
        cat = Category(id=uuid.uuid4(), user_id=test_user.id, name=name, is_income=(name == "Salary & Wages"))
        db_session.add(cat)
        categories[name] = cat
    db_session.commit()
    return categories


def _make_authenticated_client(db_session, user) -> TestClient:
    from app.main import app

    def _override_get_db():
        yield db_session

    def _override_get_current_user(request: Request):
        """Resolve the fake identity from `_TEST_USER_HEADER` rather than a
        fixed closure — see the module-level comment on why."""
        user_id = request.headers.get(_TEST_USER_HEADER)
        return db_session.query(User).filter(User.id == uuid.UUID(user_id)).first()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    test_client = TestClient(app)
    test_client.headers.update({_TEST_USER_HEADER: str(user.id)})
    return test_client


@pytest.fixture()
def client(db_session, test_user):
    """A TestClient wired to the in-memory db_session instead of the real Postgres engine,
    authenticated as `test_user`.

    Not used as a context manager, so app startup (lifespan) never runs — it would
    otherwise try to connect to the real DATABASE_URL via app.core.database.engine.

    Auth is faked via a header-driven dependency override so every existing test
    stays unauthenticated-free — the real login/session flow is exercised
    separately in test_auth_router.py via `unauthenticated_client`.
    """
    from app.main import app

    try:
        yield _make_authenticated_client(db_session, test_user)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def other_client(db_session, second_user, client):
    """Same idea as `client`, but authenticated as `second_user` — for isolation tests
    that need two distinct identities against the same in-memory database. Depends on
    `client` purely so `app.dependency_overrides` only gets cleared once, by whichever
    of the two fixtures tears down last."""
    yield _make_authenticated_client(db_session, second_user)


@pytest.fixture()
def unauthenticated_client(db_session):
    """A TestClient with real auth (only get_db is overridden) — for testing the auth flow itself."""
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
