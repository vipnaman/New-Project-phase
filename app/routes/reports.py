from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.donor_profile import DonorProfile
from app.models.hospital import Hospital
from app.models.listing_report import ListingReport

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/api/listing-reports", methods=["POST"])
@login_required
def create_listing_report():
    payload = request.get_json(silent=True) or {}
    target_type = payload.get("target_type")
    raw_target_id = payload.get("target_id")
    if isinstance(raw_target_id, bool) or not isinstance(raw_target_id, (int, str)):
        return jsonify({"success": False, "message": "Choose a valid listing to report."}), 400
    try:
        target_id = int(raw_target_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Choose a valid listing to report."}), 400
    reason = payload.get("reason")
    if target_type not in {"donor", "hospital"}:
        return jsonify({"success": False, "message": "Choose a donor or hospital listing."}), 400
    if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 1000:
        return jsonify({"success": False, "message": "Explain the issue in 5 to 1000 characters."}), 400

    model = DonorProfile if target_type == "donor" else Hospital
    listing = db.session.get(model, target_id)
    if listing is None:
        return jsonify({"success": False, "message": "That listing no longer exists."}), 404
    duplicate = ListingReport.query.filter_by(
        reporter_id=current_user.id,
        target_type=target_type,
        target_id=target_id,
        status="OPEN",
    ).first()
    if duplicate is not None:
        return jsonify({"success": False, "message": "You already have an open report for this listing."}), 409

    report = ListingReport(
        reporter_id=current_user.id,
        target_type=target_type,
        target_id=target_id,
        reason=reason.strip(),
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({"success": True, "message": "Report sent for administrator review.", "data": {"id": report.id}}), 201
