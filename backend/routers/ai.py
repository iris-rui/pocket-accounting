"""AI 记账 API 路由 — 一句话记账"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Category
from schemas import (
    AIParseRequest,
    TransactionCreate,
    TransactionResponse,
    CategoryCreate,
)
from crud import (
    get_category_by_name,
    get_account_by_name,
    create_category,
    create_transaction,
)
from ai_service import parse_accounting_text
from security import sanitize_input, sanitize_note
from seed import resolve_category_and_account

router = APIRouter(prefix="/api/ai", tags=["AI 功能"])


@router.post("/parse")
def ai_parse_text(data: AIParseRequest, db: Session = Depends(get_db)):
    """
    AI 一句话记账 — 自然语言 → 结构化账单字段。
    容错：AI API 不可用时自动降级为本地规则解析。
    """
    text = sanitize_input(data.text.strip(), max_length=200)
    if not text:
        raise HTTPException(status_code=400, detail="请输入内容")

    parsed = parse_accounting_text(text)
    category, account = resolve_category_and_account(db, parsed)

    return {
        "type": parsed["type"],
        "amount": parsed["amount"],
        "category_name": category.name if category else parsed["category_name"],
        "account_name": account.name if account else parsed["account_name"],
        "transaction_date": parsed["transaction_date"],
        "note": sanitize_note(parsed.get("note", "")),
        "confidence": parsed.get("confidence", 0),
        "raw_text": text,
    }


@router.post("/parse-and-save", response_model=TransactionResponse)
def ai_parse_and_save(data: AIParseRequest, db: Session = Depends(get_db)):
    """AI 一句记账 + 自动保存"""
    text = sanitize_input(data.text.strip(), max_length=200)
    if not text:
        raise HTTPException(status_code=400, detail="请输入内容")

    parsed = parse_accounting_text(text)

    cat_type = parsed["type"]
    category = get_category_by_name(db, parsed["category_name"], cat_type)
    if not category:
        icon = "💰" if cat_type == "income" else "📌"
        category = create_category(db, CategoryCreate(
            name=parsed["category_name"], icon=icon, type=cat_type,
        ))

    account = get_account_by_name(db, parsed["account_name"])
    if not account:
        account = get_account_by_name(db, "微信")

    assert category is not None, "分类创建失败"
    assert account is not None, "账户未找到"

    txn_data = TransactionCreate(
        type=parsed["type"],
        amount=parsed["amount"],
        category_id=category.id,  # type: ignore
        account_id=account.id,    # type: ignore
        transaction_date=date.fromisoformat(parsed["transaction_date"]),
        note=sanitize_note(parsed.get("note", "")),
    )
    return create_transaction(db, txn_data)


