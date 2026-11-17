"""Marketplace, exchange and donation end-to-end workflow tests."""
from __future__ import annotations

from app.extensions import db
from app.models import (Conversation, DonationRequest, EducationalMaterial,
                        ExchangeRequest, Notification, PurchaseRequest, Report)

from conftest import material_payload


def create_material(client, categories, listing_type="sale", **overrides):
    payload = material_payload(categories["Engineering Books"].id, listing_type, **overrides)
    response = client.post("/books/new", data=payload, follow_redirects=True)
    assert response.status_code == 200
    with client.application.app_context():
        return EducationalMaterial.query.filter_by(title=payload["title"]).order_by(
            EducationalMaterial.id.desc()).first()


def test_create_edit_and_delete_listing(client, app, users, categories, login_as):
    login_as("alice@example.com")
    item = create_material(client, categories, title="Discrete Mathematics")
    assert item.user_id == users["alice"].id
    assert item.listing_type == "sale"
    assert float(item.price) == 350.0

    edit = client.post(f"/books/{item.id}/edit", data=material_payload(
        categories["Engineering Books"].id, title="Discrete Mathematics (2nd Edition)", price="425.00"
    ), follow_redirects=True)
    assert b"Listing updated successfully" in edit.data
    with app.app_context():
        updated = db.session.get(EducationalMaterial, item.id)
    assert updated.title == "Discrete Mathematics (2nd Edition)"

    client.post("/auth/logout")
    login_as("bob@example.com")
    assert client.get(f"/books/{item.id}/edit").status_code == 403
    assert client.post(f"/books/{item.id}/delete").status_code == 403

    client.post("/auth/logout")
    login_as("alice@example.com")
    deleted = client.post(f"/books/{item.id}/delete", follow_redirects=True)
    assert b"Listing deleted" in deleted.data
    with app.app_context():
        assert db.session.get(EducationalMaterial, item.id) is None


def test_search_and_filters(client, app, users, categories, login_as):
    login_as("alice@example.com")
    create_material(client, categories, title="Digital Logic Design", price="200.00")
    create_material(client, categories, listing_type="exchange", title="Digital Notes Exchange", price="0")

    assert b"Digital Logic Design" in client.get("/search?q=Digital").data
    assert b"Digital Notes Exchange" in client.get("/search?q=Digital").data
    sale_only = client.get("/marketplace?q=Digital").get_data(as_text=True)
    assert "Digital Logic Design" in sale_only
    assert "Digital Notes Exchange" not in sale_only
    priced = client.get("/marketplace?min_price=300").get_data(as_text=True)
    assert "Digital Logic Design" not in priced


def test_purchase_interest_contact_and_report(client, app, users, categories, login_as):
    login_as("alice@example.com")
    item = create_material(client, categories, title="Signals and Systems")

    own = client.post(f"/books/{item.id}/interest", data={"message": "mine"}, follow_redirects=True)
    assert b"own listing" in own.data

    client.post("/auth/logout")
    login_as("bob@example.com")
    first = client.post(f"/books/{item.id}/interest", data={"message": "I am interested"},
                        follow_redirects=True)
    assert b"Purchase interest sent" in first.data
    with app.app_context():
        requests = PurchaseRequest.query.filter_by(material_id=item.id).all()
        assert len(requests) == 1
        assert requests[0].buyer_id == users["bob"].id
        assert Notification.query.filter_by(user_id=users["alice"].id, type="purchase_interest").count() == 1

    duplicate = client.post(f"/books/{item.id}/interest", data={"message": "again"}, follow_redirects=True)
    assert b"already expressed interest" in duplicate.data
    with app.app_context():
        assert PurchaseRequest.query.filter_by(material_id=item.id).count() == 1

    contact = client.post(f"/books/{item.id}/contact", follow_redirects=True)
    assert contact.status_code == 200
    with app.app_context():
        conversation = Conversation.query.filter_by(material_id=item.id).first()
        assert conversation is not None
        assert conversation.is_participant(users["bob"].id)
        assert not conversation.is_participant(users["admin"].id)

    report = client.post(f"/books/{item.id}/report", data={
        "reason": "Incorrect information", "details": "The edition is wrong.",
    }, follow_redirects=True)
    assert b"administrators will review" in report.data
    with app.app_context():
        report_row = Report.query.filter_by(material_id=item.id).first()
        assert report_row is not None
        assert Notification.query.filter_by(user_id=users["admin"].id, type="report").count() == 1


def test_exchange_request_lifecycle(client, app, users, categories, login_as):
    login_as("alice@example.com")
    item = create_material(client, categories, listing_type="exchange", title="Data Structures for Swap")
    client.post("/auth/logout")

    login_as("bob@example.com")
    sent = client.post(f"/exchange/{item.id}/request", data={"message": "Can I swap?"},
                       follow_redirects=True)
    assert b"Exchange request sent" in sent.data
    with app.app_context():
        exchange = ExchangeRequest.query.filter_by(material_id=item.id).first()
        assert exchange.status == "pending"
        request_id = exchange.id

    duplicate = client.post(f"/exchange/{item.id}/request", data={"message": "again"}, follow_redirects=True)
    assert b"already sent" in duplicate.data

    client.post("/auth/logout")
    login_as("alice@example.com")
    assert client.post(f"/exchange/requests/{request_id}/reject").status_code == 302
    with app.app_context():
        assert db.session.get(ExchangeRequest, request_id).status == "rejected"
        assert item.status == "available"

    # A fresh request can still be accepted and completed.
    client.post("/auth/logout")
    login_as("bob@example.com")
    second_item = create_material(client, categories, listing_type="exchange", title="Algorithms Notes")
    client.post("/auth/logout")
    login_as("alice@example.com")
    client.post(f"/exchange/{second_item.id}/request", data={"message": "Swap offer"})
    with app.app_context():
        second_request = ExchangeRequest.query.filter_by(material_id=second_item.id).first()
        second_id = second_request.id

    client.post("/auth/logout")
    login_as("bob@example.com")
    # second_item belongs to Bob, so only Bob can accept requests for it.
    client.post(f"/exchange/requests/{second_id}/accept")
    with app.app_context():
        assert db.session.get(ExchangeRequest, second_id).status == "accepted"
        assert db.session.get(EducationalMaterial, second_item.id).status == "reserved"


def test_donation_request_lifecycle(client, app, users, categories, login_as):
    login_as("alice@example.com")
    item = create_material(client, categories, listing_type="donation", title="Free NCERT Science")
    client.post("/auth/logout")

    login_as("bob@example.com")
    sent = client.post(f"/donate/{item.id}/request", data={"message": "I need this book"},
                       follow_redirects=True)
    assert b"Request sent" in sent.data
    with app.app_context():
        donation = DonationRequest.query.filter_by(material_id=item.id).first()
        assert donation.status == "pending"
        request_id = donation.id

    client.post("/auth/logout")
    login_as("alice@example.com")
    client.post(f"/donate/requests/{request_id}/approve")
    with app.app_context():
        assert db.session.get(DonationRequest, request_id).status == "approved"
        assert db.session.get(EducationalMaterial, item.id).status == "reserved"

    client.post(f"/donate/requests/{request_id}/complete", follow_redirects=True)
    with app.app_context():
        assert db.session.get(DonationRequest, request_id).status == "completed"
        assert db.session.get(EducationalMaterial, item.id).status == "sold"
