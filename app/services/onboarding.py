"""Starter data every new account gets: categories and two accounts."""
from app.extensions import db
from app.models import Account, Category

EXPENSE_CATEGORIES = [
    ("Food & Dining", "#f97316", "bi-cup-hot"),
    ("Groceries", "#84cc16", "bi-basket"),
    ("Transport", "#0ea5e9", "bi-bus-front"),
    ("Rent & Housing", "#8b5cf6", "bi-house-door"),
    ("Bills & Utilities", "#14b8a6", "bi-lightning-charge"),
    ("Shopping", "#ec4899", "bi-bag"),
    ("Health", "#ef4444", "bi-heart-pulse"),
    ("Entertainment", "#eab308", "bi-film"),
    ("Education", "#3b82f6", "bi-mortarboard"),
    ("Travel", "#06b6d4", "bi-airplane"),
    ("Subscriptions", "#a855f7", "bi-arrow-repeat"),
    ("Other", "#64748b", "bi-three-dots"),
    ("Transfer", "#94a3b8", "bi-arrow-left-right"),
]
INCOME_CATEGORIES = [
    ("Salary", "#10b981", "bi-briefcase"),
    ("Freelance", "#22c55e", "bi-laptop"),
    ("Pocket Money", "#34d399", "bi-wallet2"),
    ("Investments", "#059669", "bi-graph-up-arrow"),
    ("Gifts", "#f59e0b", "bi-gift"),
    ("Other Income", "#64748b", "bi-plus-circle"),
    ("Transfer", "#94a3b8", "bi-arrow-left-right"),
]
STARTER_ACCOUNTS = [
    ("Bank Account", "bank", "#6366f1"),
    ("Cash", "cash", "#10b981"),
]


def setup_new_user(user, with_accounts=True):
    for name, color, icon in EXPENSE_CATEGORIES:
        db.session.add(Category(user_id=user.id, name=name, kind="expense", color=color, icon=icon))
    for name, color, icon in INCOME_CATEGORIES:
        db.session.add(Category(user_id=user.id, name=name, kind="income", color=color, icon=icon))
    if with_accounts:
        for name, typ, color in STARTER_ACCOUNTS:
            db.session.add(Account(user_id=user.id, name=name, type=typ, color=color, opening_balance=0))
    db.session.commit()
