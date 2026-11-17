"""Database models for EduShare.

The schema is deliberately normalized: users own materials/library books,
requests reference both the requester and the resource, and conversations
hold messages between exactly two participants.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

LISTING_TYPES = ("sale", "exchange", "donation")
MATERIAL_STATUSES = ("available", "reserved", "sold", "unavailable")
REQUEST_STATUSES = ("pending", "accepted", "rejected", "completed")
DONATION_STATUSES = ("pending", "approved", "rejected", "completed")
BORROW_STATUSES = ("pending", "approved", "borrowed", "returned", "rejected", "overdue")
LIBRARY_STATUSES = ("available", "borrowed", "unavailable")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    educational_qualification = db.Column(db.String(120))
    institution = db.Column(db.String(180))
    location = db.Column(db.String(180))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    profile_image = db.Column(db.String(255), default="default-avatar.svg")
    bio = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_blocked = db.Column(db.Boolean, default=False, nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_seen = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    materials = db.relationship("EducationalMaterial", back_populates="seller", cascade="all, delete-orphan")
    library_books = db.relationship("LibraryBook", back_populates="owner", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    exchange_requests_sent = db.relationship(
        "ExchangeRequest", foreign_keys="ExchangeRequest.requester_id", back_populates="requester",
        cascade="all, delete-orphan",
    )
    exchange_requests_received = db.relationship(
        "ExchangeRequest", foreign_keys="ExchangeRequest.owner_id", back_populates="owner"
    )
    donation_requests_sent = db.relationship(
        "DonationRequest", foreign_keys="DonationRequest.requester_id", back_populates="requester",
        cascade="all, delete-orphan",
    )
    donation_requests_received = db.relationship(
        "DonationRequest", foreign_keys="DonationRequest.owner_id", back_populates="owner"
    )
    purchase_requests_sent = db.relationship(
        "PurchaseRequest", foreign_keys="PurchaseRequest.buyer_id", back_populates="buyer",
        cascade="all, delete-orphan",
    )
    purchase_requests_received = db.relationship(
        "PurchaseRequest", foreign_keys="PurchaseRequest.seller_id", back_populates="seller"
    )
    borrowings = db.relationship(
        "BorrowingRecord", foreign_keys="BorrowingRecord.borrower_id", back_populates="borrower",
        cascade="all, delete-orphan",
    )
    lendings = db.relationship(
        "BorrowingRecord", foreign_keys="BorrowingRecord.owner_id", back_populates="owner"
    )
    conversations_as_first = db.relationship(
        "Conversation", foreign_keys="Conversation.participant1_id", back_populates="participant1"
    )
    conversations_as_last = db.relationship(
        "Conversation", foreign_keys="Conversation.participant2_id", back_populates="participant2"
    )
    messages_sent = db.relationship(
        "Message", foreign_keys="Message.sender_id", back_populates="sender", cascade="all, delete-orphan"
    )
    reports_filed = db.relationship(
        "Report", foreign_keys="Report.reporter_id", back_populates="reporter", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        try:
            return check_password_hash(self.password_hash, password)
        except (ValueError, TypeError):
            return False

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]

    @property
    def is_active(self) -> bool:  # Flask-Login: blocked users cannot authenticate.
        return bool(self.is_active_account and not self.is_blocked)

    @property
    def unread_messages_count(self) -> int:
        return Message.query.filter_by(receiver_id=self.id, is_read=False).count()

    @property
    def unread_notifications_count(self) -> int:
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()

    def __repr__(self):
        return f"<User {self.email}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(110), nullable=False, unique=True, index=True)
    icon = db.Column(db.String(60), default="bi-book")
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    materials = db.relationship("EducationalMaterial", back_populates="category")
    library_books = db.relationship("LibraryBook", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


class EducationalMaterial(db.Model):
    """A book/marketplace listing. ``listing_type`` separates sale, exchange and donation."""

    __tablename__ = "educational_materials"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(150))
    subject = db.Column(db.String(120))
    educational_level = db.Column(db.String(120))
    listing_type = db.Column(db.String(20), default="sale", nullable=False, index=True)
    description = db.Column(db.Text)
    condition = db.Column(db.String(30), default="Good")
    price = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    original_price = db.Column(db.Numeric(10, 2))
    location = db.Column(db.String(180))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    contact_info = db.Column(db.String(180))
    status = db.Column(db.String(20), default="available", nullable=False, index=True)
    views = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    seller = db.relationship("User", back_populates="materials")
    category = db.relationship("Category", back_populates="materials")
    images = db.relationship(
        "MaterialImage", back_populates="material", cascade="all, delete-orphan", order_by="MaterialImage.id"
    )
    exchange_requests = db.relationship(
        "ExchangeRequest", foreign_keys="ExchangeRequest.material_id",
        back_populates="material", cascade="all, delete-orphan",
    )
    donation_requests = db.relationship("DonationRequest", back_populates="material", cascade="all, delete-orphan")
    purchase_requests = db.relationship("PurchaseRequest", back_populates="material", cascade="all, delete-orphan")
    reports = db.relationship("Report", back_populates="material", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_material_search", "title", "author", "subject"),
        Index("ix_material_filters", "listing_type", "status", "category_id"),
    )

    @property
    def primary_image(self):
        for image in self.images:
            if image.is_primary:
                return image
        return self.images[0] if self.images else None

    @property
    def is_available(self) -> bool:
        return self.status == "available"

    def __repr__(self):
        return f"<EducationalMaterial {self.title}>"


class MaterialImage(db.Model):
    __tablename__ = "material_images"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("educational_materials.id", ondelete="CASCADE"), index=True)
    library_book_id = db.Column(db.Integer, db.ForeignKey("library_books.id", ondelete="CASCADE"), index=True)
    filename = db.Column(db.String(255), nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    material = db.relationship("EducationalMaterial", back_populates="images")
    library_book = db.relationship("LibraryBook", back_populates="images")

    __table_args__ = (
        CheckConstraint("material_id IS NOT NULL OR library_book_id IS NOT NULL", name="ck_image_owner"),
    )

    @property
    def url(self) -> str:
        from flask import url_for
        return url_for("static", filename="uploads/" + self.filename)


class ExchangeRequest(db.Model):
    __tablename__ = "exchange_requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column(
        db.Integer, db.ForeignKey("educational_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    offered_material_id = db.Column(db.Integer, db.ForeignKey("educational_materials.id", ondelete="SET NULL"))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id], back_populates="exchange_requests_sent")
    owner = db.relationship("User", foreign_keys=[owner_id], back_populates="exchange_requests_received")
    material = db.relationship("EducationalMaterial", foreign_keys=[material_id], back_populates="exchange_requests")
    offered_material = db.relationship("EducationalMaterial", foreign_keys=[offered_material_id])

    __table_args__ = (
        UniqueConstraint("requester_id", "material_id", name="uq_exchange_request"),
    )


class DonationRequest(db.Model):
    __tablename__ = "donation_requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column(
        db.Integer, db.ForeignKey("educational_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    requester = db.relationship("User", foreign_keys=[requester_id], back_populates="donation_requests_sent")
    owner = db.relationship("User", foreign_keys=[owner_id], back_populates="donation_requests_received")
    material = db.relationship("EducationalMaterial", back_populates="donation_requests")

    __table_args__ = (
        UniqueConstraint("requester_id", "material_id", name="uq_donation_request"),
    )


class PurchaseRequest(db.Model):
    """Records genuine buyer interest; payments/collection are handled offline."""

    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column(
        db.Integer, db.ForeignKey("educational_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    buyer = db.relationship("User", foreign_keys=[buyer_id], back_populates="purchase_requests_sent")
    seller = db.relationship("User", foreign_keys=[seller_id], back_populates="purchase_requests_received")
    material = db.relationship("EducationalMaterial", back_populates="purchase_requests")

    __table_args__ = (
        UniqueConstraint("buyer_id", "material_id", name="uq_purchase_request"),
    )


class LibraryBook(db.Model):
    __tablename__ = "library_books"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(150))
    subject = db.Column(db.String(120))
    description = db.Column(db.Text)
    condition = db.Column(db.String(30), default="Good")
    borrowing_duration_days = db.Column(db.Integer, default=14, nullable=False)
    location = db.Column(db.String(180))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default="available", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    owner = db.relationship("User", back_populates="library_books")
    category = db.relationship("Category", back_populates="library_books")
    images = db.relationship(
        "MaterialImage", back_populates="library_book", cascade="all, delete-orphan", order_by="MaterialImage.id"
    )
    borrowing_records = db.relationship("BorrowingRecord", back_populates="book", cascade="all, delete-orphan")

    @property
    def primary_image(self):
        for image in self.images:
            if image.is_primary:
                return image
        return self.images[0] if self.images else None

    @property
    def active_record(self):
        for record in self.borrowing_records:
            if record.status in ("approved", "borrowed", "overdue"):
                return record
        return None

    def __repr__(self):
        return f"<LibraryBook {self.title}>"


class BorrowingRecord(db.Model):
    __tablename__ = "borrowing_records"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("library_books.id", ondelete="CASCADE"), nullable=False, index=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_duration_days = db.Column(db.Integer, default=14, nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    borrow_date = db.Column(db.Date)
    expected_return_date = db.Column(db.Date, index=True)
    actual_return_date = db.Column(db.Date)
    reminder_sent_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    book = db.relationship("LibraryBook", back_populates="borrowing_records")
    borrower = db.relationship("User", foreign_keys=[borrower_id], back_populates="borrowings")
    owner = db.relationship("User", foreign_keys=[owner_id], back_populates="lendings")

    @property
    def days_left(self):
        if self.expected_return_date and self.status in ("borrowed", "overdue", "approved"):
            return (self.expected_return_date - date.today()).days
        return None


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    participant1_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    participant2_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = db.Column(db.String(255), default="General")
    material_id = db.Column(db.Integer, db.ForeignKey("educational_materials.id", ondelete="SET NULL"))
    library_book_id = db.Column(db.Integer, db.ForeignKey("library_books.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    participant1 = db.relationship("User", foreign_keys=[participant1_id], back_populates="conversations_as_first")
    participant2 = db.relationship("User", foreign_keys=[participant2_id], back_populates="conversations_as_last")
    material = db.relationship("EducationalMaterial")
    library_book = db.relationship("LibraryBook")
    messages = db.relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                               order_by="Message.id")

    __table_args__ = (
        UniqueConstraint("participant1_id", "participant2_id", "topic", name="uq_conversation"),
    )

    def other_participant(self, user_id: int) -> User:
        return self.participant2 if self.participant1_id == user_id else self.participant1

    def is_participant(self, user_id: int) -> bool:
        return user_id in (self.participant1_id, self.participant2_id)

    def unread_count_for(self, user_id: int) -> int:
        return sum(1 for m in self.messages if not m.is_read and m.receiver_id == user_id)

    @property
    def last_message(self):
        return self.messages[-1] if self.messages else None


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="messages_sent")
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(db.String(40), default="info", nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="notifications")


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("educational_materials.id", ondelete="CASCADE"), index=True)
    library_book_id = db.Column(db.Integer, db.ForeignKey("library_books.id", ondelete="CASCADE"), index=True)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reason = db.Column(db.String(80), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default="open", nullable=False, index=True)
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)

    reporter = db.relationship("User", foreign_keys=[reporter_id], back_populates="reports_filed")
    material = db.relationship("EducationalMaterial", back_populates="reports")
    library_book = db.relationship("LibraryBook")
    reported_user = db.relationship("User", foreign_keys=[reported_user_id])
