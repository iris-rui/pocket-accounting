"""
种子数据和共享工具函数

从 main.py 拆分出来，保持主文件简洁。
"""
from sqlalchemy.orm import Session

from models import Category, Account
from crud import get_category_by_name, get_account_by_name


# ==================== 默认种子数据 ====================

DEFAULT_EXPENSE_CATEGORIES = [
    ("🍜", "餐饮"), ("🛒", "购物"), ("🚗", "交通"), ("🎮", "娱乐"),
    ("🏠", "住房"), ("📱", "通讯"), ("💊", "医疗"), ("📚", "教育"),
    ("🎁", "人情"), ("🧴", "日用"), ("👗", "服饰"), ("💄", "美容"),
    ("⚽", "运动"), ("🍿", "零食"), ("🍉", "水果"), ("📌", "其他支出"),
]

DEFAULT_INCOME_CATEGORIES = [
    ("💼", "工资"), ("💻", "兼职"), ("📈", "理财"), ("🧧", "红包"),
    ("📋", "报销"), ("↩️", "退款"), ("💰", "其他收入"),
]

DEFAULT_ACCOUNTS = [
    ("💚", "微信"), ("💙", "支付宝"), ("💵", "现金"),
    ("🏦", "银行卡"), ("💳", "信用卡"), ("🌸", "花呗"), ("📦", "其他"),
]


def seed_defaults(db: Session) -> None:
    """种子数据：默认分类和账户（幂等，已存在则跳过）"""
    for idx, (icon, name) in enumerate(DEFAULT_EXPENSE_CATEGORIES):
        if not get_category_by_name(db, name, "expense"):
            db.add(Category(name=name, icon=icon, type="expense", is_default=1, sort_order=idx))

    for idx, (icon, name) in enumerate(DEFAULT_INCOME_CATEGORIES):
        if not get_category_by_name(db, name, "income"):
            db.add(Category(name=name, icon=icon, type="income", is_default=1, sort_order=idx))

    for idx, (icon, name) in enumerate(DEFAULT_ACCOUNTS):
        if not get_account_by_name(db, name):
            db.add(Account(name=name, icon=icon, is_default=1, sort_order=idx))

    db.commit()


# ==================== 共享工具函数 ====================

def resolve_category_and_account(db: Session, parsed: dict):
    """
    统一的分类/账户匹配逻辑。

    用于 ai_parse_text / ai_parse_and_save 两个端点，
    消除重复的分类查找 + 兜底逻辑。

    返回 (category, account) 元组，保证非 None。
    """
    cat_type = parsed["type"]
    category = get_category_by_name(db, parsed["category_name"], cat_type)
    if not category:
        category = db.query(Category).filter(
            Category.type == cat_type, Category.is_default == 1
        ).first()

    account = get_account_by_name(db, parsed["account_name"])
    if not account:
        account = get_account_by_name(db, "微信")

    # 极端兜底（数据库无任何分类/账户时）
    if not category:
        category = db.query(Category).first()
    if not account:
        account = db.query(Account).first()

    return category, account
