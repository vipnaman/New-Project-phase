import hmac
import secrets

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    phone = (payload.get("phone") or "").strip()

    if not name or not email or not password:
        return jsonify({"success": False, "message": "Name, email, and password are required.", "errors": {}}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already registered.", "errors": {"email": "already exists"}}), 409

    user = User(name=name, email=email, phone=phone, role="USER")
    user.password = password
    db.session.add(user)
    db.session.commit()

    return jsonify({"success": True, "message": "Registration successful", "data": {"user": {"id": user.id, "name": user.name, "email": user.email}}}), 201


@auth_bp.route("/admin/setup", methods=["GET", "POST"])
def initial_admin_setup():
    if User.query.filter_by(role="ADMIN").first():
        abort(404)
    setup_token = current_app.config.get("ADMIN_SETUP_TOKEN")
    if request.method == "GET":
        return render_template("admin/setup.html", current_user=current_user, setup_enabled=bool(setup_token))
    if not setup_token:
        abort(404)

    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    submitted_token = request.form.get("setup_token") or ""
    if not hmac.compare_digest(submitted_token, setup_token):
        return render_template("admin/setup.html", current_user=current_user, error="Setup authorization was not accepted."), 403
    if email != "admin@gmail.com":
        return render_template("admin/setup.html", current_user=current_user, error="Use the configured administrator email."), 400
    if not name or len(password) < 10:
        return render_template("admin/setup.html", current_user=current_user, error="Enter a name and a password with at least 10 characters."), 400
    if User.query.filter_by(email=email).first():
        return render_template("admin/setup.html", current_user=current_user, error="That email already has an account."), 409

    user = User(name=name, email=email, role="ADMIN")
    user.password = password
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return render_template("admin/setup.html", current_user=current_user, error="Admin setup could not be completed. Use the secure CLI setup command."), 409
    login_user(user)
    session["_csrf_token"] = secrets.token_urlsafe(32)
    return redirect(url_for("main.admin_dashboard"))


@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.verify_password(password):
        return jsonify({"success": False, "message": "Invalid email or password", "errors": {}}), 401

    if not user.is_active:
        return jsonify({"success": False, "message": "This account is inactive.", "errors": {}}), 403

    remember = payload.get("remember") is True
    login_user(user, remember=remember)
    session["_csrf_token"] = secrets.token_urlsafe(32)
    user.last_login = __import__("datetime").datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "message": "Login successful", "data": {"user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}, "remembered": remember}})


@auth_bp.route("/api/auth/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.pop("_csrf_token", None)
    return jsonify({"success": True, "message": "Logged out successfully"})


@auth_bp.route("/api/auth/me")
@login_required
def me():
    return jsonify({
        "success": True,
        "data": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
        },
    })


@auth_bp.route("/api/auth/me", methods=["DELETE"])
@login_required
def delete_account():
    payload = request.get_json(silent=True) or {}
    password = payload.get("password") or ""
    if not isinstance(password, str) or not current_user.verify_password(password):
        return jsonify({"success": False, "message": "Enter your current password to remove your account."}), 400
    if current_user.role == "ADMIN" and User.query.filter_by(role="ADMIN", is_active=True).count() <= 1:
        return jsonify({"success": False, "message": "The last active administrator cannot remove their account."}), 409

    user_id = current_user.id
    email = f"deleted-{user_id}@deleted.invalid"
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"success": False, "message": "Account not found."}), 404

    from app.models.blood_request import BloodRequest
    from app.models.contact_request import ContactRequest
    from app.models.donation_record import DonationRecord
    from app.models.donor_profile import DonorProfile
    from app.models.listing_report import ListingReport
    from app.models.notification import Notification

    owned_requests = BloodRequest.query.filter_by(requester_id=user_id).all()
    request_ids = [item.id for item in owned_requests]
    ContactRequest.query.filter(
        db.or_(
            ContactRequest.requester_id == user_id,
            ContactRequest.donor_id == user_id,
            ContactRequest.blood_request_id.in_(request_ids) if request_ids else False,
        )
    ).delete(synchronize_session=False)
    for item in owned_requests:
        db.session.delete(item)
    DonationRecord.query.filter_by(donor_id=user_id).delete(synchronize_session=False)
    Notification.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    ListingReport.query.filter_by(reporter_id=user_id).update(
        {"reason": "Details removed after reporter account deletion."},
        synchronize_session=False,
    )

    profile = DonorProfile.query.filter_by(user_id=user_id).first()
    if profile is not None:
        db.session.delete(profile)

    user.name = "Deleted user"
    user.email = email
    user.phone = None
    user.role = "USER"
    user.is_active = False
    user.is_verified = False
    user.email_notifications_enabled = False
    user.password = secrets.token_urlsafe(32)
    db.session.commit()
    logout_user()
    return jsonify({"success": True, "message": "Your account has been removed and personal profile data anonymized."})
