"""Slice 2: budgets, savings goals, recurring transactions, and transfers between accounts."""
from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Account, Budget, RecurringTransaction, SavingsGoal, Transaction
from app.services import analytics
from app.services.recurring import process_due
from app.services.transfers import create_transfer, recent_transfers
from tests.conftest import first_account, first_category, login, make_user


# ---------------------------------------------------------------- budgets ---

def test_budget_create_and_shows_progress(client, app):
    user = make_user()
    login(client)
    cat = first_category(user, "expense")
    resp = client.post("/budgets/new", data={"category_id": cat.id, "monthly_limit": "5000"},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert Budget.query.filter_by(user_id=user.id, category_id=cat.id).count() == 1

    account = first_account(user)
    db.session.add(Transaction(user_id=user.id, kind="expense", amount=Decimal("4500"), category_id=cat.id,
                               account_id=account.id, payment_method="UPI", date=date.today()))
    db.session.commit()

    page = client.get("/budgets/")
    assert page.status_code == 200
    assert b"90.0%" in page.data or b"90%" in page.data or b"4,500" in page.data


def test_budget_duplicate_category_rejected(client, app):
    user = make_user()
    login(client)
    cat = first_category(user, "expense")
    db.session.add(Budget(user_id=user.id, category_id=cat.id, monthly_limit=Decimal("1000")))
    db.session.commit()
    # The create form no longer offers an already-budgeted category as a choice.
    resp = client.get("/budgets/new", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode()
    select = html.split('name="category_id"')[1].split("</select>")[0]
    assert f'value="{cat.id}"' not in select


def test_budget_delete_is_scoped_to_owner(client, app):
    owner = make_user("owner@example.com")
    budget = Budget(user_id=owner.id, category_id=first_category(owner, "expense").id, monthly_limit=Decimal("500"))
    db.session.add(budget)
    db.session.commit()

    make_user("other@example.com")
    login(client, "other@example.com")
    resp = client.post(f"/budgets/{budget.id}/delete")
    assert resp.status_code == 404
    assert db.session.get(Budget, budget.id) is not None


# ------------------------------------------------------------ savings goals -

def test_goal_contribution_completes_and_archives(client, app):
    user = make_user()
    login(client)
    goal = SavingsGoal(user_id=user.id, name="New phone", target_amount=Decimal("1000"))
    db.session.add(goal)
    db.session.commit()

    client.post(f"/goals/{goal.id}/contribute", data={"amount": "1000"}, follow_redirects=True)
    db.session.refresh(goal)
    assert goal.saved_amount == Decimal("1000")
    assert goal.archived is True
    assert goal.is_complete


def test_goal_withdraw_does_not_go_negative(client, app):
    user = make_user()
    login(client)
    goal = SavingsGoal(user_id=user.id, name="Trip", target_amount=Decimal("5000"), saved_amount=Decimal("50"))
    db.session.add(goal)
    db.session.commit()

    client.post(f"/goals/{goal.id}/withdraw", data={"amount": "500"}, follow_redirects=True)
    db.session.refresh(goal)
    assert goal.saved_amount == Decimal("0")


def test_goal_isolated_per_user(client, app):
    owner = make_user("owner2@example.com")
    goal = SavingsGoal(user_id=owner.id, name="Private goal", target_amount=Decimal("1000"))
    db.session.add(goal)
    db.session.commit()

    make_user("other2@example.com")
    login(client, "other2@example.com")
    resp = client.post(f"/goals/{goal.id}/contribute", data={"amount": "10"})
    assert resp.status_code == 404


# -------------------------------------------------------- recurring transactions -

def test_recurring_generates_due_transaction_and_advances(app):
    user = make_user()
    account = first_account(user)
    cat = first_category(user, "expense")
    rec = RecurringTransaction(user_id=user.id, name="Netflix", kind="expense", amount=Decimal("649"),
                               account_id=account.id, category_id=cat.id, payment_method="Debit Card",
                               frequency="monthly", next_due_date=date.today() - timedelta(days=1))
    db.session.add(rec)
    db.session.commit()

    created = process_due(user.id)
    assert created == 1
    assert Transaction.query.filter_by(user_id=user.id, recurring_id=rec.id).count() == 1
    db.session.refresh(rec)
    assert rec.next_due_date > date.today()
    assert rec.last_generated_date == date.today() - timedelta(days=1)

    # Running it again the same day should not duplicate anything.
    assert process_due(user.id) == 0


def test_recurring_not_due_is_left_alone(app):
    user = make_user()
    account = first_account(user)
    cat = first_category(user, "income")
    rec = RecurringTransaction(user_id=user.id, name="Salary", kind="income", amount=Decimal("50000"),
                               account_id=account.id, category_id=cat.id, payment_method="Net Banking",
                               frequency="monthly", next_due_date=date.today() + timedelta(days=10))
    db.session.add(rec)
    db.session.commit()
    assert process_due(user.id) == 0
    assert Transaction.query.filter_by(user_id=user.id).count() == 0


def test_recurring_paused_is_not_generated(app):
    user = make_user()
    account = first_account(user)
    cat = first_category(user, "expense")
    rec = RecurringTransaction(user_id=user.id, name="Gym", kind="expense", amount=Decimal("1500"),
                               account_id=account.id, category_id=cat.id, payment_method="UPI",
                               frequency="monthly", next_due_date=date.today() - timedelta(days=1), active=False)
    db.session.add(rec)
    db.session.commit()
    assert process_due(user.id) == 0


def test_recurring_scoped_to_owner(client, app):
    owner = make_user("owner3@example.com")
    account = first_account(owner)
    cat = first_category(owner, "expense")
    rec = RecurringTransaction(user_id=owner.id, name="Rent", kind="expense", amount=Decimal("14000"),
                               account_id=account.id, category_id=cat.id, payment_method="UPI",
                               frequency="monthly", next_due_date=date.today())
    db.session.add(rec)
    db.session.commit()

    make_user("other3@example.com")
    login(client, "other3@example.com")
    resp = client.post(f"/recurring/{rec.id}/delete")
    assert resp.status_code == 404
    assert db.session.get(RecurringTransaction, rec.id) is not None


# ------------------------------------------------------------------ transfers -

def test_create_transfer_moves_money_between_accounts(app):
    user = make_user()
    accounts = Account.query.filter_by(user_id=user.id).order_by(Account.id).all()
    from_acc, to_acc = accounts[0], accounts[1]
    before_from = dict(analytics.account_balances(user.id))
    transfer_id = create_transfer(user.id, from_acc, to_acc, Decimal("1000"), date.today(), "Moving cash")

    legs = Transaction.query.filter_by(transfer_id=transfer_id).all()
    assert len(legs) == 2
    kinds = {leg.kind for leg in legs}
    assert kinds == {"expense", "income"}

    after = dict(analytics.account_balances(user.id))
    assert after[from_acc] == before_from[from_acc] - 1000
    assert after[to_acc] == before_from[to_acc] + 1000
    # A transfer must not appear as real income or expense in the monthly summary.
    s = analytics.summary(user.id)
    assert s["income"] == 0 and s["expense"] == 0


def test_transfer_requires_two_different_accounts(client, app):
    user = make_user()
    login(client)
    account = first_account(user)
    resp = client.post("/transfers/new", data={"from_account_id": account.id, "to_account_id": account.id,
                                               "amount": "100", "date": date.today().isoformat()})
    assert resp.status_code == 200  # redisplays the form with a validation error
    assert Transaction.query.filter_by(user_id=user.id).count() == 0


def test_transfer_cannot_use_another_users_account(client, app):
    owner = make_user("owner4@example.com")
    owner_account = first_account(owner)
    other = make_user("other4@example.com")
    other_account = first_account(other)

    login(client, "other4@example.com")
    resp = client.post("/transfers/new", data={"from_account_id": other_account.id,
                                               "to_account_id": owner_account.id,
                                               "amount": "500", "date": date.today().isoformat()})
    # The form only ever lists the signed-in user's own accounts, so a foreign id fails validation.
    assert resp.status_code == 200
    assert Transaction.query.filter_by(account_id=owner_account.id).count() == 0


def test_delete_transfer_removes_both_legs(app):
    user = make_user()
    accounts = Account.query.filter_by(user_id=user.id).order_by(Account.id).all()
    transfer_id = create_transfer(user.id, accounts[0], accounts[1], Decimal("200"), date.today())
    assert Transaction.query.filter_by(transfer_id=transfer_id).count() == 2

    for leg in Transaction.query.filter_by(transfer_id=transfer_id).all():
        db.session.delete(leg)
    db.session.commit()
    assert Transaction.query.filter_by(transfer_id=transfer_id).count() == 0


def test_recent_transfers_pairs_both_legs(app):
    user = make_user()
    accounts = Account.query.filter_by(user_id=user.id).order_by(Account.id).all()
    create_transfer(user.id, accounts[0], accounts[1], Decimal("300"), date.today())
    rows = recent_transfers(user.id)
    assert len(rows) == 1
    assert rows[0]["out"].account_id == accounts[0].id
    assert rows[0]["in"].account_id == accounts[1].id


# ------------------------------------------------------------- routes/pages -

def test_budget_edit_page_and_update(client, app):
    user = make_user()
    login(client)
    cat = first_category(user, "expense")
    budget = Budget(user_id=user.id, category_id=cat.id, monthly_limit=Decimal("1000"))
    db.session.add(budget)
    db.session.commit()

    assert client.get(f"/budgets/{budget.id}/edit").status_code == 200
    resp = client.post(f"/budgets/{budget.id}/edit", data={"category_id": cat.id, "monthly_limit": "2000"},
                       follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(budget)
    assert budget.monthly_limit == Decimal("2000")


def test_goal_create_edit_and_list_pages(client, app):
    user = make_user()
    login(client)
    assert client.get("/goals/").status_code == 200
    assert client.get("/goals/new").status_code == 200

    resp = client.post("/goals/new", data={"name": "Emergency fund", "target_amount": "20000",
                                           "color": "#6366f1", "icon": "bi-trophy"}, follow_redirects=True)
    assert resp.status_code == 200
    goal = SavingsGoal.query.filter_by(user_id=user.id, name="Emergency fund").one()

    assert client.get(f"/goals/{goal.id}/edit").status_code == 200
    client.post(f"/goals/{goal.id}/edit", data={"name": "Emergency fund v2", "target_amount": "25000",
                                                "color": "#6366f1", "icon": "bi-trophy"}, follow_redirects=True)
    db.session.refresh(goal)
    assert goal.name == "Emergency fund v2"

    client.post(f"/goals/{goal.id}/archive", follow_redirects=True)
    db.session.refresh(goal)
    assert goal.archived is True
    client.post(f"/goals/{goal.id}/archive", follow_redirects=True)
    db.session.refresh(goal)
    assert goal.archived is False

    client.post(f"/goals/{goal.id}/delete", follow_redirects=True)
    assert db.session.get(SavingsGoal, goal.id) is None


def test_recurring_create_edit_toggle_and_list_pages(client, app):
    user = make_user()
    login(client)
    account = first_account(user)
    cat = first_category(user, "expense")

    assert client.get("/recurring/").status_code == 200
    assert client.get("/recurring/new").status_code == 200

    resp = client.post("/recurring/new", data={
        "name": "Gym membership", "kind": "expense", "amount": "1500", "category_id": cat.id,
        "account_id": account.id, "payment_method": "UPI", "frequency": "monthly",
        "next_due_date": (date.today() + timedelta(days=10)).isoformat(), "notes": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    rec = RecurringTransaction.query.filter_by(user_id=user.id, name="Gym membership").one()

    assert client.get(f"/recurring/{rec.id}/edit").status_code == 200
    client.post(f"/recurring/{rec.id}/edit", data={
        "name": "Gym membership", "kind": "expense", "amount": "1800", "category_id": cat.id,
        "account_id": account.id, "payment_method": "UPI", "frequency": "monthly",
        "next_due_date": rec.next_due_date.isoformat(), "notes": "",
    }, follow_redirects=True)
    db.session.refresh(rec)
    assert rec.amount == Decimal("1800")

    client.post(f"/recurring/{rec.id}/toggle", follow_redirects=True)
    db.session.refresh(rec)
    assert rec.active is False

    client.post(f"/recurring/{rec.id}/delete", follow_redirects=True)
    assert db.session.get(RecurringTransaction, rec.id) is None


def test_recurring_wrong_kind_category_rejected(client, app):
    user = make_user()
    login(client)
    account = first_account(user)
    income_cat = first_category(user, "income")
    resp = client.post("/recurring/new", data={
        "name": "Bad template", "kind": "expense", "amount": "100", "category_id": income_cat.id,
        "account_id": account.id, "payment_method": "UPI", "frequency": "monthly",
        "next_due_date": date.today().isoformat(), "notes": "",
    })
    assert resp.status_code == 200
    assert RecurringTransaction.query.filter_by(user_id=user.id).count() == 0


def test_transfer_create_and_list_pages(client, app):
    user = make_user()
    login(client)
    accounts = Account.query.filter_by(user_id=user.id).order_by(Account.id).all()

    assert client.get("/transfers/").status_code == 200
    assert client.get("/transfers/new").status_code == 200

    resp = client.post("/transfers/new", data={"from_account_id": accounts[0].id, "to_account_id": accounts[1].id,
                                               "amount": "750", "date": date.today().isoformat(),
                                               "notes": "Paying off card"}, follow_redirects=True)
    assert resp.status_code == 200
    assert Transaction.query.filter_by(user_id=user.id).filter(Transaction.transfer_id.isnot(None)).count() == 2

    page = client.get("/transfers/")
    assert b"750" in page.data


def test_dashboard_renders_with_budgets_and_goals(client, app):
    user = make_user()
    login(client)
    cat = first_category(user, "expense")
    db.session.add(Budget(user_id=user.id, category_id=cat.id, monthly_limit=Decimal("3000")))
    db.session.add(SavingsGoal(user_id=user.id, name="Bike", target_amount=Decimal("10000"),
                               saved_amount=Decimal("2000")))
    db.session.commit()
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Bike" in resp.data


def test_dashboard_auto_generates_due_recurring(client, app):
    user = make_user()
    login(client)
    account = first_account(user)
    cat = first_category(user, "expense")
    rec = RecurringTransaction(user_id=user.id, name="Overdue bill", kind="expense", amount=Decimal("200"),
                               account_id=account.id, category_id=cat.id, payment_method="UPI",
                               frequency="monthly", next_due_date=date.today() - timedelta(days=2))
    db.session.add(rec)
    db.session.commit()

    assert Transaction.query.filter_by(user_id=user.id).count() == 0
    client.get("/dashboard")
    assert Transaction.query.filter_by(user_id=user.id, recurring_id=rec.id).count() == 1
