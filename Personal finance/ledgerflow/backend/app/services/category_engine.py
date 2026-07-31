"""
Category Engine
================
Seeds a fresh registration's own private copy of the default category set
(the same set previously seeded once, globally, by migrations 001 and 005 —
now seeded per-user instead, since categories are private per design).
"""
import uuid

from sqlalchemy.orm import Session

from app.models.models import Category

# (name, icon, is_income)
DEFAULT_CATEGORIES: list[tuple[str, str, bool]] = [
    ("Salary & Wages", "💰", True),
    ("Transfer In", "📥", True),
    ("Other Income", "💵", True),
    ("Food & Dining", "🍔", False),
    ("Transport", "🚗", False),
    ("Utilities", "💡", False),
    ("Rent & Housing", "🏠", False),
    ("Health & Medical", "🏥", False),
    ("Shopping", "🛍️", False),
    ("Entertainment", "🎬", False),
    ("Education", "📚", False),
    ("Savings & Investment", "🏦", False),
    ("Transfer Out", "📤", False),
    ("Subscriptions", "🔁", False),
    ("Insurance", "🛡️", False),
    ("Fees & Charges", "💸", False),
    ("Travel", "✈️", False),
    ("Gifts & Donations", "🎁", False),
    ("Personal Care", "🧴", False),
    ("Family & Kids", "👶", False),
    ("Business Expenses", "💼", False),
    ("Taxes", "🧾", False),
    ("Other", "❓", False),
]


def seed_default_categories(db: Session, user_id: uuid.UUID) -> None:
    """Create this user's own private copy of the default category set."""
    for name, icon, is_income in DEFAULT_CATEGORIES:
        db.add(Category(
            id=uuid.uuid4(), user_id=user_id, name=name, icon=icon,
            is_income=is_income, is_system=True,
        ))
    db.commit()
