"""All WTForms in one place. Every field is validated server-side."""
from datetime import date

from flask_wtf import FlaskForm
from wtforms import (BooleanField, DateField, DecimalField, PasswordField, RadioField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError

from app.models import ACCOUNT_TYPES, CURRENCIES, PAYMENT_METHODS, RECURRING_FREQUENCIES, User

HEX = Regexp(r"^#[0-9a-fA-F]{6}$", message="Use a colour like #6366f1.")


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("Confirm password",
                            validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("That email is already registered.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")


class TransactionForm(FlaskForm):
    kind = RadioField("Type", choices=[("expense", "Expense"), ("income", "Income")], default="expense")
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01, max=99999999)])
    description = StringField("Description", validators=[Length(max=255)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    account_id = SelectField("Account", coerce=int, validators=[DataRequired()])
    payment_method = SelectField("Payment method", choices=[(m, m) for m in PAYMENT_METHODS])
    date = DateField("Date", default=date.today, validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Save transaction")


class AccountForm(FlaskForm):
    name = StringField("Account name", validators=[DataRequired(), Length(max=60)])
    type = SelectField("Type", choices=[(k, v[0]) for k, v in ACCOUNT_TYPES.items()])
    opening_balance = DecimalField("Opening balance", places=2, default=0,
                                   validators=[Optional(), NumberRange(min=-99999999, max=99999999)])
    color = StringField("Colour", default="#6366f1", validators=[DataRequired(), HEX])
    submit = SubmitField("Save account")


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    kind = SelectField("Type", choices=[("expense", "Expense"), ("income", "Income")])
    color = StringField("Colour", default="#6366f1", validators=[DataRequired(), HEX])
    icon = StringField("Icon", default="bi-tag",
                       validators=[DataRequired(), Regexp(r"^bi-[a-z0-9-]+$", message="Pick an icon.")])
    submit = SubmitField("Save category")


class ProfileForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(max=80)])
    currency = SelectField("Currency", choices=[(c, c) for c in CURRENCIES])
    theme = SelectField("Theme", choices=[("light", "Light"), ("dark", "Dark")])
    submit = SubmitField("Save profile")


class PasswordForm(FlaskForm):
    current = PasswordField("Current password", validators=[DataRequired()])
    new = PasswordField("New password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField("Confirm new password",
                            validators=[DataRequired(), EqualTo("new", message="Passwords must match.")])
    submit = SubmitField("Change password")


class BudgetForm(FlaskForm):
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    monthly_limit = DecimalField("Monthly limit", places=2,
                                 validators=[DataRequired(), NumberRange(min=1, max=99999999)])
    submit = SubmitField("Save budget")


class SavingsGoalForm(FlaskForm):
    name = StringField("Goal name", validators=[DataRequired(), Length(max=80)])
    target_amount = DecimalField("Target amount", places=2,
                                 validators=[DataRequired(), NumberRange(min=1, max=99999999)])
    target_date = DateField("Target date", validators=[Optional()])
    color = StringField("Colour", default="#6366f1", validators=[DataRequired(), HEX])
    icon = StringField("Icon", default="bi-trophy",
                       validators=[DataRequired(), Regexp(r"^bi-[a-z0-9-]+$", message="Pick an icon.")])
    submit = SubmitField("Save goal")


class GoalContributionForm(FlaskForm):
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01, max=99999999)])
    note = StringField("Note", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Save")


class RecurringForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=80)])
    kind = RadioField("Type", choices=[("expense", "Expense"), ("income", "Income")], default="expense")
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01, max=99999999)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    account_id = SelectField("Account", coerce=int, validators=[DataRequired()])
    payment_method = SelectField("Payment method", choices=[(m, m) for m in PAYMENT_METHODS])
    frequency = SelectField("Frequency", choices=list(RECURRING_FREQUENCIES.items()), default="monthly")
    next_due_date = DateField("Next due date", default=date.today, validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Save recurring transaction")


class TransferForm(FlaskForm):
    from_account_id = SelectField("From account", coerce=int, validators=[DataRequired()])
    to_account_id = SelectField("To account", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount", places=2, validators=[DataRequired(), NumberRange(min=0.01, max=99999999)])
    date = DateField("Date", default=date.today, validators=[DataRequired()])
    notes = StringField("Note", validators=[Optional(), Length(max=200)])
    submit = SubmitField("Transfer")

    def validate_to_account_id(self, field):
        if self.from_account_id.data and field.data == self.from_account_id.data:
            raise ValidationError("Pick two different accounts.")
