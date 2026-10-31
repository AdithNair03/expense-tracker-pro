"""Liveness/readiness probes for Kubernetes and the Prometheus /metrics endpoint."""
from flask import Blueprint, Response, jsonify
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.extensions import csrf, db, limiter

bp = Blueprint("health", __name__)


@bp.get("/health/live")
@limiter.exempt
def live():
    return jsonify(status="ok")


@bp.get("/health/ready")
@limiter.exempt
def ready():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        return jsonify(status="unavailable", database="down"), 503
    return jsonify(status="ready", database="up")


@bp.get("/metrics")
@limiter.exempt
@csrf.exempt
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
