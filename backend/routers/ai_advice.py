"""AI 财务建议路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from crud import get_overview, get_category_stats, get_budget_status
from ai_service import get_financial_advice

router = APIRouter(prefix="/api/ai", tags=["AI 功能"])


@router.get("/advice")
def ai_advice(
    year: int = Query(..., ge=2024, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """毒舌财务点评 — 根据当月数据生成一针见血的分析"""
    overview = get_overview(db, year, month)
    category_stats = get_category_stats(db, year, month, "expense")
    budget_status = get_budget_status(db, year, month)
    return get_financial_advice(year, month, overview, category_stats, budget_status)
