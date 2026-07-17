"""
Transactions router
===================
Endpoints:
  POST /transactions/import/csv   – upload a CSV bank statement
  POST /transactions/import/pdf   – upload a PDF bank statement
  GET  /transactions              – list transactions (filterable)
  GET  /transactions/{id}         – single transaction detail
  PATCH /transactions/{id}        – confirm/update category
  DELETE /transactions/{id}       – soft-delete (sets category to None)
"""
import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Category, Transaction
from app.services.importer import import_csv, import_pdf
from app.services.ai_engine import categorise_batch

router = APIRouter(prefix="/transactions", tags=["Transactions"])
logger = logging.getLogger(__name__)


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    id:            str
    account_id:    str
    date:          date
    description:   str
    amount:        float
    type:          str
    balance_after: Optional[float]
    category:      Optional[str]
    ai_confidence: Optional[float]
    is_confirmed:  bool
    notes:         Optional[str]

    class Config:
        from_attributes = True


class TransactionPatch(BaseModel):
    category_name: Optional[str] = None
    notes:         Optional[str] = None
    is_confirmed:  Optional[bool] = None


# ── Import helpers ─────────────────────────────────────────────────────────────

def _persist_transactions(raw_rows: list[dict], db: Session) -> tuple[int, int]:
    """
    Bulk-insert raw transaction rows, skipping duplicates.
    Returns (inserted_count, skipped_count).
    """
    inserted = skipped = 0
    for row in raw_rows:
        existing = db.query(Transaction).filter_by(fingerprint=row["fingerprint"]).first()
        if existing:
            skipped += 1
            continue

        txn = Transaction(
            id           = uuid.uuid4(),
            account_id   = uuid.UUID(row["account_id"]),
            date         = row["date"],
            description  = row["description"],
            amount       = row["amount"],
            type         = row["type"],
            balance_after= row["balance_after"],
            fingerprint  = row["fingerprint"],
        )
        try:
            # SAVEPOINT so a failed row only rolls back itself, not the whole batch.
            with db.begin_nested():
                db.add(txn)
        except IntegrityError:
            # Duplicate fingerprint within this same batch (or a concurrent import) — skip it.
            skipped += 1
            continue
        inserted += 1

    db.commit()
    return inserted, skipped


def _run_ai_categorisation(raw_rows: list[dict], db: Session) -> bool:
    """
    Call the AI engine and write category + confidence back to the DB.
    Skips transactions whose fingerprint was already in the DB (already categorised).

    Returns True if categorisation ran (or there was nothing to categorise),
    False if the AI service failed. The transactions themselves are already
    persisted by this point, so an AI failure here must not fail the request —
    it just means categorisation is left pending for the user to do manually.
    """
    # Fetch freshly inserted transactions using fingerprints
    fingerprints = [r["fingerprint"] for r in raw_rows]
    txns = db.query(Transaction).filter(Transaction.fingerprint.in_(fingerprints)).all()

    payload = [
        {"id": str(t.id), "description": t.description, "amount": str(t.amount), "type": t.type.value}
        for t in txns if t.category_id is None
    ]
    if not payload:
        return True

    try:
        suggestions = categorise_batch(payload)
    except Exception:
        logger.exception("AI categorisation failed; transactions remain uncategorised")
        return False

    # Build a name→id lookup for categories
    categories = {c.name: c for c in db.query(Category).all()}

    txn_map = {str(t.id): t for t in txns}
    for suggestion in suggestions:
        txn = txn_map.get(suggestion["transaction_id"])
        if txn is None:
            continue
        cat = categories.get(suggestion["category"]) or categories.get("Other")
        txn.category_id    = cat.id if cat else None
        txn.ai_category    = suggestion["category"]
        txn.ai_confidence  = suggestion["confidence"]
        txn.is_confirmed   = False

    db.commit()
    return True


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/import/csv", summary="Import transactions from a CSV bank statement")
async def import_csv_file(
    account_id: str = Form(...),
    file:       UploadFile = File(...),
    auto_categorise: bool = Form(True),
    db:         Session = Depends(get_db),
):
    contents = await file.read()
    try:
        rows = import_csv(contents, account_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    inserted, skipped = _persist_transactions(rows, db)
    categorised = _run_ai_categorisation(rows, db) if auto_categorise else False

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_parsed": len(rows),
        "categorised": categorised,
    }


@router.post("/import/pdf", summary="Import transactions from a PDF bank statement")
async def import_pdf_file(
    account_id: str = Form(...),
    file:       UploadFile = File(...),
    auto_categorise: bool = Form(True),
    db:         Session = Depends(get_db),
):
    contents = await file.read()
    rows = import_pdf(contents, account_id)
    if not rows:
        raise HTTPException(status_code=422, detail="No transactions could be extracted from this PDF.")

    inserted, skipped = _persist_transactions(rows, db)
    categorised = _run_ai_categorisation(rows, db) if auto_categorise else False

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_parsed": len(rows),
        "categorised": categorised,
    }


@router.get("", response_model=list[TransactionOut], summary="List transactions")
def list_transactions(
    account_id: Optional[str]  = Query(None),
    category:   Optional[str]  = Query(None),
    from_date:  Optional[date] = Query(None),
    to_date:    Optional[date] = Query(None),
    txn_type:   Optional[str]  = Query(None, description="debit | credit"),
    limit:      int = Query(100, le=500),
    offset:     int = Query(0),
    db:         Session = Depends(get_db),
):
    q = db.query(Transaction)
    if account_id:
        q = q.filter(Transaction.account_id == uuid.UUID(account_id))
    if category:
        cat = db.query(Category).filter(Category.name.ilike(f"%{category}%")).first()
        if cat:
            q = q.filter(Transaction.category_id == cat.id)
    if from_date:
        q = q.filter(Transaction.date >= from_date)
    if to_date:
        q = q.filter(Transaction.date <= to_date)
    if txn_type:
        q = q.filter(Transaction.type == txn_type)

    txns = q.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

    return [
        TransactionOut(
            id            = str(t.id),
            account_id    = str(t.account_id),
            date          = t.date,
            description   = t.description,
            amount        = float(t.amount),
            type          = t.type.value,
            balance_after = float(t.balance_after) if t.balance_after else None,
            category      = t.category.name if t.category else None,
            ai_confidence = float(t.ai_confidence) if t.ai_confidence else None,
            is_confirmed  = t.is_confirmed,
            notes         = t.notes,
        )
        for t in txns
    ]


@router.patch("/{txn_id}", summary="Confirm or update a transaction's category")
def patch_transaction(
    txn_id: str,
    body:   TransactionPatch,
    db:     Session = Depends(get_db),
):
    txn = db.query(Transaction).filter(Transaction.id == uuid.UUID(txn_id)).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if body.category_name is not None:
        cat = db.query(Category).filter(Category.name == body.category_name).first()
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category '{body.category_name}' not found")
        txn.category_id = cat.id

    if body.notes is not None:
        txn.notes = body.notes

    if body.is_confirmed is not None:
        txn.is_confirmed = body.is_confirmed

    db.commit()
    db.refresh(txn)
    return {"status": "updated", "id": txn_id}


@router.delete("/{txn_id}", summary="Remove a transaction")
def delete_transaction(txn_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == uuid.UUID(txn_id)).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(txn)
    db.commit()
    return {"status": "deleted", "id": txn_id}
