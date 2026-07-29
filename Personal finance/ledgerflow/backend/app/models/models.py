"""
Core ORM models for LedgerFlow.

Tables:
  users          – app-level login accounts
  sessions       – active login sessions (opaque token, hashed at rest)
  accounts       – bank accounts the user tracks
  categories     – spending/income categories (seeded + user-defined)
  transactions   – individual financial transactions
  budgets        – monthly spending caps per category
  income_entries – manually tracked expected/received income
  assets         – things the user owns (shares, bonds, etc.)
  asset_values   – dated value snapshots per asset
"""
import uuid
from datetime import date, datetime
from sqlalchemy import (
    Column, String, Numeric, Date, DateTime,
    Boolean, ForeignKey, Text, Integer, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class TransactionType(str, enum.Enum):
    debit  = "debit"    # money leaving the account
    credit = "credit"   # money entering the account


class BudgetPeriod(str, enum.Enum):
    monthly = "monthly"
    weekly  = "weekly"


class RecurrencePeriod(str, enum.Enum):
    monthly = "monthly"
    weekly  = "weekly"


class AssetType(str, enum.Enum):
    cash        = "cash"
    stocks      = "stocks"
    bonds       = "bonds"
    real_estate = "real_estate"
    vehicle     = "vehicle"
    other       = "other"


# ── Auth ───────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username      = Column(String(80), nullable=False, unique=True)
    password_hash = Column(String(120), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # Login lockout — see core/auth.py for the attempt/lockout thresholds.
    failed_login_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    locked_until           = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)   # sha256 hex digest
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Bumped on every authenticated request — used to enforce the idle
    # timeout independently of the long-lived absolute `expires_at`.
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="sessions")


# ── Accounts ───────────────────────────────────────────────────────────────────

class Account(Base):
    __tablename__ = "accounts"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(120), nullable=False)          # e.g. "KCB Salary Account"
    bank       = Column(String(120), nullable=False)          # e.g. "KCB"
    currency   = Column(String(10), default="TZS")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # User-entered "known balance as of X" — used when there's no imported
    # transaction history (or it's stale) to derive a balance from. See
    # account_engine.compute_balance for how this competes with the latest
    # transaction's balance_after.
    manual_balance      = Column(Numeric(18, 2), nullable=True)
    manual_balance_date = Column(Date, nullable=True)

    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")


# ── Categories ─────────────────────────────────────────────────────────────────

class Category(Base):
    __tablename__ = "categories"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(String(80), nullable=False, unique=True)   # e.g. "Food & Dining"
    icon        = Column(String(10), default="💳")                  # emoji shorthand
    is_income   = Column(Boolean, default=False)                    # True for salary/transfers in
    is_system   = Column(Boolean, default=True)                     # False = user-created

    transactions = relationship("Transaction", back_populates="category")
    budgets      = relationship("Budget", back_populates="category", cascade="all, delete-orphan")


# ── Transactions ───────────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id      = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    category_id     = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)

    date            = Column(Date, nullable=False)
    description     = Column(String(300), nullable=False)    # raw bank description
    amount          = Column(Numeric(18, 2), nullable=False) # always positive
    type            = Column(SAEnum(TransactionType), nullable=False)
    balance_after   = Column(Numeric(18, 2), nullable=True)  # running balance if available

    # AI-assisted fields
    ai_category     = Column(String(80), nullable=True)      # raw AI suggestion before user confirms
    ai_confidence   = Column(Numeric(4, 3), nullable=True)   # 0.000 – 1.000
    is_confirmed    = Column(Boolean, default=False)         # user confirmed the category

    # Deduplication hash (date + description + amount)
    fingerprint     = Column(String(64), nullable=False, unique=True)

    notes           = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    account  = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")


# ── Budgets ────────────────────────────────────────────────────────────────────

class Budget(Base):
    __tablename__ = "budgets"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    period      = Column(SAEnum(BudgetPeriod), default=BudgetPeriod.monthly)
    limit_amount= Column(Numeric(18, 2), nullable=False)
    start_date  = Column(Date, nullable=False)              # budget active from this date
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category", back_populates="budgets")


# ── Income entries ─────────────────────────────────────────────────────────────

class IncomeEntry(Base):
    __tablename__ = "income_entries"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id   = Column(UUID(as_uuid=True), ForeignKey("income_entries.id"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)

    source          = Column(String(120), nullable=False)   # e.g. "Salary — Company X"
    expected_amount = Column(Numeric(18, 2), nullable=False)
    expected_date   = Column(Date, nullable=False)
    received_amount = Column(Numeric(18, 2), default=0, nullable=False)
    received_date   = Column(Date, nullable=True)

    is_recurring       = Column(Boolean, default=False)
    recurrence_period  = Column(SAEnum(RecurrencePeriod), nullable=True)

    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category")


# ── Assets ─────────────────────────────────────────────────────────────────────

class Asset(Base):
    __tablename__ = "assets"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(120), nullable=False)          # e.g. "CRDB Bank shares"
    asset_type = Column(SAEnum(AssetType), nullable=False)
    quantity   = Column(Numeric(18, 4), nullable=True)         # e.g. share count
    currency   = Column(String(10), default="TZS")
    is_active  = Column(Boolean, default=True)                 # False = disposed of
    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    values = relationship(
        "AssetValue", back_populates="asset",
        cascade="all, delete-orphan", order_by="AssetValue.value_date",
    )


class AssetValue(Base):
    __tablename__ = "asset_values"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id   = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    value_date = Column(Date, nullable=False)
    unit_value = Column(Numeric(18, 4), nullable=True)         # optional price per unit
    total_value= Column(Numeric(18, 2), nullable=False)        # source of truth for aggregation
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    asset = relationship("Asset", back_populates="values")
