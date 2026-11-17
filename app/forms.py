"""WTForms definitions with server-side validation for every submitted form."""
from __future__ import annotations

from wtforms import (BooleanField, DecimalField, FileField, HiddenField, IntegerField,
                     PasswordField, SelectField, StringField, SubmitField, TextAreaField)
from wtforms.fields import EmailField
from wtforms.validators import (DataRequired, Email, EqualTo, Length, NumberRange,
                                Optional, Regexp, ValidationError)

from flask_wtf import FlaskForm

from .models import User

PASSWORD_RULE = Regexp(
    r"^(?=.*[A-Za-z])(?=.*\d).{8,}$",
    message="Password must be at least 8 characters and include a letter and a number.",
)

LEVEL_CHOICES = [
    ("", "Any level"), ("School", "School"), ("PUC", "PUC"), ("Diploma", "Diploma"),
    ("Engineering", "Engineering"), ("Medical", "Medical"), ("Degree", "Degree"),
    ("Competitive Exam", "Competitive Exam"), ("Other", "Other"),
]
CONDITION_CHOICES = [
    ("", "Any condition"), ("New", "New"), ("Like New", "Like New"), ("Good", "Good"),
    ("Fair", "Fair"), ("Worn", "Worn"),
]


class RegistrationForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = EmailField("Email address", validators=[DataRequired(), Email(), Length(max=190)])
    phone = StringField("Phone number", validators=[DataRequired(), Length(min=7, max=30)])
    password = PasswordField("Password", validators=[DataRequired(), PASSWORD_RULE])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    educational_qualification = StringField("Educational qualification", validators=[DataRequired(), Length(max=120)])
    institution = StringField("College / institution", validators=[DataRequired(), Length(max=180)])
    location = StringField("Location", validators=[DataRequired(), Length(max=180)])
    latitude = HiddenField("Latitude")
    longitude = HiddenField("Longitude")
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.query.filter(User.email.ilike(field.data.strip())).first():
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    email = EmailField("Email address", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class ForgotPasswordForm(FlaskForm):
    email = EmailField("Email address", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), PASSWORD_RULE])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match.")]
    )
    submit = SubmitField("Reset password")


class ProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField("Phone number", validators=[DataRequired(), Length(min=7, max=30)])
    educational_qualification = StringField("Educational qualification", validators=[Optional(), Length(max=120)])
    institution = StringField("College / institution", validators=[Optional(), Length(max=180)])
    location = StringField("Location", validators=[Optional(), Length(max=180)])
    latitude = HiddenField("Latitude")
    longitude = HiddenField("Longitude")
    bio = TextAreaField("About me", validators=[Optional(), Length(max=500)])
    profile_image = FileField("Profile photograph")
    submit = SubmitField("Save changes")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), PASSWORD_RULE])
    confirm_password = PasswordField(
        "Confirm new password", validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")]
    )
    submit = SubmitField("Change password")


class MaterialForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    author = StringField("Author", validators=[Optional(), Length(max=150)])
    subject = StringField("Subject", validators=[Optional(), Length(max=120)])
    educational_level = SelectField("Educational level", choices=LEVEL_CHOICES, validators=[Optional()])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    listing_type = SelectField(
        "Listing type",
        choices=[("sale", "Sell"), ("exchange", "Exchange"), ("donation", "Donate")],
        validators=[DataRequired()],
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=4000)])
    condition = SelectField("Condition", choices=CONDITION_CHOICES[1:], validators=[DataRequired()])
    price = DecimalField("Selling price (₹)", validators=[Optional(), NumberRange(min=0)])
    original_price = DecimalField("Original price (₹, optional)", validators=[Optional(), NumberRange(min=0)])
    location = StringField("Location", validators=[DataRequired(), Length(max=180)])
    latitude = HiddenField("Latitude")
    longitude = HiddenField("Longitude")
    contact_info = StringField("Contact information", validators=[Optional(), Length(max=180)])
    images = FileField("Photos (up to 5, 3 MB each)")
    submit = SubmitField("Publish listing")


class LibraryBookForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    author = StringField("Author", validators=[Optional(), Length(max=150)])
    subject = StringField("Subject", validators=[Optional(), Length(max=120)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=4000)])
    condition = SelectField("Condition", choices=CONDITION_CHOICES[1:], validators=[DataRequired()])
    borrowing_duration_days = IntegerField(
        "Default borrowing duration (days)", validators=[DataRequired(), NumberRange(min=1, max=90)], default=14
    )
    location = StringField("Location", validators=[DataRequired(), Length(max=180)])
    latitude = HiddenField("Latitude")
    longitude = HiddenField("Longitude")
    images = FileField("Photos (up to 5, 3 MB each)")
    submit = SubmitField("Add to library")


class ExchangeRequestForm(FlaskForm):
    message = TextAreaField("Message to the owner", validators=[Optional(), Length(max=1000)])
    offered_material_id = SelectField(
        "Book you offer (optional)", coerce=int, choices=[(0, "Nothing to add")], validators=[Optional()]
    )
    submit = SubmitField("Send exchange request")


class DonationRequestForm(FlaskForm):
    message = TextAreaField("Message to the donor", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Request this book")


class PurchaseRequestForm(FlaskForm):
    message = TextAreaField("Message to the seller", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Express purchase interest")


class BorrowRequestForm(FlaskForm):
    requested_duration_days = IntegerField(
        "How many days do you need it?", validators=[DataRequired(), NumberRange(min=1, max=90)], default=14
    )
    message = TextAreaField("Message to the owner", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Request to borrow")


class MessageForm(FlaskForm):
    body = TextAreaField("Write a message", validators=[DataRequired(), Length(max=4000)])
    submit = SubmitField("Send")


class SearchForm(FlaskForm):
    q = StringField("Search", validators=[Optional(), Length(max=150)])
    category_id = SelectField("Category", coerce=int, choices=[(0, "All categories")], validators=[Optional()])
    level = SelectField("Educational level", choices=LEVEL_CHOICES)
    condition = SelectField("Condition", choices=CONDITION_CHOICES)
    location = StringField("Location", validators=[Optional(), Length(max=180)])
    min_price = DecimalField("Min price", validators=[Optional(), NumberRange(min=0)])
    max_price = DecimalField("Max price", validators=[Optional(), NumberRange(min=0)])
    availability = SelectField(
        "Availability",
        choices=[("", "Available / Reserved"), ("available", "Available"), ("reserved", "Reserved"),
                 ("sold", "Sold"), ("unavailable", "Unavailable")],
    )
    sort = SelectField(
        "Sort by",
        choices=[("recent", "Recently added"), ("price_asc", "Price: Low to High"),
                 ("price_desc", "Price: High to Low")],
    )


class LocationForm(FlaskForm):
    location = StringField("Your location", validators=[DataRequired(), Length(max=180)])
    latitude = HiddenField("Latitude")
    longitude = HiddenField("Longitude")
    submit = SubmitField("Save location")


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=100)])
    icon = StringField("Bootstrap icon class", validators=[Optional(), Length(max=60)], default="bi-book")
    description = TextAreaField("Description", validators=[Optional(), Length(max=300)])
    submit = SubmitField("Save category")


class ReportForm(FlaskForm):
    reason = SelectField(
        "Reason",
        choices=[("Inappropriate content", "Inappropriate content"), ("Incorrect information", "Incorrect information"),
                 ("Spam or scam", "Spam or scam"), ("Offensive material", "Offensive material"),
                 ("Other", "Other")],
    )
    details = TextAreaField("Details", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Submit report")
