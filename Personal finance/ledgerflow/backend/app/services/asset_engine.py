"""
Asset Engine
============
Net-worth aggregation: current value per asset (from its latest value
snapshot), a breakdown by asset type, and a forward-filled combined
value trend across all assets' history.

Computed in Python rather than SQL — a personal portfolio's data volume
is trivial, so simple list scans are fine and keep the query layer thin.
"""
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.models import Asset, AssetValue


def get_assets_summary(db: Session, user_id: uuid.UUID) -> dict:
    assets = (
        db.query(Asset)
        .filter(Asset.user_id == user_id, Asset.is_active == True)
        .all()
    )

    total_value = Decimal(0)
    breakdown: dict[str, Decimal] = defaultdict(Decimal)
    asset_rows = []

    for asset in assets:
        values: list[AssetValue] = sorted(asset.values, key=lambda v: v.value_date)
        if not values:
            continue

        first, current = values[0], values[-1]
        change_amount = current.total_value - first.total_value
        change_pct = float(change_amount / first.total_value) if first.total_value else 0.0

        total_value += current.total_value
        breakdown[asset.asset_type.value] += current.total_value

        asset_rows.append({
            "id":            str(asset.id),
            "name":          asset.name,
            "asset_type":    asset.asset_type.value,
            "quantity":      float(asset.quantity) if asset.quantity is not None else None,
            "currency":      asset.currency,
            "current_value": float(current.total_value),
            "value_date":    current.value_date,
            "change_amount": float(change_amount),
            "change_pct":    round(change_pct, 4),
        })

    return {
        "total_value": float(total_value),
        "breakdown":   [{"asset_type": k, "total": float(v)} for k, v in sorted(breakdown.items())],
        "assets":      asset_rows,
        "trend":       _combined_trend(assets),
    }


def _combined_trend(assets: list[Asset]) -> list[dict]:
    """
    Forward-filled combined portfolio value over time: for every distinct
    value_date across all assets' history, sum each asset's most-recent
    value as of that date.
    """
    per_asset: dict = {}
    all_dates: set = set()
    for asset in assets:
        values = sorted(asset.values, key=lambda v: v.value_date)
        if not values:
            continue
        per_asset[asset.id] = values
        all_dates.update(v.value_date for v in values)

    trend = []
    for d in sorted(all_dates):
        total = Decimal(0)
        for values in per_asset.values():
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
