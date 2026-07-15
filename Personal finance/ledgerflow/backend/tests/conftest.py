import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.models import Category


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
def client(db_session):
    """A TestClient wired to the in-memory db_session instead of the real Postgres engine.

    Not used as a context manager, so app startup (lifespan) never runs — it would
    otherwise try to connect to the real DATABASE_URL via app.core.database.engine.
    """
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
