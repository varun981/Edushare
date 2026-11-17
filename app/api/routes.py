"""Small REST-style JSON API used by the PWA front-end."""
from __future__ import annotations

from flask import abort, jsonify, request
from flask_login import current_user, login_required

from ..extensions import db, limiter
from ..models import (Conversation, EducationalMaterial, LibraryBook, Message,
                      Notification, utcnow)
from ..utils import apply_material_filters, bounding_box, distance_km, get_or_404, notify
from . import bp


def material_json(material):
    image = material.primary_image.url if material.primary_image else None
    return {
        "id": material.id,
        "title": material.title,
        "author": material.author,
        "subject": material.subject,
        "category": material.category.name if material.category else None,
        "listing_type": material.listing_type,
        "condition": material.condition,
        "price": str(material.price),
        "location": material.location,
        "status": material.status,
        "image": image,
        "url": f"/books/{material.id}",
    }


@bp.route("/materials")
@limiter.limit("120 per minute")
def materials():
    query = apply_material_filters(db.session.query(EducationalMaterial), request.args)
    items = query.limit(30).all()
    return jsonify(items=[material_json(item) for item in items])


@bp.route("/materials/<int:material_id>")
def material_detail(material_id):
    return jsonify(material=material_json(get_or_404(EducationalMaterial, material_id)))


@bp.route("/nearby")
def nearby():
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
        radius = float(request.args.get("radius", 25))
    except (TypeError, ValueError):
        abort(400, description="lat and lon must be valid numbers")
    results = []
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius)
    candidates = list(EducationalMaterial.query.filter(
        EducationalMaterial.status == "available",
        EducationalMaterial.latitude.between(min_lat, max_lat),
        EducationalMaterial.longitude.between(min_lon, max_lon),
    ).all())
    candidates += list(LibraryBook.query.filter(
        LibraryBook.status == "available",
        LibraryBook.latitude.between(min_lat, max_lat),
        LibraryBook.longitude.between(min_lon, max_lon),
    ).all())
    for item in candidates:
        km = distance_km(lat, lon, item.latitude, item.longitude)
        if km is not None and km <= radius:
            results.append({
                "id": item.id,
                "title": item.title,
                "type": "library" if isinstance(item, LibraryBook) else item.listing_type,
                "location": item.location,
                "distance_km": round(km, 1),
                "url": f"/library/{item.id}" if isinstance(item, LibraryBook) else f"/books/{item.id}",
            })
    results.sort(key=lambda row: row["distance_km"])
    return jsonify(items=results[:30])


@bp.route("/notifications")
@login_required
def notifications():
    rows = (Notification.query.filter_by(user_id=current_user.id)
            .order_by(Notification.created_at.desc()).limit(20).all())
    return jsonify(
        unread=current_user.unread_notifications_count,
        items=[{"id": n.id, "title": n.title, "message": n.message, "link": n.link,
                "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in rows],
    )


@bp.route("/conversations/<int:conversation_id>/messages")
@login_required
def messages(conversation_id):
    conversation = get_or_404(Conversation, conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    after = request.args.get("after", 0, type=int)
    rows = [m for m in conversation.messages if m.id > after]
    return jsonify(messages=[{
        "id": m.id, "body": m.body, "sender_id": m.sender_id,
        "sender": m.sender.display_name, "created_at": m.created_at.isoformat(),
    } for m in rows])


@bp.route("/conversations/<int:conversation_id>/messages", methods=["POST"])
@login_required
def post_message(conversation_id):
    conversation = get_or_404(Conversation, conversation_id)
    if not conversation.is_participant(current_user.id):
        abort(403)
    payload = request.get_json(silent=True) or {}
    body = str(payload.get("body", "")).strip()
    if not body or len(body) > 4000:
        abort(400, description="Message body must be 1-4000 characters")
    receiver_id = conversation.other_participant(current_user.id).id
    message = Message(
        conversation_id=conversation.id, sender_id=current_user.id,
        receiver_id=receiver_id, body=body, created_at=utcnow(),
    )
    db.session.add(message)
    conversation.updated_at = utcnow()
    notify(receiver_id, "new_message", f"New message from {current_user.display_name}",
           body[:120], f"/messages/{conversation.id}")
    db.session.commit()
    return jsonify(message={
        "id": message.id, "body": message.body, "sender_id": message.sender_id,
        "created_at": message.created_at.isoformat(),
    }), 201
