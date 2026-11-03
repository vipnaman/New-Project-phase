from datetime import datetime
import re

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.donor_profile import DonorProfile
from app.models.user import User


donors_bp = Blueprint("donors", __name__)


def serialize_donor(donor_profile):
    user = donor_profile.user
    return {
        "id": donor_profile.id,
        "name": user.name,
        "blood_group": donor_profile.blood_group,
        "city": donor_profile.city,
        "state": donor_profile.state,
        "area": donor_profile.area,
        "availability": donor_profile.availability,
        "emergency_available": donor_profile.emergency_available,
        "visibility": donor_profile.visibility,
        "last_donation_date": donor_profile.last_donation_date.isoformat() if donor_profile.last_donation_date else None,
        "updated_at": donor_profile.updated_at.isoformat() if donor_profile.updated_at else None,
        "verified": user.is_verified,
    }


@donors_bp.route("/api/donors", methods=["GET"])
def list_donors():
    blood_group = request.args.get("blood_group")
    city = request.args.get("city")
    state = request.args.get("state")
    area = request.args.get("area")
    availability = request.args.get("availability")
    emergency = request.args.get("emergency_available")
    page = request.args.get("page", 1, type=int)
    per_page = 12

    query = DonorProfile.query.join(User).filter(
        User.is_active.is_(True),
        User.is_verified.is_(True),
        DonorProfile.visibility == "public",
        DonorProfile.availability == "available",
    )

    if blood_group:
        query = query.filter(DonorProfile.blood_group == blood_group)
    if city:
        query = query.filter(DonorProfile.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(DonorProfile.state.ilike(f"%{state}%"))
    if area:
        query = query.filter(DonorProfile.area.ilike(f"%{area}%"))
    if availability:
        query = query.filter(DonorProfile.availability == availability)
    if emergency is not None:
        query = query.filter(DonorProfile.emergency_available == (emergency.lower() in {"1", "true", "yes"}))

    pagination = query.order_by(DonorProfile.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = [serialize_donor(item) for item in pagination.items]

    return jsonify({
        "success": True,
        "data": {
            "items": items,
            "page": page,
            "pages": pagination.pages,
            "total": pagination.total,
        },
    })


@donors_bp.route("/api/search/donors")
def search_donors():
    return list_donors()


@donors_bp.route("/api/donors", methods=["POST"])
@login_required
def create_donor_profile():
    payload = request.get_json(silent=True) or {}
    if payload.get("consent") not in {True, "true", "on", 1}:
        return jsonify({"success": False, "message": "Donor consent is required before saving this profile."}), 400
    blood_group = (payload.get("blood_group") or "").upper()
    if blood_group not in {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}:
        return jsonify({"success": False, "message": "Choose a valid blood group."}), 400
    availability = payload.get("availability", "available")
    if availability not in {"available", "busy"}:
        return jsonify({"success": False, "message": "Availability must be available or busy."}), 400
    visibility = payload.get("visibility", "public")
    if visibility not in {"public", "private"}:
        return jsonify({"success": False, "message": "Visibility must be public or private."}), 400
    phone = (payload.get("phone") or current_user.phone or "").strip()
    if phone and not re.fullmatch(r"\+?[0-9 ()-]{7,30}", phone):
        return jsonify({"success": False, "message": "Enter a valid contact phone number."}), 400
    city = (payload.get("city") or "").strip()
    state = (payload.get("state") or "").strip()
    if not city or len(city) > 80 or not state or len(state) > 80:
        return jsonify({"success": False, "message": "Choose a valid state and city."}), 400

    emergency_value = payload.get("emergency_available", False)
    if isinstance(emergency_value, bool):
        emergency_available = emergency_value
    elif str(emergency_value).lower() in {"true", "1", "yes", "on"}:
        emergency_available = True
    elif str(emergency_value).lower() in {"false", "0", "no", "off", ""}:
        emergency_available = False
    else:
        return jsonify({"success": False, "message": "Choose a valid emergency availability value."}), 400

    parsed_dates = {}
    for field in ("date_of_birth", "last_donation_date"):
        raw_date = payload.get(field)
        if raw_date:
            try:
                parsed_dates[field] = datetime.fromisoformat(raw_date)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": f"{field.replace('_', ' ').title()} is not a valid date."}), 400
        else:
            parsed_dates[field] = None
    profile = DonorProfile.query.filter_by(user_id=current_user.id).first()
    if profile is None:
        profile = DonorProfile(user_id=current_user.id)

    profile.blood_group = blood_group
    profile.date_of_birth = parsed_dates["date_of_birth"] or profile.date_of_birth
    profile.gender = payload.get("gender") or profile.gender
    profile.city = city
    profile.state = state
    profile.area = payload.get("area") or profile.area
    profile.availability = availability
    profile.last_donation_date = parsed_dates["last_donation_date"] or profile.last_donation_date
    profile.emergency_available = emergency_available
    profile.bio = payload.get("bio") or profile.bio
    profile.visibility = visibility
    current_user.phone = phone or None

    if profile.blood_group and profile.city:
        db.session.add(profile)
        db.session.commit()
        return jsonify({"success": True, "message": "Donor profile saved", "data": serialize_donor(profile)})

    return jsonify({"success": False, "message": "Blood group and city are required.", "errors": {}}), 400


@donors_bp.route("/api/donors/<int:donor_id>", methods=["GET"])
def donor_detail(donor_id):
    donor = DonorProfile.query.join(User).filter(
        DonorProfile.id == donor_id,
        User.is_active.is_(True),
        User.is_verified.is_(True),
        DonorProfile.visibility == "public",
        DonorProfile.availability == "available",
    ).first_or_404()
    return jsonify({"success": True, "data": serialize_donor(donor)})
