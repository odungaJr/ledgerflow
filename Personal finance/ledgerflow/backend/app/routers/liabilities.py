"""
Liabilities router
===================
Endpoints:
  POST   /liabilities                – create a liability with its initial balance snapshot
  GET    /liabilities                – list active liabilities with current balance + change
  PATCH  /liabilities/{id}           – edit a liability's static fields (not its balance)
  POST   /liabilities/{id}/values    – add a new dated balance snapshot
  GET    /liabilities/{id}/history   – balance snapshot history for one liability
  DELETE /liabilities/{id}           – remove a liability (cascades its balance history)
  GET    /liabilities/summary        – total owed: total, breakdown by type, trend
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Liability, LiabilityType, LiabilityValue, User
from app.services.liability_engine import get_liabilities_summary

router = APIRouter(prefix="/liabilities", tags=["Liabilities"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class LiabilityCreate(BaseModel):
    name:             str
    liability_type:   str   # credit_card | loan | mortgage | personal_debt | other
    currency:         str = "TZS"
    value_date:       date
    total_value:      float
    notes:            Optional[str] = None


class LiabilityPatch(BaseModel):
    name:           Optional[str] = None
    liability_type: Optional[str] = None
    currency:       Optional[str] = None
    is_active:      Optional[bool] = None
    notes:          Optional[str] = None


class LiabilityValueCreate(BaseModel):
    value_date:  date
    total_value: float


def _serialise(liability: Liability) -> dict:
    values = sorted(liability.values, key=lambda v: v.value_date)
    current = values[-1] if values else None
    first = values[0] if values else None
    change_amount = (current.total_value - first.total_value) if current and first else None
    return {
        "id":             str(liability.id),
        "name":           liability.name,
        "liability_type": liability.liability_type.value,
        "currency":       liability.currency,
        "is_active":      liability.is_active,
        "notes":          liability.notes,
        "current_value":  float(current.total_value) if current else None,
        "value_date":     current.value_date if current else None,
        "change_amount":  float(change_amount) if change_amount is not None else None,
    }


def _get_owned_liability(liability_id: str, user_id: uuid.UUID, db: Session) -> Liability:
    liability = db.query(Liability).filter(
        Liability.id == uuid.UUID(liability_id), Liability.user_id == user_id,
    ).first()
    if not liability:
        raise HTTPException(status_code=404, detail="Liability not found")
    return liability


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create a liability with its initial balance")
def create_liability(body: LiabilityCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.liability_type not in LiabilityType._value2member_map_:
        raise HTTPException(status_code=422, detail=f"liability_type must be one of {list(LiabilityType._value2member_map_)}")

    liability = Liability(
        id             = uuid.uuid4(),
        user_id        = user.id,
        name           = body.name,
        liability_type = LiabilityType(body.liability_type),
        currency       = body.currency,
        notes          = body.notes,
    )
    db.add(liability)
    db.flush()

    db.add(LiabilityValue(
        id           = uuid.uuid4(),
        user_id      = liability.user_id,   # copied from the liability, not set independently
        liability_id = liability.id,
        value_date   = body.value_date,
        total_value  = body.total_value,
    ))
    db.commit()
    db.refresh(liability)

    return _serialise(liability)


@router.get("", summary="List active liabilities with current balance")
def list_liabilities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    liabilities = (
        db.query(Liability)
        .filter(Liability.user_id == user.id, Liability.is_active == True)
        .order_by(Liability.name)
        .all()
    )
    return [_serialise(l) for l in liabilities]


@router.patch("/{liability_id}", summary="Edit a liability's static fields")
def patch_liability(
    liability_id: str, body: LiabilityPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    liability = _get_owned_liability(liability_id, user.id, db)

    if body.name is not None:
        liability.name = body.name
    if body.liability_type is not None:
        if body.liability_type not in LiabilityType._value2member_map_:
            raise HTTPException(status_code=422, detail=f"liability_type must be one of {list(LiabilityType._value2member_map_)}")
        liability.liability_type = LiabilityType(body.liability_type)
    if body.currency is not None:
        liability.currency = body.currency
    if body.is_active is not None:
        liability.is_active = body.is_active
    if body.notes is not None:
        liability.notes = body.notes

    db.commit()
    db.refresh(liability)
    return _serialise(liability)


@router.post("/{liability_id}/values", status_code=201, summary="Add a new balance snapshot")
def add_liability_value(
    liability_id: str, body: LiabilityValueCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    liability = _get_owned_liability(liability_id, user.id, db)

    value = LiabilityValue(
        id           = uuid.uuid4(),
        user_id      = liability.user_id,   # copied from the liability, not set independently
        liability_id = liability.id,
        value_date   = body.value_date,
        total_value  = body.total_value,
    )
    db.add(value)
    db.commit()
    db.refresh(liability)
    return _serialise(liability)


@router.get("/{liability_id}/history", summary="Balance snapshot history for one liability")
def liability_history(liability_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    liability = _get_owned_liability(liability_id, user.id, db)

    values = sorted(liability.values, key=lambda v: v.value_date)
    return [
        {
            "id":          str(v.id),
            "value_date":  v.value_date,
            "total_value": float(v.total_value),
        }
        for v in values
    ]


@router.delete("/{liability_id}", summary="Delete a liability")
def delete_liability(liability_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    liability = _get_owned_liability(liability_id, user.id, db)
    db.delete(liability)
    db.commit()
    return {"status": "deleted", "id": liability_id}


@router.get("/summary", summary="Total owed: total balance, breakdown by type, trend")
def liabilities_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_liabilities_summary(db, user.id)
