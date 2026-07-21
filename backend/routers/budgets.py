"""预算 API 路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import BudgetCreate, BudgetResponse, BudgetStatus
from crud import create_budget, get_budgets, get_budget_status

router = APIRouter(prefix="/api/budgets", tags=["预算"])


@router.post("", response_model=BudgetResponse)
def set_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    """设置月度预算"""
    return create_budget(db, data)


@router.get("", response_model=list[BudgetResponse])
def list_budgets(
    year: int = Query(..., ge=2024, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    return get_budgets(db, year, month)


@router.get("/status", response_model=list[BudgetStatus])
def check_budget_status(
    year: int = Query(..., ge=2024, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """获取预算执行状态（含超支/预警判断）"""
    return get_budget_status(db, year, month)
