from app.models import Account, AuditLog, Category, User
from tests.conftest import login, make_user


def test_register_logs_in_and_sets_up_starter_data(client, app):
    resp = client.post("/auth/register", data={"name": "New Person", "email": "New@Example.com",
                                               "password": "password123", "confirm": "password123"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/dashboard")
    user = User.query.filter_by(email="new@example.com").one()
    assert user.password_hash != "password123"
    assert Category.query.filter_by(user_id=user.id, kind="expense").count() == 13
    assert Category.query.filter_by(user_id=user.id, kind="income").count() == 7
    assert Account.query.filter_by(user_id=user.id).count() == 2


def test_duplicate_email_rejected(client, app):
    make_user()
    resp = client.post("/auth/register", data={"name": "Dup", "email": "a@example.com",
                                               "password": "password123", "confirm": "password123"})
    assert b"already registered" in resp.data


def test_short_password_rejected(client, app):
    resp = client.post("/auth/register", data={"name": "X", "email": "x@example.com",
                                               "password": "short", "confirm": "short"})
    assert resp.status_code == 200 and User.query.count() == 0


def test_wrong_password_and_failed_login_audited(client, app):
    make_user()
    resp = login(client, password="wrongpass")
    assert b"Invalid email or password" in resp.data
    assert AuditLog.query.filter_by(action="login_failed").count() == 1


def test_protected_pages_redirect_to_login(client):
    for url in ["/dashboard", "/transactions/", "/accounts/", "/categories/", "/settings/"]:
        resp = client.get(url)
        assert resp.status_code == 302 and "/auth/login" in resp.headers["Location"]


def test_open_redirect_blocked(client, app):
    make_user()
    resp = client.post("/auth/login?next=//evil.com", data={"email": "a@example.com", "password": "password123"})
    assert "evil.com" not in resp.headers["Location"]


def test_logout(client, app):
    make_user()
    login(client)
    client.post("/auth/logout")
    assert client.get("/dashboard").status_code == 302
