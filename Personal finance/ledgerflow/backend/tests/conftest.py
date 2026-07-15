import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import Category


@pytest.fixture()
def db_session():
    """An isolated in-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:")
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
