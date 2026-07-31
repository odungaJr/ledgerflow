"""
Budgets router
==============
Endpoints:
  POST  /budgets          – create a budget for a category
  GET   /budgets          – list all budgets with live spend status
  PATCH /budgets/{id}     – update limit or deactivate
  DELETE /budgets/{id}    – delete a budget
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Budget, Category, BudgetPeriod, User
from app.services.budget_engine import get_budget_status

router = APIRouter(prefix="/budgets", tags=["Budgets"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    category_name: str
    limit_amount:  float
    period:        str = "monthly"    # "monthly" | "weekly"
    start_date:    date


class BudgetPatch(BaseModel):
    limit_amount: float | None = None
    is_active:    bool | None  = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create a budget")
def create_budget(body: BudgetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.user_id == user.id, Category.name == body.category_name).first()
    if not cat:
        raise HTTPException(status_code=404, detail=f"Category '{body.category_name}' not found")

    if body.period not in BudgetPeriod._value2member_map_:
        raise HTTPException(status_code=422, detail="period must be 'monthly' or 'weekly'")

    budget = Budget(
        id           = uuid.uuid4(),
        user_id      = user.id,
        category_id  = cat.id,
        period       = BudgetPeriod(body.period),
        limit_amount = body.limit_amount,
        start_date   = body.start_date,
        is_active    = True,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)

    return {"id": str(budget.id), "category": body.category_name, "limit": body.limit_amount}


@router.get("", summary="List budgets with live spend status")
def list_budgets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_budget_status(db, user.id)


@router.patch("/{budget_id}", summary="Update a budget")
def update_budget(
    budget_id: str, body: BudgetPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    budget = db.query(Budget).filter(Budget.id == uuid.UUID(budget_id), Budget.user_id == user.id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    if body.limit_amount is not None:
        budget.limit_amount = body.limit_amount
    if body.is_active is not None:
        budget.is_active = body.is_active

    db.commit()
    return {"status": "updated", "id": budget_id}


@router.delete("/{budget_id}", summary="Delete a budget")
def delete_budget(budget_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    budget = db.query(Budget).filter(Budget.id == uuid.UUID(budget_id), Budget.user_id == user.id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()
    return {"status": "deleted", "id": budget_id}
