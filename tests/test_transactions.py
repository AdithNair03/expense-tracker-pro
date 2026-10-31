from decimal import Decimal

from app.extensions import db
from app.models import Transaction
from tests.conftest import first_account, first_category, login, make_user, tx_data


def test_create_edit_delete_transaction(client, app):
    user = make_user()
    login(client)
    resp = client.post("/transactions/new", data=tx_data(user), follow_redirects=True)
    assert b"saved" in resp.data
    tx = Transaction.query.one()
    assert tx.amount == Decimal("250.50") and tx.kind == "expense"

    client.post(f"/transactions/{tx.id}/edit", data=tx_data(user, amount="300", description="Dinner"))
    tx = Transaction.query.one()
    assert tx.amount == Decimal("300.00") and tx.description == "Dinner"

    client.post(f"/transactions/{tx.id}/delete")
    assert Transaction.query.count() == 0


def test_income_requires_income_category(client, app):
    user = make_user()
    login(client)
    data = tx_data(user, kind="income", category_id=first_category(user, "expense").id)
    client.post("/transactions/new", data=data)
    assert Transaction.query.count() == 0
    client.post("/transactions/new", data=tx_data(user, kind="income", amount="50000"))
    assert Transaction.query.filter_by(kind="income").count() == 1


def test_invalid_amount_rejected(client, app):
    user = make_user()
    login(client)
    for bad in ["0", "-5", "abc"]:
        client.post("/transactions/new", data=tx_data(user, amount=bad))
    assert Transaction.query.count() == 0


def test_cannot_use_another_users_category_or_account(client, app):
    owner = make_user("owner@example.com")
    attacker = make_user("attacker@example.com")
    login(client, "attacker@example.com")
    data = tx_data(attacker, category_id=first_category(owner).id)
    client.post("/transactions/new", data=data)
    data = tx_data(attacker, account_id=first_account(owner).id)
    client.post("/transactions/new", data=data)
    assert Transaction.query.count() == 0


def test_user_cannot_see_or_modify_other_users_transactions(client, app):
    owner = make_user("owner@example.com")
    make_user("other@example.com")
    tx = Transaction(user_id=owner.id, account_id=first_account(owner).id, category_id=first_category(owner).id,
                     kind="expense", amount=100, description="top-secret-purchase")
    db.session.add(tx)
    db.session.commit()
    login(client, "other@example.com")
    assert client.get(f"/transactions/{tx.id}/edit").status_code == 404
    assert client.post(f"/transactions/{tx.id}/delete").status_code == 404
    assert b"top-secret-purchase" not in client.get("/transactions/").data
    assert b"top-secret-purchase" not in client.get("/transactions/export.csv").data
    assert b"top-secret-purchase" not in client.get("/dashboard").data
    assert Transaction.query.count() == 1


def test_filters_and_totals(client, app):
    user = make_user()
    login(client)
    acct = first_account(user)
    food = first_category(user)
    salary = first_category(user, "income")
    db.session.add_all([
        Transaction(user_id=user.id, account_id=acct.id, category_id=food.id, kind="expense", amount=100,
                    description="coffee beans", payment_method="UPI"),
        Transaction(user_id=user.id, account_id=acct.id, category_id=food.id, kind="expense", amount=40,
                    description="movie popcorn", payment_method="Cash"),
        Transaction(user_id=user.id, account_id=acct.id, category_id=salary.id, kind="income", amount=1000,
                    description="salary", payment_method="Net Banking"),
    ])
    db.session.commit()
    page = client.get("/transactions/?q=coffee").data
    assert b"coffee beans" in page and b"movie popcorn" not in page
    page = client.get("/transactions/?payment_method=Cash").data
    assert b"movie popcorn" in page and b"coffee beans" not in page
    page = client.get("/transactions/?kind=income").data
    assert b"salary" in page and b"coffee" not in page
    page = client.get("/transactions/").data.decode()
    assert "1,000.00" in page and "860.00" in page  # income and net


def test_csv_export(client, app):
    user = make_user()
    login(client)
    client.post("/transactions/new", data=tx_data(user, description="Exported item"))
    resp = client.get("/transactions/export.csv")
    assert resp.mimetype == "text/csv"
    text = resp.data.decode()
    assert text.splitlines()[0].startswith("Date,Type,Amount") and "Exported item" in text
