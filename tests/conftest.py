"""Shared pytest fixtures for EduShare."""
from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.models import Category, User
from app.seed import seed_categories

TEST_PASSWORD = "Test@1234"


@pytest.fixture()
def app():
    application = create_app("testing")
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
        SERVER_NAME="localhost",
    )
    with application.app_context():
        db.create_all()
        seed_categories()
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def categories(app):
    return {category.name: category for category in Category.query.all()}


def make_user(email: str, full_name: str, *, is_admin: bool = False, **kwargs) -> User:
    user = User(
        full_name=full_name,
        email=email,
        phone=kwargs.get("phone", "9876543210"),
        educational_qualification=kwargs.get("qualification", "B.Tech"),
        institution=kwargs.get("institution", "Test College"),
        location=kwargs.get("location", "Bengaluru"),
        latitude=kwargs.get("latitude", 12.9716),
        longitude=kwargs.get("longitude", 77.5946),
        is_admin=is_admin,
        **{key: value for key, value in kwargs.items()
           if key not in {"phone", "qualification", "institution", "location", "latitude", "longitude"}},
    )
    user.set_password(kwargs.get("password", TEST_PASSWORD))
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture()
def users(app):
    people = {
        "alice": make_user("alice@example.com", "Alice Student"),
        "bob": make_user("bob@example.com", "Bob Buyer", location="Mysuru",
                         latitude=12.2958, longitude=76.6394),
        "admin": make_user("admin@example.com", "Ada Admin", is_admin=True),
    }
    db.session.commit()
    return people


@pytest.fixture()
def login_as(client):
    def _login(email: str, password: str = TEST_PASSWORD):
        return client.post(
            "/auth/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )
    return _login


def registration_payload(email: str = "new@example.com", **overrides):
    data = {
        "full_name": "New Student",
        "email": email,
        "phone": "9876500000",
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
        "educational_qualification": "B.Tech",
        "institution": "Test College",
        "location": "Bengaluru",
        "latitude": "12.9716",
        "longitude": "77.5946",
    }
    data.update(overrides)
    return data


def material_payload(category_id: int, listing_type: str = "sale", **overrides):
    data = {
        "title": "Engineering Mathematics",
        "author": "Dr. Sharma",
        "subject": "Mathematics",
        "educational_level": "Engineering",
        "category_id": str(category_id),
        "listing_type": listing_type,
        "description": "A clean textbook with solved examples.",
        "condition": "Good",
        "price": "350.00" if listing_type == "sale" else "0",
        "original_price": "799.00",
        "location": "Bengaluru",
        "latitude": "12.9716",
        "longitude": "77.5946",
        "contact_info": "Campus library",
    }
    data.update(overrides)
    return data


def library_payload(category_id: int, **overrides):
    data = {
        "title": "Operating System Concepts",
        "author": "Community Collection",
        "subject": "Computer Science",
        "category_id": str(category_id),
        "description": "Available to borrow free of cost.",
        "condition": "Good",
        "borrowing_duration_days": "14",
        "location": "Bengaluru",
        "latitude": "12.9716",
        "longitude": "77.5946",
    }
    data.update(overrides)
    return data
