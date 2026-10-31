"""Database models.

Every user-owned table carries user_id, and every query in the services layer
filters on it. That is how one user's data stays invisible to another.
"""
from datetime import date, datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager

PAYMENT_METHODS = ["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking", "Wallet", "Other"]
RECURRING_FREQUENCIES = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}
ACCOUNT_TYPES = {
    "bank": ("Bank account", "bi-bank"),
    "cash": ("Cash", "bi-cash-stack"),
    "card": ("Credit card", "bi-credit-card-2-front"),
    "wallet": ("Wallet / UPI", "bi-phone"),
    "savings": ("Savings", "bi-piggy-bank"),
}
KINDS = ("expense", "income")
CURRENCIES = ["INR", "USD", "EUR", "GBP"]


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    currency = db.Column(db.String(3), nullable=False, default="INR")
    theme = db.Column(db.String(10), nullable=False, default="light")
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    accounts = db.relationship("Account", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    categories = db.relationship("Category", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    transactions = db.relationship("Transaction", backref="user", cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_active(self):
        return self.is_active_user

    @property
    def first_name(self):
        return (self.name or "").split(" ")[0]

    @property
    def initials(self):
        parts = [p for p in (self.name or "?").split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "?"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Account(db.Model):
    __tablename__ = "accounts"
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_account_user_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(60), nullable=False)
    type = db.Column(db.String(20), nullable=False, default="bank")
    opening_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    color = db.Column(db.String(7), nullable=False, default="#6366f1")
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    transactions = db.relationship("Transaction", backref="account", lazy="dynamic")

    @property
    def type_label(self):
        return ACCOUNT_TYPES.get(self.type, ("Account", "bi-wallet2"))[0]

    @property
    def icon(self):
        return ACCOUNT_TYPES.get(self.type, ("Account", "bi-wallet2"))[1]


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (db.UniqueConstraint("user_id", "name", "kind", name="uq_category_user_name_kind"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(10), nullable=False, default="expense")
    color = db.Column(db.String(7), nullable=False, default="#64748b")
    icon = db.Column(db.String(40), nullable=False, default="bi-tag")

    transactions = db.relationship("Transaction", backref="category", lazy="dynamic")


class Transaction(db.Model):
    """One money movement. kind='expense' or 'income'."""

    __tablename__ = "transactions"
    __table_args__ = (db.Index("ix_tx_user_date", "user_id", "date"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False, default="expense", index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.String(255), nullable=False, default="")
    payment_method = db.Column(db.String(30), nullable=False, default="UPI")
    notes = db.Column(db.Text)
    transfer_id = db.Column(db.String(36), index=True)
    recurring_id = db.Column(db.Integer, db.ForeignKey("recurring_transactions.id"), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    @property
    def signed_amount(self):
        return self.amount if self.kind == "income" else -self.amount

    @property
    def is_transfer(self):
        return self.transfer_id is not None


class Budget(db.Model):
    """Monthly spending limit per category."""

    __tablename__ = "budgets"
    __table_args__ = (db.UniqueConstraint("user_id", "category_id", name="uq_budget_user_category"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    monthly_limit = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    category = db.relationship("Category")


class SavingsGoal(db.Model):
    """A named savings target the user tracks progress toward."""

    __tablename__ = "savings_goals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)
    saved_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    target_date = db.Column(db.Date)
    color = db.Column(db.String(7), nullable=False, default="#6366f1")
    icon = db.Column(db.String(40), nullable=False, default="bi-trophy")
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    @property
    def progress_pct(self):
        if not self.target_amount:
            return 0
        return min(100, round(float(self.saved_amount) / float(self.target_amount) * 100, 1))

    @property
    def remaining(self):
        return max(float(self.target_amount) - float(self.saved_amount), 0)

    @property
    def is_complete(self):
        return float(self.saved_amount) >= float(self.target_amount) > 0


class RecurringTransaction(db.Model):
    """A transaction template that generates real transactions on a schedule."""

    __tablename__ = "recurring_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    kind = db.Column(db.String(10), nullable=False, default="expense")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    payment_method = db.Column(db.String(30), nullable=False, default="UPI")
    frequency = db.Column(db.String(10), nullable=False, default="monthly")
    next_due_date = db.Column(db.Date, nullable=False)
    last_generated_date = db.Column(db.Date)
    active = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    account = db.relationship("Account")
    category = db.relationship("Category")
    generated = db.relationship("Transaction", backref="recurring_source", lazy="dynamic")

    @property
    def frequency_label(self):
        return RECURRING_FREQUENCIES.get(self.frequency, self.frequency)

    def advance(self, from_date=None):
        """Push next_due_date forward by one period, based on from_date (or itself)."""
        base = from_date or self.next_due_date
        if self.frequency == "weekly":
            self.next_due_date = base + timedelta(days=7)
        elif self.frequency == "yearly":
            try:
                self.next_due_date = base.replace(year=base.year + 1)
            except ValueError:
                self.next_due_date = base.replace(month=2, day=28, year=base.year + 1)
        else:  # monthly
            year = base.year + (1 if base.month == 12 else 0)
            month = 1 if base.month == 12 else base.month + 1
            day = min(base.day, 28) if month == 2 else base.day
            try:
                self.next_due_date = base.replace(year=year, month=month, day=day)
            except ValueError:
                self.next_due_date = base.replace(year=year, month=month, day=28)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.String(255), nullable=False, default="")
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
