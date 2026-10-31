"""Transaction queries and filters, always scoped to one user."""
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import case, func, or_

from app.extensions import db
from app.models import KINDS, PAYMENT_METHODS, Account, Category, Transaction


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@dataclass
class TxFilters:
    q: str = ""
    kind: str = ""
    account_id: str = ""
    category_id: str = ""
    payment_method: str = ""
    date_from: str = ""
    date_to: str = ""
    period: str = ""
    active: dict = field(default_factory=dict)

    @classmethod
    def from_args(cls, args):
        f = cls(**{k: (args.get(k) or "").strip() for k in
                   ("q", "kind", "account_id", "category_id", "payment_method", "date_from", "date_to", "period")})
        f.active = {k: v for k, v in f.__dict__.items() if k != "active" and v}
        return f


def _period_range(period):
    today = date.today()
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this.fromordinal(first_this.toordinal() - 1)
        return last_prev.replace(day=1), last_prev
    if period == "this_year":
        return today.replace(month=1, day=1), today
    return None, None


def conditions(user_id, f: TxFilters):
    conds = [Transaction.user_id == user_id]
    if f.q:
        like = f"%{f.q}%"
        conds.append(or_(Transaction.description.ilike(like), Transaction.notes.ilike(like)))
    if f.kind in KINDS:
        conds.append(Transaction.kind == f.kind)
    if f.account_id.isdigit():
        conds.append(Transaction.account_id == int(f.account_id))
    if f.category_id.isdigit():
        conds.append(Transaction.category_id == int(f.category_id))
    if f.payment_method in PAYMENT_METHODS:
        conds.append(Transaction.payment_method == f.payment_method)
    start, end = _period_range(f.period)
    start = parse_date(f.date_from) or start
    end = parse_date(f.date_to) or end
    if start:
        conds.append(Transaction.date >= start)
    if end:
        conds.append(Transaction.date <= end)
    return conds


def filtered_query(user_id, f: TxFilters):
    return Transaction.query.filter(*conditions(user_id, f)).order_by(Transaction.date.desc(), Transaction.id.desc())


def totals(user_id, f: TxFilters):
    """Income, expense and net for the filtered set, in one query. Transfers between a
    user's own accounts are excluded - they don't represent real income or spending."""
    income, expense = db.session.query(
        func.coalesce(func.sum(case((Transaction.kind == "income", Transaction.amount), else_=0)), 0),
        func.coalesce(func.sum(case((Transaction.kind == "expense", Transaction.amount), else_=0)), 0),
    ).filter(*conditions(user_id, f), Transaction.transfer_id.is_(None)).one()
    return {"income": income, "expense": expense, "net": income - expense}


def owned_or_none(model, obj_id, user_id):
    return model.query.filter_by(id=obj_id, user_id=user_id).first()


def user_accounts(user_id, include_archived=False):
    q = Account.query.filter_by(user_id=user_id)
    if not include_archived:
        q = q.filter_by(archived=False)
    return q.order_by(Account.name).all()


def user_categories(user_id, kind=None):
    q = Category.query.filter_by(user_id=user_id)
    if kind:
        q = q.filter_by(kind=kind)
    return q.order_by(Category.kind, Category.name).all()
