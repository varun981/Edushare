"""Application configuration.

All sensitive values come from environment variables (see .env.example).
MySQL is the default database in production. A local SQLite database is used
only when DATABASE_URL is not provided, so the project can be demonstrated
without inventing database credentials.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "app" / "static" / "uploads"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-insecure-key-change-in-production"
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    _database_url = os.environ.get("DATABASE_URL", "").strip()
    if not _database_url:
        _database_url = f"sqlite:///{INSTANCE_DIR / 'edushare.sqlite3'}"
    # Normalise the heroku-style postgres URL if a compatible driver is supplied.
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Session Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Uploads: maximum 6 MB per request, 3 MB per image.
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    UPLOAD_FOLDER = str(UPLOAD_DIR)
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
    ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    MAX_IMAGE_BYTES = 3 * 1024 * 1024
    MAX_IMAGES_PER_LISTING = 5

    # Rate limiting (sensitive endpoints have additional per-route limits).
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "1") == "1"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = "300 per hour"
    # Set to 1 only when deployed behind a trusted reverse proxy (e.g. Render)
    # so rate limiting and secure redirects see the real client address.
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"

    # Optional e-mail delivery for password resets. When SMTP is not
    # configured the reset link is shown on screen (development mode).
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@example.com")

    # Create missing tables automatically. Set to 0 when using Flask-Migrate.
    AUTO_CREATE_TABLES = os.environ.get("AUTO_CREATE_TABLES", "1") == "1"


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    AUTO_CREATE_TABLES = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": Config,
}
