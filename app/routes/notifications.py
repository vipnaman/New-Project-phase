from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.notification import Notification

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/api/notifications", methods=["GET"])
@login_required
def list_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return jsonify({"success": True, "data": [{
        "id": item.id,
        "title": item.title,
        "message": item.message,
        "type": item.type,
        "is_read": item.is_read,
        "email_delivery_status": item.email_delivery_status,
        "created_at": item.created_at.isoformat(),
    } for item in notifications]})


@notifications_bp.route("/api/notifications/preferences", methods=["GET", "PATCH"])
@login_required
def notification_preferences():
    if request.method == "GET":
        return jsonify({"success": True, "data": {
            "email_notifications_enabled": current_user.email_notifications_enabled,
            "sms_available": False,
        }})
    payload = request.get_json(silent=True) or {}
    enabled = payload.get("email_notifications_enabled")
    if not isinstance(enabled, bool):
        return jsonify({"success": False, "message": "email_notifications_enabled must be true or false."}), 400
    current_user.email_notifications_enabled = enabled
    db.session.commit()
    return jsonify({"success": True, "data": {
        "email_notifications_enabled": current_user.email_notifications_enabled,
        "sms_available": False,
    }})


@notifications_bp.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def read_notification(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    item.is_read = True
    db.session.commit()
    return jsonify({"success": True, "message": "Notification marked as read"})
