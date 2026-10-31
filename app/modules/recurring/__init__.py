"""Recurring transaction templates (rent, subscriptions, salary...) that auto-generate."""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import RecurringForm
from app.models import Category, RecurringTransaction
from app.services.audit import log_action
from app.services.recurring import process_due
from app.services.transactions import owned_or_none, user_accounts, user_categories

bp = Blueprint("recurring", __name__, url_prefix="/recurring")


def _bind_choices(form):
    form.category_id.choices = [(c.id, c.name) for c in user_categories(current_user.id)]
    form.account_id.choices = [(a.id, a.name) for a in user_accounts(current_user.id)]
    return form


def _kind_matches(form):
    cat = db.session.get(Category, form.category_id.data)
    if not cat or cat.user_id != current_user.id or cat.kind != form.kind.data:
        form.category_id.errors.append(f"Choose an {form.kind.data} category.")
        return False
    return True


@bp.get("/")
@login_required
def index():
    generated = process_due(current_user.id)
    if generated:
        flash(f"{generated} recurring transaction(s) were due and have been added.", "info")
    items = (RecurringTransaction.query.filter_by(user_id=current_user.id)
             .order_by(RecurringTransaction.active.desc(), RecurringTransaction.next_due_date).all())
    return render_template("recurring/index.html", items=items, today=date.today())


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = _bind_choices(RecurringForm())
    if form.validate_on_submit() and _kind_matches(form):
        rec = RecurringTransaction(user_id=current_user.id)
        form.populate_obj(rec)
        rec.name = rec.name.strip()
        db.session.add(rec)
        db.session.commit()
        log_action(current_user.id, "recurring_create", f"id={rec.id}")
        flash(f"'{rec.name}' will repeat {rec.frequency}, starting {rec.next_due_date}.", "success")
        return redirect(url_for("recurring.index"))
    return render_template("recurring/form.html", form=form, title="New recurring transaction")


@bp.route("/<int:rec_id>/edit", methods=["GET", "POST"])
@login_required
def edit(rec_id):
    rec = owned_or_none(RecurringTransaction, rec_id, current_user.id) or abort(404)
    form = _bind_choices(RecurringForm(obj=rec))
    if form.validate_on_submit() and _kind_matches(form):
        form.populate_obj(rec)
        rec.name = rec.name.strip()
        db.session.commit()
        log_action(current_user.id, "recurring_update", f"id={rec.id}")
        flash("Recurring transaction updated.", "success")
        return redirect(url_for("recurring.index"))
    return render_template("recurring/form.html", form=form, title="Edit recurring transaction", rec=rec)


@bp.post("/<int:rec_id>/toggle")
@login_required
def toggle_active(rec_id):
    rec = owned_or_none(RecurringTransaction, rec_id, current_user.id) or abort(404)
    rec.active = not rec.active
    db.session.commit()
    flash(f"'{rec.name}' {'paused' if not rec.active else 'resumed'}.", "info")
    return redirect(url_for("recurring.index"))


@bp.post("/<int:rec_id>/delete")
@login_required
def delete(rec_id):
    rec = owned_or_none(RecurringTransaction, rec_id, current_user.id) or abort(404)
    rec.generated.update({"recurring_id": None})  # keep the already-created transactions, just unlink them
    db.session.delete(rec)
    db.session.commit()
    log_action(current_user.id, "recurring_delete", f"id={rec_id}")
    flash("Recurring transaction deleted.", "info")
    return redirect(url_for("recurring.index"))
