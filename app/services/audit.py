from flask import has_request_context, request

from app.extensions import db
from app.models import AuditLog


def log_action(user_id, action, detail=""):
    ip = request.remote_addr if has_request_context() else None
    db.session.add(AuditLog(user_id=user_id, action=action, detail=(detail or "")[:255], ip=ip))
    db.session.commit()
