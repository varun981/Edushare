"""Shared helpers: authorization, uploads, notifications, search and due dates."""
from __future__ import annotations

import hmac
import math
import os
import smtplib
import uuid
from datetime import date, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from .extensions import db
from .models import (BorrowingRecord, EducationalMaterial, MaterialImage,
                     Notification, User, utcnow)

_IMAGE_SIGNATURES = (
    b"\x89PNG\r\n\x1a\n",          # PNG
    b"\xff\xd8\xff",               # JPEG
    b"GIF87a", b"GIF89a",         # GIF
    b"RIFF",                       # WEBP (RIFF....WEBP)
)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def active_required(view):
    """Blocked accounts cannot interact even if an old session exists."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated and not current_user.is_active:
            from flask_login import logout_user
            logout_user()
            flash("Your account has been suspended. Please contact an administrator.", "danger")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def get_or_404(model, object_id):
    obj = db.session.get(model, object_id)
    if obj is None:
        abort(404)
    return obj


def safe_next_url(target: str | None, default: str = "main.index") -> str:
    if not target:
        return url_for(default)
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return url_for(default)
    return target if target.startswith("/") else url_for(default)


def notify(user_id: int, kind: str, title: str, message: str, link: str | None = None) -> Notification:
    notification = Notification(
        user_id=user_id, type=kind, title=title, message=message, link=link, created_at=utcnow()
    )
    db.session.add(notification)
    return notification


def parse_optional_float(value) -> float | None:
    """Parse optional numeric form fields without raising on tampered input."""
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def flash_form_errors(form) -> None:
    for field, errors in form.errors.items():
        label = getattr(getattr(form, field), "label", None)
        name = label.text if label else field.replace("_", " ").title()
        for error in errors:
            flash(f"{name}: {error}", "danger")


# ---------------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------------

def _valid_image_signature(stream) -> bool:
    start = stream.read(16)
    stream.seek(0)
    if not any(start.startswith(sig) for sig in _IMAGE_SIGNATURES):
        return False
    if start.startswith(b"RIFF"):
        return start[8:12] == b"WEBP"
    return True


def save_images(files, subfolder: str = "listings", max_images: int | None = None) -> list[str]:
    """Validate and persist uploaded images. Returns stored filenames."""
    cfg = current_app.config
    max_images = max_images or cfg.get("MAX_IMAGES_PER_LISTING", 5)
    stored = []
    seen = set()
    for file in files:
        if not file or not getattr(file, "filename", None):
            continue
        if len(stored) >= max_images:
            flash(f"Only {max_images} images can be uploaded per item.", "warning")
            break
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in cfg.get("ALLOWED_IMAGE_EXTENSIONS", set()):
            flash(f"'{filename}' is not an allowed image type.", "danger")
            continue
        if file.mimetype not in cfg.get("ALLOWED_IMAGE_MIMES", set()):
            flash(f"'{filename}' has an invalid image content type.", "danger")
            continue
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > cfg.get("MAX_IMAGE_BYTES", 3 * 1024 * 1024):
            flash(f"'{filename}' is larger than 3 MB.", "danger")
            continue
        if not _valid_image_signature(file.stream):
            flash(f"'{filename}' does not appear to be a valid image.", "danger")
            continue
        if filename in seen:
            continue
        seen.add(filename)
        safe_name = f"{uuid.uuid4().hex}.{ext}"
        target = Path(cfg["UPLOAD_FOLDER"]) / subfolder
        target.mkdir(parents=True, exist_ok=True)
        file.save(target / safe_name)
        stored.append(f"{subfolder}/{safe_name}")
    return stored


def add_images(filenames: list[str], *, material=None, library_book=None) -> None:
    for index, filename in enumerate(filenames):
        db.session.add(MaterialImage(
            filename=filename, material=material, library_book=library_book, is_primary=(index == 0)
        ))


def remove_image(filename: str | None) -> None:
    if not filename or filename.startswith("http"):
        return
    path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
    try:
        path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not delete upload %s", filename)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class Pagination:
    def __init__(self, query, page: int | None = None, per_page: int = 12):
        self.page = max(1, page or request.args.get("page", 1, type=int) or 1)
        self.per_page = per_page
        self.total = query.count()
        self.pages = max(1, math.ceil(self.total / per_page))
        self.page = min(self.page, self.pages)
        self.items = query.offset((self.page - 1) * per_page).limit(per_page).all()

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None

    def iter_pages(self, edge=2):
        result = set()
        for number in range(1, self.pages + 1):
            if number <= edge or number > self.pages - edge or abs(number - self.page) <= 2:
                result.add(number)
        previous = 0
        for number in sorted(result):
            if previous and number - previous > 1:
                yield None
            yield number
            previous = number


# ---------------------------------------------------------------------------
# Location / search
# ---------------------------------------------------------------------------

def distance_km(lat1, lon1, lat2, lon2) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    try:
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return None
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Return (min_lat, max_lat, min_lon, max_lon) for a coarse radius filter."""
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


def user_coordinates() -> tuple[float | None, float | None]:
    """Location stored in the session (set by the location picker) or profile."""
    if current_user.is_authenticated:
        if current_user.latitude is not None and current_user.longitude is not None:
            return current_user.latitude, current_user.longitude
    try:
        return session_lat(), session_lon()
    except RuntimeError:
        return None, None


def session_lat():
    from flask import session
    return session.get("latitude")


def session_lon():
    from flask import session
    return session.get("longitude")


def item_distance(item) -> float | None:
    lat, lon = user_coordinates()
    return distance_km(lat, lon, getattr(item, "latitude", None), getattr(item, "longitude", None))


def apply_material_filters(query, args, listing_type: str | None = None):
    q = (args.get("q") or "").strip()
    if q:
        term = f"%{q}%"
        query = query.filter(or_(
            EducationalMaterial.title.ilike(term),
            EducationalMaterial.author.ilike(term),
            EducationalMaterial.subject.ilike(term),
            EducationalMaterial.educational_level.ilike(term),
            EducationalMaterial.description.ilike(term),
            EducationalMaterial.location.ilike(term),
        ))
    if listing_type:
        query = query.filter(EducationalMaterial.listing_type == listing_type)
    elif args.get("type") in ("sale", "exchange", "donation"):
        query = query.filter(EducationalMaterial.listing_type == args["type"])
    if args.get("category_id", type=int):
        query = query.filter(EducationalMaterial.category_id == args.get("category_id", type=int))
    if args.get("level"):
        query = query.filter(EducationalMaterial.educational_level.ilike(f"%{args['level']}%"))
    if args.get("condition"):
        query = query.filter(EducationalMaterial.condition == args["condition"])
    if args.get("location"):
        query = query.filter(EducationalMaterial.location.ilike(f"%{args['location']}%"))
    if args.get("availability"):
        query = query.filter(EducationalMaterial.status == args["availability"])
    else:
        query = query.filter(EducationalMaterial.status.in_(("available", "reserved")))
    if args.get("min_price", type=float) is not None:
        query = query.filter(EducationalMaterial.price >= args.get("min_price", type=float))
    if args.get("max_price", type=float) is not None:
        query = query.filter(EducationalMaterial.price <= args.get("max_price", type=float))
    sort = args.get("sort", "recent")
    if sort == "price_asc":
        query = query.order_by(EducationalMaterial.price.asc(), EducationalMaterial.created_at.desc())
    elif sort == "price_desc":
        query = query.order_by(EducationalMaterial.price.desc(), EducationalMaterial.created_at.desc())
    else:
        query = query.order_by(EducationalMaterial.created_at.desc())
    return query


# ---------------------------------------------------------------------------
# Passwords, messaging and due dates
# ---------------------------------------------------------------------------

def reset_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="edushare-password-reset")


def generate_reset_token(user: User) -> str:
    # Binding the token to the current password hash makes it single-use: as
    # soon as the password changes, any previously issued token stops working.
    return reset_serializer().dumps({
        "user_id": user.id,
        "pwd": user.password_hash,
    })


def verify_reset_token(token: str, max_age: int = 3600) -> User | None:
    try:
        data = reset_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get("user_id"))
    if not user:
        return None
    if not hmac.compare_digest(str(user.password_hash), str(data.get("pwd", ""))):
        return None
    return user


def send_reset_email(user: User, token: str) -> bool:
    """Send reset mail when SMTP is configured; otherwise return False."""
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER") or not cfg.get("MAIL_USERNAME"):
        return False
    link = url_for("auth.reset_password", token=token, _external=True)
    message = EmailMessage()
    message["Subject"] = "Reset your EduShare password"
    message["From"] = cfg["MAIL_DEFAULT_SENDER"]
    message["To"] = user.email
    message.set_content(
        f"Hello {user.display_name},\n\nUse this link within one hour to reset your "
        f"password:\n{link}\n\nIf you did not request this, ignore this email.\n"
    )
    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as smtp:
            if cfg.get("MAIL_USE_TLS"):
                smtp.starttls()
            if cfg.get("MAIL_USERNAME") and cfg.get("MAIL_PASSWORD"):
                smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(message)
        return True
    except OSError:
        current_app.logger.exception("Password reset e-mail could not be sent")
        return False


def get_or_create_conversation(user1_id: int, user2_id: int, topic: str = "General",
                               material_id=None, library_book_id=None) -> Conversation:
    from .models import Conversation
    first, second = sorted((user1_id, user2_id))
    conversation = Conversation.query.filter_by(
        participant1_id=first, participant2_id=second, topic=topic[:255]
    ).first()
    if conversation is None:
        conversation = Conversation(
            participant1_id=first, participant2_id=second, topic=topic[:255],
            material_id=material_id, library_book_id=library_book_id,
        )
        db.session.add(conversation)
        db.session.flush()
    return conversation


def check_due_books() -> int:
    """Mark overdue loans and create return reminders. Safe to call repeatedly."""
    today = date.today()
    changes = 0
    records = BorrowingRecord.query.filter(
        BorrowingRecord.status.in_(("borrowed", "approved", "overdue"))
    ).all()
    for record in records:
        if not record.expected_return_date:
            continue
        days_left = (record.expected_return_date - today).days
        link = url_for("library.book_detail", book_id=record.book_id)
        if days_left < 0 and record.status != "overdue":
            record.status = "overdue"
            notify(record.borrower_id, "overdue", "Book return is overdue",
                   f"'{record.book.title}' was due on {record.expected_return_date}.", link)
            notify(record.owner_id, "overdue", "Borrowed book is overdue",
                   f"{record.borrower.display_name} has not returned '{record.book.title}'.", link)
            changes += 1
        elif 0 <= days_left <= 3 and record.reminder_sent_on != today:
            notify(record.borrower_id, "return_reminder", "Upcoming book return",
                   f"'{record.book.title}' is due in {days_left} day(s).", link)
            record.reminder_sent_on = today
            changes += 1
    if changes:
        db.session.commit()
    return changes


def stats_snapshot() -> dict:
    from .models import (Conversation, DonationRequest, ExchangeRequest,
                         LibraryBook, Message, Report)
    return {
        "users": User.query.count(),
        "listings": EducationalMaterial.query.count(),
        "exchange_requests": ExchangeRequest.query.count(),
        "donation_requests": DonationRequest.query.count(),
        "library_books": LibraryBook.query.count(),
        "borrowings": BorrowingRecord.query.count(),
        "messages": Message.query.count(),
        "conversations": Conversation.query.count(),
        "reports": Report.query.filter_by(status="open").count(),
    }
