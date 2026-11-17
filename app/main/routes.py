"""Home dashboard, personalized dashboard, global search and PWA shell routes."""
from __future__ import annotations

from flask import (current_app, flash, make_response, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import LocationForm
from ..models import (BorrowingRecord, DonationRequest, EducationalMaterial,
                      ExchangeRequest, LibraryBook, PurchaseRequest, utcnow)
from ..utils import (Pagination, apply_material_filters, bounding_box, check_due_books,
                     distance_km, flash_form_errors, item_distance, parse_optional_float,
                     safe_next_url, user_coordinates)
from . import bp


@bp.route("/")
def index():
    check_due_books()
    base = EducationalMaterial.query.filter(
        EducationalMaterial.status.in_(("available", "reserved"))
    )
    recent = base.order_by(EducationalMaterial.created_at.desc()).limit(8).all()
    featured = (base.filter(EducationalMaterial.listing_type == "sale")
                .order_by(EducationalMaterial.views.desc(), EducationalMaterial.created_at.desc())
                .limit(4).all())
    donated = (base.filter(EducationalMaterial.listing_type == "donation")
               .order_by(EducationalMaterial.created_at.desc()).limit(4).all())
    for_sale = (base.filter(EducationalMaterial.listing_type == "sale")
                .order_by(EducationalMaterial.created_at.desc()).limit(8).all())
    for_exchange = (base.filter(EducationalMaterial.listing_type == "exchange")
                    .order_by(EducationalMaterial.created_at.desc()).limit(4).all())
    library_books = (LibraryBook.query.filter_by(status="available")
                     .order_by(LibraryBook.created_at.desc()).limit(4).all())

    lat, lon = user_coordinates()
    location_text = None
    if current_user.is_authenticated:
        location_text = current_user.location
    else:
        location_text = session.get("location")
    nearby = []
    if lat is not None and lon is not None:
        min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, 100)
        candidates = base.filter(
            EducationalMaterial.latitude.between(min_lat, max_lat),
            EducationalMaterial.longitude.between(min_lon, max_lon),
        ).all()
        candidates += LibraryBook.query.filter(
            LibraryBook.status == "available",
            LibraryBook.latitude.between(min_lat, max_lat),
            LibraryBook.longitude.between(min_lon, max_lon),
        ).all()
        for item in candidates:
            km = distance_km(lat, lon, item.latitude, item.longitude)
            if km is not None and km <= 100:
                setattr(item, "_distance", km)
                nearby.append(item)
        nearby.sort(key=lambda item: item._distance)
        nearby = nearby[:6]
    elif location_text:
        nearby = (base.filter(EducationalMaterial.location.ilike(f"%{location_text}%"))
                  .order_by(EducationalMaterial.created_at.desc()).limit(6).all())

    my_stats = {}
    if current_user.is_authenticated:
        my_stats = {
            "listings": len(current_user.materials),
            "incoming_requests": (
                PurchaseRequest.query.filter_by(seller_id=current_user.id, status="pending").count()
                + ExchangeRequest.query.filter_by(owner_id=current_user.id, status="pending").count()
                + DonationRequest.query.filter_by(owner_id=current_user.id, status="pending").count()
                + BorrowingRecord.query.filter_by(owner_id=current_user.id, status="pending").count()
            ),
            "borrowed": BorrowingRecord.query.filter(
                BorrowingRecord.borrower_id == current_user.id,
                BorrowingRecord.status.in_(("approved", "borrowed", "overdue")),
            ).count(),
        }
    return render_template(
        "index.html", title="Home", recent=recent, featured=featured, donated=donated,
        for_sale=for_sale, for_exchange=for_exchange, library_books=library_books,
        nearby=nearby, location_text=location_text, my_stats=my_stats,
    )


@bp.route("/dashboard")
@login_required
def dashboard():
    check_due_books()
    incoming_purchase = PurchaseRequest.query.filter_by(seller_id=current_user.id).order_by(
        PurchaseRequest.created_at.desc()).limit(5).all()
    incoming_exchange = ExchangeRequest.query.filter_by(owner_id=current_user.id).order_by(
        ExchangeRequest.created_at.desc()).limit(5).all()
    incoming_donation = DonationRequest.query.filter_by(owner_id=current_user.id).order_by(
        DonationRequest.created_at.desc()).limit(5).all()
    my_borrowings = BorrowingRecord.query.filter_by(borrower_id=current_user.id).order_by(
        BorrowingRecord.created_at.desc()).limit(5).all()
    my_lendings = BorrowingRecord.query.filter_by(owner_id=current_user.id).order_by(
        BorrowingRecord.created_at.desc()).limit(5).all()
    conversations = sorted(
        current_user.conversations_as_first + current_user.conversations_as_last,
        key=lambda c: c.updated_at or utcnow(), reverse=True,
    )[:5]
    return render_template(
        "dashboard.html", title="My dashboard",
        my_materials=current_user.materials[:8],
        my_library_books=current_user.library_books[:5],
        incoming_purchase=incoming_purchase, incoming_exchange=incoming_exchange,
        incoming_donation=incoming_donation, my_borrowings=my_borrowings,
        my_lendings=my_lendings, conversations=conversations,
    )


@bp.route("/search")
def search():
    query = apply_material_filters(
        db.session.query(EducationalMaterial), request.args
    )
    pagination = Pagination(query, per_page=12)
    q = (request.args.get("q") or "").strip()
    library_query = LibraryBook.query
    if q:
        library_query = library_query.filter(
            LibraryBook.title.ilike(f"%{q}%") | LibraryBook.author.ilike(f"%{q}%")
            | LibraryBook.subject.ilike(f"%{q}%")
        )
    if request.args.get("category_id", type=int):
        library_query = library_query.filter(
            LibraryBook.category_id == request.args.get("category_id", type=int)
        )
    if request.args.get("condition"):
        library_query = library_query.filter(
            LibraryBook.condition == request.args["condition"]
        )
    if request.args.get("location"):
        library_query = library_query.filter(
            LibraryBook.location.ilike(f"%{request.args['location']}%")
        )
    availability = request.args.get("availability")
    if availability in ("reserved", "sold", "unavailable"):
        library_query = library_query.filter(LibraryBook.status != "available")
    else:
        library_query = library_query.filter(LibraryBook.status == "available")
    library_books = library_query.order_by(LibraryBook.created_at.desc()).limit(6).all()
    return render_template(
        "search_results.html", title="Search results", pagination=pagination,
        library_books=library_books, query_text=q,
    )


@bp.route("/location", methods=["POST"])
@login_required
def set_location():
    form = LocationForm()
    if form.validate_on_submit():
        session["location"] = form.location.data.strip()
        session["latitude"] = parse_optional_float(form.latitude.data)
        session["longitude"] = parse_optional_float(form.longitude.data)
        current_user.location = form.location.data.strip()
        current_user.latitude = session["latitude"]
        current_user.longitude = session["longitude"]
        db.session.commit()
        flash("Your preferred location has been updated.", "success")
    else:
        flash_form_errors(form)
    return redirect(safe_next_url(request.referrer, "main.index"))


@bp.route("/service-worker.js")
def service_worker():
    response = make_response(send_from_directory(
        current_app.static_folder, "service-worker.js", mimetype="application/javascript"
    ))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@bp.route("/offline")
def offline():
    return render_template("offline.html", title="You are offline")
