"""Savings goals: a named target with a running saved amount."""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import GoalContributionForm, SavingsGoalForm
from app.models import SavingsGoal
from app.services.audit import log_action
from app.services.transactions import owned_or_none

bp = Blueprint("goals", __name__, url_prefix="/goals")


@bp.get("/")
@login_required
def index():
    active = (SavingsGoal.query.filter_by(user_id=current_user.id, archived=False)
              .order_by(SavingsGoal.created_at.desc()).all())
    done = (SavingsGoal.query.filter_by(user_id=current_user.id, archived=True)
            .order_by(SavingsGoal.created_at.desc()).all())
    return render_template("goals/index.html", goals=active, archived=done,
                           contrib_form=GoalContributionForm(formdata=None))


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = SavingsGoalForm()
    if form.validate_on_submit():
        goal = SavingsGoal(user_id=current_user.id)
        form.populate_obj(goal)
        goal.name = goal.name.strip()
        db.session.add(goal)
        db.session.commit()
        log_action(current_user.id, "goal_create", f"id={goal.id}")
        flash(f"Goal '{goal.name}' created.", "success")
        return redirect(url_for("goals.index"))
    return render_template("goals/form.html", form=form, title="New savings goal")


@bp.route("/<int:goal_id>/edit", methods=["GET", "POST"])
@login_required
def edit(goal_id):
    goal = owned_or_none(SavingsGoal, goal_id, current_user.id) or abort(404)
    form = SavingsGoalForm(obj=goal)
    if form.validate_on_submit():
        form.populate_obj(goal)
        goal.name = goal.name.strip()
        db.session.commit()
        log_action(current_user.id, "goal_update", f"id={goal.id}")
        flash("Goal updated.", "success")
        return redirect(url_for("goals.index"))
    return render_template("goals/form.html", form=form, title="Edit goal", goal=goal)


@bp.post("/<int:goal_id>/contribute")
@login_required
def contribute(goal_id):
    goal = owned_or_none(SavingsGoal, goal_id, current_user.id) or abort(404)
    form = GoalContributionForm()
    if form.validate_on_submit():
        goal.saved_amount = (goal.saved_amount or 0) + form.amount.data
        if goal.is_complete:
            goal.archived = True
        db.session.commit()
        log_action(current_user.id, "goal_contribute", f"id={goal.id} amount={form.amount.data}")
        flash(f"Added to '{goal.name}'." + (" Goal reached! 🎉" if goal.is_complete else ""), "success")
    else:
        flash("Enter a valid amount.", "danger")
    return redirect(url_for("goals.index"))


@bp.post("/<int:goal_id>/withdraw")
@login_required
def withdraw(goal_id):
    goal = owned_or_none(SavingsGoal, goal_id, current_user.id) or abort(404)
    form = GoalContributionForm()
    if form.validate_on_submit():
        goal.saved_amount = max((goal.saved_amount or 0) - form.amount.data, 0)
        db.session.commit()
        log_action(current_user.id, "goal_withdraw", f"id={goal.id} amount={form.amount.data}")
        flash(f"Withdrew from '{goal.name}'.", "info")
    else:
        flash("Enter a valid amount.", "danger")
    return redirect(url_for("goals.index"))


@bp.post("/<int:goal_id>/archive")
@login_required
def toggle_archive(goal_id):
    goal = owned_or_none(SavingsGoal, goal_id, current_user.id) or abort(404)
    goal.archived = not goal.archived
    db.session.commit()
    flash(f"Goal '{goal.name}' {'archived' if goal.archived else 'restored'}.", "info")
    return redirect(url_for("goals.index"))


@bp.post("/<int:goal_id>/delete")
@login_required
def delete(goal_id):
    goal = owned_or_none(SavingsGoal, goal_id, current_user.id) or abort(404)
    db.session.delete(goal)
    db.session.commit()
    log_action(current_user.id, "goal_delete", f"id={goal_id}")
    flash("Goal deleted.", "info")
    return redirect(url_for("goals.index"))
