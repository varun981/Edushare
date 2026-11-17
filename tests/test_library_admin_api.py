"""Community library, admin moderation, messaging, API and CLI tests."""
from __future__ import annotations

import re
from datetime import date, timedelta

from click.testing import CliRunner

from app.extensions import db
from app.models import (BorrowingRecord, Category, Conversation, EducationalMaterial,
                        LibraryBook, Message, Notification, Report, User)
from app.seed import seed_demo

from conftest import library_payload, material_payload


def create_book(client, categories, **overrides):
    response = client.post("/library/new", data=library_payload(categories["Engineering Books"].id, **overrides),
                           follow_redirects=True)
    assert response.status_code == 200
    with client.application.app_context():
        return LibraryBook.query.filter_by(title=overrides.get("title", "Operating System Concepts")).order_by(
            LibraryBook.id.desc()).first()


def create_listing(client, categories, **overrides):
    response = client.post("/books/new", data=material_payload(categories["Engineering Books"].id, **overrides),
                           follow_redirects=True)
    assert response.status_code == 200
    with client.application.app_context():
        return EducationalMaterial.query.filter_by(title=overrides.get("title", "Engineering Mathematics")).order_by(
            EducationalMaterial.id.desc()).first()


def test_library_borrow_handover_return_and_overdue(client, app, users, categories, login_as):
    login_as("alice@example.com")
    book = create_book(client, categories)
    own = client.post(f"/library/{book.id}/borrow", data={"requested_duration_days": "14"}, follow_redirects=True)
    assert b"own book" in own.data

    client.post("/auth/logout")
    login_as("bob@example.com")
    detail = client.get(f"/library/{book.id}")
    assert b"Operating System Concepts" in detail.data
    sent = client.post(f"/library/{book.id}/borrow",
                       data={"requested_duration_days": "14", "message": "For revision"},
                       follow_redirects=True)
    assert b"Borrow request sent" in sent.data
    with app.app_context():
        record = BorrowingRecord.query.filter_by(book_id=book.id).first()
        assert record.status == "pending"
        record_id = record.id

    client.post("/auth/logout")
    login_as("alice@example.com")
    client.post(f"/library/borrow/{record_id}/approve")
    with app.app_context():
        assert db.session.get(BorrowingRecord, record_id).status == "approved"

    client.post(f"/library/borrow/{record_id}/handover")
    with app.app_context():
        record = db.session.get(BorrowingRecord, record_id)
        assert record.status == "borrowed"
        assert record.borrow_date == date.today()
        assert record.expected_return_date == date.today() + timedelta(days=14)
        assert db.session.get(LibraryBook, book.id).status == "borrowed"

    with app.app_context():
        record = db.session.get(BorrowingRecord, record_id)
        record.expected_return_date = date.today() - timedelta(days=1)
        db.session.commit()

    client.get("/library/")  # triggers the due-date check
    with app.app_context():
        assert db.session.get(BorrowingRecord, record_id).status == "overdue"
        assert Notification.query.filter_by(type="overdue").count() >= 2

    client.post(f"/library/borrow/{record_id}/return")
    with app.app_context():
        assert db.session.get(BorrowingRecord, record_id).status == "returned"
        assert db.session.get(LibraryBook, book.id).status == "available"


def test_library_reject_and_cancel(client, app, users, categories, login_as):
    login_as("alice@example.com")
    book = create_book(client, categories, title="Database Systems")
    client.post("/auth/logout")

    login_as("bob@example.com")
    client.post(f"/library/{book.id}/borrow", data={"requested_duration_days": "7"})
    with app.app_context():
        record = BorrowingRecord.query.filter_by(book_id=book.id).first()
        record_id = record.id

    cancel = client.post(f"/library/borrow/{record_id}/cancel", follow_redirects=True)
    assert b"request has been cancelled" in cancel.data
    with app.app_context():
        assert db.session.get(BorrowingRecord, record_id) is None

    client.post(f"/library/{book.id}/borrow", data={"requested_duration_days": "7"})
    client.post("/auth/logout")
    login_as("alice@example.com")
    client.post(f"/library/borrow/{BorrowingRecord.query.first().id}/reject")
    with app.app_context():
        assert BorrowingRecord.query.first().status == "rejected"


def test_admin_rbac_and_moderation(client, app, users, categories, login_as):
    assert client.get("/admin/").status_code == 302
    login_as("bob@example.com")
    assert client.get("/admin/").status_code == 403

    client.post("/auth/logout")
    login_as("admin@example.com")
    for path in ("/admin/", "/admin/users", "/admin/listings", "/admin/reports",
                 "/admin/categories", "/admin/donations", "/admin/borrowing"):
        assert client.get(path).status_code == 200, path

    client.post("/auth/logout")
    login_as("alice@example.com")
    listing = create_listing(client, categories, title="Listing For Removal")
    client.post("/auth/logout")

    login_as("admin@example.com")
    removed = client.post(f"/admin/listings/{listing.id}/remove", follow_redirects=True)
    assert b"Listing removed" in removed.data
    with app.app_context():
        assert db.session.get(EducationalMaterial, listing.id) is None
        assert Notification.query.filter_by(user_id=users["alice"].id, type="moderation").count() == 1

    blocked = client.post(f"/admin/users/{users['bob'].id}/block", follow_redirects=True)
    assert b"status updated" in blocked.data
    with app.app_context():
        assert users["bob"].is_blocked is True
        assert users["bob"].is_active is False
    client.post(f"/admin/users/{users['bob'].id}/block")

    promoted = client.post(f"/admin/users/{users['bob'].id}/admin", follow_redirects=True)
    assert b"role updated" in promoted.data
    with app.app_context():
        assert users["bob"].is_admin is True


def test_admin_categories_and_reports(client, app, users, categories, login_as):
    login_as("admin@example.com")
    created = client.post("/admin/categories", data={
        "name": "Commerce Books", "icon": "bi-graph-up", "description": "Commerce materials",
    }, follow_redirects=True)
    assert b"Category created" in created.data
    with app.app_context():
        category = Category.query.filter_by(name="Commerce Books").first()
        assert category is not None
        category_id = category.id

    edited = client.post(f"/admin/categories?edit={category_id}", data={
        "category_id": str(category_id), "name": "Commerce & Finance", "icon": "bi-graph-up",
        "description": "Updated",
    }, follow_redirects=True)
    assert b"Category updated" in edited.data
    assert client.post(f"/admin/categories/{category_id}/toggle").status_code == 302
    with app.app_context():
        assert Category.query.filter_by(name="Commerce & Finance").first().is_active is False

    login_as("alice@example.com")
    listing = create_listing(client, categories, title="Reported Listing")
    with app.app_context():
        report = Report(reporter_id=users["bob"].id, material_id=listing.id,
                        reported_user_id=users["alice"].id, reason="Spam or scam")
        db.session.add(report)
        db.session.commit()
        report_id = report.id

    client.post("/auth/logout")
    login_as("admin@example.com")
    resolved = client.post(f"/admin/reports/{report_id}/resolve", data={
        "decision": "resolved", "admin_notes": "Reviewed and removed.", "status": "open",
    }, follow_redirects=True)
    assert b"Report updated" in resolved.data
    with app.app_context():
        assert db.session.get(Report, report_id).status == "resolved"
        assert db.session.get(Report, report_id).admin_notes == "Reviewed and removed."


def test_admin_form_csrf_token_is_submittable(client, app, users, login_as):
    login_as("admin@example.com")
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        page = client.get("/admin/categories").get_data(as_text=True)
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
        assert token is not None, "admin forms must render a hidden CSRF field"

        response = client.post("/admin/categories", data={
            "csrf_token": token.group(1),
            "name": "CSRF Check Books",
            "icon": "bi-shield-check",
            "description": "Created with CSRF protection enabled.",
        })
        assert response.status_code == 302
        with app.app_context():
            assert Category.query.filter_by(name="CSRF Check Books").first() is not None
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_messaging_ui_and_api_isolation(client, app, users, login_as):
    login_as("alice@example.com")
    started = client.post(f"/messages/start/{users['bob'].id}", data={"topic": "Study notes"}, follow_redirects=True)
    assert started.status_code == 200
    with app.app_context():
        conversation = Conversation.query.filter_by(topic="Study notes").first()
        assert conversation is not None
        conversation_id = conversation.id

    sent = client.post(f"/messages/{conversation_id}/send", data={"body": "Hello Bob!"}, follow_redirects=True)
    assert b"Hello Bob!" in sent.data
    with app.app_context():
        assert Message.query.filter_by(conversation_id=conversation_id).count() == 1

    api = client.get(f"/api/conversations/{conversation_id}/messages")
    assert api.status_code == 200
    assert api.get_json()["messages"][0]["body"] == "Hello Bob!"

    posted = client.post(f"/api/conversations/{conversation_id}/messages", json={"body": "API reply"})
    assert posted.status_code == 201
    assert posted.get_json()["message"]["body"] == "API reply"

    client.post("/auth/logout")
    login_as("admin@example.com")
    assert client.get(f"/messages/{conversation_id}").status_code == 403
    assert client.get(f"/api/conversations/{conversation_id}/messages").status_code == 403


def test_notifications_and_public_api(client, app, users, categories, login_as):
    login_as("alice@example.com")
    listing = create_listing(client, categories)
    client.post("/auth/logout")

    login_as("bob@example.com")
    client.post(f"/books/{listing.id}/interest", data={"message": "Interested"})
    page = client.get("/notifications/")
    assert page.status_code == 200
    with app.app_context():
        notification = Notification.query.filter_by(user_id=users["alice"].id).first()
        notification_id = notification.id

    client.post("/auth/logout")
    login_as("alice@example.com")
    assert client.post(f"/notifications/{notification_id}/read").status_code == 302
    with app.app_context():
        assert db.session.get(Notification, notification_id).is_read is True

    client.post("/notifications/read-all", follow_redirects=True)
    api = client.get("/api/notifications")
    assert api.status_code == 200
    assert api.get_json()["unread"] == 0

    client.post("/auth/logout")
    assert client.get("/api/notifications").status_code == 302
    materials = client.get("/api/materials")
    assert materials.status_code == 200
    assert materials.get_json()["items"]
    assert client.get(f"/api/materials/{listing.id}").get_json()["material"]["id"] == listing.id
    nearby = client.get("/api/nearby?lat=12.9716&lon=77.5946&radius=50")
    assert nearby.status_code == 200
    assert any(item["id"] == listing.id for item in nearby.get_json()["items"])
    assert client.get("/api/nearby?lat=bad&lon=0").status_code == 400


def test_cli_commands(app, client, users):
    runner = CliRunner()
    assert runner.invoke(app.cli, ["init-db"]).exit_code == 0
    assert runner.invoke(app.cli, ["check-due"]).exit_code == 0

    result = runner.invoke(app.cli, ["set-admin", "alice@example.com"])
    assert result.exit_code == 0
    with app.app_context():
        assert users["alice"].is_admin is True

    demo = runner.invoke(app.cli, ["seed-demo"])
    assert demo.exit_code == 0
    with app.app_context():
        assert User.query.filter_by(email="demo.admin@example.com").first() is not None
        assert Category.query.count() >= 12

    # Demo credentials must pass the same form validation as real accounts.
    demo_login = client.post("/auth/login", data={
        "email": "demo.admin@example.com",
        "password": "Demo@1234",
    })
    assert demo_login.status_code == 302
