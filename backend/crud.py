"""
数据库 CRUD 操作

所有涉及金额的计算均使用 Python Decimal，杜绝浮点数精度问题。
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, extract, and_
from sqlalchemy.orm import Session, joinedload

from models import Category, Account, Transaction, Budget
from schemas import (
    CategoryCreate,
    AccountCreate,
    TransactionCreate,
    BudgetCreate,
)


def _safe_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    """安全地将查询结果转为 Decimal，防止 None / 非数字字符串导致崩溃"""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


# ==================== 分类 ====================

def get_categories(db: Session, category_type: Optional[str] = None):
    """获取分类列表"""
    q = db.query(Category)
    if category_type:
        q = q.filter(Category.type == category_type)
    return q.order_by(Category.sort_order, Category.id).all()


def get_category_by_name(db: Session, name: str, category_type: str) -> Optional[Category]:
    """按名称查找分类"""
    return (
        db.query(Category)
        .filter(Category.name == name, Category.type == category_type)
        .first()
    )


def create_category(db: Session, data: CategoryCreate) -> Category:
    cat = Category(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ==================== 账户 ====================

def get_accounts(db: Session):
    return db.query(Account).order_by(Account.sort_order, Account.id).all()


def get_account_by_name(db: Session, name: str) -> Optional[Account]:
    return db.query(Account).filter(Account.name == name).first()


def create_account(db: Session, data: AccountCreate) -> Account:
    acc = Account(**data.model_dump())
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


# ==================== 交易/流水 ====================

def create_transaction(db: Session, data: TransactionCreate) -> Transaction:
    """创建交易，使用 Decimal 保证精度"""
    txn = Transaction(
        type=data.type,
        amount=data.amount,
        category_id=data.category_id,
        account_id=data.account_id,
        transaction_date=data.transaction_date,
        note=data.note,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    # 重新查询以加载关联对象
    return (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.id == txn.id)
        .first()
    )


def get_transactions(
    db: Session,
    year: Optional[int] = None,
    month: Optional[int] = None,
    week_start: Optional[date] = None,
    week_end: Optional[date] = None,
    category_id: Optional[int] = None,
    txn_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """获取交易列表，支持按月/周/分类筛选"""
    q = db.query(Transaction).options(
        joinedload(Transaction.category), joinedload(Transaction.account)
    )

    # 按月筛选
    if year and month:
        q = q.filter(
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
    elif year:
        q = q.filter(extract("year", Transaction.transaction_date) == year)

    # 按周筛选（优先级高于按月）
    if week_start and week_end:
        q = q.filter(
            Transaction.transaction_date >= week_start,
            Transaction.transaction_date <= week_end,
        )

    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if txn_type:
        q = q.filter(Transaction.type == txn_type)

    # 统计汇总（不受分页影响）
    income_q = q.filter(Transaction.type == "income")
    expense_q = q.filter(Transaction.type == "expense")
    total_income = income_q.with_entities(func.coalesce(func.sum(Transaction.amount), 0)).scalar()
    total_expense = expense_q.with_entities(func.coalesce(func.sum(Transaction.amount), 0)).scalar()

    total_count = q.count()
    items = (
        q.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total_count,
        "items": items,
        "total_income": _safe_decimal(total_income),
        "total_expense": _safe_decimal(total_expense),
    }


def get_transaction(db: Session, txn_id: int) -> Optional[Transaction]:
    return (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.id == txn_id)
        .first()
    )


def delete_transaction(db: Session, txn_id: int) -> bool:
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        return False
    db.delete(txn)
    db.commit()
    return True


# ==================== 统计 ====================

def get_category_stats(
    db: Session,
    year: int,
    month: int,
    txn_type: str = "expense",
) -> list:
    """获取某月各类别支出/收入统计（用于饼图）"""
    total = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == txn_type,
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .scalar()
    )
    total = _safe_decimal(total)

    rows = (
        db.query(
            Category.id,
            Category.name,
            Category.icon,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("cnt"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == txn_type,
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    results = []
    for row in rows:
        amount = _safe_decimal(row.total)
        results.append({
            "category_id": row.id,
            "category_name": row.name,
            "category_icon": row.icon,
            "amount": amount,
            "percentage": float(amount / total * 100) if total > 0 else 0,
            "count": row.cnt,
        })
    return results


def get_monthly_stats(db: Session, year: int) -> list:
    """获取某年各月收支统计（用于趋势折线图）"""
    rows = (
        db.query(
            extract("month", Transaction.transaction_date).label("month"),
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .filter(extract("year", Transaction.transaction_date) == year)
        .group_by(extract("month", Transaction.transaction_date), Transaction.type)
        .order_by("month")
        .all()
    )

    monthly: dict[int, dict] = {}
    for m in range(1, 13):
        monthly[m] = {"month": f"{year}-{m:02d}", "income": Decimal("0"), "expense": Decimal("0")}

    for row in rows:
        m = int(row.month)
        if row.type == "income":
            monthly[m]["income"] = _safe_decimal(row.total)
        else:
            monthly[m]["expense"] = _safe_decimal(row.total)

    for m in monthly:
        monthly[m]["balance"] = monthly[m]["income"] - monthly[m]["expense"]

    return [monthly[m] for m in range(1, 13)]


def get_overview(db: Session, year: int, month: int) -> dict:
    """获取月度概览"""
    income = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "income",
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .scalar()
    )
    expense = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "expense",
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .scalar()
    )
    count = (
        db.query(func.count(Transaction.id))
        .filter(
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .scalar()
    )

    income_d = _safe_decimal(income)
    expense_d = _safe_decimal(expense)
    return {
        "total_income": income_d,
        "total_expense": expense_d,
        "balance": income_d - expense_d,
        "transaction_count": count,
    }


# ==================== 预算 ====================

def create_budget(db: Session, data: BudgetCreate) -> Budget:
    """设置预算（使用 upsert 防止竞态条件）"""
    existing = (
        db.query(Budget)
        .filter(
            Budget.year == data.year,
            Budget.month == data.month,
            Budget.category_id == data.category_id,
        )
        .with_for_update()
        .first()
    )
    if existing:
        existing.amount = data.amount
        existing.alert_threshold = data.alert_threshold
        db.commit()
        db.refresh(existing)
        return existing

    budget = Budget(**data.model_dump())
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def get_budgets(db: Session, year: int, month: int):
    return (
        db.query(Budget)
        .options(joinedload(Budget.category))
        .filter(Budget.year == year, Budget.month == month)
        .all()
    )


def get_budget_status(db: Session, year: int, month: int) -> list:
    """
    计算预算执行状态。

    优化：使用一条 GROUP BY 查询代替逐条 N+1 查询。
    防护：amount=0 / scalar()=None / alert_threshold=None 均有兜底。
    """
    budgets = get_budgets(db, year, month)
    if not budgets:
        return []

    # ── 一次查询：按 category_id 汇总当月所有支出 ──
    #   category_id = NULL 时表示"总预算"（不限分类），使用特殊哨兵 -1
    agg_rows = (
        db.query(
            Transaction.category_id,
            func.coalesce(func.sum(Transaction.amount), 0).label("spent"),
        )
        .filter(
            Transaction.type == "expense",
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .group_by(Transaction.category_id)
        .all()
    )

    # 构建快速查找表：{category_id: spent}
    spent_map: dict = {row.category_id: _safe_decimal(row.spent) for row in agg_rows}
    # 总支出（所有分类合计）
    total_spent_all = sum(spent_map.values(), Decimal("0"))

    results = []
    for b in budgets:
        # 确定该预算对应的已花金额
        if b.category_id is not None:
            spent = spent_map.get(b.category_id, Decimal("0"))
        else:
            spent = total_spent_all  # 总预算 → 取所有分类合计

        # 安全计算百分比（防止 amount=0 或 None）
        budget_amount = b.amount if b.amount is not None else Decimal("0")
        if budget_amount > 0:
            pct = float(spent / budget_amount)
        else:
            pct = 0.0

        # 安全获取告警阈值
        alert_threshold = float(b.alert_threshold) if b.alert_threshold is not None else 0.8

        results.append({
            "budget_id": b.id,
            "year": b.year,
            "month": b.month,
            "budget_amount": budget_amount,
            "spent_amount": spent,
            "remaining": budget_amount - spent,
            "percentage": round(pct * 100, 1),
            "is_over_budget": spent > budget_amount,
            "is_alert": pct >= alert_threshold,
            "alert_threshold": b.alert_threshold,
        })
    return results
