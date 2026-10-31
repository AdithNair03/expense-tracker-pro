import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from prometheus_client import Counter
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.forms import TransactionForm
from app.models import PAYMENT_METHODS, Category, Transaction
from app.services import transactions as svc
from app.services.audit import log_action
from app.services.formatting import money

bp = Blueprint("transactions", __name__, url_prefix="/transactions")

PER_PAGE = 20
TX_CREATED = Counter("transactions_created_total", "Transactions created", ["kind"])


def _bind_choices(form):
    uid = current_user.id
    form.category_id.choices = [(c.id, c.name) for c in svc.user_categories(uid)]
    form.account_id.choices = [(a.id, a.name) for a in svc.user_accounts(uid)]
    return form


def _form_context(form, **extra):
    uid = current_user.id
    return dict(form=form, categories=svc.user_categories(uid), accounts=svc.user_accounts(uid), **extra)


def _kind_matches(form):
    cat = db.session.get(Category, form.category_id.data)
    if not cat or cat.user_id != current_user.id or cat.kind != form.kind.data:
        form.category_id.errors.append(f"Choose an {form.kind.data} category.")
        return False
    return True


def _back():
    nxt = request.form.get("next") or request.args.get("next") or ""
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("transactions.index")


@bp.get("/")
@login_required
def index():
    uid = current_user.id
    f = svc.TxFilters.from_args(request.args)
    page = request.args.get("page", 1, type=int)
    pagination = (svc.filtered_query(uid, f)
                  .options(joinedload(Transaction.category), joinedload(Transaction.account))
                  .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template(
        "transactions/index.html",
        pagination=pagination,
        totals=svc.totals(uid, f),
        f=f,
        categories=svc.user_categories(uid),
        accounts=svc.user_accounts(uid, include_archived=True),
        payment_methods=PAYMENT_METHODS,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = _bind_choices(TransactionForm())
    if request.method == "GET":
        form.kind.data = request.args.get("kind", "expense") if request.args.get("kind") in ("expense", "income") \
            else "expense"
    if form.validate_on_submit() and _kind_matches(form):
        tx = Transaction(
            user_id=current_user.id,
            kind=form.kind.data,
            amount=form.amount.data,
            description=(form.description.data or "").strip(),
            category_id=form.category_id.data,
            account_id=form.account_id.data,
            payment_method=form.payment_method.data,
            date=form.date.data,
            notes=(form.notes.data or "").strip() or None,
        )
        db.session.add(tx)
        db.session.commit()
        TX_CREATED.labels(tx.kind).inc()
        log_action(current_user.id, "transaction_add", f"id={tx.id} kind={tx.kind}")
        flash(f"{tx.kind.capitalize()} of {money(tx.amount, current_user.currency)} saved.", "success")
        return redirect(_back())
    if request.method == "POST":
        flash("Please fix the highlighted fields.", "danger")
    return render_template("transactions/form.html", **_form_context(form, title="New transaction"))


@bp.route("/<int:tx_id>/edit", methods=["GET", "POST"])
@login_required
def edit(tx_id):
    tx = svc.owned_or_none(Transaction, tx_id, current_user.id) or abort(404)
    form = _bind_choices(TransactionForm(obj=tx))
    if form.validate_on_submit() and _kind_matches(form):
        form.populate_obj(tx)
        tx.description = (tx.description or "").strip()
        tx.notes = (tx.notes or "").strip() or None
        db.session.commit()
        log_action(current_user.id, "transaction_edit", f"id={tx.id}")
        flash("Transaction updated.", "success")
        return redirect(_back())
    return render_template("transactions/form.html", **_form_context(form, title="Edit transaction", tx=tx))


@bp.post("/<int:tx_id>/delete")
@login_required
def delete(tx_id):
    tx = svc.owned_or_none(Transaction, tx_id, current_user.id) or abort(404)
    db.session.delete(tx)
    db.session.commit()
    log_action(current_user.id, "transaction_delete", f"id={tx_id}")
    flash("Transaction deleted.", "info")
    return redirect(_back())


@bp.get("/export.csv")
@login_required
def export_csv():
    """Download the currently filtered transactions as CSV."""
    f = svc.TxFilters.from_args(request.args)
    rows = svc.filtered_query(current_user.id, f).options(
        joinedload(Transaction.category), joinedload(Transaction.account)).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Type", "Amount", "Category", "Account", "Payment method", "Description", "Notes"])
    for t in rows:
        w.writerow([t.date.isoformat(), t.kind, f"{t.amount:.2f}", t.category.name, t.account.name,
                    t.payment_method, t.description, t.notes or ""])
    log_action(current_user.id, "export_csv", f"rows={len(rows)}")
    filename = f"transactions-{date.today().isoformat()}.csv"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})
