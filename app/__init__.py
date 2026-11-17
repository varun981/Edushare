"""EduShare application factory."""
from __future__ import annotations

import os
from datetime import datetime

import click
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import logout_user
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import config_by_name
from .extensions import csrf, db, limiter, login_manager
from .models import Category, User, utcnow
from .utils import check_due_books


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    selected = config_name or os.environ.get("FLASK_CONFIG", "default")
    app.config.from_object(config_by_name.get(selected, config_by_name["default"]))

    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1,
                                x_port=1, x_prefix=1)

    if selected == "production":
        missing = [name for name in ("SECRET_KEY", "DATABASE_URL") if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                "Production requires " + ", ".join(missing) + ". See .env.example for setup."
            )

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register modular blueprints.
    from .admin import bp as admin_bp
    from .api import bp as api_bp
    from .auth import bp as auth_bp
    from .donation import bp as donation_bp
    from .exchange import bp as exchange_bp
    from .library import bp as library_bp
    from .main import bp as main_bp
    from .marketplace import bp as marketplace_bp
    from .messaging import bp as messaging_bp
    from .notifications import bp as notifications_bp
    from .profile import bp as profile_bp

    for blueprint in (main_bp, auth_bp, marketplace_bp, exchange_bp, donation_bp,
                      library_bp, messaging_bp, notifications_bp, profile_bp,
                      admin_bp, api_bp):
        app.register_blueprint(blueprint)

    @app.before_request
    def enforce_active_account():
        if request.endpoint in (None, "static"):
            return None
        if current_user_is_blocked():
            logout_user()
            flash("Your account has been suspended. Please contact an administrator.", "danger")
            return redirect(url_for("auth.login"))
        return None

    def current_user_is_blocked() -> bool:
        from flask_login import current_user
        return bool(current_user.is_authenticated and not current_user.is_active)

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        categories = []
        try:
            categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
        except Exception:  # e.g. during first migration before tables exist
            pass
        unread_notifications = current_user.unread_notifications_count if current_user.is_authenticated else 0
        unread_messages = current_user.unread_messages_count if current_user.is_authenticated else 0
        return {
            "categories": categories,
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages,
            "current_year": datetime.now().year,
            "app_name": "EduShare",
        }

    @app.template_filter("currency")
    def currency(value):
        try:
            return f"₹{float(value):,.2f}"
        except (TypeError, ValueError):
            return "₹0.00"

    @app.template_filter("datefmt")
    def datefmt(value, fmt="%d %b %Y"):
        return value.strftime(fmt) if value else "—"

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; font-src 'self' data:; manifest-src 'self'; "
            "worker-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
        )
        return response

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403,
                               title="Access denied",
                               message="You do not have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404,
                               title="Page not found",
                               message="The page or resource you requested does not exist."), 404

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return render_template("error.html", code=413, title="Upload too large",
                               message="Images must be smaller than 3 MB each (6 MB total per request)."), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled application error")
        return render_template("error.html", code=500, title="Something went wrong",
                               message="Please try again later. The issue has been logged."), 500

    @app.cli.command("init-db")
    def init_db_command():
        """Create all tables and seed educational categories."""
        db.create_all()
        from .seed import seed_categories
        count = seed_categories()
        db.session.commit()
        print(f"Database ready. {count} categories seeded.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Create sample data for local testing/demonstration only."""
        from .seed import seed_demo
        seed_demo()
        print("Demo data created. Demo password: Demo@1234 (development use only).")

    @app.cli.command("check-due")
    def check_due_command():
        """Create return reminders/overdue flags (intended for cron)."""
        changes = check_due_books()
        print(f"Due-date check complete: {changes} update(s).")

    @app.cli.command("set-admin")
    @click.argument("email")
    def set_admin_command(email):
        user = User.query.filter(User.email.ilike(email)).first()
        if not user:
            raise SystemExit(f"No user found with email {email}")
        user.is_admin = True
        db.session.commit()
        print(f"{user.email} is now an administrator.")

    with app.app_context():
        if app.config.get("AUTO_CREATE_TABLES"):
            db.create_all()
        try:
            from .seed import seed_categories
            seed_categories()
            db.session.commit()
        except Exception as exc:  # pragma: no cover - first-run guard
            db.session.rollback()
            app.logger.warning("Category seeding skipped: %s", exc)

    return app
