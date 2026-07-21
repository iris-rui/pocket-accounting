"""统计 API 路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import OverviewStat
from crud import get_overview, get_category_stats, get_monthly_stats

router = APIRouter(prefix="/api/stats", tags=["统计"])


@router.get("/overview", response_model=OverviewStat)
def stats_overview(
    year: int = Query(..., ge=2024, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """月度收支概览"""
    return get_overview(db, year, month)


@router.get("/categories")
def stats_categories(
    year: int = Query(..., ge=2024, le=2100),
    month: int = Query(..., ge=1, le=12),
    type: str = Query(default="expense", pattern="^(income|expense)$"),
    db: Session = Depends(get_db),
):
    """分类统计（饼图数据）"""
    return get_category_stats(db, year, month, txn_type=type)


@router.get("/monthly")
def stats_monthly(
    year: int = Query(..., ge=2024, le=2100),
    db: Session = Depends(get_db),
):
    """月度趋势统计（折线图数据）"""
    return get_monthly_stats(db, year)
