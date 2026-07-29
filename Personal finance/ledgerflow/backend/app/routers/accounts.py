"""
Accounts router
===============
Endpoints:
  POST   /accounts          – create a bank account
  GET    /accounts          – list accounts (with computed current balance)
  GET    /accounts/{id}     – single account detail
  PATCH  /accounts/{id}     – update an account (including manual balance)
  DELETE /accounts/{id}     – delete an account (cascades to its transactions)
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Account
from app.services.account_engine import compute_balance

router = APIRouter(prefix="/accounts", tags=["Accounts"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name:     str
    bank:     str
    currency: str = "TZS"


class AccountPatch(BaseModel):
    name:                Optional[str]   = None
    bank:                Optional[str]   = None
    currency:            Optional[str]   = None
    is_active:           Optional[bool]  = None
    manual_balance:      Optional[float] = None
    manual_balance_date: Optional[date]  = None


def _serialise(account: Account) -> dict:
    balance = compute_balance(account)
    return {
        "id":                  str(account.id),
        "name":                account.name,
        "bank":                account.bank,
        "currency":            account.currency,
        "is_active":           account.is_active,
        "created_at":          account.created_at,
        "manual_balance":      float(account.manual_balance) if account.manual_balance is not None else None,
        "manual_balance_date": account.manual_balance_date,
        **balance,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Create a bank account")
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    account = Account(
        id       = uuid.uuid4(),
        name     = body.name,
        bank     = body.bank,
        currency = body.currency,
        is_active= True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _serialise(account)


@router.get("", summary="List accounts")
def list_accounts(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(Account)
    if not include_inactive:
        q = q.filter(Account.is_active == True)
    accounts = q.order_by(Account.created_at).all()
    return [_serialise(a) for a in accounts]


@router.get("/{account_id}", summary="Get a single account")
def get_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == uuid.UUID(account_id)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return _serialise(account)


@router.patch("/{account_id}", summary="Update an account")
def update_account(account_id: str, body: AccountPatch, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == uuid.UUID(account_id)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if body.name is not None:
        account.name = body.name
    if body.bank is not None:
        account.bank = body.bank
    if body.currency is not None:
        account.currency = body.currency
    if body.is_active is not None:
        account.is_active = body.is_active
    if body.manual_balance is not None:
        account.manual_balance = body.manual_balance
    if body.manual_balance_date is not None:
        account.manual_balance_date = body.manual_balance_date

    db.commit()
    db.refresh(account)
    return _serialise(account)


@router.delete("/{account_id}", summary="Delete an account (cascades to its transactions)")
def delete_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == uuid.UUID(account_id)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"status": "deleted", "id": account_id}
