"""Dashboard numbers, chart series and automatic insights. All real queries, nothing hardcoded."""
import calendar
from datetime import date, timedelta

from sqlalchemy import case, extract, func

from app.extensions import db
from app.models import Account, Category, Transaction


def month_bounds(d: date):
    first = d.replace(day=1)
    last = d.replace(day=calendar.monthrange(d.year, d.month)[1])
    return first, last


def prev_month(d: date):
    first = d.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


def _sum_kind(user_id, kind, start=None, end=None):
    q = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id, Transaction.kind == kind, Transaction.transfer_id.is_(None)
    )
    if start:
        q = q.filter(Transaction.date >= start)
    if end:
        q = q.filter(Transaction.date <= end)
    return float(q.scalar())


def account_balances(user_id):
    """[(account, balance)] where balance = opening + income - expense."""
    flows = dict(
        db.session.query(
            Transaction.account_id,
            func.sum(case((Transaction.kind == "income", Transaction.amount), else_=-Transaction.amount)),
        )
        .filter(Transaction.user_id == user_id)
        .group_by(Transaction.account_id)
        .all()
    )
    accounts = Account.query.filter_by(user_id=user_id, archived=False).order_by(Account.name).all()
    return [(a, float(a.opening_balance or 0) + float(flows.get(a.id) or 0)) for a in accounts]


def pct_change(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def summary(user_id, today=None):
    today = today or date.today()
    m_start, m_end = month_bounds(today)
    p_start, p_end = month_bounds(prev_month(today))
    income = _sum_kind(user_id, "income", m_start, m_end)
    expense = _sum_kind(user_id, "expense", m_start, m_end)
    p_income = _sum_kind(user_id, "income", p_start, p_end)
    p_expense = _sum_kind(user_id, "expense", p_start, p_end)
    balance = sum(b for _, b in account_balances(user_id))
    savings_rate = round((income - expense) / income * 100, 1) if income else None
    p_savings_rate = round((p_income - p_expense) / p_income * 100, 1) if p_income else None
    return {
        "balance": balance,
        "income": income,
        "expense": expense,
        "net": income - expense,
        "income_change": pct_change(income, p_income),
        "expense_change": pct_change(expense, p_expense),
        "savings_rate": savings_rate,
        "savings_rate_change": (round(savings_rate - p_savings_rate, 1)
                                if savings_rate is not None and p_savings_rate is not None else None),
    }


def cashflow_series(user_id, months=6, today=None):
    today = today or date.today()
    keys, d = [], today.replace(day=1)
    for _ in range(months):
        keys.append((d.year, d.month))
        d = prev_month(d)
    keys.reverse()
    start = date(keys[0][0], keys[0][1], 1)
    rows = (
        db.session.query(extract("year", Transaction.date), extract("month", Transaction.date),
                         Transaction.kind, func.sum(Transaction.amount))
        .filter(Transaction.user_id == user_id, Transaction.date >= start, Transaction.transfer_id.is_(None))
        .group_by(extract("year", Transaction.date), extract("month", Transaction.date), Transaction.kind)
        .all()
    )
    sums = {(int(y), int(m), k): float(v) for y, m, k, v in rows}
    return {
        "labels": [date(y, m, 1).strftime("%b") for y, m in keys],
        "income": [round(sums.get((y, m, "income"), 0.0), 2) for y, m in keys],
        "expense": [round(sums.get((y, m, "expense"), 0.0), 2) for y, m in keys],
    }


def category_breakdown(user_id, start, end, kind="expense", limit=None):
    q = (
        db.session.query(Category.id, Category.name, Category.color, Category.icon, func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(Transaction.user_id == user_id, Transaction.kind == kind,
                Transaction.date >= start, Transaction.date <= end, Transaction.transfer_id.is_(None))
        .group_by(Category.id, Category.name, Category.color, Category.icon)
        .order_by(func.sum(Transaction.amount).desc())
    )
    rows = q.limit(limit).all() if limit else q.all()
    total = sum(float(r[4]) for r in rows) or 1
    return [
        {"id": r[0], "name": r[1], "color": r[2], "icon": r[3], "amount": float(r[4]),
         "share": round(float(r[4]) / total * 100, 1)}
        for r in rows
    ]


def daily_spend(user_id, start, end):
    rows = (
        db.session.query(Transaction.date, func.sum(Transaction.amount))
        .filter(Transaction.user_id == user_id, Transaction.kind == "expense",
                Transaction.date >= start, Transaction.date <= end, Transaction.transfer_id.is_(None))
        .group_by(Transaction.date)
        .all()
    )
    by_day = {d: float(v) for d, v in rows}
    days, d = [], start
    while d <= end:
        days.append({"x": d.isoformat(), "y": round(by_day.get(d, 0.0), 2)})
        d += timedelta(days=1)
    return days


def recent(user_id, limit=6):
    return (Transaction.query.filter_by(user_id=user_id)
            .order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all())


def insights(user_id, currency_fmt, today=None):
    """Plain-language observations generated from the user's own data."""
    today = today or date.today()
    m_start, m_end = month_bounds(today)
    p_start, p_end = month_bounds(prev_month(today))
    out = []

    spent = _sum_kind(user_id, "expense", m_start, today)
    last_month = _sum_kind(user_id, "expense", p_start, p_end)
    days_in_month = m_end.day
    if spent and today.day >= 3:
        projected = spent / today.day * days_in_month
        diff = pct_change(projected, last_month)
        tone = "danger" if diff and diff > 10 else "success" if diff is not None and diff < 0 else "info"
        text = f"At your current pace you'll spend about {currency_fmt(projected)} this month"
        if diff is not None:
            text += f", {abs(diff)}% {'more' if diff > 0 else 'less'} than last month."
        else:
            text += "."
        out.append({"icon": "bi-graph-up-arrow", "tone": tone, "title": "Month-end forecast", "text": text})

    this_cats = {c["name"]: c for c in category_breakdown(user_id, m_start, m_end)}
    prev_cats = {c["name"]: c for c in category_breakdown(user_id, p_start, p_end)}
    movers = []
    for name, c in this_cats.items():
        prev = prev_cats.get(name, {}).get("amount")
        change = pct_change(c["amount"], prev)
        if change is not None and abs(change) >= 20 and c["amount"] >= 500:
            movers.append((change, name, c))
    if movers:
        change, name, c = max(movers, key=lambda m: abs(m[0]))
        up = change > 0
        out.append({
            "icon": c["icon"], "tone": "warning" if up else "success",
            "title": f"{name} {'up' if up else 'down'} {abs(change):.0f}%",
            "text": f"You've spent {currency_fmt(c['amount'])} on {name.lower()} this month "
                    f"vs {currency_fmt(prev_cats[name]['amount'])} last month.",
        })

    biggest = (Transaction.query.filter(Transaction.user_id == user_id, Transaction.kind == "expense",
                                        Transaction.transfer_id.is_(None),
                                        Transaction.date >= m_start, Transaction.date <= m_end)
               .order_by(Transaction.amount.desc()).first())
    if biggest:
        out.append({
            "icon": "bi-lightning", "tone": "info", "title": "Biggest expense this month",
            "text": f"{currency_fmt(biggest.amount)} on {biggest.description or biggest.category.name} "
                    f"({biggest.date.strftime('%d %b')}).",
        })

    if this_cats:
        top = next(iter(this_cats.values()))
        out.append({
            "icon": "bi-pie-chart", "tone": "primary", "title": f"Top category: {top['name']}",
            "text": f"{top['share']}% of this month's spending went to {top['name'].lower()}.",
        })

    if not out:
        out.append({"icon": "bi-stars", "tone": "primary", "title": "Insights unlock as you go",
                    "text": "Add a few transactions and this panel will start spotting patterns for you."})
    return out[:4]
