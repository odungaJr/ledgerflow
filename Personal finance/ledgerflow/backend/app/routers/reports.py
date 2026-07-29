"""
Reports router
==============
Endpoints:
  GET /reports/pnl – Profit & Loss statement for a date range
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.report_engine import get_pnl

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/pnl", summary="Profit & Loss statement for a date range")
def pnl_statement(
    from_date: date = Query(..., description="Start of the period, inclusive"),
    to_date:   date = Query(..., description="End of the period, inclusive"),
    db:        Session = Depends(get_db),
):
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    return get_pnl(db, from_date, to_date)
