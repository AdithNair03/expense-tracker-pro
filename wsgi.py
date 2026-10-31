"""Entry point for `flask run` (via FLASK_APP=wsgi.py) and gunicorn (wsgi:app)."""
import os

from app import create_app

app = create_app(os.environ.get("FLASK_CONFIG", "development"))
