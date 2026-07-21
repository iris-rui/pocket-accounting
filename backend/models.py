"""
数据库模型定义

货币金额统一使用 Numeric(12,2) 类型存储，避免浮点数精度问题。
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Enum,
    Numeric,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from database import Base


class Category(Base):
    """收支分类表"""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="分类名称")
    icon = Column(String(10), nullable=False, default="📌", comment="图标emoji")
    type = Column(
        Enum("income", "expense", name="category_type"),
        nullable=False,
        default="expense",
        comment="类型: income=收入, expense=支出",
    )
    is_default = Column(Integer, nullable=False, default=0, comment="是否默认分类")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序")

    transactions = relationship("Transaction", back_populates="category")


class Account(Base):
    """账户表"""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="账户名称")
    icon = Column(String(10), nullable=False, default="💳", comment="图标")
    is_default = Column(Integer, nullable=False, default=0, comment="是否默认")
    sort_order = Column(Integer, nullable=False, default=0)

    transactions = relationship("Transaction", back_populates="account")


class Transaction(Base):
    """交易流水表（核心表）"""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(
        Enum("income", "expense", name="transaction_type"),
        nullable=False,
        default="expense",
        comment="类型",
    )
    # 使用 DECIMAL 而非 FLOAT，彻底避免 0.1+0.2=0.30000000000000004 这类精度问题
    amount = Column(
        Numeric(12, 2),
        nullable=False,
        comment="金额（元），精确到分",
    )
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    transaction_date = Column(Date, nullable=False, default=func.current_date(), comment="交易日期")
    note = Column(String(255), nullable=True, default="", comment="备注")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    category = relationship("Category", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")

    # 复合索引：按日期+类型查询是最高频场景
    __table_args__ = (
        Index("ix_txn_date_type", "transaction_date", "type"),
        Index("ix_txn_category", "category_id"),
        Index("ix_txn_account", "account_id"),
    )


class Budget(Base):
    """预算表"""
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, comment="年份")
    month = Column(Integer, nullable=False, comment="月份")
    # DECIMAL 保证预算金额精度
    amount = Column(
        Numeric(12, 2),
        nullable=False,
        comment="预算金额",
    )
    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=True,
        comment="为空=总预算，不为空=分类预算",
    )
    alert_threshold = Column(
        Numeric(5, 2),
        nullable=False,
        default=0.80,
        comment="预警阈值（比例），默认0.80即80%时预警",
    )
    created_at = Column(DateTime, nullable=False, default=func.now())

    category = relationship("Category")
