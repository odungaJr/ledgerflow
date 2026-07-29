"""
Report Engine
=============
Builds a Profit & Loss statement (income vs. expenses, by category) for an
arbitrary date range, from imported/confirmed transactions.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Category, Transaction


def _breakdown(db: Session, txn_type: str, from_date: date, to_date: date) -> list[dict]:
    rows = (
        db.query(
            func.coalesce(Category.name, "Uncategorised").label("name"),
            func.coalesce(Category.icon, "❓").label("icon"),
            func.sum(Transaction.amount).label("total"),
        )
        .select_from(Transaction)
        .outerjoin(Category, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == txn_type,
            Transaction.date >= from_date,
            Transaction.date <= to_date,
        )
        .group_by(Category.name, Category.icon)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    return [{"name": r.name, "icon": r.icon, "total": float(r.total)} for r in rows]


def get_pnl(db: Session, from_date: date, to_date: date) -> dict:
    """Profit & Loss statement for [from_date, to_date] (inclusive)."""
    income = _breakdown(db, "credit", from_date, to_date)
    expenses = _breakdown(db, "debit", from_date, to_date)

    total_income = Decimal(str(sum(r["total"] for r in income))) if income else Decimal(0)
    total_expenses = Decimal(str(sum(r["total"] for r in expenses))) if expenses else Decimal(0)

    return {
        "from_date":       from_date.isoformat(),
        "to_date":         to_date.isoformat(),
        "currency":        "TZS",
        "income":          income,
        "expenses":        expenses,
        "total_income":    float(total_income),
        "total_expenses":  float(total_expenses),
        "net_income":      float(total_income - total_expenses),
    }
