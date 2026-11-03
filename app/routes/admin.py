from functools import wraps
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.admin_activity import AdminActivity
from app.models.blood_request import BloodRequest
from app.models.donor_profile import DonorProfile
from app.models.hospital import Hospital
from app.models.listing_report import ListingReport
from app.models.site_appearance import SiteAppearance
from app.models.user import User
from app.services.request_lifecycle import expire_stale_requests, notify_request_status
from app.services.email_service import send_notification_email
from app.utils.blood_compatibility import BLOOD_COMPATIBILITY

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "ADMIN":
            return jsonify({"success": False, "message": "Admin access required.", "errors": {}}), 403
        return fn(*args, **kwargs)
    return wrapper

DEFAULT_APPEARANCE = {"palette": "red-blue", "motion_level": "balanced", "live_background": True}


def get_appearance():
    appearance = db.session.get(SiteAppearance, 1)
    if appearance is None:
        appearance = SiteAppearance(id=1, **DEFAULT_APPEARANCE)
        db.session.add(appearance)
        db.session.commit()
    return appearance


def serialize_appearance(appearance):
    return {
        "palette": appearance.palette,
        "motion_level": appearance.motion_level,
        "live_background": appearance.live_background,
    }


def record_admin_action(action, target_type, target_id, details=None):
    db.session.add(AdminActivity(
        admin_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    ))


@admin_bp.route("/api/site/appearance")
def public_appearance():
    return jsonify({"success": True, "data": serialize_appearance(get_appearance())})


@admin_bp.route("/api/admin/appearance", methods=["GET", "PATCH"])
@login_required
@admin_required
def admin_appearance():
    appearance = get_appearance()
    if request.method == "GET":
        return jsonify({"success": True, "data": serialize_appearance(appearance)})

    payload = request.get_json(silent=True) or {}
    palette = payload.get("palette", appearance.palette)
    motion_level = payload.get("motion_level", appearance.motion_level)
    live_background = payload.get("live_background", appearance.live_background)
    if palette not in {"red-blue", "berry", "ocean"}:
        return jsonify({"success": False, "message": "Choose a supported palette."}), 400
    if motion_level not in {"reduced", "balanced", "expressive"}:
        return jsonify({"success": False, "message": "Choose a supported motion level."}), 400
    if not isinstance(live_background, bool):
        return jsonify({"success": False, "message": "live_background must be true or false."}), 400

    appearance.palette = palette
    appearance.motion_level = motion_level
    appearance.live_background = live_background
    record_admin_action("Updated site appearance", "site_appearance", appearance.id, f"Palette: {palette}; motion: {motion_level}; background: {live_background}")
    db.session.commit()
    return jsonify({"success": True, "data": serialize_appearance(appearance)})


@admin_bp.route("/api/admin/stats")
@login_required
@admin_required
def stats():
    expire_stale_requests()
    data = {
        "users": User.query.count(),
        "donors": DonorProfile.query.count(),
        "open_requests": BloodRequest.query.filter_by(status="OPEN").count(),
        "fulfilled_requests": BloodRequest.query.filter_by(status="FULFILLED").count(),
        "hospitals": Hospital.query.count(),
    }
    return jsonify({"success": True, "data": data})


@admin_bp.route("/api/admin/users")
@login_required
@admin_required
def users():
    items = [{"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active, "is_verified": user.is_verified, "created_at": user.created_at.isoformat()} for user in User.query.order_by(User.created_at.desc()).all()]
    return jsonify({"success": True, "data": {"items": items}})


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@login_required
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}
    changes = {key: payload[key] for key in ("is_active", "is_verified") if key in payload}
    if not changes or any(not isinstance(value, bool) for value in changes.values()):
        return jsonify({"success": False, "message": "Provide is_active and/or is_verified as true or false."}), 400
    if user.id == current_user.id and changes.get("is_active") is False:
        return jsonify({"success": False, "message": "You cannot deactivate your own admin account."}), 400
    for key, value in changes.items():
        setattr(user, key, value)
    record_admin_action("Updated user account", "user", user.id, "; ".join(f"{key}: {value}" for key, value in changes.items()))
    db.session.commit()
    return jsonify({"success": True, "data": {"id": user.id, "is_active": user.is_active, "is_verified": user.is_verified}})


@admin_bp.route("/api/admin/donors")
@login_required
@admin_required
def donors():
    items = [{"id": donor.id, "name": donor.user.name, "blood_group": donor.blood_group, "city": donor.city, "state": donor.state, "availability": donor.availability, "visibility": donor.visibility, "emergency_available": donor.emergency_available} for donor in DonorProfile.query.order_by(DonorProfile.updated_at.desc()).all()]
    return jsonify({"success": True, "data": {"items": items}})


@admin_bp.route("/api/admin/donors/<int:profile_id>", methods=["PATCH"])
@login_required
@admin_required
def update_donor(profile_id):
    donor = DonorProfile.query.get_or_404(profile_id)
    payload = request.get_json(silent=True) or {}
    changes = {}
    if "availability" in payload:
        if payload["availability"] not in {"available", "busy"}:
            return jsonify({"success": False, "message": "Choose available or busy."}), 400
        changes["availability"] = payload["availability"]
    if "visibility" in payload:
        if payload["visibility"] not in {"public", "private"}:
            return jsonify({"success": False, "message": "Choose public or private visibility."}), 400
        changes["visibility"] = payload["visibility"]
    if "blood_group" in payload:
        if payload["blood_group"] not in BLOOD_COMPATIBILITY:
            return jsonify({"success": False, "message": "Choose a valid blood group."}), 400
        changes["blood_group"] = payload["blood_group"]
    for field in ("city", "state"):
        if field in payload:
            value = payload[field]
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
                return jsonify({"success": False, "message": f"{field.title()} must contain 1 to 80 characters."}), 400
            changes[field] = value.strip()
    if not changes:
        return jsonify({"success": False, "message": "Provide at least one donor field to update."}), 400
    for field, value in changes.items():
        setattr(donor, field, value)
    record_admin_action("Updated donor listing", "donor_profile", donor.id, "; ".join(f"{key}: {value}" for key, value in changes.items()))
    db.session.commit()
    return jsonify({"success": True, "data": {
        "id": donor.id,
        "availability": donor.availability,
        "visibility": donor.visibility,
        "blood_group": donor.blood_group,
        "city": donor.city,
        "state": donor.state,
    }})


@admin_bp.route("/api/admin/requests")
@login_required
@admin_required
def admin_requests():
    expire_stale_requests()
    items = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    return jsonify({"success": True, "data": {"items": [{"id": item.id, "patient_name": item.patient_name, "status": item.status, "blood_group": item.blood_group, "city": item.city, "state": item.state, "units_required": item.units_required, "urgency": item.urgency} for item in items]}})


@admin_bp.route("/api/admin/listing-reports")
@login_required
@admin_required
def listing_reports():
    items = ListingReport.query.order_by(ListingReport.created_at.desc()).limit(200).all()
    serialized = []
    for item in items:
        if item.target_type == "donor":
            listing = db.session.get(DonorProfile, item.target_id)
            target = (
                f"{listing.user.name} · {listing.blood_group} · {listing.city or 'Unknown location'}"
                if listing is not None
                else "Listing no longer exists"
            )
        else:
            listing = db.session.get(Hospital, item.target_id)
            target = (
                f"{listing.name} · {listing.city or 'Unknown location'}"
                if listing is not None
                else "Listing no longer exists"
            )
        serialized.append({
            "id": item.id,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "target": target,
            "reason": item.reason,
            "status": item.status,
            "reporter": item.reporter.name,
            "created_at": item.created_at.isoformat(),
            "resolution_notes": item.resolution_notes,
        })
    return jsonify({"success": True, "data": {"items": serialized}})


@admin_bp.route("/api/admin/listing-reports/<int:report_id>", methods=["PATCH"])
@login_required
@admin_required
def update_listing_report(report_id):
    report = ListingReport.query.get_or_404(report_id)
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    notes = payload.get("resolution_notes", report.resolution_notes)
    if status not in {"OPEN", "RESOLVED", "DISMISSED"}:
        return jsonify({"success": False, "message": "Choose OPEN, RESOLVED, or DISMISSED."}), 400
    if notes is not None and (not isinstance(notes, str) or len(notes.strip()) > 1000):
        return jsonify({"success": False, "message": "Resolution notes must be under 1000 characters."}), 400
    report.status = status
    report.resolution_notes = notes.strip() or None if isinstance(notes, str) else None
    report.resolved_at = datetime.utcnow() if status in {"RESOLVED", "DISMISSED"} else None
    record_admin_action("Reviewed listing report", "listing_report", report.id, f"Status: {status}")
    db.session.commit()
    return jsonify({"success": True, "data": {"id": report.id, "status": report.status}})


@admin_bp.route("/api/admin/requests/<int:request_id>", methods=["PATCH"])
@login_required
@admin_required
def update_request(request_id):
    item = BloodRequest.query.get_or_404(request_id)
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in {"OPEN", "FULFILLED", "CANCELLED"}:
        return jsonify({"success": False, "message": "Choose an allowed request status."}), 400
    if item.status != "OPEN" and status != item.status:
        return jsonify({"success": False, "message": "Only open requests can transition to another status."}), 409
    item.status = status
    alerts = notify_request_status(item)
    record_admin_action("Changed blood request status", "blood_request", item.id, f"Status: {status}")
    db.session.commit()
    for recipient, notification, title, message in alerts:
        send_notification_email(recipient, title, message, notification)
    return jsonify({"success": True, "data": {"id": item.id, "status": item.status}})


@admin_bp.route("/api/admin/hospitals")
@login_required
@admin_required
def hospitals():
    items = Hospital.query.order_by(Hospital.created_at.desc()).all()
    return jsonify({"success": True, "data": {"items": [{"id": item.id, "name": item.name, "address": item.address, "city": item.city, "state": item.state, "phone": item.phone, "email": item.email, "verified": item.verified} for item in items]}})


@admin_bp.route("/api/admin/hospitals", methods=["POST"])
@login_required
@admin_required
def create_hospital():
    payload = request.get_json(silent=True) or {}
    if any(key in payload and not isinstance(payload[key], str) for key in ("name", "city", "state", "address", "phone", "email")):
        return jsonify({"success": False, "message": "Hospital fields must be text."}), 400
    name = (payload.get("name") or "").strip()
    city = (payload.get("city") or "").strip()
    state = (payload.get("state") or "").strip()
    if not name or not city or not state or len(name) > 180 or len(city) > 80 or len(state) > 80:
        return jsonify({"success": False, "message": "Hospital name, city, and state are required and must be valid."}), 400
    hospital = Hospital(
        name=name,
        city=city,
        state=state,
        address=(payload.get("address") or "").strip()[:255] or None,
        phone=(payload.get("phone") or "").strip()[:30] or None,
        email=(payload.get("email") or "").strip()[:150] or None,
        verified=False,
    )
    db.session.add(hospital)
    db.session.flush()
    record_admin_action("Added hospital for review", "hospital", hospital.id, f"{name}, {city}, {state}")
    db.session.commit()
    return jsonify({"success": True, "data": {"id": hospital.id, "verified": hospital.verified}}), 201


@admin_bp.route("/api/admin/hospitals/<int:hospital_id>", methods=["PATCH"])
@login_required
@admin_required
def update_hospital(hospital_id):
    hospital = Hospital.query.get_or_404(hospital_id)
    payload = request.get_json(silent=True) or {}
    changes = {}
    if "verified" in payload:
        if not isinstance(payload["verified"], bool):
            return jsonify({"success": False, "message": "verified must be true or false."}), 400
        changes["verified"] = payload["verified"]
    for key, maximum in {"name": 180, "address": 255, "city": 80, "state": 80, "phone": 30, "email": 150}.items():
        if key in payload:
            if payload[key] is not None and not isinstance(payload[key], str):
                return jsonify({"success": False, "message": f"{key} must be text."}), 400
            value = (payload[key] or "").strip()
            if key in {"name", "city", "state"} and not value:
                return jsonify({"success": False, "message": f"{key} cannot be blank."}), 400
            if len(value) > maximum:
                return jsonify({"success": False, "message": f"{key} is too long."}), 400
            changes[key] = value or None
    if not changes:
        return jsonify({"success": False, "message": "Provide at least one hospital field to update."}), 400
    for key, value in changes.items():
        setattr(hospital, key, value)
    record_admin_action("Updated hospital", "hospital", hospital.id, "; ".join(f"{key}: {value}" for key, value in changes.items()))
    db.session.commit()
    return jsonify({"success": True, "data": {"id": hospital.id, "verified": hospital.verified}})


@admin_bp.route("/api/admin/activities")
@login_required
@admin_required
def activities():
    items = AdminActivity.query.order_by(AdminActivity.created_at.desc()).limit(20).all()
    return jsonify({"success": True, "data": {"items": [{"id": item.id, "action": item.action, "target_type": item.target_type, "target_id": item.target_id, "metadata": item.details, "created_at": item.created_at.isoformat()} for item in items]}})
