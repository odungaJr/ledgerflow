"""
Assets router
=============
Endpoints:
  POST   /assets                – create an asset with its initial value snapshot
  GET    /assets                – list active assets with current value + change
  PATCH  /assets/{id}           – edit an asset's static fields (not its value)
  POST   /assets/{id}/values    – add a new dated value snapshot
  GET    /assets/{id}/history   – value snapshot history for one asset
  DELETE /assets/{id}           – remove an asset (cascades its value history)
  GET    /assets/summary        – net worth: total, breakdown by type, trend
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Asset, AssetType, AssetValue
from app.services.asset_engine import get_assets_summary

router = APIRouter(prefix="/assets", tags=["Assets"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AssetCreate(BaseModel):
    name:             str
    asset_type:       str   # cash | stocks | bonds | real_estate | vehicle | other
    quantity:         Optional[float] = None
    currency:         str = "TZS"
    value_date:       date
    total_value:      float
    unit_value:       Optional[float] = None
    notes:            Optional[str] = None


class AssetPatch(BaseModel):
    name:       Optional[str] = None
    asset_type: Optional[str] = None
    quantity:   Optional[float] = None
    currency:   Optional[str] = None
    is_active:  Optional[bool] = None
    notes:      Optional[str] = None


class AssetValueCreate(BaseModel):
    value_date:  date
    total_value: float
    unit_value:  Optional[float] = None


def _serialise(asset: Asset) -> dict:
    values = sorted(asset.values, key=lambda v: v.value_date)
    current = values[-1] if values else None
    first = values[0] if values else None
    change_amount = (current.total_value - first.total_value) if current and first else None
    return {
        "id":            str(asset.id),
        "name":          asset.name,
        "asset_type":    asset.asset_type.value,
        "quantity":      float(asset.quantity) if asset.quantity is not None else None,
        "currency":      asset.currency,
        "is_active":     asset.is_active,
        "notes":         asset.notes,
        "current_value": float(current.total_value) if current else None,
        "value_date":    current.value_date if current else None,
        "change_amount": float(change_amount) if change_amount is not None else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create an asset with its initial value")
def create_asset(body: AssetCreate, db: Session = Depends(get_db)):
    if body.asset_type not in AssetType._value2member_map_:
        raise HTTPException(status_code=422, detail=f"asset_type must be one of {list(AssetType._value2member_map_)}")

    asset = Asset(
        id         = uuid.uuid4(),
        name       = body.name,
        asset_type = AssetType(body.asset_type),
        quantity   = body.quantity,
        currency   = body.currency,
        notes      = body.notes,
    )
    db.add(asset)
    db.flush()

    db.add(AssetValue(
        id          = uuid.uuid4(),
        asset_id    = asset.id,
        value_date  = body.value_date,
        unit_value  = body.unit_value,
        total_value = body.total_value,
    ))
    db.commit()
    db.refresh(asset)

    return _serialise(asset)


@router.get("", summary="List active assets with current value")
def list_assets(db: Session = Depends(get_db)):
    assets = db.query(Asset).filter(Asset.is_active == True).order_by(Asset.name).all()
    return [_serialise(a) for a in assets]


@router.patch("/{asset_id}", summary="Edit an asset's static fields")
def patch_asset(asset_id: str, body: AssetPatch, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if body.name is not None:
        asset.name = body.name
    if body.asset_type is not None:
        if body.asset_type not in AssetType._value2member_map_:
            raise HTTPException(status_code=422, detail=f"asset_type must be one of {list(AssetType._value2member_map_)}")
        asset.asset_type = AssetType(body.asset_type)
    if body.quantity is not None:
        asset.quantity = body.quantity
    if body.currency is not None:
        asset.currency = body.currency
    if body.is_active is not None:
        asset.is_active = body.is_active
    if body.notes is not None:
        asset.notes = body.notes

    db.commit()
    db.refresh(asset)
    return _serialise(asset)


@router.post("/{asset_id}/values", status_code=201, summary="Add a new value snapshot")
def add_asset_value(asset_id: str, body: AssetValueCreate, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    value = AssetValue(
        id          = uuid.uuid4(),
        asset_id    = asset.id,
        value_date  = body.value_date,
        unit_value  = body.unit_value,
        total_value = body.total_value,
    )
    db.add(value)
    db.commit()
    db.refresh(asset)
    return _serialise(asset)


@router.get("/{asset_id}/history", summary="Value snapshot history for one asset")
def asset_history(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    values = sorted(asset.values, key=lambda v: v.value_date)
    return [
        {
            "id":          str(v.id),
            "value_date":  v.value_date,
            "unit_value":  float(v.unit_value) if v.unit_value is not None else None,
            "total_value": float(v.total_value),
        }
        for v in values
    ]


@router.delete("/{asset_id}", summary="Delete an asset")
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == uuid.UUID(asset_id)).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(asset)
    db.commit()
    return {"status": "deleted", "id": asset_id}


@router.get("/summary", summary="Net worth: total value, breakdown by type, trend")
def assets_summary(db: Session = Depends(get_db)):
    return get_assets_summary(db)
