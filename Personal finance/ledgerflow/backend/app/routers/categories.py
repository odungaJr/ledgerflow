"""
Categories router
==================
Endpoints:
  GET /categories – list all spending/income categories
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Category

router = APIRouter(prefix="/categories", tags=["Categories"])


class CategoryOut(BaseModel):
    id:        str
    name:      str
    icon:      str
    is_income: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[CategoryOut], summary="List categories")
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.name).all()
    return [
        CategoryOut(id=str(c.id), name=c.name, icon=c.icon, is_income=c.is_income)
        for c in categories
    ]
