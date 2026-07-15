"""
Core ORM models for LedgerFlow.

Tables:
  accounts     – bank accounts the user tracks
  categories   – spending/income categories (seeded + user-defined)
  transactions – individual financial transactions
  budgets      – monthly spending caps per category
"""
import uuid
from datetime import date, datetime
from sqlalchemy import (
    Column, String, Numeric, Date, DateTime,
    Boolean, ForeignKey, Text, Enum as SAEnum
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


# ── Accounts ───────────────────────────────────────────────────────────────────

class Account(Base):
    __tablename__ = "accounts"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(120), nullable=False)          # e.g. "KCB Salary Account"
    bank       = Column(String(120), nullable=False)          # e.g. "KCB"
    currency   = Column(String(10), default="TZS")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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
