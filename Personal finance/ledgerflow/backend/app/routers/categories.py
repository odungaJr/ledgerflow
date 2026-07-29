"""
Categories router
==================
Endpoints:
  GET    /categories      – list all spending/income categories
  POST   /categories      – create a custom category
  PATCH  /categories/{id} – rename/re-icon a category
  DELETE /categories/{id} – remove a custom (non-system) category
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import Budget, Category, Transaction

router = APIRouter(prefix="/categories", tags=["Categories"])


class CategoryOut(BaseModel):
    id:        str
    name:      str
    icon:      str
    is_income: bool
    is_system: bool

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name:      str
    icon:      str = "💳"
    is_income: bool = False


class CategoryPatch(BaseModel):
    name: str | None = None
    icon: str | None = None


def _to_out(c: Category) -> CategoryOut:
    return CategoryOut(id=str(c.id), name=c.name, icon=c.icon, is_income=c.is_income, is_system=c.is_system)


@router.get("", response_model=list[CategoryOut], summary="List categories")
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.name).all()
    return [_to_out(c) for c in categories]


@router.post("", response_model=CategoryOut, status_code=201, summary="Create a custom category")
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Category name is required")

    if db.query(Category).filter(Category.name == name).first():
        raise HTTPException(status_code=409, detail=f"A category named '{name}' already exists")

    category = Category(
        id        = uuid.uuid4(),
        name      = name,
        icon      = body.icon.strip() or "💳",
        is_income = body.is_income,
        is_system = False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.patch("/{category_id}", response_model=CategoryOut, summary="Rename or re-icon a category")
def patch_category(category_id: str, body: CategoryPatch, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == uuid.UUID(category_id)).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Category name is required")
        if db.query(Category).filter(Category.name == name, Category.id != category.id).first():
            raise HTTPException(status_code=409, detail=f"A category named '{name}' already exists")
        category.name = name

    if body.icon is not None:
        category.icon = body.icon.strip() or category.icon

    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.delete("/{category_id}", summary="Remove a custom category")
def delete_category(category_id: str, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == uuid.UUID(category_id)).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.is_system:
        raise HTTPException(status_code=409, detail="Built-in categories can't be deleted")

    in_use = (
        db.query(Transaction).filter(Transaction.category_id == category.id).first()
        or db.query(Budget).filter(Budget.category_id == category.id).first()
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="This category is still used by transactions or budgets — reassign them first",
        )

    db.delete(category)
    db.commit()
    return {"status": "deleted", "id": category_id}
