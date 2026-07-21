"""账户 API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import AccountCreate, AccountResponse
from crud import get_accounts, get_account_by_name, create_account

router = APIRouter(prefix="/api/accounts", tags=["账户"])


@router.get("", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    return get_accounts(db)


@router.post("", response_model=AccountResponse)
def add_account(data: AccountCreate, db: Session = Depends(get_db)):
    existing = get_account_by_name(db, data.name)
    if existing:
        raise HTTPException(status_code=400, detail="该账户已存在")
    return create_account(db, data)
