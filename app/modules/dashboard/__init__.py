from datetime import date, datetime

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models import Budget, SavingsGoal
from app.services import analytics
from app.services.formatting import money
from app.services.recurring import process_due

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


def _budget_alerts(uid, m_start, m_end):
    budgets = Budget.query.filter_by(user_id=uid).join(Budget.category).all()
    if not budgets:
        return []
    spent_by_cat = {c["id"]: c["amount"] for c in analytics.category_breakdown(uid, m_start, m_end)}
    rows = []
    for b in budgets:
        spent = spent_by_cat.get(b.category_id, 0.0)
        limit = float(b.monthly_limit)
        pct = min(100, round(spent / limit * 100, 1)) if limit else 0
        rows.append({"budget": b, "spent": spent, "limit": limit, "pct": pct,
                     "tone": "danger" if pct >= 100 else "warning" if pct >= 80 else "success"})
    rows.sort(key=lambda r: r["pct"], reverse=True)
    return rows[:4]


@bp.get("/dashboard")
@login_required
def index():
    uid = current_user.id
    process_due(uid)  # catch up any recurring transactions that fell due since the last visit
    today = date.today()
    m_start, m_end = analytics.month_bounds(today)
    fmt = lambda v: money(v, current_user.currency, 0)  # noqa: E731
    categories = analytics.category_breakdown(uid, m_start, m_end)
    charts = {
        "cashflow": analytics.cashflow_series(uid),
        "categories": {
            "labels": [c["name"] for c in categories],
            "values": [round(c["amount"], 2) for c in categories],
            "colors": [c["color"] for c in categories],
        },
        "daily": analytics.daily_spend(uid, m_start, today),
    }
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    goals = (SavingsGoal.query.filter_by(user_id=uid, archived=False)
             .order_by(SavingsGoal.created_at.desc()).limit(3).all())
    return render_template(
        "dashboard/index.html",
        greeting=greeting,
        today=today,
        s=analytics.summary(uid, today),
        balances=analytics.account_balances(uid),
        categories=categories[:6],
        recent=analytics.recent(uid),
        insights=analytics.insights(uid, fmt, today),
        charts=charts,
        budget_alerts=_budget_alerts(uid, m_start, m_end),
        goals=goals,
    )
