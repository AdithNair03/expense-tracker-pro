"""Application factory: builds and configures the Flask app."""
import logging
import time

from flask import Flask, g, render_template, request
from flask_login import current_user
from prometheus_client import Counter, Histogram

from app.extensions import csrf, db, limiter, login_manager, migrate
from config import config_by_name

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency in seconds", ["endpoint"])

# All assets are self-hosted (app/static/vendor), so the policy only allows our own origin.
# 'unsafe-inline' covers small page scripts; 'unsafe-eval' is required by Alpine.js expressions.
CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)


def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    logging.basicConfig(level=app.config.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app import models  # noqa: F401  (registers tables with SQLAlchemy)

    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_handlers(app)
    _register_metrics_and_headers(app)

    from app.cli import register_cli
    register_cli(app)
    return app


def _register_blueprints(app):
    from app.modules.accounts import bp as accounts_bp
    from app.modules.auth import bp as auth_bp
    from app.modules.budgets import bp as budgets_bp
    from app.modules.categories import bp as categories_bp
    from app.modules.dashboard import bp as dashboard_bp
    from app.modules.goals import bp as goals_bp
    from app.modules.health import bp as health_bp
    from app.modules.recurring import bp as recurring_bp
    from app.modules.settings import bp as settings_bp
    from app.modules.transactions import bp as transactions_bp
    from app.modules.transfers import bp as transfers_bp

    for bp in (health_bp, auth_bp, dashboard_bp, transactions_bp, accounts_bp, categories_bp, settings_bp,
               budgets_bp, goals_bp, recurring_bp, transfers_bp):
        app.register_blueprint(bp)


def _register_template_helpers(app):
    from app.services.formatting import SYMBOLS, money, money_short

    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["money_short"] = money_short

    @app.context_processor
    def inject_globals():
        ctx = {"app_name": app.config["APP_NAME"], "currency_symbol": "₹"}
        if current_user.is_authenticated:
            from app.forms import TransactionForm
            from app.models import PAYMENT_METHODS
            from app.services.transactions import user_accounts, user_categories

            ctx.update(
                currency_symbol=SYMBOLS.get(current_user.currency, current_user.currency),
                qa_form=TransactionForm(formdata=None),
                qa_categories=user_categories(current_user.id),
                qa_accounts=user_accounts(current_user.id),
                qa_payment_methods=PAYMENT_METHODS,
            )
        return ctx


def _register_error_handlers(app):
    def render_error(code, title, message):
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(404)
    def not_found(_e):
        return render_error(404, "Page not found", "The page you're looking for doesn't exist or was moved.")

    @app.errorhandler(403)
    def forbidden(_e):
        return render_error(403, "Access denied", "You don't have permission to view this page.")

    @app.errorhandler(429)
    def too_many(_e):
        return render_error(429, "Slow down", "Too many requests. Please wait a moment and try again.")

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_error(500, "Something went wrong", "An unexpected error occurred. It has been logged.")


def _register_metrics_and_headers(app):
    @app.before_request
    def _start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def _after(response):
        endpoint = request.endpoint or "unknown"
        if endpoint not in ("health.metrics", "static"):
            elapsed = time.perf_counter() - getattr(g, "start", time.perf_counter())
            REQUEST_LATENCY.labels(endpoint).observe(elapsed)
            REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", CSP)
        return response
