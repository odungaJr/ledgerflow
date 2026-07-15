"""
Budget Engine
=============
Calculates how much of each budget has been spent in the current
period and whether any limits have been breached or are close (>80%).
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.models import Budget, Transaction, Category, BudgetPeriod


def _period_start(period: BudgetPeriod, ref: date) -> date:
    """Return the start of the current period relative to `ref`."""
    if period == BudgetPeriod.monthly:
        return ref.replace(day=1)
    # Weekly: go back to Monday
    return ref - __import__("datetime").timedelta(days=ref.weekday())


def get_budget_status(db: Session, ref_date: date | None = None) -> list[dict]:
    """
    Return a list of budget status objects for all active budgets.

    Each object:
      {
        budget_id, category_name, limit, spent, remaining,
        pct_used, is_breached, is_warning
      }
    """
    if ref_date is None:
        ref_date = date.today()

    active_budgets = (
        db.query(Budget)
        .filter(Budget.is_active == True, Budget.start_date <= ref_date)
        .all()
    )

    statuses = []
    for budget in active_budgets:
        period_start = _period_start(budget.period, ref_date)

        # Sum transactions in this category for the current period
        spent = (
            db.query(func.sum(Transaction.amount))
            .join(Category, Transaction.category_id == Category.id)
            .filter(
                Transaction.category_id == budget.category_id,
                Transaction.type == "debit",
                Transaction.date >= period_start,
                Transaction.date <= ref_date,
            )
            .scalar()
        ) or Decimal(0)

        limit      = Decimal(str(budget.limit_amount))
        remaining  = limit - spent
        pct_used   = float(spent / limit) if limit > 0 else 0.0

        statuses.append({
            "budget_id":     str(budget.id),
            "category_name": budget.category.name,
            "period":        budget.period.value,
            "limit":         float(limit),
            "spent":         float(spent),
            "remaining":     float(remaining),
            "pct_used":      round(pct_used, 4),
            "is_breached":   pct_used > 1.0,
            "is_warning":    0.8 <= pct_used <= 1.0,
        })

    return statuses


def get_monthly_summary(db: Session, year: int, month: int) -> dict:
    """
    Aggregate income and expenses for a given month.
    Returns data suitable for generate_insights().
    """
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    # Total income
    total_income = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.type == "credit", Transaction.date >= start, Transaction.date < end)
        .scalar()
    ) or Decimal(0)

    # Total expenses
    total_expenses = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.type == "debit", Transaction.date >= start, Transaction.date < end)
        .scalar()
    ) or Decimal(0)

    # Expenses per category
    category_rows = (
        db.query(Category.name, func.sum(Transaction.amount).label("total"))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(Transaction.type == "debit", Transaction.date >= start, Transaction.date < end)
        .group_by(Category.name)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(8)
        .all()
    )

    # Merge budget limits into category data
    budget_status = {b["category_name"]: b["limit"] for b in get_budget_status(db, end - __import__("datetime").timedelta(days=1))}

    top_categories = [
        {
            "name":         row.name,
            "total":        float(row.total),
            "budget_limit": budget_status.get(row.name),
        }
        for row in category_rows
    ]

    return {
        "period":         f"{start.strftime('%B %Y')}",
        "total_income":   float(total_income),
        "total_expenses": float(total_expenses),
        "net":            float(total_income - total_expenses),
        "currency":       "TZS",
        "top_categories": top_categories,
        "anomalies":      [],   # caller can enrich this from detect_anomalies()
    }
