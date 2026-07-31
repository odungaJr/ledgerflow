"""
Dashboard router
================
Endpoints:
  GET /dashboard/summary          – monthly income/expense/net + budget alerts
  GET /dashboard/insights         – AI-generated financial health report
  GET /dashboard/categories       – spending breakdown per category
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.budget_engine import get_budget_status, get_monthly_summary, get_monthly_trend
from app.services.ai_engine import generate_insights, detect_anomalies
from app.services.income_engine import get_income_summary, get_income_summary_all_time
from app.services.asset_engine import get_assets_summary
from app.services.liability_engine import get_liabilities_summary, get_net_worth_trend
from app.models.models import Transaction, User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", summary="Monthly financial summary with budget alerts")
def monthly_summary(
    year:  int = Query(default=date.today().year),
    month: int = Query(default=date.today().month),
    user:  User = Depends(get_current_user),
    db:    Session = Depends(get_db),
):
    summary = get_monthly_summary(db, user.id, year, month)
    budget_status = get_budget_status(db, user.id)

    alerts = [b for b in budget_status if b["is_breached"] or b["is_warning"]]

    assets_summary = get_assets_summary(db, user.id)
    liabilities_summary = get_liabilities_summary(db, user.id)

    return {
        "summary":         summary,
        "budget_alerts":   alerts,
        "income_tracker":  get_income_summary(db, user.id, year, month),
        "income_all_time": get_income_summary_all_time(db, user.id),
        "assets":          assets_summary,
        "liabilities":     liabilities_summary,
        "net_worth": {
            "total": assets_summary["total_value"] - liabilities_summary["total_value"],
            "trend": get_net_worth_trend(db, user.id),
        },
        "monthly_trend": get_monthly_trend(db, user.id, year, month),
    }


@router.get("/insights", summary="AI-generated financial insights for the month")
def monthly_insights(
    year:  int = Query(default=date.today().year),
    month: int = Query(default=date.today().month),
    user:  User = Depends(get_current_user),
    db:    Session = Depends(get_db),
):
    summary = get_monthly_summary(db, user.id, year, month)

    # Fetch this month's transactions for anomaly detection
    start = date(year, month, 1)
    end   = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id, Transaction.date >= start, Transaction.date < end)
        .order_by(Transaction.date)
        .all()
    )
    txn_dicts = [
        {"date": str(t.date), "description": t.description,
         "type": t.type.value, "amount": str(t.amount)}
        for t in txns
    ]

    anomalies = detect_anomalies(txn_dicts)
    summary["anomalies"] = anomalies

    narrative = generate_insights(summary)

    return {
        "period":    summary["period"],
        "summary":   summary,
        "anomalies": anomalies,
        "narrative": narrative,
    }


@router.get("/categories", summary="Spending breakdown by category for the month")
def category_breakdown(
    year:  int = Query(default=date.today().year),
    month: int = Query(default=date.today().month),
    user:  User = Depends(get_current_user),
    db:    Session = Depends(get_db),
):
    summary = get_monthly_summary(db, user.id, year, month)
    return {
        "period":     summary["period"],
        "categories": summary["top_categories"],
    }
