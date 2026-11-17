"""Marketplace listing creation, browsing, editing and purchase interest."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import (abort, flash, redirect, render_template, request, url_for)
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import (DonationRequestForm, ExchangeRequestForm, MaterialForm,
                     PurchaseRequestForm, ReportForm, SearchForm)
from ..models import (Category, EducationalMaterial, PurchaseRequest, Report,
                      User, utcnow)
from ..utils import (Pagination, add_images, apply_material_filters, flash_form_errors,
                     get_or_create_conversation, get_or_404, item_distance, notify,
                     remove_image, save_images)
from . import bp


def _category_choices():
    return [(c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name)]


def _parse_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _sync_form_from_model(form, material):
    form.title.data = material.title
    form.author.data = material.author
    form.subject.data = material.subject
    form.educational_level.data = material.educational_level or ""
    form.category_id.data = material.category_id
    form.listing_type.data = material.listing_type
    form.description.data = material.description
    form.condition.data = material.condition
    form.price.data = material.price
    form.original_price.data = material.original_price
    form.location.data = material.location
    form.contact_info.data = material.contact_info
    form.latitude.data = material.latitude
    form.longitude.data = material.longitude


@bp.route("/marketplace")
def marketplace():
    form = SearchForm(formdata=request.args)
    form.category_id.choices = [(0, "All categories")] + _category_choices()
    query = apply_material_filters(db.session.query(EducationalMaterial), request.args,
                                   listing_type="sale")
    pagination = Pagination(query, per_page=12)
    return render_template("marketplace.html", title="Marketplace", pagination=pagination,
                           form=form, active_type="sale")


@bp.route("/books/new", methods=["GET", "POST"])
@login_required
def create_listing():
    form = MaterialForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        price = form.price.data if form.price.data is not None else Decimal("0")
        material = EducationalMaterial(
            user_id=current_user.id,
            category_id=form.category_id.data,
            title=form.title.data.strip(),
            author=form.author.data.strip() if form.author.data else None,
            subject=form.subject.data.strip() if form.subject.data else None,
            educational_level=form.educational_level.data or None,
            listing_type=form.listing_type.data,
            description=form.description.data,
            condition=form.condition.data,
            price=price,
            original_price=form.original_price.data,
            location=form.location.data.strip(),
            latitude=_parse_float(form.latitude.data),
            longitude=_parse_float(form.longitude.data),
            contact_info=form.contact_info.data.strip() if form.contact_info.data else None,
            status="available",
            created_at=utcnow(),
        )
        db.session.add(material)
        db.session.flush()
        add_images(save_images(request.files.getlist("images"), "listings"), material=material)
        db.session.commit()
        flash("Your listing is live. Students can now discover it!", "success")
        return redirect(url_for("marketplace.book_detail", material_id=material.id))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("sell_book.html", title="Sell a book", form=form, material=None)


@bp.route("/books/<int:material_id>")
def book_detail(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    material.views += 1
    db.session.commit()
    purchase_form = PurchaseRequestForm()
    report_form = ReportForm()
    exchange_form = ExchangeRequestForm()
    exchange_form.offered_material_id.choices = [(0, "Nothing to add")] + [
        (m.id, m.title) for m in EducationalMaterial.query.filter_by(
            user_id=current_user.id, status="available"
        ).all()
    ] if current_user.is_authenticated else [(0, "Nothing to add")]
    donation_form = DonationRequestForm()
    related = (EducationalMaterial.query.filter(
        EducationalMaterial.listing_type == material.listing_type,
        EducationalMaterial.id != material.id,
        EducationalMaterial.status == "available",
    ).order_by(EducationalMaterial.created_at.desc()).limit(4).all())
    return render_template(
        "book_details.html", title=material.title, material=material, related=related,
        purchase_form=purchase_form, report_form=report_form, distance=item_distance(material),
        exchange_form=exchange_form, donation_form=donation_form,
    )


@bp.route("/books/<int:material_id>/edit", methods=["GET", "POST"])
@login_required
def edit_listing(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    if material.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    form = MaterialForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        material.title = form.title.data.strip()
        material.author = form.author.data.strip() if form.author.data else None
        material.subject = form.subject.data.strip() if form.subject.data else None
        material.educational_level = form.educational_level.data or None
        material.category_id = form.category_id.data
        material.listing_type = form.listing_type.data
        material.description = form.description.data
        material.condition = form.condition.data
        material.price = form.price.data if form.price.data is not None else Decimal("0")
        material.original_price = form.original_price.data
        material.location = form.location.data.strip()
        material.latitude = _parse_float(form.latitude.data)
        material.longitude = _parse_float(form.longitude.data)
        material.contact_info = form.contact_info.data.strip() if form.contact_info.data else None
        material.updated_at = utcnow()

        remove_ids = set(request.form.getlist("delete_images"))
        for image in list(material.images):
            if str(image.id) in remove_ids:
                remove_image(image.filename)
                db.session.delete(image)
        add_images(save_images(request.files.getlist("images"), "listings"), material=material)
        db.session.commit()
        flash("Listing updated successfully.", "success")
        return redirect(url_for("marketplace.book_detail", material_id=material.id))
    if request.method == "GET":
        _sync_form_from_model(form, material)
    return render_template("sell_book.html", title="Edit listing", form=form, material=material)


@bp.route("/books/<int:material_id>/delete", methods=["POST"])
@login_required
def delete_listing(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    if material.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    for image in material.images:
        remove_image(image.filename)
    db.session.delete(material)
    db.session.commit()
    flash("Listing deleted.", "info")
    return redirect(url_for("main.dashboard"))


@bp.route("/books/<int:material_id>/interest", methods=["POST"])
@login_required
def purchase_interest(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    if material.user_id == current_user.id:
        flash("You cannot express interest in your own listing.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    if not material.is_available:
        flash("This listing is no longer available.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    form = PurchaseRequestForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    request_obj = PurchaseRequest.query.filter_by(buyer_id=current_user.id, material_id=material.id).first()
    if request_obj:
        flash("You have already expressed interest in this book. The seller can see your request.", "info")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    db.session.add(PurchaseRequest(
        buyer_id=current_user.id, seller_id=material.user_id, material_id=material.id,
        message=form.message.data, status="pending", created_at=utcnow(),
    ))
    notify(material.user_id, "purchase_interest", "New purchase interest",
           f"{current_user.display_name} is interested in '{material.title}'.",
           url_for("main.dashboard"))
    db.session.commit()
    flash("Purchase interest sent. Arrange payment and collection directly with the seller.", "success")
    return redirect(url_for("marketplace.book_detail", material_id=material_id))


@bp.route("/books/<int:material_id>/contact", methods=["POST"])
@login_required
def contact_seller(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    if material.user_id == current_user.id:
        flash("This is your own listing.", "warning")
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    conversation = get_or_create_conversation(
        current_user.id, material.user_id, topic=material.title, material_id=material.id
    )
    notify(material.user_id, "new_message", "New conversation started",
           f"{current_user.display_name} messaged you about '{material.title}'.",
           url_for("messaging.conversation", conversation_id=conversation.id))
    db.session.commit()
    return redirect(url_for("messaging.conversation", conversation_id=conversation.id))


@bp.route("/books/<int:material_id>/report", methods=["POST"])
@login_required
def report_listing(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    form = ReportForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("marketplace.book_detail", material_id=material_id))
    db.session.add(Report(
        reporter_id=current_user.id, material_id=material.id, reported_user_id=material.user_id,
        reason=form.reason.data, details=form.details.data,
    ))
    for admin in User.query.filter_by(is_admin=True, is_blocked=False).all():
        notify(admin.id, "report", "New content report",
               f"A listing was reported: {material.title}", url_for("admin.reports"))
    db.session.commit()
    flash("Thank you. Our administrators will review this listing.", "success")
    return redirect(url_for("marketplace.book_detail", material_id=material_id))
