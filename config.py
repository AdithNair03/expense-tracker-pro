"""Application configuration.

Every value comes from environment variables (or a local .env file), so the same
code runs on a laptop, in Docker, in Kubernetes and on AWS without edits.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


def _build_db_uri():
    """DATABASE_URL wins; otherwise assemble a MySQL URL from DB_*; otherwise local SQLite."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("DB_HOST")
    if host:
        user = os.environ.get("DB_USER", "expense")
        password = os.environ.get("DB_PASSWORD", "")
        name = os.environ.get("DB_NAME", "expense_tracker")
        port = os.environ.get("DB_PORT", "3306")
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
    return "sqlite:///" + os.path.join(basedir, "dev.sqlite3")


class Config:
    APP_NAME = "Spendwise"
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-change-me"
    SQLALCHEMY_DATABASE_URI = _build_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = "600 per hour"

    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "INR")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    WTF_CSRF_TIME_LIMIT = None
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    SHOW_DEMO_LOGIN = os.environ.get("SHOW_DEMO_LOGIN", "1") == "1"


class DevelopmentConfig(Config):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SECRET_KEY = "test-secret"


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
