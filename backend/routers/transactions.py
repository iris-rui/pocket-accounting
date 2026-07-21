"""交易 API 路由"""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import TransactionCreate, TransactionResponse, MessageResponse
from crud import (
    create_transaction,
    get_transactions,
    get_transaction,
    delete_transaction,
)

router = APIRouter(prefix="/api/transactions", tags=["交易"])


@router.post("", response_model=TransactionResponse)
def add_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    """手动添加一笔交易"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于 0")
    if data.amount > Decimal("9999999999.99"):
        raise HTTPException(status_code=400, detail="金额不能超过 99 亿")
    return create_transaction(db, data)


@router.get("")
def list_transactions(
    year: int = Query(default=None, ge=2024, le=2100),
    month: int = Query(default=None, ge=1, le=12),
    week: str = Query(default=None, description="周起始日期 YYYY-MM-DD"),
    category_id: int = Query(default=None),
    type: str = Query(default=None, pattern="^(income|expense)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取交易流水列表，支持按月/周筛选"""
    week_start, week_end = None, None
    if week:
        try:
            week_start = date.fromisoformat(week)
            week_end = week_start + timedelta(days=6)
        except ValueError:
            raise HTTPException(status_code=400, detail="周日期格式错误，应为 YYYY-MM-DD")

    return get_transactions(
        db, year=year, month=month,
        week_start=week_start, week_end=week_end,
        category_id=category_id, txn_type=type,
        page=page, page_size=page_size,
    )


@router.get("/{txn_id}", response_model=TransactionResponse)
def get_one_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = get_transaction(db, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="交易不存在")
    return txn


@router.delete("/{txn_id}", response_model=MessageResponse)
def remove_transaction(txn_id: int, db: Session = Depends(get_db)):
    ok = delete_transaction(db, txn_id)
    if not ok:
        raise HTTPException(status_code=404, detail="交易不存在")
    return {"message": "删除成功", "success": True}
