from datetime import date

from app.cli import DEMO_EMAIL
from app.extensions import db
from app.models import Transaction, User
from app.services.formatting import money, money_short
from tests.conftest import first_account, first_category, login, make_user


def test_health_and_metrics(client):
    assert client.get("/health/live").get_json() == {"status": "ok"}
    assert client.get("/health/ready").get_json()["database"] == "up"
    body = client.get("/metrics").data.decode()
    assert "http_requests_total" in body


def test_security_headers(client):
    resp = client.get("/auth/login")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def test_dashboard_shows_real_numbers(client, app):
    user = make_user()
    login(client)
    db.session.add_all([
        Transaction(user_id=user.id, account_id=first_account(user).id, category_id=first_category(user).id,
                    kind="expense", amount=1234.5, date=date.today(), description="Big dinner"),
        Transaction(user_id=user.id, account_id=first_account(user).id,
                    category_id=first_category(user, "income").id, kind="income", amount=50000, date=date.today()),
    ])
    db.session.commit()
    page = client.get("/dashboard").data.decode()
    assert "₹1,235" in page and "₹50,000" in page and "Big dinner" in page


def test_empty_dashboard_renders(client, app):
    make_user()
    login(client)
    assert b"No transactions yet" in client.get("/dashboard").data


def test_custom_404(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404 and b"Page not found" in resp.data


def test_money_formatting():
    assert money(123456.5) == "₹1,23,456.50"
    assert money(1234567, "USD", 0) == "$1,234,567"
    assert money(-50) == "-₹50.00"
    assert money_short(250000) == "₹2.50L"


def test_seed_demo_command(app):
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert "Demo ready" in result.output
    user = User.query.filter_by(email=DEMO_EMAIL).one()
    assert Transaction.query.filter_by(user_id=user.id).count() > 150
