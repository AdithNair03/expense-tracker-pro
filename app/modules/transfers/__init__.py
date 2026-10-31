"""Move money between a user's own accounts (doesn't count as income or expense)."""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import TransferForm
from app.models import Account, Transaction
from app.services.audit import log_action
from app.services.transactions import owned_or_none, user_accounts
from app.services.transfers import create_transfer, recent_transfers

bp = Blueprint("transfers", __name__, url_prefix="/transfers")


def _bind_choices(form):
    choices = [(a.id, a.name) for a in user_accounts(current_user.id)]
    form.from_account_id.choices = choices
    form.to_account_id.choices = choices
    return form


@bp.get("/")
@login_required
def index():
    return render_template("transfers/index.html", transfers=recent_transfers(current_user.id))


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = _bind_choices(TransferForm())
    if len(form.from_account_id.choices) < 2:
        flash("You need at least two accounts to make a transfer.", "info")
        return redirect(url_for("accounts.index"))
    if form.validate_on_submit():
        from_acc = owned_or_none(Account, form.from_account_id.data, current_user.id)
        to_acc = owned_or_none(Account, form.to_account_id.data, current_user.id)
        if not from_acc or not to_acc:
            abort(404)
        create_transfer(current_user.id, from_acc, to_acc, form.amount.data, form.date.data,
                        (form.notes.data or "").strip())
        log_action(current_user.id, "transfer_create", f"{from_acc.name}->{to_acc.name} amount={form.amount.data}")
        flash(f"Transferred to {to_acc.name}.", "success")
        return redirect(url_for("transfers.index"))
    return render_template("transfers/form.html", form=form, title="New transfer")


@bp.post("/<transfer_id>/delete")
@login_required
def delete(transfer_id):
    legs = Transaction.query.filter_by(user_id=current_user.id, transfer_id=transfer_id).all() or abort(404)
    for leg in legs:
        db.session.delete(leg)
    db.session.commit()
    log_action(current_user.id, "transfer_delete", f"transfer_id={transfer_id}")
    flash("Transfer deleted.", "info")
    return redirect(url_for("transfers.index"))
