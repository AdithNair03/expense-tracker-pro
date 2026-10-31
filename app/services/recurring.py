"""Generates real transactions from due recurring templates.

Called lazily on dashboard load (so a plain `flask run` behaves correctly), and
also exposed as `flask process-recurring` so a scheduler (cron, a Kubernetes
CronJob once the app is deployed) can run it independently of any page view.
"""
from datetime import date

from app.extensions import db
from app.models import RecurringTransaction, Transaction


def process_due(user_id=None, today=None):
    """Generate every transaction that is now due. Returns how many were created."""
    today = today or date.today()
    q = RecurringTransaction.query.filter(RecurringTransaction.active.is_(True),
                                          RecurringTransaction.next_due_date <= today)
    if user_id is not None:
        q = q.filter(RecurringTransaction.user_id == user_id)

    created = 0
    for rec in q.all():
        # A recurring item can be overdue by more than one period (e.g. the app
        # wasn't opened for a while) - catch it up fully, one transaction per period.
        guard = 0
        while rec.next_due_date <= today and guard < 36:
            db.session.add(Transaction(
                user_id=rec.user_id, kind=rec.kind, amount=rec.amount, account_id=rec.account_id,
                category_id=rec.category_id, payment_method=rec.payment_method, date=rec.next_due_date,
                description=rec.name, notes=rec.notes, recurring_id=rec.id,
            ))
            rec.last_generated_date = rec.next_due_date
            rec.advance()
            created += 1
            guard += 1
    if created:
        db.session.commit()
    return created
