import pytest

from app import create_app
from app.extensions import db
from app.models import Account, Category, User
from app.services.onboarding import setup_new_user


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(email="a@example.com", password="password123", name="Test User"):
    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    setup_new_user(user)
    return user


def login(client, email="a@example.com", password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def first_category(user, kind="expense"):
    return Category.query.filter_by(user_id=user.id, kind=kind).order_by(Category.id).first()


def first_account(user):
    return Account.query.filter_by(user_id=user.id).order_by(Account.id).first()


def tx_data(user, **overrides):
    data = {
        "kind": "expense", "amount": "250.50", "description": "Lunch",
        "category_id": first_category(user, overrides.get("kind", "expense")).id,
        "account_id": first_account(user).id, "payment_method": "UPI", "date": "2026-10-01", "notes": "",
    }
    data.update(overrides)
    return data
