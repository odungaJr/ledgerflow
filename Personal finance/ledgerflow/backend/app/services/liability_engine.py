"""
Liability Engine
================
Mirrors asset_engine.py's shape for debts: current balance per liability
(from its latest value snapshot), a breakdown by liability type, a
forward-filled combined balance trend, and a combined net-worth trend
(assets minus liabilities) for the Dashboard.
"""
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.models import Asset, Liability, LiabilityValue


def get_liabilities_summary(db: Session, user_id: uuid.UUID) -> dict:
    liabilities = (
        db.query(Liability)
        .filter(Liability.user_id == user_id, Liability.is_active == True)
        .all()
    )

    total_value = Decimal(0)
    breakdown: dict[str, Decimal] = defaultdict(Decimal)
    liability_rows = []

    for liability in liabilities:
        values: list[LiabilityValue] = sorted(liability.values, key=lambda v: v.value_date)
        if not values:
            continue

        first, current = values[0], values[-1]
        change_amount = current.total_value - first.total_value
        change_pct = float(change_amount / first.total_value) if first.total_value else 0.0

        total_value += current.total_value
        breakdown[liability.liability_type.value] += current.total_value

        liability_rows.append({
            "id":             str(liability.id),
            "name":           liability.name,
            "liability_type": liability.liability_type.value,
            "currency":       liability.currency,
            "current_value":  float(current.total_value),
            "value_date":     current.value_date,
            "change_amount":  float(change_amount),
            "change_pct":     round(change_pct, 4),
        })

    return {
        "total_value": float(total_value),
        "breakdown":   [{"liability_type": k, "total": float(v)} for k, v in sorted(breakdown.items())],
        "liabilities": liability_rows,
        "trend":       _combined_trend(liabilities),
    }


def _combined_trend(liabilities: list[Liability]) -> list[dict]:
    """Forward-filled combined balance owed over time (see asset_engine._combined_trend)."""
    per_liability: dict = {}
    all_dates: set = set()
    for liability in liabilities:
        values = sorted(liability.values, key=lambda v: v.value_date)
        if not values:
            continue
        per_liability[liability.id] = values
        all_dates.update(v.value_date for v in values)

    trend = []
    for d in sorted(all_dates):
        total = Decimal(0)
        for values in per_liability.values():
            latest = None
            for v in values:
                if v.value_date <= d:
                    latest = v
                else:
                    break
            if latest is not None:
                total += latest.total_value
        trend.append({"date": str(d), "total_value": float(total)})
    return trend


def _latest_as_of(values: list, d) -> object | None:
    latest = None
    for v in values:
        if v.value_date <= d:
            latest = v
        else:
            break
    return latest


def get_net_worth_trend(db: Session, user_id: uuid.UUID) -> list[dict]:
    """
    Combined net-worth trend: for every distinct value_date across both
    assets' and liabilities' history, sum each asset's most-recent value
    minus each liability's most-recent balance as of that date.
    """
    assets = db.query(Asset).filter(Asset.user_id == user_id, Asset.is_active == True).all()
    liabilities = db.query(Liability).filter(Liability.user_id == user_id, Liability.is_active == True).all()

    asset_series: dict = {}
    liability_series: dict = {}
    all_dates: set = set()

    for asset in assets:
        values = sorted(asset.values, key=lambda v: v.value_date)
        if values:
            asset_series[asset.id] = values
            all_dates.update(v.value_date for v in values)

    for liability in liabilities:
        values = sorted(liability.values, key=lambda v: v.value_date)
        if values:
            liability_series[liability.id] = values
            all_dates.update(v.value_date for v in values)

    trend = []
    for d in sorted(all_dates):
        total_assets = Decimal(0)
        for values in asset_series.values():
            latest = _latest_as_of(values, d)
            if latest is not None:
                total_assets += latest.total_value

        total_liabilities = Decimal(0)
        for values in liability_series.values():
            latest = _latest_as_of(values, d)
            if latest is not None:
                total_liabilities += latest.total_value

        trend.append({"date": str(d), "net_worth": float(total_assets - total_liabilities)})
    return trend
