"""User profile, account settings and personal activity history."""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import ChangePasswordForm, ProfileForm
from ..models import (BorrowingRecord, DonationRequest, EducationalMaterial,
                      ExchangeRequest, LibraryBook, PurchaseRequest, User)
from ..utils import (flash_form_errors, get_or_404, parse_optional_float,
                     remove_image, save_images)
from . import bp


@bp.route("/")
@login_required
def profile():
    user = current_user
    return render_template(
        "profile.html", title="My profile", profile=user, is_own=True,
        my_materials=user.materials,
        my_library_books=user.library_books,
        my_exchange_requests=user.exchange_requests_sent,
        my_donation_requests=user.donation_requests_sent,
        my_purchase_requests=user.purchase_requests_sent,
        my_borrowings=user.borrowings,
        my_lendings=user.lendings,
    )


@bp.route("/<int:user_id>")
def public_profile(user_id):
    user = get_or_404(User, user_id)
    if not user.is_active:
        abort(404)
    materials = (EducationalMaterial.query.filter_by(user_id=user.id, status="available",
                                                     listing_type="sale")
                 .order_by(EducationalMaterial.created_at.desc()).limit(12).all())
    return render_template("profile.html", title=user.display_name, profile=user,
                           is_own=False, my_materials=materials)


@bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.phone = form.phone.data.strip()
        current_user.educational_qualification = form.educational_qualification.data or None
        current_user.institution = form.institution.data or None
        current_user.location = form.location.data or None
        current_user.bio = form.bio.data or None
        current_user.latitude = parse_optional_float(form.latitude.data)
        current_user.longitude = parse_optional_float(form.longitude.data)
        photos = save_images([form.profile_image.data] if form.profile_image.data else [],
                             "profiles", max_images=1)
        if photos:
            old = current_user.profile_image
            current_user.profile_image = photos[0]
            if old and old != "default-avatar.svg":
                remove_image(old)
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile.profile"))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("profile_form.html", title="Edit profile", form=form)


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Your current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("profile.profile"))
    elif request.method == "POST":
        flash_form_errors(form)
    return render_template("change_password.html", title="Change password", form=form)
