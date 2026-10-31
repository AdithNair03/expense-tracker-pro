"""Move money between a user's own accounts without touching income/expense totals."""
import uuid

from app.extensions import db
from app.models import Category, Transaction


def ensure_transfer_category(user_id, kind):
    cat = Category.query.filter_by(user_id=user_id, name="Transfer", kind=kind).first()
    if not cat:
        cat = Category(user_id=user_id, name="Transfer", kind=kind, color="#94a3b8", icon="bi-arrow-left-right")
        db.session.add(cat)
        db.session.flush()
    return cat


def create_transfer(user_id, from_account, to_account, amount, date, notes=""):
    """Writes a linked expense (source) + income (destination) pair sharing a transfer_id."""
    transfer_id = uuid.uuid4().hex
    expense_cat = ensure_transfer_category(user_id, "expense")
    income_cat = ensure_transfer_category(user_id, "income")
    out_tx = Transaction(
        user_id=user_id, kind="expense", amount=amount, account_id=from_account.id, category_id=expense_cat.id,
        payment_method="Other", date=date, description=f"Transfer to {to_account.name}", notes=notes,
        transfer_id=transfer_id,
    )
    in_tx = Transaction(
        user_id=user_id, kind="income", amount=amount, account_id=to_account.id, category_id=income_cat.id,
        payment_method="Other", date=date, description=f"Transfer from {from_account.name}", notes=notes,
        transfer_id=transfer_id,
    )
    db.session.add_all([out_tx, in_tx])
    db.session.commit()
    return transfer_id


def recent_transfers(user_id, limit=20):
    """One row per transfer (the outgoing leg), newest first."""
    rows = (
        Transaction.query.filter_by(user_id=user_id, kind="expense")
        .filter(Transaction.transfer_id.isnot(None))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for out_tx in rows:
        in_tx = Transaction.query.filter_by(transfer_id=out_tx.transfer_id, kind="income").first()
        out.append({"out": out_tx, "in": in_tx})
    return out
