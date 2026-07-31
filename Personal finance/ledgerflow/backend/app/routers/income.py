"""
Income router
=============
Endpoints:
  POST   /income                    – create an expected-income entry (optionally recurring)
  GET    /income                     – list income entries (optionally filtered by period)
  GET    /income/summary             – expected/received/pending totals for a period
  GET    /income/summary/all-time    – lifetime expected/received/pending totals
  PATCH  /income/{id}                – record a received amount / edit an entry
  DELETE /income/{id}                – remove a single occurrence
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Category, IncomeEntry, RecurrencePeriod, User
from app.services.income_engine import (
    entry_status,
    get_income_summary,
    get_income_summary_all_time,
    list_entries,
)

router = APIRouter(prefix="/income", tags=["Income"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class IncomeCreate(BaseModel):
    source:            str
    expected_amount:   float
    expected_date:     date
    category_name:     Optional[str] = None
    is_recurring:      bool = False
    recurrence_period: Optional[str] = None   # "monthly" | "weekly", required if is_recurring
    notes:             Optional[str] = None


class IncomePatch(BaseModel):
    received_amount: Optional[float] = None
    received_date:   Optional[date] = None
    expected_amount: Optional[float] = None
    expected_date:   Optional[date] = None
    notes:           Optional[str] = None


def _serialise(entry: IncomeEntry) -> dict:
    derived = entry_status(entry)
    return {
        "id":                str(entry.id),
        "series_id":         str(entry.series_id) if entry.series_id else None,
        "source":            entry.source,
        "category":          entry.category.name if entry.category else None,
        "expected_amount":   float(entry.expected_amount),
        "expected_date":     entry.expected_date,
        "received_amount":   float(entry.received_amount),
        "received_date":     entry.received_date,
        "is_recurring":      entry.is_recurring,
        "recurrence_period": entry.recurrence_period.value if entry.recurrence_period else None,
        "status":            derived["status"],
        "pending_amount":    float(derived["pending_amount"]),
        "notes":             entry.notes,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create an expected-income entry")
def create_income_entry(body: IncomeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.is_recurring:
        if not body.recurrence_period or body.recurrence_period not in RecurrencePeriod._value2member_map_:
            raise HTTPException(status_code=422, detail="recurrence_period must be 'monthly' or 'weekly' when is_recurring is true")

    category = None
    if body.category_name:
        category = db.query(Category).filter(Category.user_id == user.id, Category.name == body.category_name).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Category '{body.category_name}' not found")

    entry = IncomeEntry(
        id                = uuid.uuid4(),
        user_id           = user.id,
        category_id       = category.id if category else None,
        source            = body.source,
        expected_amount   = body.expected_amount,
        expected_date     = body.expected_date,
        received_amount   = 0,
        is_recurring      = body.is_recurring,
        recurrence_period = RecurrencePeriod(body.recurrence_period) if body.is_recurring else None,
        notes             = body.notes,
    )
    db.add(entry)
    db.flush()
    if body.is_recurring:
        entry.series_id = entry.id   # a recurring entry is the root of its own series
    db.commit()
    db.refresh(entry)

    return _serialise(entry)


@router.get("", summary="List income entries")
def get_income_entries(
    year:  Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    user:  User = Depends(get_current_user),
    db:    Session = Depends(get_db),
):
    entries = list_entries(db, user.id, year, month)
    return [_serialise(e) for e in entries]


@router.get("/summary", summary="Expected/received/pending totals for a period")
def income_summary(
    year:  int = Query(default=date.today().year),
    month: int = Query(default=date.today().month),
    user:  User = Depends(get_current_user),
    db:    Session = Depends(get_db),
):
    return get_income_summary(db, user.id, year, month)


@router.get("/summary/all-time", summary="Lifetime expected/received/pending totals")
def income_summary_all_time(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_income_summary_all_time(db, user.id)


@router.patch("/{entry_id}", summary="Record a received amount or edit an entry")
def patch_income_entry(
    entry_id: str, body: IncomePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    entry = db.query(IncomeEntry).filter(IncomeEntry.id == uuid.UUID(entry_id), IncomeEntry.user_id == user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Income entry not found")

    if body.received_amount is not None:
        entry.received_amount = body.received_amount
    if body.received_date is not None:
        entry.received_date = body.received_date
    if body.expected_amount is not None:
        entry.expected_amount = body.expected_amount
    if body.expected_date is not None:
        entry.expected_date = body.expected_date
    if body.notes is not None:
        entry.notes = body.notes

    db.commit()
    db.refresh(entry)
    return _serialise(entry)


@router.delete("/{entry_id}", summary="Delete a single income entry")
def delete_income_entry(entry_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.query(IncomeEntry).filter(IncomeEntry.id == uuid.UUID(entry_id), IncomeEntry.user_id == user.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Income entry not found")

    # Deleting the root of a recurring series would otherwise leave its
    # occurrences pointing at a series_id with nothing behind it (and a
    # dangling FK if any still exist) — delete the whole series instead.
    if entry.series_id == entry.id:
        db.query(IncomeEntry).filter(IncomeEntry.series_id == entry.id, IncomeEntry.user_id == user.id).delete()
    else:
        db.delete(entry)
    db.commit()
    return {"status": "deleted", "id": entry_id}
