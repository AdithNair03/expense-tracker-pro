from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import AccountForm
from app.models import ACCOUNT_TYPES, Account
from app.services import analytics
from app.services.audit import log_action
from app.services.transactions import owned_or_none

bp = Blueprint("accounts", __name__, url_prefix="/accounts")


@bp.get("/")
@login_required
def index():
    balances = analytics.account_balances(current_user.id)
    archived = Account.query.filter_by(user_id=current_user.id, archived=True).order_by(Account.name).all()
    return render_template("accounts/index.html", balances=balances, archived=archived,
                           total=sum(b for _, b in balances), types=ACCOUNT_TYPES)


def _save(form, account, verb):
    form.populate_obj(account)
    account.name = account.name.strip()
    account.opening_balance = account.opening_balance or 0
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        form.name.errors.append("You already have an account with that name.")
        return False
    log_action(current_user.id, f"account_{verb}", f"id={account.id}")
    flash(f"Account '{account.name}' {verb}d.", "success")
    return True


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = AccountForm()
    if form.validate_on_submit():
        account = Account(user_id=current_user.id)
        db.session.add(account)
        if _save(form, account, "create"):
            return redirect(url_for("accounts.index"))
    return render_template("accounts/form.html", form=form, title="New account", types=ACCOUNT_TYPES)


@bp.route("/<int:account_id>/edit", methods=["GET", "POST"])
@login_required
def edit(account_id):
    account = owned_or_none(Account, account_id, current_user.id) or abort(404)
    form = AccountForm(obj=account)
    if form.validate_on_submit() and _save(form, account, "update"):
        return redirect(url_for("accounts.index"))
    return render_template("accounts/form.html", form=form, title="Edit account", account=account,
                           types=ACCOUNT_TYPES)


@bp.post("/<int:account_id>/archive")
@login_required
def toggle_archive(account_id):
    account = owned_or_none(Account, account_id, current_user.id) or abort(404)
    account.archived = not account.archived
    db.session.commit()
    log_action(current_user.id, "account_archive" if account.archived else "account_restore", f"id={account.id}")
    flash(f"Account '{account.name}' {'archived' if account.archived else 'restored'}.", "info")
    return redirect(url_for("accounts.index"))


@bp.post("/<int:account_id>/delete")
@login_required
def delete(account_id):
    account = owned_or_none(Account, account_id, current_user.id) or abort(404)
    if account.transactions.count():
        flash("This account has transactions. Archive it instead so your history stays intact.", "warning")
        return redirect(url_for("accounts.index"))
    db.session.delete(account)
    db.session.commit()
    log_action(current_user.id, "account_delete", f"id={account_id}")
    flash("Account deleted.", "info")
    return redirect(url_for("accounts.index"))
