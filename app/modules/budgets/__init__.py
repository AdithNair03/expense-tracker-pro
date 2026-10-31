"""Monthly spending limits per category, with live progress against this month's spending."""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import BudgetForm
from app.models import Budget
from app.services import analytics
from app.services.audit import log_action
from app.services.transactions import owned_or_none, user_categories

bp = Blueprint("budgets", __name__, url_prefix="/budgets")


def _progress(budgets):
    today = date.today()
    m_start, m_end = analytics.month_bounds(today)
    spent_by_cat = {c["id"]: c["amount"] for c in analytics.category_breakdown(current_user.id, m_start, m_end)}
    rows = []
    for b in budgets:
        spent = spent_by_cat.get(b.category_id, 0.0)
        limit = float(b.monthly_limit)
        pct = min(100, round(spent / limit * 100, 1)) if limit else 0
        tone = "danger" if pct >= 100 else "warning" if pct >= 80 else "success"
        rows.append({"budget": b, "spent": spent, "limit": limit, "pct": pct, "tone": tone,
                     "remaining": max(limit - spent, 0)})
    return sorted(rows, key=lambda r: r["pct"], reverse=True)


@bp.get("/")
@login_required
def index():
    budgets = Budget.query.filter_by(user_id=current_user.id).join(Budget.category).order_by("name").all()
    budgeted_ids = {b.category_id for b in budgets}
    available = [c for c in user_categories(current_user.id, kind="expense") if c.id not in budgeted_ids]
    return render_template("budgets/index.html", rows=_progress(budgets), available=available)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = BudgetForm()
    budgeted_ids = {b.category_id for b in Budget.query.filter_by(user_id=current_user.id)}
    form.category_id.choices = [(c.id, c.name) for c in user_categories(current_user.id, kind="expense")
                                if c.id not in budgeted_ids]
    if not form.category_id.choices:
        flash("Every expense category already has a budget. Edit one instead, or add a new category first.", "info")
        return redirect(url_for("budgets.index"))
    if form.validate_on_submit():
        budget = Budget(user_id=current_user.id)
        db.session.add(budget)
        form.populate_obj(budget)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That category already has a budget.", "warning")
            return render_template("budgets/form.html", form=form, title="New budget")
        log_action(current_user.id, "budget_create", f"id={budget.id}")
        flash("Budget saved.", "success")
        return redirect(url_for("budgets.index"))
    return render_template("budgets/form.html", form=form, title="New budget")


@bp.route("/<int:budget_id>/edit", methods=["GET", "POST"])
@login_required
def edit(budget_id):
    budget = owned_or_none(Budget, budget_id, current_user.id) or abort(404)
    form = BudgetForm(obj=budget)
    form.category_id.choices = [(budget.category.id, budget.category.name)]
    form.category_id.render_kw = {"disabled": True}
    if form.validate_on_submit():
        budget.monthly_limit = form.monthly_limit.data
        db.session.commit()
        log_action(current_user.id, "budget_update", f"id={budget.id}")
        flash("Budget updated.", "success")
        return redirect(url_for("budgets.index"))
    return render_template("budgets/form.html", form=form, title="Edit budget", budget=budget)


@bp.post("/<int:budget_id>/delete")
@login_required
def delete(budget_id):
    budget = owned_or_none(Budget, budget_id, current_user.id) or abort(404)
    db.session.delete(budget)
    db.session.commit()
    log_action(current_user.id, "budget_delete", f"id={budget_id}")
    flash("Budget removed.", "info")
    return redirect(url_for("budgets.index"))
