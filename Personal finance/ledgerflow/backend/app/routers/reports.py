"""
Reports router
==============
Endpoints:
  GET /reports/pnl      – Profit & Loss statement for a date range (JSON)
  GET /reports/pnl/pdf  – the same statement, rendered as a downloadable PDF
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.services.pdf_report import generate_pnl_pdf
from app.services.report_engine import get_pnl

router = APIRouter(prefix="/reports", tags=["Reports"])


def _validated_pnl(from_date: date, to_date: date, user: User, db: Session) -> dict:
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    return get_pnl(db, user.id, from_date, to_date)


@router.get("/pnl", summary="Profit & Loss statement for a date range")
def pnl_statement(
    from_date: date = Query(..., description="Start of the period, inclusive"),
    to_date:   date = Query(..., description="End of the period, inclusive"),
    user:      User = Depends(get_current_user),
    db:        Session = Depends(get_db),
):
    return _validated_pnl(from_date, to_date, user, db)


@router.get("/pnl/pdf", summary="Profit & Loss statement as a downloadable PDF")
def pnl_statement_pdf(
    from_date: date = Query(..., description="Start of the period, inclusive"),
    to_date:   date = Query(..., description="End of the period, inclusive"),
    user:      User = Depends(get_current_user),
    db:        Session = Depends(get_db),
):
    statement = _validated_pnl(from_date, to_date, user, db)
    pdf_bytes = generate_pnl_pdf(statement)
    filename = f"pnl_{from_date.isoformat()}_to_{to_date.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
