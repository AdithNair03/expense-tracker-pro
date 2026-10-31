"""Custom `flask` commands: seed-demo, create-admin and process-recurring."""
import random
from datetime import date, timedelta
from decimal import Decimal

import click

from app.extensions import db
from app.models import Account, Budget, Category, RecurringTransaction, SavingsGoal, Transaction, User
from app.services.onboarding import setup_new_user

DEMO_EMAIL = "demo@spendwise.app"
DEMO_PASSWORD = "Demo@1234"
DEMO_NAME = "Adith Nair"


def _months_back(today, n):
    first = today.replace(day=1)
    for _ in range(n):
        first = (first - timedelta(days=1)).replace(day=1)
    return first


def generate_demo_transactions(user, today=None, months=6, seed=42):
    """Six months of realistic Indian-context transactions so every chart has data on demo day."""
    rnd = random.Random(seed)
    today = today or date.today()
    cats = {c.name: c for c in Category.query.filter_by(user_id=user.id)}
    accts = {a.name: a for a in Account.query.filter_by(user_id=user.id)}
    bank, cash, card, upi = accts["HDFC Bank"], accts["Cash"], accts["ICICI Credit Card"], accts["Paytm UPI"]
    rows = []

    def add(kind, amount, cat, acct, method, day, desc):
        if day <= today:
            rows.append(Transaction(user_id=user.id, kind=kind, amount=Decimal(str(round(amount, 2))),
                                    category_id=cats[cat].id, account_id=acct.id, payment_method=method,
                                    date=day, description=desc))

    start = _months_back(today, months - 1)
    m = start
    while m <= today:
        is_current = (m.year, m.month) == (today.year, today.month)
        nxt = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        days = (nxt - m).days

        def d(n):
            return m + timedelta(days=min(n, days) - 1)

        add("income", 52000, "Salary", bank, "Net Banking", d(1), "Monthly salary - Acme Analytics")
        if rnd.random() < 0.7:
            add("income", rnd.choice([4500, 6000, 8500, 12000]), "Freelance", bank, "UPI", d(rnd.randint(8, 25)),
                rnd.choice(["Logo design client", "Website fix - local cafe", "Data cleaning gig", "Tutoring"]))
        add("expense", 14000, "Rent & Housing", bank, "Net Banking", d(5), "Flat rent")
        add("expense", rnd.randint(1100, 1900), "Bills & Utilities", bank, "UPI", d(10), "Electricity bill - KSEB")
        add("expense", 699, "Bills & Utilities", bank, "UPI", d(12), "Jio Fiber")
        add("expense", 299, "Bills & Utilities", upi, "Wallet", d(14), "Mobile recharge")
        add("expense", 649, "Subscriptions", bank, "Debit Card", d(3), "Netflix")
        add("expense", 119, "Subscriptions", bank, "Debit Card", d(7), "Spotify")
        for week in range(4):
            add("expense", rnd.randint(900, 2400), "Groceries", bank, "UPI", d(2 + week * 7 + rnd.randint(0, 3)),
                rnd.choice(["BigBasket order", "Reliance Fresh", "More Supermarket", "Zepto groceries"]))
        food_n = rnd.randint(9, 13) + (5 if is_current else 0)
        for _ in range(food_n):
            acct, method = rnd.choice([(bank, "UPI"), (bank, "UPI"), (bank, "UPI"),
                                       (card, "Credit Card") if is_current else (bank, "Debit Card")])
            add("expense", rnd.randint(140, 950), "Food & Dining", acct, method, d(rnd.randint(1, days)),
                rnd.choice(["Swiggy - biryani", "Zomato - pizza", "Cafe Coffee Day", "Dinner with friends",
                            "Chai & snacks", "Lunch at office canteen", "Burger King"]))
        for _ in range(rnd.randint(10, 16)):
            acct, method = rnd.choice([(bank, "UPI"), (bank, "UPI"), (cash, "Cash")])
            add("expense", rnd.randint(40, 320), "Transport", acct, method,
                d(rnd.randint(1, days)), rnd.choice(["Uber", "Ola auto", "Metro card top-up", "Rapido bike", "Bus"]))
        add("expense", rnd.randint(1800, 2600), "Transport", bank, "Debit Card", d(rnd.randint(15, 20)), "Petrol")
        for _ in range(rnd.randint(1, 3)):
            add("expense", rnd.randint(600, 4200), "Shopping", card if is_current else bank,
                "Credit Card" if is_current else "Debit Card", d(rnd.randint(1, days)),
                rnd.choice(["Amazon order", "Myntra - clothes", "Decathlon", "Flipkart - headphones"]))
        if rnd.random() < 0.8:
            add("expense", rnd.randint(350, 1400), "Entertainment", bank, "UPI", d(rnd.randint(1, days)),
                rnd.choice(["PVR movie tickets", "Bowling night", "Concert entry", "Steam game"]))
        if rnd.random() < 0.4:
            add("expense", rnd.randint(250, 2200), "Health", bank, "UPI", d(rnd.randint(1, days)),
                rnd.choice(["Apollo Pharmacy", "Doctor consultation", "Gym supplement"]))
        if rnd.random() < 0.3:
            add("expense", rnd.choice([449, 1299, 3499]), "Education", bank, "Debit Card", d(rnd.randint(1, days)),
                rnd.choice(["Udemy - DevOps course", "Books", "Coursera certificate"]))
        if (m.year, m.month) == (_months_back(today, 2).year, _months_back(today, 2).month):
            add("expense", 7800, "Travel", bank, "Debit Card", d(18), "Flight to Kochi")
            add("expense", 5400, "Travel", bank, "UPI", d(19), "Munnar homestay")
        add("expense", 5000, "Other", bank, "Net Banking", d(2), "SIP - index fund")
        m = nxt

    db.session.add_all(rows)
    db.session.commit()
    return len(rows)


def seed_budgets_goals_recurring(user):
    """Give the demo account a few budgets, a savings goal and recurring items, so Slice 2
    features look lived-in instead of empty on first login."""
    cats = {c.name: c for c in Category.query.filter_by(user_id=user.id, kind="expense")}
    accts = {a.name: a for a in Account.query.filter_by(user_id=user.id)}
    today = date.today()

    for name, limit in [("Food & Dining", 9000), ("Groceries", 6000), ("Shopping", 5000),
                        ("Entertainment", 2500), ("Transport", 3500)]:
        if name in cats:
            db.session.add(Budget(user_id=user.id, category_id=cats[name].id, monthly_limit=Decimal(limit)))

    db.session.add(SavingsGoal(user_id=user.id, name="Emergency fund top-up", target_amount=Decimal(100000),
                               saved_amount=Decimal(60000), target_date=today.replace(year=today.year + 1),
                               color="#f59e0b", icon="bi-piggy-bank"))
    db.session.add(SavingsGoal(user_id=user.id, name="New laptop", target_amount=Decimal(85000),
                               saved_amount=Decimal(22000), target_date=today + timedelta(days=150),
                               color="#6366f1", icon="bi-laptop"))

    income_cats = {c.name: c for c in Category.query.filter_by(user_id=user.id, kind="income")}
    bank = accts.get("HDFC Bank")
    if bank:
        db.session.add(RecurringTransaction(
            user_id=user.id, name="Monthly salary", kind="income", amount=Decimal(52000), account_id=bank.id,
            category_id=income_cats["Salary"].id, payment_method="Net Banking", frequency="monthly",
            next_due_date=today.replace(day=1) + timedelta(days=32)))
        db.session.add(RecurringTransaction(
            user_id=user.id, name="Flat rent", kind="expense", amount=Decimal(14000), account_id=bank.id,
            category_id=cats["Rent & Housing"].id, payment_method="Net Banking", frequency="monthly",
            next_due_date=today.replace(day=1) + timedelta(days=35)))
        db.session.add(RecurringTransaction(
            user_id=user.id, name="Netflix", kind="expense", amount=Decimal(649), account_id=bank.id,
            category_id=cats["Subscriptions"].id, payment_method="Debit Card", frequency="monthly",
            next_due_date=today + timedelta(days=3)))
    db.session.commit()


def register_cli(app):
    @app.cli.command("seed-demo")
    @click.option("--reset", is_flag=True, help="Delete and recreate the demo user first.")
    def seed_demo(reset):
        """Create a demo user with 6 months of realistic data."""
        user = User.query.filter_by(email=DEMO_EMAIL).first()
        if user and not reset:
            click.echo(f"Demo user already exists ({DEMO_EMAIL}). Use --reset to recreate it.")
            return
        if user:
            db.session.delete(user)
            db.session.commit()
        user = User(name=DEMO_NAME, email=DEMO_EMAIL, currency="INR")
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.commit()
        setup_new_user(user, with_accounts=False)
        for name, typ, opening, color in [
            ("HDFC Bank", "bank", 38000, "#6366f1"), ("Cash", "cash", 6500, "#10b981"),
            ("ICICI Credit Card", "card", 0, "#f43f5e"), ("Paytm UPI", "wallet", 2500, "#0ea5e9"),
            ("Emergency Fund", "savings", 60000, "#f59e0b"),
        ]:
            db.session.add(Account(user_id=user.id, name=name, type=typ, opening_balance=opening, color=color))
        db.session.commit()
        n = generate_demo_transactions(user)
        seed_budgets_goals_recurring(user)
        click.echo(f"Demo ready: {DEMO_EMAIL} / {DEMO_PASSWORD} ({n} transactions)")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option()
    def create_admin(email, name, password):
        """Create an admin user (admin panel arrives in a later slice)."""
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            raise click.ClickException("A user with that email already exists.")
        user = User(name=name.strip(), email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        setup_new_user(user)
        click.echo(f"Admin {email} created.")

    @app.cli.command("process-recurring")
    def process_recurring_cmd():
        """Generate any recurring transactions that are now due, for every user.

        Runs automatically when a user opens their dashboard, but this command lets a
        scheduler (cron, or later a Kubernetes CronJob) run it independently of a page view.
        """
        from app.services.recurring import process_due
        n = process_due()
        click.echo(f"Generated {n} transaction(s) from recurring templates.")
