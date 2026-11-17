"""Free donation listings and donation request workflow."""
from __future__ import annotations

from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import DonationRequestForm, MaterialForm
from ..models import Category, DonationRequest, EducationalMaterial, utcnow
from ..utils import (Pagination, add_images, apply_material_filters, flash_form_errors,
                     get_or_404, notify, parse_optional_float, save_images)
from . import bp


def _category_choices():
    return [(c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name)]


@bp.route("/")
def donation():
    query = apply_material_filters(
        db.session.query(EducationalMaterial), request.args, listing_type="donation"
    )
    pagination = Pagination(query, per_page=12)
    my_listings = []
    sent = []
    received = []
    if current_user.is_authenticated:
        my_listings = (EducationalMaterial.query.filter_by(user_id=current_user.id, listing_type="donation")
                       .order_by(EducationalMaterial.created_at.desc()).all())
        sent = (DonationRequest.query.filter_by(requester_id=current_user.id)
                .order_by(DonationRequest.created_at.desc()).all())
        received = (DonationRequest.query.filter_by(owner_id=current_user.id)
                    .order_by(DonationRequest.created_at.desc()).all())
    return render_template(
        "donation.html", title="Free books", pagination=pagination,
        my_listings=my_listings, sent_requests=sent, received_requests=received,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_donation():
    form = MaterialForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        material = EducationalMaterial(
            user_id=current_user.id, category_id=form.category_id.data,
            title=form.title.data.strip(), author=form.author.data or None,
            subject=form.subject.data or None,
            educational_level=form.educational_level.data or None,
            listing_type="donation", description=form.description.data,
            condition=form.condition.data, price=Decimal("0"),
            location=form.location.data.strip(),
            latitude=parse_optional_float(form.latitude.data),
            longitude=parse_optional_float(form.longitude.data),
            contact_info=form.contact_info.data or None, status="available", created_at=utcnow(),
        )
        db.session.add(material)
        db.session.flush()
        add_images(save_images(request.files.getlist("images"), "listings"), material=material)
        db.session.commit()
        flash("Thank you! Your donation is now listed for the community.", "success")
        return redirect(url_for("marketplace.book_detail", material_id=material.id))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("sell_book.html", title="Donate a book", form=form,
                           material=None, listing_type="donation")


@bp.route("/<int:material_id>/request", methods=["POST"])
@login_required
def request_donation(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    if material.listing_type != "donation":
        abort(404)
    if material.user_id == current_user.id:
        flash("This is your own donation.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    if not material.is_available:
        flash("This donated book is no longer available.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    form = DonationRequestForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    if DonationRequest.query.filter_by(requester_id=current_user.id, material_id=material.id).first():
        flash("You have already requested this donated book.", "info")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    db.session.add(DonationRequest(
        requester_id=current_user.id, owner_id=material.user_id, material_id=material.id,
        message=form.message.data, status="pending", created_at=utcnow(),
    ))
    notify(material.user_id, "donation_request", "New donation request",
           f"{current_user.display_name} requested your donated book '{material.title}'.",
           url_for("donation.donation", _anchor="incoming"))
    db.session.commit()
    flash("Request sent. The donor will review it shortly.", "success")
    return redirect(url_for("donation.donation", _anchor="my-requests"))


def _owned_request(request_id):
    item = get_or_404(DonationRequest, request_id)
    if item.owner_id != current_user.id:
        abort(403)
    return item


@bp.route("/requests/<int:request_id>/approve", methods=["POST"])
@login_required
def approve_request(request_id):
    item = _owned_request(request_id)
    if item.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("donation.donation", _anchor="incoming"))
    item.status = "approved"
    item.material.status = "reserved"
    item.updated_at = utcnow()
    notify(item.requester_id, "donation_approved", "Donation request approved",
           f"Your request for '{item.material.title}' was approved.",
           url_for("donation.donation", _anchor="my-requests"))
    db.session.commit()
    flash("Donation request approved.", "success")
    return redirect(url_for("donation.donation", _anchor="incoming"))


@bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_request(request_id):
    item = _owned_request(request_id)
    if item.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("donation.donation", _anchor="incoming"))
    item.status = "rejected"
    item.updated_at = utcnow()
    notify(item.requester_id, "donation_rejected", "Donation request update",
           f"Your request for '{item.material.title}' was not approved.",
           url_for("donation.donation", _anchor="my-requests"))
    db.session.commit()
    flash("Donation request rejected.", "info")
    return redirect(url_for("donation.donation", _anchor="incoming"))


@bp.route("/requests/<int:request_id>/complete", methods=["POST"])
@login_required
def complete_request(request_id):
    item = _owned_request(request_id)
    if item.status != "accepted" and item.status != "approved":
        flash("Only approved donations can be completed.", "warning")
        return redirect(url_for("donation.donation", _anchor="incoming"))
    item.status = "completed"
    item.material.status = "sold"
    item.updated_at = utcnow()
    notify(item.requester_id, "donation_completed", "Donation handed over",
           f"'{item.material.title}' has been marked as handed over.",
           url_for("donation.donation", _anchor="my-requests"))
    db.session.commit()
    flash("Donation marked as handed over.", "success")
    return redirect(url_for("donation.donation", _anchor="incoming"))
