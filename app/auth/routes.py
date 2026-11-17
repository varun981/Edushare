"""Registration, login, logout and password recovery."""
from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db, limiter
from ..forms import (ForgotPasswordForm, LoginForm, RegistrationForm, ResetPasswordForm)
from ..models import User
from ..utils import (flash_form_errors, generate_reset_token, safe_next_url,
                     send_reset_email, verify_reset_token)
from . import bp


def _coordinates_from_form(form) -> tuple[float | None, float | None]:
    def parse(value):
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None
    return parse(form.latitude.data), parse(form.longitude.data)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter(User.email.ilike(email)).first():
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for("auth.login"))
        latitude, longitude = _coordinates_from_form(form)
        user = User(
            full_name=form.full_name.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            educational_qualification=form.educational_qualification.data.strip(),
            institution=form.institution.data.strip(),
            location=form.location.data.strip(),
            latitude=latitude,
            longitude=longitude,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash("Welcome to EduShare! Your account has been created.", "success")
        return redirect(safe_next_url(request.args.get("next")))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("register.html", form=form, title="Create your account")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("8 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(User.email.ilike(form.email.data.strip())).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember.data)
            flash(f"Welcome back, {user.display_name}!", "success")
            return redirect(safe_next_url(request.args.get("next")))
        flash("Invalid email or password, or your account is suspended.", "danger")
    elif request.method == "POST":
        flash_form_errors(form)
    return render_template("login.html", form=form, title="Log in to EduShare")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out safely.", "info")
    return redirect(url_for("main.index"))


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = ForgotPasswordForm()
    reset_link = None
    generic_message = "If that email is registered, a reset link has been sent."
    if form.validate_on_submit():
        user = User.query.filter(User.email.ilike(form.email.data.strip())).first()
        if user:
            token = generate_reset_token(user)
            emailed = send_reset_email(user, token)
            # Never expose a live reset token in production. Local development
            # and the test suite may show it when SMTP is intentionally absent.
            if not emailed and (current_app.debug or current_app.config.get("TESTING")):
                reset_link = url_for("auth.reset_password", token=token, _external=True)
                flash("Email delivery is not configured here. Use the secure reset link below "
                      "(valid for one hour).", "warning")
            else:
                flash(generic_message, "info")
        else:
            # Do not disclose whether an account exists.
            flash(generic_message, "info")
    elif request.method == "POST":
        flash_form_errors(form)
    return render_template("forgot_password.html", form=form, reset_link=reset_link,
                           title="Forgot your password?")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    user = verify_reset_token(token)
    if not user:
        flash("This reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been updated. You can now log in.", "success")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("reset_password.html", form=form, title="Choose a new password")
