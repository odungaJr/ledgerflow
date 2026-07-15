"""
Accounts router
===============
Endpoints:
  POST   /accounts          – create a bank account
  GET    /accounts          – list accounts
  GET    /accounts/{id}     – single account detail
  PATCH  /accounts/{id}     – update an account
  DELETE /accounts/{id}     – delete an account (cascades to its transactions)
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Account

router = APIRouter(prefix="/accounts", tags=["Accounts"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name:     str
    bank:     str
    currency: str = "TZS"


class AccountPatch(BaseModel):
    name:       Optional[str]  = None
    bank:       Optional[str]  = None
    currency:   Optional[str]  = None
    is_active:  Optional[bool] = None


class AccountOut(BaseModel):
    id:         uuid.UUID
    name:       str
    bank:       str
    currency:   str
    is_active:  bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=AccountOut, summary="Create a bank account")
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
    return account


@router.get("", response_model=list[AccountOut], summary="List accounts")
def list_accounts(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(Account)
    if not include_inactive:
        q = q.filter(Account.is_active == True)
    return q.order_by(Account.created_at).all()


@router.get("/{account_id}", response_model=AccountOut, summary="Get a single account")
def get_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == uuid.UUID(account_id)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountOut, summary="Update an account")
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

    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", summary="Delete an account (cascades to its transactions)")
def delete_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == uuid.UUID(account_id)).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"status": "deleted", "id": account_id}
