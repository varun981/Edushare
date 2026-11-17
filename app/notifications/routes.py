"""In-app notification centre."""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Notification
from ..utils import Pagination, get_or_404, safe_next_url
from . import bp


@bp.route("/")
@login_required
def notifications():
    query = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc())
    pagination = Pagination(query, per_page=20)
    return render_template("notifications.html", title="Notifications", pagination=pagination)


@bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = get_or_404(Notification, notification_id)
    if notification.user_id != current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return redirect(safe_next_url(request.referrer, "notifications.notifications"))


@bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    for notification in Notification.query.filter_by(user_id=current_user.id, is_read=False):
        notification.is_read = True
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.notifications"))


@bp.route("/<int:notification_id>/open")
@login_required
def open_notification(notification_id):
    notification = get_or_404(Notification, notification_id)
    if notification.user_id != current_user.id:
        abort(403)
    # Read state is updated by the POST /read endpoint from the page script;
    # following this link must not mutate server state.
    return redirect(safe_next_url(notification.link))

