"""Role-protected administration: users, listings, reports, categories and monitoring."""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from ..extensions import db
from ..forms import CategoryForm
from ..models import (BorrowingRecord, Category, DonationRequest, EducationalMaterial,
                      LibraryBook, Report, User, utcnow)
from ..utils import (Pagination, admin_required, flash_form_errors, get_or_404,
                     notify, remove_image, stats_snapshot)
from . import bp


@bp.before_request
@admin_required
def require_admin():
    return None


@bp.route("/")
def dashboard():
    stats = stats_snapshot()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()
    recent_listings = EducationalMaterial.query.order_by(
        EducationalMaterial.created_at.desc()).limit(6).all()
    open_reports = Report.query.filter_by(status="open").order_by(Report.created_at.desc()).limit(5).all()
    overdue = BorrowingRecord.query.filter_by(status="overdue").count()
    pending_borrows = BorrowingRecord.query.filter_by(status="pending").count()
    return render_template("admin_dashboard.html", title="Admin dashboard", stats=stats,
                           recent_users=recent_users, recent_listings=recent_listings,
                           open_reports=open_reports, overdue=overdue,
                           pending_borrows=pending_borrows)


@bp.route("/users")
def users():
    q = (request.args.get("q") or "").strip()
    query = User.query
    if q:
        query = query.filter(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"),
                                 User.location.ilike(f"%{q}%")))
    query = query.order_by(User.created_at.desc())
    pagination = Pagination(query, per_page=20)
    return render_template("admin_users.html", title="Manage users", pagination=pagination, q=q)


@bp.route("/users/<int:user_id>/block", methods=["POST"])
def toggle_block(user_id):
    user = get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot suspend your own administrator account.", "warning")
        return redirect(url_for("admin.users"))
    user.is_blocked = not user.is_blocked
    user.is_active_account = not user.is_blocked
    db.session.commit()
    notify(user.id, "account", "Account status changed",
           "Your account was suspended." if user.is_blocked else "Your account is active again.",
           url_for("main.index"))
    flash("User account status updated.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/admin", methods=["POST"])
def toggle_admin(user_id):
    user = get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot change your own administrator role.", "warning")
        return redirect(url_for("admin.users"))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash("Administrator role updated.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/listings")
def listings():
    query = EducationalMaterial.query
    if request.args.get("type") in ("sale", "exchange", "donation"):
        query = query.filter(EducationalMaterial.listing_type == request.args["type"])
    if request.args.get("status"):
        query = query.filter(EducationalMaterial.status == request.args["status"])
    query = query.order_by(EducationalMaterial.created_at.desc())
    pagination = Pagination(query, per_page=20)
    return render_template("admin_listings.html", title="Manage listings", pagination=pagination)


@bp.route("/listings/<int:material_id>/remove", methods=["POST"])
def remove_listing(material_id):
    material = get_or_404(EducationalMaterial, material_id)
    for image in material.images:
        remove_image(image.filename)
    owner_id = material.user_id
    title = material.title
    db.session.delete(material)
    db.session.commit()
    notify(owner_id, "moderation", "Listing removed",
           f"Your listing '{title}' was removed by an administrator.", url_for("main.index"))
    flash("Listing removed from the platform.", "success")
    return redirect(url_for("admin.listings"))


@bp.route("/reports")
def reports():
    query = Report.query
    status = request.args.get("status", "open")
    if status:
        query = query.filter(Report.status == status)
    query = query.order_by(Report.created_at.desc())
    pagination = Pagination(query, per_page=20)
    return render_template("admin_reports.html", title="Reported content", pagination=pagination,
                           status=status)


@bp.route("/reports/<int:report_id>/resolve", methods=["POST"])
def resolve_report(report_id):
    report = get_or_404(Report, report_id)
    decision = request.form.get("decision", "resolved")
    if decision not in ("open", "reviewed", "resolved", "dismissed"):
        decision = "resolved"
    report.status = decision
    report.admin_notes = request.form.get("admin_notes", "")[:1000]
    report.reviewed_at = utcnow()
    db.session.commit()
    flash("Report updated.", "success")
    return redirect(url_for("admin.reports", status=request.form.get("status", "open")))


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        category_id = request.form.get("category_id", type=int)
        if category_id:
            category = get_or_404(Category, category_id)
            category.name = form.name.data.strip()
            category.icon = form.icon.data or "bi-book"
            category.description = form.description.data
            flash("Category updated.", "success")
        else:
            db.session.add(Category(name=form.name.data.strip(),
                                    slug=form.name.data.strip().lower().replace(" ", "-"),
                                    icon=form.icon.data or "bi-book",
                                    description=form.description.data))
            flash("Category created.", "success")
        db.session.commit()
        return redirect(url_for("admin.categories"))
    if request.method == "POST":
        flash_form_errors(form)
    edit_id = request.args.get("edit", type=int)
    if edit_id and request.method == "GET":
        category = get_or_404(Category, edit_id)
        form.name.data = category.name
        form.icon.data = category.icon
        form.description.data = category.description
    items = Category.query.order_by(Category.name).all()
    return render_template("admin_categories.html", title="Manage categories", form=form,
                           items=items, edit_id=edit_id)


@bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
def toggle_category(category_id):
    category = get_or_404(Category, category_id)
    category.is_active = not category.is_active
    db.session.commit()
    flash("Category visibility updated.", "success")
    return redirect(url_for("admin.categories"))


@bp.route("/donations")
def donations():
    query = DonationRequest.query
    if request.args.get("status"):
        query = query.filter(DonationRequest.status == request.args["status"])
    query = query.order_by(DonationRequest.created_at.desc())
    pagination = Pagination(query, per_page=20)
    return render_template("admin_donations.html", title="Donation activity", pagination=pagination)


@bp.route("/borrowing")
def borrowing():
    query = BorrowingRecord.query
    if request.args.get("status"):
        query = query.filter(BorrowingRecord.status == request.args["status"])
    query = query.order_by(BorrowingRecord.created_at.desc())
    pagination = Pagination(query, per_page=20)
    return render_template("admin_borrowing.html", title="Borrowing records", pagination=pagination)
