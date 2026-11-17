"""Category seeding and opt-in demo data (never enabled automatically)."""
from __future__ import annotations

import re

from .extensions import db
from .models import (BorrowingRecord, Category, Conversation, DonationRequest,
                     EducationalMaterial, ExchangeRequest, LibraryBook, Message,
                     Notification, PurchaseRequest, Report, User, utcnow)

CATEGORY_NAMES = [
    ("School Books", "bi-book"),
    ("PUC Books", "bi-journal-text"),
    ("Diploma Books", "bi-award"),
    ("Engineering Books", "bi-cpu"),
    ("Medical Books", "bi-heart-pulse"),
    ("Degree Books", "bi-mortarboard"),
    ("Competitive Exam Books", "bi-trophy"),
    ("Handwritten Notes", "bi-pencil-square"),
    ("Previous-Year Question Papers", "bi-file-earmark-text"),
    ("Laboratory Manuals", "bi-flask"),
    ("Reference Books", "bi-library"),
    ("Study Materials", "bi-journal-code"),
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def seed_categories() -> int:
    count = 0
    for name, icon in CATEGORY_NAMES:
        if Category.query.filter_by(name=name).first():
            continue
        db.session.add(Category(name=name, slug=_slug(name), icon=icon,
                                description=f"{name} shared by the EduShare community."))
        count += 1
    return count


def _get_or_create_user(email, name, **kwargs):
    user = User.query.filter(User.email.ilike(email)).first()
    if user:
        return user
    password = kwargs.pop("password", "Demo@1234")
    user = User(
        full_name=name, email=email,
        phone=kwargs.pop("phone", "9876543210"),
        educational_qualification=kwargs.pop("qualification", "B.Tech"),
        institution=kwargs.pop("institution", "EduShare College"),
        location=kwargs.pop("location", "Bengaluru"),
        latitude=kwargs.pop("latitude", 12.9716),
        longitude=kwargs.pop("longitude", 77.5946),
        is_admin=kwargs.pop("is_admin", False),
        **kwargs,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def _material(owner, category, title, listing_type, price, **kwargs):
    item = EducationalMaterial(
        user_id=owner.id, category_id=category.id, title=title, listing_type=listing_type,
        price=price, author=kwargs.get("author", "Dr. A. Sharma"),
        subject=kwargs.get("subject", "Mathematics"),
        educational_level=kwargs.get("level", "Engineering"),
        description=kwargs.get("description", "Well-maintained educational material."),
        condition=kwargs.get("condition", "Good"),
        location=kwargs.get("location", owner.location),
        latitude=owner.latitude, longitude=owner.longitude,
        original_price=kwargs.get("original_price"),
        status="available", created_at=utcnow(),
    )
    db.session.add(item)
    db.session.flush()
    return item


def seed_demo() -> None:
    """Populate a local development database with realistic, functional samples."""
    seed_categories()
    db.session.commit()

    alice = _get_or_create_user("demo.student@example.com", "Demo Student", password="Demo@1234")
    rahul = _get_or_create_user("demo.seller@example.com", "Rahul Verma",
                                password="Demo@1234", location="Bengaluru",
                                latitude=12.9352, longitude=77.6245)
    librarian = _get_or_create_user("demo.librarian@example.com", "Priya Nair",
                                    password="Demo@1234", location="Mysuru",
                                    latitude=12.2958, longitude=76.6394)
    admin = _get_or_create_user("demo.admin@example.com", "EduShare Admin",
                                password="Demo@1234", is_admin=True)
    db.session.flush()

    categories = {c.name: c for c in Category.query.all()}
    eng = categories["Engineering Books"]
    notes = categories["Handwritten Notes"]
    school = categories["School Books"]

    listings = [
        _material(rahul, eng, "Engineering Mathematics – Volume I", "sale", 350,
                  subject="Mathematics", original_price=799,
                  description="Complete mathematics textbook with solved examples. Clean copy, no torn pages."),
        _material(rahul, eng, "Data Structures & Algorithms", "sale", 420,
                  subject="Computer Science", original_price=950),
        _material(alice, notes, "Machine Learning Handwritten Notes", "exchange", 0,
                  subject="Artificial Intelligence", description="Neat handwritten notes, 120 pages."),
        _material(alice, school, "NCERT Science Textbook – Class 10", "donation", 0,
                  subject="Science", level="School"),
    ]
    db.session.flush()

    library_books = []
    for title, owner, category in [
        ("Operating System Concepts", librarian, eng),
        ("Database Management Systems", librarian, eng),
        ("High School Physics Guide", alice, school),
    ]:
        book = LibraryBook(
            owner_id=owner.id, category_id=category.id, title=title,
            author="Community Collection", subject="Computer Science",
            description="Available to borrow free of cost from the community library.",
            condition="Good", borrowing_duration_days=14, location=owner.location,
            latitude=owner.latitude, longitude=owner.longitude, status="available",
            created_at=utcnow(),
        )
        db.session.add(book)
        library_books.append(book)
    db.session.flush()

    # A sample conversation demonstrating messaging between students.
    conversation = Conversation.query.filter_by(
        participant1_id=min(alice.id, rahul.id), participant2_id=max(alice.id, rahul.id),
        topic="Engineering Mathematics – Volume I",
    ).first()
    if not conversation:
        conversation = Conversation(
            participant1_id=min(alice.id, rahul.id), participant2_id=max(alice.id, rahul.id),
            topic=listings[0].title, material_id=listings[0].id,
        )
        db.session.add(conversation)
        db.session.flush()
        db.session.add_all([
            Message(conversation_id=conversation.id, sender_id=alice.id, receiver_id=rahul.id,
                    body="Hi! Is the Mathematics book still available?", created_at=utcnow()),
            Message(conversation_id=conversation.id, sender_id=rahul.id, receiver_id=alice.id,
                    body="Yes, it is. You can collect it on campus this week.", created_at=utcnow()),
        ])

    # A sample borrowing history record (approved but not yet handed over).
    existing = BorrowingRecord.query.filter_by(book_id=library_books[0].id, borrower_id=alice.id).first()
    if not existing:
        db.session.add(BorrowingRecord(
            book_id=library_books[0].id, borrower_id=alice.id, owner_id=librarian.id,
            requested_duration_days=14, status="approved", message="Needed for semester revision.",
            created_at=utcnow(),
        ))

    # A few sample requests and notices so dashboards/admin views are not empty.
    if not PurchaseRequest.query.filter_by(buyer_id=alice.id, material_id=listings[0].id).first():
        db.session.add(PurchaseRequest(
            buyer_id=alice.id, seller_id=rahul.id, material_id=listings[0].id,
            message="Is the book still available for pickup?", status="pending",
            created_at=utcnow(),
        ))
    if not ExchangeRequest.query.filter_by(requester_id=rahul.id, material_id=listings[2].id).first():
        db.session.add(ExchangeRequest(
            requester_id=rahul.id, owner_id=alice.id, material_id=listings[2].id,
            message="I can offer a Data Structures textbook in return.", status="pending",
            created_at=utcnow(),
        ))
    if not DonationRequest.query.filter_by(requester_id=rahul.id, material_id=listings[3].id).first():
        db.session.add(DonationRequest(
            requester_id=rahul.id, owner_id=alice.id, material_id=listings[3].id,
            message="Would love this for a student in my class.", status="pending",
            created_at=utcnow(),
        ))
    if not Notification.query.filter_by(user_id=rahul.id, title="New purchase interest").first():
        db.session.add(Notification(
            user_id=rahul.id, type="purchase_request", title="New purchase interest",
            message=f"Demo Student is interested in {listings[0].title}.",
            link=f"/books/{listings[0].id}", created_at=utcnow(),
        ))
    if not Report.query.filter_by(reporter_id=alice.id, material_id=listings[1].id).first():
        db.session.add(Report(
            reporter_id=alice.id, material_id=listings[1].id, reported_user_id=rahul.id,
            reason="Other", details="Sample report for administrator demonstration.",
            status="open", created_at=utcnow(),
        ))

    db.session.commit()
    print("Seeded users:", ", ".join(u.email for u in (alice, rahul, librarian, admin)))
