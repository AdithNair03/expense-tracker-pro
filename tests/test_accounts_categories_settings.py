from app.extensions import db
from app.models import Account, Category, User
from app.services.analytics import account_balances
from tests.conftest import first_account, first_category, login, make_user, tx_data


def test_account_balance_is_opening_plus_income_minus_expense(client, app):
    user = make_user()
    login(client)
    client.post("/accounts/new",
                data={"name": "Wallet", "type": "wallet", "opening_balance": "1000", "color": "#123456"})
    wallet = Account.query.filter_by(name="Wallet").one()
    client.post("/transactions/new", data=tx_data(user, account_id=wallet.id, amount="300"))
    client.post("/transactions/new", data=tx_data(user, account_id=wallet.id, amount="500", kind="income"))
    balances = {a.name: b for a, b in account_balances(user.id)}
    assert balances["Wallet"] == 1200


def test_account_with_transactions_cannot_be_deleted_but_can_be_archived(client, app):
    user = make_user()
    login(client)
    client.post("/transactions/new", data=tx_data(user))
    acct = first_account(user)
    client.post(f"/accounts/{acct.id}/delete")
    assert db.session.get(Account, acct.id) is not None
    client.post(f"/accounts/{acct.id}/archive")
    assert db.session.get(Account, acct.id).archived is True


def test_category_crud_and_in_use_protection(client, app):
    user = make_user()
    login(client)
    client.post("/categories/new", data={"name": "Coffee", "kind": "expense", "color": "#aa5500", "icon": "bi-cup-hot"})
    coffee = Category.query.filter_by(name="Coffee").one()
    client.post(f"/categories/{coffee.id}/edit", data={"name": "Cafes", "kind": "expense", "color": "#aa5500",
                                                       "icon": "bi-cup-hot"})
    assert db.session.get(Category, coffee.id).name == "Cafes"
    client.post("/transactions/new", data=tx_data(user, category_id=coffee.id))
    client.post(f"/categories/{coffee.id}/delete")
    assert db.session.get(Category, coffee.id) is not None
    empty = first_category(user, "income")
    client.post(f"/categories/{empty.id}/delete")
    assert db.session.get(Category, empty.id) is None


def test_bad_colour_rejected(client, app):
    make_user()
    login(client)
    client.post("/categories/new", data={"name": "X", "kind": "expense", "color": "red;}", "icon": "bi-tag"})
    assert Category.query.filter_by(name="X").count() == 0


def test_other_users_account_is_404(client, app):
    owner = make_user("owner@example.com")
    make_user("other@example.com")
    login(client, "other@example.com")
    assert client.get(f"/accounts/{first_account(owner).id}/edit").status_code == 404
    assert client.get(f"/categories/{first_category(owner).id}/edit").status_code == 404


def test_profile_theme_and_password(client, app):
    make_user()
    login(client)
    client.post("/settings/", data={"p-name": "Renamed", "p-currency": "USD", "p-theme": "dark", "p-submit": "1"})
    user = User.query.one()
    assert user.name == "Renamed" and user.currency == "USD" and user.theme == "dark"
    assert client.post("/settings/theme", json={"theme": "light"}).get_json() == {"theme": "light"}
    assert client.post("/settings/theme", json={"theme": "pink"}).status_code == 400
    client.post("/settings/", data={"pw-current": "password123", "pw-new": "newpassword1",
                                    "pw-confirm": "newpassword1", "pw-submit": "1"})
    assert User.query.one().check_password("newpassword1")
