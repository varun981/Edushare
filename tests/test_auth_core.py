"""Authentication, public pages, PWA assets and responsive shell tests."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.extensions import db
from app.models import User
from app.utils import generate_reset_token

from conftest import registration_payload, TEST_PASSWORD


def test_public_pages_load(client):
    for path in ("/", "/marketplace", "/exchange/", "/donate/", "/library/", "/search"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"EduShare" in response.data


def test_category_filter_links_do_not_500(client, categories):
    category_id = next(iter(categories.values())).id
    for path in (f"/search?category_id={category_id}", f"/library/?category_id={category_id}"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"EduShare" in response.data


def test_home_and_pwa_assets(client, app):
    manifest_response = client.get("/static/manifest.json")
    assert manifest_response.status_code == 200
    manifest = json.loads(manifest_response.data)
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert len(manifest["icons"]) >= 2

    sw = client.get("/service-worker.js")
    assert sw.status_code == 200
    assert sw.headers["Service-Worker-Allowed"] == "/"
    assert "no-cache" in sw.headers["Cache-Control"]
    body = sw.get_data(as_text=True)
    assert "/offline" in body
    assert "/static/images/icon-maskable-512.png" in body
    for private in ("/auth/", "/messages", "/profile", "/admin/", "/api/", "/static/uploads/"):
        assert private in body
    # A signed-in home page is personalised, so it must never be precached.
    assert "  '/',\n" not in body

    static_root = Path(app.static_folder)
    for icon in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "default-avatar.svg"):
        assert (static_root / "images" / icon).is_file()


def test_security_headers_and_responsive_css(client, app):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert b'rel="manifest"' in response.data
    assert b'class="mobile-nav"' in response.data

    css = (Path(app.static_folder) / "css" / "style.css").read_text(encoding="utf-8")
    assert "@media" in css
    assert ".mobile-nav" in css
    assert re.search(r"@media \(min-width:\s*820px\)[\s\S]*?\.mobile-nav\s*\{\s*display:\s*none", css)
    assert "grid-template-columns" in css


def test_registration_login_and_logout(client, app):
    response = client.post("/auth/register", data=registration_payload(), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="new@example.com").first()
        assert user is not None
        assert user.check_password(TEST_PASSWORD)
        assert user.is_active

    client.post("/auth/logout")
    bad = client.post("/auth/login", data={"email": "new@example.com", "password": "wrong"})
    assert bad.status_code == 200
    assert b"Invalid email or password" in bad.data

    good = client.post("/auth/login", data={"email": "new@example.com", "password": TEST_PASSWORD},
                       follow_redirects=True)
    assert b"Welcome back" in good.data
    client.post("/auth/logout")
    assert client.get("/dashboard").status_code == 302


def test_registration_validation_and_duplicate_email(client, app):
    weak = client.post("/auth/register", data=registration_payload(
        email="weak@example.com", password="short", confirm_password="short"))
    assert weak.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="weak@example.com").first() is None

    client.post("/auth/register", data=registration_payload())
    client.post("/auth/logout")
    duplicate = client.post("/auth/register", data=registration_payload(), follow_redirects=True)
    assert b"already exists" in duplicate.data


def test_blocked_account_cannot_log_in(client, app):
    with app.app_context():
        user = User(full_name="Blocked", email="blocked@example.com", phone="1234567890",
                    educational_qualification="B.Tech", institution="Test", location="Bengaluru")
        user.set_password(TEST_PASSWORD)
        user.is_blocked = True
        user.is_active_account = False
        db.session.add(user)
        db.session.commit()

    response = client.post("/auth/login", data={"email": "blocked@example.com", "password": TEST_PASSWORD},
                           follow_redirects=True)
    assert b"suspended" in response.data


def test_password_reset_flow(client, app, users):
    with app.app_context():
        token = generate_reset_token(users["alice"])

    forgot = client.post("/auth/forgot-password", data={"email": "alice@example.com"},
                         follow_redirects=True)
    assert b"secure reset link" in forgot.data

    page = client.get(f"/auth/reset-password/{token}")
    assert page.status_code == 200
    result = client.post(f"/auth/reset-password/{token}", data={
        "password": "Fresh@1234", "confirm_password": "Fresh@1234",
    }, follow_redirects=True)
    assert b"password has been updated" in result.data

    client.post("/auth/logout")
    assert client.post("/auth/login", data={"email": "alice@example.com", "password": "Fresh@1234"}).status_code == 302

    # A reset token is bound to the password hash, so replaying it fails.
    client.post("/auth/logout")
    replay = client.post(f"/auth/reset-password/{token}", data={
        "password": "Another@1234", "confirm_password": "Another@1234",
    })
    assert replay.status_code == 302
    assert "/auth/forgot-password" in replay.headers["Location"]


def test_production_never_exposes_password_reset_link(client, app, users):
    original = {key: app.config[key] for key in
                ("TESTING", "DEBUG", "MAIL_SERVER", "MAIL_USERNAME")}
    app.config.update(TESTING=False, DEBUG=False, MAIL_SERVER=None, MAIL_USERNAME=None)
    try:
        response = client.post("/auth/forgot-password",
                               data={"email": "alice@example.com"}, follow_redirects=True)
        assert response.status_code == 200
        assert b"/auth/reset-password/" not in response.data
        assert b"If that email is registered" in response.data
    finally:
        app.config.update(original)


def test_profile_edit_without_new_photo(client, app, users, login_as):
    login_as("alice@example.com")
    response = client.post("/profile/edit", data={
        "full_name": "Alice Updated",
        "phone": "9876501111",
        "educational_qualification": "M.Tech",
        "institution": "Test College",
        "location": "Mysuru",
        "latitude": "12.2958",
        "longitude": "76.6394",
        "bio": "Updated bio",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Profile updated successfully." in response.data
    with app.app_context():
        user = db.session.get(User, users["alice"].id)
        assert user.full_name == "Alice Updated"
        assert user.profile_image == "default-avatar.svg"


def test_public_profile_hides_contact_details(client, users):
    response = client.get(f"/profile/{users['alice'].id}")
    assert response.status_code == 200
    assert b"alice@example.com" not in response.data
    assert b"9876543210" not in response.data


def test_location_redirect_ignores_external_referrer(client, users, login_as):
    login_as("alice@example.com")
    response = client.post("/location", data={
        "location": "Bengaluru", "latitude": "12.9716", "longitude": "77.5946",
    }, headers={"Referer": "https://evil.example/phish"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/")
