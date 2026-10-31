from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.forms import LoginForm, RegisterForm
from app.models import User, utcnow
from app.services.audit import log_action
from app.services.onboarding import setup_new_user

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next():
    nxt = request.args.get("next", "")
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else None


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(name=form.name.data.strip(), email=form.email.data.strip().lower(),
                    currency=current_app.config["DEFAULT_CURRENCY"])
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        setup_new_user(user)
        log_action(user.id, "register")
        login_user(user)
        flash(f"Welcome aboard, {user.first_name}! We've set up starter categories and accounts for you.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active_user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            user.last_login_at = utcnow()
            db.session.commit()
            log_action(user.id, "login")
            return redirect(_safe_next() or url_for("dashboard.index"))
        log_action(user.id if user else None, "login_failed", form.email.data.strip().lower())
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    log_action(current_user.id, "logout")
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
