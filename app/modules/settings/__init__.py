from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import PasswordForm, ProfileForm
from app.models import AuditLog
from app.services.audit import log_action

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    profile = ProfileForm(obj=current_user, prefix="p")
    password = PasswordForm(prefix="pw")
    if profile.submit.data and profile.validate_on_submit():
        profile.populate_obj(current_user)
        db.session.commit()
        log_action(current_user.id, "profile_update")
        flash("Profile saved.", "success")
        return redirect(url_for("settings.index"))
    if password.submit.data and password.validate_on_submit():
        if not current_user.check_password(password.current.data):
            password.current.errors.append("Current password is incorrect.")
        else:
            current_user.set_password(password.new.data)
            db.session.commit()
            log_action(current_user.id, "password_change")
            flash("Password changed.", "success")
            return redirect(url_for("settings.index"))
    activity = (AuditLog.query.filter_by(user_id=current_user.id)
                .order_by(AuditLog.created_at.desc()).limit(8).all())
    return render_template("settings/index.html", profile=profile, password=password, activity=activity)


@bp.post("/theme")
@login_required
def theme():
    """Called by the sidebar toggle (fetch with X-CSRFToken header)."""
    value = (request.get_json(silent=True) or {}).get("theme")
    if value not in ("light", "dark"):
        return jsonify(error="invalid theme"), 400
    current_user.theme = value
    db.session.commit()
    return jsonify(theme=value)
