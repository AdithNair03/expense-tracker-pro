from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import CategoryForm
from app.models import Category, Transaction
from app.services.audit import log_action
from app.services.transactions import owned_or_none

bp = Blueprint("categories", __name__, url_prefix="/categories")

ICON_CHOICES = [
    "bi-cup-hot", "bi-basket", "bi-bus-front", "bi-car-front", "bi-fuel-pump", "bi-house-door", "bi-lightning-charge",
    "bi-wifi", "bi-phone", "bi-bag", "bi-heart-pulse", "bi-capsule", "bi-film", "bi-controller", "bi-music-note-beamed",
    "bi-mortarboard", "bi-book", "bi-airplane", "bi-arrow-repeat", "bi-gift", "bi-briefcase", "bi-laptop",
    "bi-graph-up-arrow", "bi-wallet2", "bi-piggy-bank", "bi-scissors", "bi-tree", "bi-emoji-smile", "bi-tag",
    "bi-three-dots",
]


@bp.get("/")
@login_required
def index():
    usage = dict(
        db.session.query(Transaction.category_id, func.count(Transaction.id))
        .filter(Transaction.user_id == current_user.id).group_by(Transaction.category_id).all()
    )
    cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
    return render_template("categories/index.html",
                           expense=[c for c in cats if c.kind == "expense"],
                           income=[c for c in cats if c.kind == "income"], usage=usage)


def _save(form, cat, verb):
    form.populate_obj(cat)
    cat.name = cat.name.strip()
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        form.name.errors.append("A category with that name already exists.")
        return False
    log_action(current_user.id, f"category_{verb}", f"id={cat.id}")
    flash(f"Category '{cat.name}' saved.", "success")
    return True


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = CategoryForm()
    if request.method == "GET" and request.args.get("kind") in ("expense", "income"):
        form.kind.data = request.args["kind"]
    if form.validate_on_submit():
        cat = Category(user_id=current_user.id)
        db.session.add(cat)
        if _save(form, cat, "create"):
            return redirect(url_for("categories.index"))
    return render_template("categories/form.html", form=form, title="New category", icons=ICON_CHOICES)


@bp.route("/<int:cat_id>/edit", methods=["GET", "POST"])
@login_required
def edit(cat_id):
    cat = owned_or_none(Category, cat_id, current_user.id) or abort(404)
    form = CategoryForm(obj=cat)
    if cat.transactions.count():
        form.kind.render_kw = {"disabled": True}
        form.kind.data = cat.kind
    if form.validate_on_submit():
        if cat.transactions.count():
            form.kind.data = cat.kind
        if _save(form, cat, "update"):
            return redirect(url_for("categories.index"))
    return render_template("categories/form.html", form=form, title="Edit category", cat=cat, icons=ICON_CHOICES)


@bp.post("/<int:cat_id>/delete")
@login_required
def delete(cat_id):
    cat = owned_or_none(Category, cat_id, current_user.id) or abort(404)
    if cat.transactions.count():
        flash(f"'{cat.name}' is used by {cat.transactions.count()} transaction(s), so it can't be deleted.", "warning")
        return redirect(url_for("categories.index"))
    db.session.delete(cat)
    db.session.commit()
    log_action(current_user.id, "category_delete", f"id={cat_id}")
    flash("Category deleted.", "info")
    return redirect(url_for("categories.index"))
