"""分类 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import CategoryCreate, CategoryResponse
from crud import get_categories, get_category_by_name, create_category

router = APIRouter(prefix="/api/categories", tags=["分类"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    type: str = Query(default=None, pattern="^(income|expense)$", description="筛选类型"),
    db: Session = Depends(get_db),
):
    return get_categories(db, category_type=type)


@router.post("", response_model=CategoryResponse)
def add_category(data: CategoryCreate, db: Session = Depends(get_db)):
    existing = get_category_by_name(db, data.name, data.type)
    if existing:
        raise HTTPException(status_code=400, detail="该分类已存在")
    return create_category(db, data)
