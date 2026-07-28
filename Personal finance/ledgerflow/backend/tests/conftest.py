import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import Base, get_db
from app.models.models import Category, User


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
def seed_categories(db_session):
    """Seed a handful of categories used across budget/transaction tests."""
    names = ["Food & Dining", "Transport", "Salary & Wages", "Other"]
    categories = {}
    for name in names:
        cat = Category(id=uuid.uuid4(), name=name, is_income=(name == "Salary & Wages"))
        db_session.add(cat)
        categories[name] = cat
    db_session.commit()
    return categories


@pytest.fixture()
def test_user(db_session):
    """A logged-in user row, used to fake authentication in the `client` fixture."""
    user = User(id=uuid.uuid4(), username="testuser", password_hash="unused-in-tests")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def client(db_session, test_user):
    """A TestClient wired to the in-memory db_session instead of the real Postgres engine.

    Not used as a context manager, so app startup (lifespan) never runs — it would
    otherwise try to connect to the real DATABASE_URL via app.core.database.engine.

    Auth is faked via a dependency override (`test_user`) so every existing test
    stays unauthenticated-free — the real login/session flow is exercised
    separately in test_auth_router.py via `unauthenticated_client`.
    """
    from app.main import app

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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
