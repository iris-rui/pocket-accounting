"""
Pydantic 请求/响应模型
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ==================== 分类 ====================

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="分类名称")
    icon: str = Field(default="📌", max_length=10)
    type: str = Field(default="expense", pattern="^(income|expense)$")


class CategoryResponse(BaseModel):
    id: int
    name: str
    icon: str
    type: str
    is_default: int
    sort_order: int

    model_config = {"from_attributes": True}


# ==================== 账户 ====================

class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    icon: str = Field(default="💳", max_length=10)


class AccountResponse(BaseModel):
    id: int
    name: str
    icon: str
    is_default: int
    sort_order: int

    model_config = {"from_attributes": True}


# ==================== 交易/流水 ====================

class TransactionCreate(BaseModel):
    """手动创建交易"""
    type: str = Field(default="expense", pattern="^(income|expense)$")
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, description="金额（元）")
    category_id: int = Field(..., gt=0)
    account_id: int = Field(..., gt=0)
    transaction_date: date = Field(default_factory=date.today)
    note: str = Field(default="", max_length=255)


class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: Decimal
    category_id: int
    account_id: int
    transaction_date: date
    note: str
    created_at: datetime
    category: Optional[CategoryResponse] = None
    account: Optional[AccountResponse] = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    total: int
    items: list[TransactionResponse]
    total_income: Decimal
    total_expense: Decimal


# ==================== AI 一句话记账 ====================

class AIParseRequest(BaseModel):
    """AI 一句话记账请求"""
    text: str = Field(..., min_length=1, max_length=500, description="用户输入的自然语言")


class AIParseResponse(BaseModel):
    """AI 解析结果"""
    type: str = Field(description="income 或 expense")
    amount: Decimal = Field(description="解析出的金额")
    category_name: str = Field(description="解析出的分类名称")
    account_name: str = Field(description="解析出的账户名称")
    transaction_date: date = Field(description="解析出的日期")
    note: str = Field(default="", description="备注")
    confidence: float = Field(default=0.0, description="置信度 0-1")
    raw_text: str = Field(default="", description="原始输入")
    source: str = Field(default="local_fallback", description="解析来源: llm 或 local_fallback")


# ==================== 预算 ====================

class BudgetCreate(BaseModel):
    year: int = Field(..., ge=2024, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    category_id: Optional[int] = Field(default=None, description="为空表示总预算")
    alert_threshold: Decimal = Field(default=Decimal("0.80"), ge=0, le=1)


class BudgetResponse(BaseModel):
    id: int
    year: int
    month: int
    amount: Decimal
    category_id: Optional[int] = None
    alert_threshold: Decimal
    created_at: datetime
    category: Optional[CategoryResponse] = None

    model_config = {"from_attributes": True}


# ==================== 统计 ====================

class CategoryStat(BaseModel):
    category_id: int
    category_name: str
    category_icon: str
    amount: Decimal
    percentage: float
    count: int


class MonthlyStat(BaseModel):
    month: str  # 格式: "2026-07"
    income: Decimal
    expense: Decimal
    balance: Decimal


class OverviewStat(BaseModel):
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
    transaction_count: int


class BudgetStatus(BaseModel):
    budget_id: int
    year: int
    month: int
    budget_amount: Decimal
    spent_amount: Decimal
    remaining: Decimal
    percentage: float
    is_over_budget: bool
    is_alert: bool
    alert_threshold: Decimal


# ==================== AI 财务建议 ====================

class AIAdviceRequest(BaseModel):
    year: int
    month: int


class AIAdviceResponse(BaseModel):
    advice: str
    style: str = Field(default="毒舌", description="建议风格")
    spending_summary: str
    created_at: datetime = Field(default_factory=datetime.now)


# ==================== 通用响应 ====================

class MessageResponse(BaseModel):
    message: str
    success: bool = True
