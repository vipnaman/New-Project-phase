from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.blood_request import BloodRequest
from app.models.contact_request import ContactRequest
from app.models.donation_record import DonationRecord
from app.models.donor_profile import DonorProfile
from app.models.hospital import Hospital
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import send_notification_email
from app.services.request_lifecycle import expire_stale_requests, notify_request_status
from app.services.matching_service import MatchingService
from app.utils.blood_compatibility import BLOOD_COMPATIBILITY, can_donate_to

requests_bp = Blueprint("requests", __name__)
REQUEST_STATUSES = {"OPEN", "FULFILLED", "CANCELLED", "EXPIRED"}
URGENCY_EXPIRY = {"normal": timedelta(days=7), "urgent": timedelta(days=7), "emergency": timedelta(days=7)}


def serialize_public_request(item):
    return {
        "id": item.id,
        "blood_group": item.blood_group,
        "city": item.city,
        "state": item.state,
        "urgency": item.urgency,
        "status": item.status,
        "units_required": item.units_required,
        "hospital": item.hospital.name if item.hospital and item.hospital.verified else None,
        "created_at": item.created_at.isoformat(),
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
    }


@requests_bp.route("/api/requests", methods=["GET"])
def list_requests():
    expire_stale_requests()
    query = BloodRequest.query
    status = request.args.get("status", "OPEN").upper()
    blood_group = request.args.get("blood_group")
    city = request.args.get("city")
    if status == "ALL" and current_user.is_authenticated and current_user.role == "ADMIN":
        pass
    elif status == "ALL" and current_user.is_authenticated:
        query = query.filter(BloodRequest.requester_id == current_user.id)
    elif status in REQUEST_STATUSES:
        query = query.filter(BloodRequest.status == status)
    else:
        return jsonify({"success": False, "message": "Invalid request status filter."}), 400
    if blood_group:
        query = query.filter(BloodRequest.blood_group == blood_group)
    if city:
        query = query.filter(BloodRequest.city.ilike(f"%{city}%"))
    if status == "ALL" and not current_user.is_authenticated:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    items = query.order_by(BloodRequest.created_at.desc()).limit(100).all()
    public_items = [serialize_public_request(item) for item in items]
    if current_user.is_authenticated:
        for data, item in zip(public_items, items):
            data["is_owner"] = item.requester_id == current_user.id
            if data["is_owner"] or current_user.role == "ADMIN":
                data.update({"patient_name": item.patient_name, "description": item.description})
    return jsonify({"success": True, "data": {"items": public_items}})


@requests_bp.route("/api/hospitals", methods=["GET"])
def list_verified_hospitals():
    hospitals = Hospital.query.filter_by(verified=True).order_by(Hospital.name.asc()).limit(500).all()
    return jsonify({"success": True, "data": {"items": [{
        "id": hospital.id,
        "name": hospital.name,
        "city": hospital.city,
        "state": hospital.state,
    } for hospital in hospitals]}})


@requests_bp.route("/api/requests", methods=["POST"])
@login_required
def create_request():
    payload = request.get_json(silent=True) or {}
    blood_group = (payload.get("blood_group") or "").upper()
    urgency = (payload.get("urgency") or "normal").lower()
    city = (payload.get("city") or "").strip()
    state = (payload.get("state") or "").strip()
    try:
        units_required = int(payload.get("units_required", 1) or 1)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Units required must be a whole number."}), 400

    if blood_group not in BLOOD_COMPATIBILITY:
        return jsonify({"success": False, "message": "Choose a valid blood group."}), 400
    if urgency not in URGENCY_EXPIRY:
        return jsonify({"success": False, "message": "Choose normal, urgent, or emergency urgency."}), 400
    if not city or len(city) > 80 or len(state) > 80:
        return jsonify({"success": False, "message": "A valid city and state are required."}), 400
    if not 1 <= units_required <= 20:
        return jsonify({"success": False, "message": "Units required must be between 1 and 20."}), 400

    now = datetime.utcnow()
    request_obj = BloodRequest(
        requester_id=current_user.id,
        patient_name=(payload.get("patient_name") or current_user.name).strip()[:120],
        blood_group=blood_group,
        units_required=units_required,
        city=city,
        state=state,
        urgency=urgency,
        required_date=now,
        description=(payload.get("description") or "").strip()[:2000],
        contact_preference="platform",
        status="OPEN",
        expires_at=now + URGENCY_EXPIRY[urgency],
    )
    hospital_id = payload.get("hospital_id")
    if hospital_id:
        try:
            hospital_id = int(hospital_id)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Choose a valid hospital."}), 400
        hospital = Hospital.query.filter_by(id=hospital_id, verified=True).first()
        if hospital is None:
            return jsonify({"success": False, "message": "Choose a hospital verified by RAKTA or leave hospital blank."}), 400
        request_obj.hospital_id = hospital.id
    elif payload.get("hospital_name"):
        return jsonify({"success": False, "message": "Select a verified hospital from the list."}), 400

    db.session.add(request_obj)
    db.session.commit()

    matches = MatchingService.find_compatible_donors(request_obj.blood_group, city=request_obj.city, state=request_obj.state, emergency_only=request_obj.urgency.lower() == "emergency")
    alert_recipients = []
    for donor in matches[:5]:
        if donor.user_id == current_user.id:
            continue
        title = "Blood request matched"
        message = f"A blood request for {request_obj.blood_group} is active in {request_obj.city}. Sign in to review the request and respond."
        notification = Notification(user_id=donor.user_id, title=title, message=message, type="match")
        db.session.add(notification)
        alert_recipients.append((donor.user, notification, title, message))
    if not matches:
        title = "Request published"
        message = "Your request is live. We will notify you if a compatible donor becomes available."
        notification = Notification(user_id=current_user.id, title=title, message=message, type="request")
        db.session.add(notification)
        alert_recipients.append((current_user._get_current_object(), notification, title, message))
    db.session.commit()
    for recipient, notification, title, message in alert_recipients:
        send_notification_email(recipient, title, message, notification)

    return jsonify({"success": True, "message": "Blood request created successfully", "data": {"id": request_obj.id, "status": request_obj.status, "matches": len(matches)}}), 201


@requests_bp.route("/api/requests/<int:request_id>", methods=["GET"])
def request_detail(request_id):
    expire_stale_requests()
    item = BloodRequest.query.get_or_404(request_id)
    data = serialize_public_request(item)
    if current_user.is_authenticated and (current_user.id == item.requester_id or current_user.role == "ADMIN"):
        data.update({"patient_name": item.patient_name, "description": item.description})
    return jsonify({"success": True, "data": data})


@requests_bp.route("/api/requests/<int:request_id>", methods=["PATCH"])
@login_required
def update_request(request_id):
    item = BloodRequest.query.get_or_404(request_id)
    if item.requester_id != current_user.id and current_user.role != "ADMIN":
        return jsonify({"success": False, "message": "Unauthorized", "errors": {}}), 403

    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    alerts = []
    if status is not None:
        status = str(status).upper()
        if status not in REQUEST_STATUSES:
            return jsonify({"success": False, "message": "Choose a valid request status."}), 400
        if current_user.role != "ADMIN" and status not in {"CANCELLED", "FULFILLED"}:
            return jsonify({"success": False, "message": "Requesters may only cancel or fulfill their own open requests."}), 403
        if item.status != "OPEN" or status == "EXPIRED":
            return jsonify({"success": False, "message": "This request cannot transition from its current status."}), 409
        item.status = status
        alerts = notify_request_status(item, notify_requester=current_user.role == "ADMIN")
    db.session.commit()
    for recipient, notification, title, message in alerts:
        send_notification_email(recipient, title, message, notification)
    return jsonify({"success": True, "message": "Request updated", "data": {"id": item.id, "status": item.status}})


def serialize_contact_request(item, viewer_id):
    data = {
        "id": item.id,
        "status": item.status,
        "message": item.message,
        "created_at": item.created_at.isoformat(),
        "request_id": item.blood_request_id,
        "requester_name": item.requester.name,
        "donor_name": item.donor.name,
        "initiator_name": item.requester.name if item.initiator_id == item.requester_id else item.donor.name,
        "initiated_by_viewer": item.initiator_id == viewer_id,
        "can_respond": viewer_id != item.initiator_id and item.status == "PENDING",
        "blood_group": item.donor.donor_profile.blood_group if item.donor.donor_profile else None,
        "city": item.donor.donor_profile.city if item.donor.donor_profile else None,
    }
    if item.status == "ACCEPTED":
        contact = item.requester if viewer_id == item.donor_id else item.donor
        data["contact_phone"] = contact.phone
    return data


@requests_bp.route("/api/contact-requests", methods=["GET", "POST"])
@login_required
def contact_requests():
    if request.method == "GET":
        items = ContactRequest.query.filter(
            db.or_(ContactRequest.requester_id == current_user.id, ContactRequest.donor_id == current_user.id)
        ).order_by(ContactRequest.created_at.desc(), ContactRequest.id.desc()).limit(100).all()
        return jsonify({"success": True, "data": {"items": [serialize_contact_request(item, current_user.id) for item in items]}})

    payload = request.get_json(silent=True) or {}
    try:
        profile_id = int(payload.get("donor_profile_id"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "A valid donor profile is required."}), 400
    profile = DonorProfile.query.join(User).filter(
        DonorProfile.id == profile_id,
        User.is_active.is_(True),
        User.is_verified.is_(True),
        DonorProfile.visibility == "public",
        DonorProfile.availability == "available",
    ).first()
    if profile is None:
        return jsonify({"success": False, "message": "This donor is not currently available for contact."}), 404
    if profile.user_id == current_user.id:
        return jsonify({"success": False, "message": "You cannot contact your own donor profile."}), 400

    blood_request_id = payload.get("request_id")
    if blood_request_id:
        blood_request = BloodRequest.query.filter_by(id=blood_request_id, requester_id=current_user.id, status="OPEN").first()
        if blood_request is None:
            return jsonify({"success": False, "message": "Choose one of your open requests."}), 400
    else:
        blood_request = None

    duplicate = ContactRequest.query.filter_by(
        requester_id=current_user.id,
        donor_id=profile.user_id,
        blood_request_id=blood_request.id if blood_request else None,
        status="PENDING",
    ).first()
    if duplicate:
        return jsonify({"success": False, "message": "A contact request is already pending."}), 409

    contact = ContactRequest(
        requester_id=current_user.id,
        donor_id=profile.user_id,
        initiator_id=current_user.id,
        blood_request_id=blood_request.id if blood_request else None,
        message=(payload.get("message") or "A requester would like to contact you about donating.").strip()[:255],
        status="PENDING",
    )
    db.session.add(contact)
    notification_title = "Donor contact request"
    notification_message = f"{current_user.name} would like to contact you about a donation in {profile.city or 'your area'}."
    notification = Notification(
        user_id=profile.user_id,
        title=notification_title,
        message=notification_message,
        type="contact_request",
    )
    db.session.add(notification)
    db.session.commit()
    send_notification_email(profile.user, notification_title, notification_message, notification)
    return jsonify({"success": True, "message": "Contact request sent. Your phone details stay private until the donor accepts.", "data": {"id": contact.id, "status": contact.status}}), 201


@requests_bp.route("/api/contact-requests/<int:contact_id>/respond", methods=["POST"])
@login_required
def respond_to_contact_request(contact_id):
    contact = ContactRequest.query.filter(
        ContactRequest.id == contact_id,
        db.or_(ContactRequest.donor_id == current_user.id, ContactRequest.requester_id == current_user.id),
    ).first_or_404()
    if contact.initiator_id == current_user.id:
        return jsonify({"success": False, "message": "The recipient of this contact request must respond."}), 403
    if contact.status != "PENDING":
        return jsonify({"success": False, "message": "This contact request has already been answered."}), 409
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).upper()
    if status not in {"ACCEPTED", "DECLINED"}:
        return jsonify({"success": False, "message": "Choose ACCEPTED or DECLINED."}), 400
    contact.status = status
    contact.responded_at = datetime.utcnow()
    title = "Donor responded"
    message = "Your contact request was accepted. Phone details are now available in your contact requests." if status == "ACCEPTED" else "Your contact request was declined."
    notification = Notification(
        user_id=contact.initiator_id,
        title=title,
        message=message,
        type="contact_response",
    )
    db.session.add(notification)
    db.session.commit()
    recipient = contact.requester if contact.initiator_id == contact.requester_id else contact.donor
    send_notification_email(recipient, title, message, notification)
    return jsonify({"success": True, "data": serialize_contact_request(contact, current_user.id)})


@requests_bp.route("/api/dashboard/summary")
@login_required
def dashboard_summary():
    expire_stale_requests()
    profile = DonorProfile.query.filter_by(user_id=current_user.id).first()
    open_requests = BloodRequest.query.filter_by(requester_id=current_user.id, status="OPEN").count()
    fulfilled_requests = BloodRequest.query.filter_by(requester_id=current_user.id, status="FULFILLED").count()
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    pending_contacts = ContactRequest.query.filter(
        db.or_(ContactRequest.requester_id == current_user.id, ContactRequest.donor_id == current_user.id),
        ContactRequest.status == "PENDING",
        ContactRequest.initiator_id != current_user.id,
    ).count()
    donation_count = DonationRecord.query.filter_by(donor_id=current_user.id).count()
    return jsonify({"success": True, "data": {
        "donor_status": profile.availability.title() if profile else "Not registered",
        "open_requests": open_requests,
        "fulfilled_requests": fulfilled_requests,
        "unread_notifications": unread_notifications,
        "pending_contacts": pending_contacts,
        "donations": donation_count,
        "verified": current_user.is_verified,
    }})


@requests_bp.route("/api/requests/<int:request_id>/interest", methods=["POST"])
@login_required
def express_request_interest(request_id):
    expire_stale_requests()
    blood_request = BloodRequest.query.filter_by(id=request_id, status="OPEN").first_or_404()
    donor_profile = DonorProfile.query.join(User).filter(
        DonorProfile.user_id == current_user.id,
        User.is_active.is_(True),
        User.is_verified.is_(True),
        DonorProfile.visibility == "public",
        DonorProfile.availability == "available",
    ).first()
    if donor_profile is None:
        return jsonify({"success": False, "message": "Only verified donors marked available can respond to requests."}), 403
    if blood_request.requester_id == current_user.id:
        return jsonify({"success": False, "message": "You cannot respond to your own request."}), 400
    if not can_donate_to(donor_profile.blood_group, blood_request.blood_group):
        return jsonify({"success": False, "message": "Your blood group is not compatible with this request."}), 400
    duplicate = ContactRequest.query.filter_by(
        requester_id=blood_request.requester_id,
        donor_id=current_user.id,
        blood_request_id=blood_request.id,
        status="PENDING",
    ).first()
    if duplicate:
        return jsonify({"success": False, "message": "You already expressed interest in this request."}), 409

    contact = ContactRequest(
        requester_id=blood_request.requester_id,
        donor_id=current_user.id,
        initiator_id=current_user.id,
        blood_request_id=blood_request.id,
        message="A verified donor is available to help with your request.",
        status="PENDING",
    )
    db.session.add(contact)
    title = "A donor is available"
    message = f"A verified {donor_profile.blood_group} donor is available in {donor_profile.city or 'your area'}."
    notification = Notification(
        user_id=blood_request.requester_id,
        title=title,
        message=message,
        type="contact_request",
    )
    db.session.add(notification)
    db.session.commit()
    send_notification_email(blood_request.requester, title, message, notification)
    return jsonify({"success": True, "message": "Your interest was sent. Your phone remains private until the requester accepts.", "data": {"id": contact.id, "status": contact.status}}), 201
