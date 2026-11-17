"""Community library: lending, borrowing, reminders and return management."""
from __future__ import annotations

from datetime import timedelta

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import BorrowRequestForm, LibraryBookForm, ReportForm
from ..models import (BorrowingRecord, Category, LibraryBook, MaterialImage,
                      Report, User, utcnow)
from ..utils import (Pagination, add_images, check_due_books, flash_form_errors,
                     get_or_404, item_distance, notify, parse_optional_float,
                     remove_image, save_images)
from . import bp


def _category_choices():
    return [(c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name)]


def _sync_form(form, book):
    form.title.data = book.title
    form.author.data = book.author
    form.subject.data = book.subject
    form.category_id.data = book.category_id
    form.description.data = book.description
    form.condition.data = book.condition
    form.borrowing_duration_days.data = book.borrowing_duration_days
    form.location.data = book.location
    form.latitude.data = book.latitude
    form.longitude.data = book.longitude


@bp.route("/")
def community_library():
    check_due_books()
    query = LibraryBook.query
    q = (request.args.get("q") or "").strip()
    if q:
        query = query.filter(
            LibraryBook.title.ilike(f"%{q}%") | LibraryBook.author.ilike(f"%{q}%")
            | LibraryBook.subject.ilike(f"%{q}%")
        )
    if request.args.get("category_id", type=int):
        query = query.filter(LibraryBook.category_id == request.args.get("category_id", type=int))
    if request.args.get("location"):
        query = query.filter(LibraryBook.location.ilike(f"%{request.args['location']}%"))
    sort = request.args.get("sort", "recent")
    if sort == "title":
        query = query.order_by(LibraryBook.title.asc())
    else:
        query = query.order_by(LibraryBook.created_at.desc())
    pagination = Pagination(query, per_page=12)

    my_books = []
    my_borrowings = []
    my_lendings = []
    if current_user.is_authenticated:
        my_books = (LibraryBook.query.filter_by(owner_id=current_user.id)
                    .order_by(LibraryBook.created_at.desc()).all())
        my_borrowings = (BorrowingRecord.query.filter_by(borrower_id=current_user.id)
                         .order_by(BorrowingRecord.created_at.desc()).all())
        my_lendings = (BorrowingRecord.query.filter_by(owner_id=current_user.id)
                       .order_by(BorrowingRecord.created_at.desc()).all())
    return render_template(
        "community_library.html", title="Community library", pagination=pagination,
        my_books=my_books, my_borrowings=my_borrowings, my_lendings=my_lendings,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_book():
    form = LibraryBookForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        book = LibraryBook(
            owner_id=current_user.id, category_id=form.category_id.data,
            title=form.title.data.strip(), author=form.author.data or None,
            subject=form.subject.data or None, description=form.description.data,
            condition=form.condition.data,
            borrowing_duration_days=form.borrowing_duration_days.data,
            location=form.location.data.strip(),
            latitude=parse_optional_float(form.latitude.data),
            longitude=parse_optional_float(form.longitude.data),
            status="available", created_at=utcnow(),
        )
        db.session.add(book)
        db.session.flush()
        add_images(save_images(request.files.getlist("images"), "library"), library_book=book)
        db.session.commit()
        flash("Your book has been added to the community library.", "success")
        return redirect(url_for("library.book_detail", book_id=book.id))
    if request.method == "POST":
        flash_form_errors(form)
    return render_template("library_book_form.html", title="Add a library book", form=form, book=None)


@bp.route("/<int:book_id>")
def book_detail(book_id):
    book = get_or_404(LibraryBook, book_id)
    history = (BorrowingRecord.query.filter_by(book_id=book.id)
               .order_by(BorrowingRecord.created_at.desc()).all())
    return render_template(
        "library_book_details.html", title=book.title, book=book, history=history,
        form=BorrowRequestForm(), report_form=ReportForm(), distance=item_distance(book),
    )


@bp.route("/<int:book_id>/borrow", methods=["POST"])
@login_required
def borrow_book(book_id):
    book = get_or_404(LibraryBook, book_id)
    if book.owner_id == current_user.id:
        flash("You cannot borrow your own book.", "warning")
        return redirect(url_for("library.book_detail", book_id=book.id))
    if book.status != "available":
        flash("This book is currently not available for borrowing.", "warning")
        return redirect(url_for("library.book_detail", book_id=book.id))
    form = BorrowRequestForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("library.book_detail", book_id=book.id))
    if BorrowingRecord.query.filter(
        BorrowingRecord.book_id == book.id,
        BorrowingRecord.borrower_id == current_user.id,
        BorrowingRecord.status.in_(("pending", "approved", "borrowed", "overdue")),
    ).first():
        flash("You already have an active or pending request for this book.", "info")
        return redirect(url_for("library.book_detail", book_id=book.id))
    db.session.add(BorrowingRecord(
        book_id=book.id, borrower_id=current_user.id, owner_id=book.owner_id,
        requested_duration_days=form.requested_duration_days.data,
        message=form.message.data, status="pending", created_at=utcnow(),
    ))
    notify(book.owner_id, "borrow_request", "New borrow request",
           f"{current_user.display_name} wants to borrow '{book.title}'.",
           url_for("library.book_detail", book_id=book.id))
    db.session.commit()
    flash("Borrow request sent. There are no borrowing charges.", "success")
    return redirect(url_for("library.book_detail", book_id=book.id))


def _owned_record(record_id):
    record = get_or_404(BorrowingRecord, record_id)
    if record.owner_id != current_user.id:
        abort(403)
    return record


@bp.route("/borrow/<int:record_id>/approve", methods=["POST"])
@login_required
def approve_borrow(record_id):
    record = _owned_record(record_id)
    if record.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("library.community_library", _anchor="lending"))
    record.status = "approved"
    record.updated_at = utcnow()
    notify(record.borrower_id, "borrow_approved", "Borrow request approved",
           f"Your request for '{record.book.title}' was approved.",
           url_for("library.book_detail", book_id=record.book_id))
    db.session.commit()
    flash("Borrow request approved. Confirm handover when you give the book.", "success")
    return redirect(url_for("library.community_library", _anchor="lending"))


@bp.route("/borrow/<int:record_id>/reject", methods=["POST"])
@login_required
def reject_borrow(record_id):
    record = _owned_record(record_id)
    if record.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("library.community_library", _anchor="lending"))
    record.status = "rejected"
    record.updated_at = utcnow()
    notify(record.borrower_id, "borrow_rejected", "Borrow request update",
           f"Your request for '{record.book.title}' was not approved.",
           url_for("library.community_library", _anchor="borrowing"))
    db.session.commit()
    flash("Borrow request rejected.", "info")
    return redirect(url_for("library.community_library", _anchor="lending"))


@bp.route("/borrow/<int:record_id>/handover", methods=["POST"])
@login_required
def confirm_handover(record_id):
    from datetime import date
    record = _owned_record(record_id)
    if record.status != "approved":
        flash("Only approved requests can be handed over.", "warning")
        return redirect(url_for("library.community_library", _anchor="lending"))
    today = date.today()
    record.status = "borrowed"
    record.borrow_date = today
    record.expected_return_date = today + timedelta(days=record.requested_duration_days)
    record.book.status = "borrowed"
    record.updated_at = utcnow()
    notify(record.borrower_id, "borrow_handover", "Book handed over",
           f"'{record.book.title}' is now borrowed by you. Return by {record.expected_return_date}.",
           url_for("library.book_detail", book_id=record.book_id))
    db.session.commit()
    flash("Handover confirmed. Return date has been recorded.", "success")
    return redirect(url_for("library.community_library", _anchor="lending"))


@bp.route("/borrow/<int:record_id>/return", methods=["POST"])
@login_required
def confirm_return(record_id):
    from datetime import date
    record = _owned_record(record_id)
    if record.status not in ("borrowed", "overdue"):
        flash("This book is not currently on loan.", "warning")
        return redirect(url_for("library.community_library", _anchor="lending"))
    record.status = "returned"
    record.actual_return_date = date.today()
    record.book.status = "available"
    record.updated_at = utcnow()
    notify(record.borrower_id, "borrow_returned", "Book return confirmed",
           f"Thank you for returning '{record.book.title}'.",
           url_for("library.book_detail", book_id=record.book_id))
    db.session.commit()
    flash("Return confirmed. The book is available again.", "success")
    return redirect(url_for("library.community_library", _anchor="lending"))


@bp.route("/borrow/<int:record_id>/cancel", methods=["POST"])
@login_required
def cancel_request(record_id):
    record = get_or_404(BorrowingRecord, record_id)
    if record.borrower_id != current_user.id or record.status != "pending":
        abort(403)
    db.session.delete(record)
    db.session.commit()
    flash("Your borrow request has been cancelled.", "info")
    return redirect(url_for("library.community_library", _anchor="borrowing"))


@bp.route("/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = get_or_404(LibraryBook, book_id)
    if book.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    form = LibraryBookForm()
    form.category_id.choices = _category_choices()
    if form.validate_on_submit():
        book.title = form.title.data.strip()
        book.author = form.author.data or None
        book.subject = form.subject.data or None
        book.category_id = form.category_id.data
        book.description = form.description.data
        book.condition = form.condition.data
        book.borrowing_duration_days = form.borrowing_duration_days.data
        book.location = form.location.data.strip()
        book.latitude = parse_optional_float(form.latitude.data)
        book.longitude = parse_optional_float(form.longitude.data)
        book.updated_at = utcnow()
        remove_ids = set(request.form.getlist("delete_images"))
        for image in list(book.images):
            if str(image.id) in remove_ids:
                remove_image(image.filename)
                db.session.delete(image)
        add_images(save_images(request.files.getlist("images"), "library"), library_book=book)
        db.session.commit()
        flash("Library book updated.", "success")
        return redirect(url_for("library.book_detail", book_id=book.id))
    if request.method == "GET":
        _sync_form(form, book)
    return render_template("library_book_form.html", title="Edit library book", form=form, book=book)


@bp.route("/<int:book_id>/toggle", methods=["POST"])
@login_required
def toggle_availability(book_id):
    book = get_or_404(LibraryBook, book_id)
    if book.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    if book.status == "borrowed":
        flash("A borrowed book cannot be hidden until it is returned.", "warning")
    else:
        book.status = "unavailable" if book.status == "available" else "available"
        book.updated_at = utcnow()
        db.session.commit()
        flash("Book availability updated.", "success")
    return redirect(url_for("library.community_library", _anchor="my-books"))


@bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    book = get_or_404(LibraryBook, book_id)
    if book.owner_id != current_user.id and not current_user.is_admin:
        abort(403)
    if book.status == "borrowed":
        flash("Return the book before deleting its record.", "warning")
        return redirect(url_for("library.community_library", _anchor="my-books"))
    for image in book.images:
        remove_image(image.filename)
    db.session.delete(book)
    db.session.commit()
    flash("Library book removed.", "info")
    return redirect(url_for("library.community_library", _anchor="my-books"))


@bp.route("/<int:book_id>/report", methods=["POST"])
@login_required
def report_book(book_id):
    book = get_or_404(LibraryBook, book_id)
    form = ReportForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("library.book_detail", book_id=book_id))
    db.session.add(Report(
        reporter_id=current_user.id, library_book_id=book.id,
        reported_user_id=book.owner_id, reason=form.reason.data,
        details=form.details.data,
    ))
    for admin in User.query.filter_by(is_admin=True, is_blocked=False).all():
        notify(admin.id, "report", "New content report",
               f"A library book was reported: {book.title}", url_for("admin.reports"))
    db.session.commit()
    flash("Thank you. Our administrators will review this book.", "success")
    return redirect(url_for("library.book_detail", book_id=book_id))
