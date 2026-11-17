"""Private in-app messaging between conversation participants only."""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import MessageForm
from ..models import Conversation, Message, User, utcnow
from ..utils import (flash_form_errors, get_or_create_conversation, get_or_404,
                     notify, safe_next_url)
from . import bp


def _my_conversations():
    return sorted(
        current_user.conversations_as_first + current_user.conversations_as_last,
        key=lambda c: c.updated_at or c.created_at or utcnow(), reverse=True,
    )


def _participant_conversation(conversation_id):
    conversation = get_or_404(Conversation, conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    return conversation


@bp.route("/")
@login_required
def inbox():
    conversations = _my_conversations()
    active = conversations[0] if conversations else None
    for message in active.messages if active else []:
        if message.receiver_id == current_user.id:
            message.is_read = True
    if active:
        db.session.commit()
    return render_template("messages.html", title="Messages", conversations=conversations,
                           active=active, form=MessageForm())


@bp.route("/<int:conversation_id>")
@login_required
def conversation(conversation_id):
    active = _participant_conversation(conversation_id)
    for message in active.messages:
        if message.receiver_id == current_user.id:
            message.is_read = True
    db.session.commit()
    return render_template("messages.html", title="Messages", conversations=_my_conversations(),
                           active=active, form=MessageForm())


@bp.route("/<int:conversation_id>/send", methods=["POST"])
@login_required
def send_message(conversation_id):
    active = _participant_conversation(conversation_id)
    form = MessageForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("messaging.conversation", conversation_id=conversation_id))
    body = form.body.data.strip()
    message = Message(
        conversation_id=active.id, sender_id=current_user.id,
        receiver_id=active.other_participant(current_user.id).id,
        body=body, created_at=utcnow(),
    )
    db.session.add(message)
    active.updated_at = utcnow()
    notify(message.receiver_id, "new_message", f"New message from {current_user.display_name}",
           body[:120], url_for("messaging.conversation", conversation_id=active.id))
    db.session.commit()
    return redirect(url_for("messaging.conversation", conversation_id=active.id))


@bp.route("/start/<int:user_id>", methods=["POST"])
@login_required
def start_conversation(user_id):
    other = get_or_404(User, user_id)
    if other.id == current_user.id:
        flash("You cannot message yourself.", "warning")
        return redirect(url_for("main.index"))
    topic = (request.values.get("topic") or "General").strip()
    conversation_obj = get_or_create_conversation(current_user.id, other.id, topic=topic)
    db.session.commit()
    return redirect(url_for("messaging.conversation", conversation_id=conversation_obj.id))
