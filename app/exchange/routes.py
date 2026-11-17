"""Book exchange listings and request workflow."""
from __future__ import annotations

from decimal import Decimal

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import ExchangeRequestForm, MaterialForm
from ..models import (Category, EducationalMaterial, ExchangeRequest, Notification,
                      User, utcnow)
from ..utils import (Pagination, add_images, apply_material_filters, flash_form_errors,
                     get_or_404, notify, parse_optional_float, remove_image, save_images)
from . import bp


def _category_choices():
    return [(c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name)]


@bp.route("/")
def exchange():
    form = MaterialForm()
    form.category_id.choices = _category_choices()
    query = apply_material_filters(
        db.session.query(EducationalMaterial), request.args, listing_type="exchange"
    )
    pagination = Pagination(query, per_page=12)
    my_listings = []
    sent = []
    received = []
    if current_user.is_authenticated:
        my_listings = (EducationalMaterial.query.filter_by(user_id=current_user.id, listing_type="exchange")
                       .order_by(EducationalMaterial.created_at.desc()).all())
        sent = (ExchangeRequest.query.filter_by(requester_id=current_user.id)
                .order_by(ExchangeRequest.created_at.desc()).all())
        received = (ExchangeRequest.query.filter_by(owner_id=current_user.id)
                    .order_by(ExchangeRequest.created_at.desc()).all())
    return render_template(
        "exchange.html", title="Book exchange", pagination=pagination,
        my_listings=my_listings, sent_requests=sent, received_requests=received,
        active_type="exchange",
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_exchange_book():
    form = MaterialForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        material = EducationalMaterial(
            user_id=current_user.id, category_id=form.category_id.data,
            title=form.title.data.strip(), author=form.author.data or None,
            subject=form.subject.data or None,
            educational_level=form.educational_level.data or None,
            listing_type="exchange", description=form.description.data,
            condition=form.condition.data, price=Decimal("0"),
            original_price=form.original_price.data, location=form.location.data.strip(),
            latitude=parse_optional_float(form.latitude.data),
            longitude=parse_optional_float(form.longitude.data),
            contact_info=form.contact_info.data or None, status="available", created_at=utcnow(),
        )
        db.session.add(material)
        db.session.flush()
        add_images(save_images(request.files.getlist("images"), "listings"), material=material)
        db.session.commit()
        flash("Your book is now available for exchange.", "success")
        return redirect(url_for("marketplace.book_detail", material_id=material.id))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("sell_book.html", title="Add a book for exchange", form=form,
                           material=None, listing_type="exchange")


@bp.route("/<int:material_id>/request", methods=["POST"])
@login_required
def send_request(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    if material.listing_type != "exchange":
        abort(404)
    if material.user_id == current_user.id:
        flash("You cannot request your own book.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    if not material.is_available:
        flash("This book is no longer available for exchange.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    form = ExchangeRequestForm()
    form.offered_material_id.choices = [(0, "Nothing to add")] + [
        (m.id, m.title) for m in EducationalMaterial.query.filter_by(
            user_id=current_user.id, status="available"
        ).all()
    ]
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    offered = form.offered_material_id.data or None
    if offered and not EducationalMaterial.query.filter_by(id=offered, user_id=current_user.id).first():
        abort(403)
    if ExchangeRequest.query.filter_by(requester_id=current_user.id, material_id=material.id).first():
        flash("You have already sent an exchange request for this book.", "info")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    db.session.add(ExchangeRequest(
        requester_id=current_user.id, owner_id=material.user_id, material_id=material.id,
        offered_material_id=offered, message=form.message.data, status="pending", created_at=utcnow(),
    ))
    notify(material.user_id, "exchange_request", "New exchange request",
           f"{current_user.display_name} wants to exchange '{material.title}'.",
           url_for("exchange.exchange", _anchor="incoming"))
    db.session.commit()
    flash("Exchange request sent. The owner can accept or reject it.", "success")
    return redirect(url_for("exchange.exchange", _anchor="my-requests"))


def _owned_request(request_id):
    item = get_or_404(ExchangeRequest, request_id)
    if item.owner_id != current_user.id:
        abort(403)
    return item


@bp.route("/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id):
    item = _owned_request(request_id)
    if item.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("exchange.exchange", _anchor="incoming"))
    item.status = "accepted"
    item.material.status = "reserved"
    item.updated_at = utcnow()
    notify(item.requester_id, "exchange_accepted", "Exchange request accepted",
           f"Your request for '{item.material.title}' was accepted.",
           url_for("exchange.exchange", _anchor="my-requests"))
    db.session.commit()
    flash("Exchange request accepted. Message the student to arrange the swap.", "success")
    return redirect(url_for("exchange.exchange", _anchor="incoming"))


@bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@login_required
def reject_request(request_id):
    item = _owned_request(request_id)
    if item.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("exchange.exchange", _anchor="incoming"))
    item.status = "rejected"
    item.updated_at = utcnow()
    notify(item.requester_id, "exchange_rejected", "Exchange request update",
           f"Your request for '{item.material.title}' was not accepted.",
           url_for("exchange.exchange", _anchor="my-requests"))
    db.session.commit()
    flash("Exchange request rejected.", "info")
    return redirect(url_for("exchange.exchange", _anchor="incoming"))


@bp.route("/requests/<int:request_id>/complete", methods=["POST"])
@login_required
def complete_request(request_id):
    item = _owned_request(request_id)
    if item.status != "accepted":
        flash("Only accepted exchanges can be completed.", "warning")
        return redirect(url_for("exchange.exchange", _anchor="incoming"))
    item.status = "completed"
    item.material.status = "sold"
    if item.offered_material:
        item.offered_material.status = "sold"
    item.updated_at = utcnow()
    notify(item.requester_id, "exchange_completed", "Exchange completed",
           f"The exchange of '{item.material.title}' is marked complete.",
           url_for("exchange.exchange", _anchor="my-requests"))
    db.session.commit()
    flash("Exchange marked as completed.", "success")
    return redirect(url_for("exchange.exchange", _anchor="incoming"))
