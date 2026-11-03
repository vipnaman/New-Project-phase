import os
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest

from app import create_app
from app.config import Config, get_database_url
from app.extensions import db
from app.models.donor_profile import DonorProfile
from app.models.blood_request import BloodRequest
from app.models.contact_request import ContactRequest
from app.models.hospital import Hospital
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import send_notification_email


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"RAKTA" in response.data


def test_location_dataset_has_state_city_options(client):
    response = client.get("/static/data/india-cities.json")
    assert response.status_code == 200
    locations = response.get_json()["states"]
    assert len(locations) == 36
    assert "Agra" in locations["Uttar Pradesh"]
    assert "Mumbai" in locations["Maharashtra"]


def test_registration_and_login(client):
    response = client.post(
        "/api/auth/register",
        json={"name": "Demo User", "email": "demo@example.com", "password": "secret123"},
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["success"] is True

    login_response = client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200
    body = login_response.get_json()
    assert body["success"] is True


def test_remember_me_sets_persistent_cookie(client):
    user = User(name="Remember User", email="remember@example.com", role="USER")
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": "remember@example.com", "password": "secret123", "remember": True},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["remembered"] is True
    assert any(cookie.startswith("remember_token=") for cookie in response.headers.getlist("Set-Cookie"))


def test_donor_search_returns_results(client):
    user = User(name="Donor One", email="donor@example.com", phone="9999999999", role="DONOR", is_verified=True)
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()

    profile = DonorProfile(
        user_id=user.id,
        blood_group="O+",
        city="Lucknow",
        state="UP",
        area="Aliganj",
        availability="available",
        emergency_available=True,
        visibility="public",
    )
    db.session.add(profile)
    db.session.commit()

    response = client.get("/api/donors?blood_group=O%2B&city=Lucknow")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["items"][0]["city"] == "Lucknow"
    assert "email" not in payload["data"]["items"][0]


def test_unverified_or_unavailable_donors_are_not_public(client):
    unverified = User(name="Pending Donor", email="pending@example.com", role="DONOR", is_verified=False)
    unverified.password = "secret123"
    unavailable = User(name="Busy Donor", email="busy@example.com", role="DONOR", is_verified=True)
    unavailable.password = "secret123"
    db.session.add_all([unverified, unavailable])
    db.session.commit()
    db.session.add_all([
        DonorProfile(user_id=unverified.id, blood_group="O+", city="Lucknow", state="Uttar Pradesh", availability="available", visibility="public"),
        DonorProfile(user_id=unavailable.id, blood_group="O+", city="Lucknow", state="Uttar Pradesh", availability="busy", visibility="public"),
    ])
    db.session.commit()

    response = client.get("/api/donors?city=Lucknow")
    assert response.status_code == 200
    assert response.get_json()["data"]["items"] == []


def test_donor_profile_requires_consent_and_valid_values(client):
    user = User(name="New Donor", email="new-donor@example.com", role="USER")
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})

    missing_consent = client.post("/api/donors", json={"blood_group": "O+", "city": "Lucknow", "state": "Uttar Pradesh"})
    assert missing_consent.status_code == 400
    invalid_group = client.post("/api/donors", json={"consent": True, "blood_group": "X+", "city": "Lucknow", "state": "Uttar Pradesh"})
    assert invalid_group.status_code == 400
    saved = client.post("/api/donors", json={"consent": True, "blood_group": "O+", "city": "Lucknow", "state": "Uttar Pradesh", "emergency_available": "false"})
    assert saved.status_code == 200
    assert saved.get_json()["data"]["emergency_available"] is False


def test_request_expiry_and_public_response_privacy(client):
    requester = User(name="Patient Name", email="patient@example.com", role="USER")
    requester.password = "secret123"
    db.session.add(requester)
    db.session.commit()
    expired = BloodRequest(
        requester_id=requester.id,
        patient_name="Private Patient",
        blood_group="O+",
        units_required=2,
        city="Lucknow",
        state="Uttar Pradesh",
        urgency="urgent",
        status="OPEN",
        description="Sensitive medical details",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    active = BloodRequest(
        requester_id=requester.id,
        patient_name="Private Patient",
        blood_group="A+",
        units_required=1,
        city="Kanpur",
        state="Uttar Pradesh",
        urgency="normal",
        status="OPEN",
        description="Do not expose this",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.session.add_all([expired, active])
    db.session.commit()

    listing = client.get("/api/requests").get_json()["data"]["items"]
    assert len(listing) == 1
    assert "patient_name" not in listing[0]
    assert "description" not in listing[0]
    assert db.session.get(BloodRequest, expired.id).status == "EXPIRED"
    detail = client.get(f"/api/requests/{active.id}").get_json()["data"]
    assert "patient_name" not in detail
    assert "description" not in detail


def test_requests_only_link_verified_hospitals(client):
    requester = User(name="Requester", email="requester@example.com", role="USER")
    requester.password = "secret123"
    db.session.add(requester)
    db.session.commit()
    client.post("/api/auth/login", json={"email": requester.email, "password": "secret123"})
    response = client.post("/api/requests", json={
        "blood_group": "O+", "city": "Lucknow", "state": "Uttar Pradesh", "hospital_name": "Unlisted Hospital"
    })
    assert response.status_code == 400
    assert Hospital.query.count() == 0

    approved = Hospital(name="Verified City Hospital", city="Lucknow", state="Uttar Pradesh", verified=True)
    pending = Hospital(name="Pending Clinic", city="Lucknow", state="Uttar Pradesh", verified=False)
    db.session.add_all([approved, pending])
    db.session.commit()
    visible_hospitals = client.get("/api/hospitals").get_json()["data"]["items"]
    assert [item["name"] for item in visible_hospitals] == [approved.name]
    linked = client.post("/api/requests", json={
        "blood_group": "O+",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "hospital_id": approved.id,
    })
    assert linked.status_code == 201
    assert BloodRequest.query.filter_by(id=linked.get_json()["data"]["id"]).first().hospital_id == approved.id


def test_contact_request_shares_phone_only_after_recipient_accepts(client):
    requester = User(name="Requester", email="contact-requester@example.com", phone="1111111111", role="USER")
    requester.password = "requester-password"
    donor = User(name="Verified Donor", email="contact-donor@example.com", phone="2222222222", role="DONOR", is_verified=True)
    donor.password = "donor-password"
    db.session.add_all([requester, donor])
    db.session.commit()
    profile = DonorProfile(user_id=donor.id, blood_group="O+", city="Lucknow", state="Uttar Pradesh", availability="available", visibility="public")
    blood_request = BloodRequest(
        requester_id=requester.id,
        patient_name="Patient",
        blood_group="O+",
        units_required=1,
        city="Lucknow",
        state="Uttar Pradesh",
        urgency="normal",
        status="OPEN",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.session.add_all([profile, blood_request])
    db.session.commit()

    client.post("/api/auth/login", json={"email": requester.email, "password": "requester-password"})
    assert client.get("/api/auth/me").get_json()["data"]["id"] == requester.id
    sent = client.post("/api/contact-requests", json={"donor_profile_id": profile.id, "request_id": blood_request.id})
    assert sent.status_code == 201
    contact_id = sent.get_json()["data"]["id"]
    pending = client.get("/api/contact-requests").get_json()["data"]["items"][0]
    assert "contact_phone" not in pending

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": donor.email, "password": "donor-password"})
    assert client.get("/api/auth/me").get_json()["data"]["id"] == donor.id
    donor_pending = client.get("/api/contact-requests").get_json()["data"]["items"][0]
    assert donor_pending["can_respond"] is True
    accepted = client.post(f"/api/contact-requests/{contact_id}/respond", json={"status": "ACCEPTED"})
    assert accepted.status_code == 200
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": requester.email, "password": "requester-password"})
    requester_contacts = client.get("/api/contact-requests").get_json()["data"]["items"]
    assert client.get("/api/auth/me").get_json()["data"]["id"] == requester.id
    requester_contact = next(item for item in requester_contacts if item["id"] == contact_id)
    assert requester_contact["requester_name"] == requester.name
    assert requester_contact["donor_name"] == donor.name
    assert requester_contact["initiated_by_viewer"] is True
    assert requester_contact["contact_phone"] == donor.phone

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": donor.email, "password": "donor-password"})
    donor_interest = client.post(f"/api/requests/{blood_request.id}/interest", json={})
    assert donor_interest.status_code == 201
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": requester.email, "password": "requester-password"})
    donor_contacts = client.get("/api/contact-requests").get_json()["data"]["items"]
    donor_initiated = next(item for item in donor_contacts if item["id"] != contact_id)
    assert donor_initiated["initiated_by_viewer"] is False
    assert donor_initiated["can_respond"] is True
    donor_initiated_id = donor_initiated["id"]
    requester_accepts = client.post(
        f"/api/contact-requests/{donor_initiated_id}/respond",
        json={"status": "ACCEPTED"},
    )
    assert requester_accepts.status_code == 200
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": donor.email, "password": "donor-password"})
    donor_view = client.get("/api/contact-requests").get_json()["data"]["items"]
    accepted_interest = next(item for item in donor_view if item["id"] == donor_initiated_id)
    assert accepted_interest["contact_phone"] == requester.phone


def test_dashboard_uses_authenticated_user_data(client):
    user = User(name="Dashboard User", email="dashboard@example.com", role="USER")
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()
    assert client.get("/dashboard").status_code == 302
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})
    summary = client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    data = summary.get_json()["data"]
    assert data["open_requests"] == 0
    assert data["donations"] == 0
    assert data["donor_status"] == "Not registered"


def test_incompatible_donor_cannot_offer_for_request(client):
    requester = User(name="Requester", email="compat-requester@example.com", role="USER")
    requester.password = "requester-password"
    donor = User(name="A Negative Donor", email="compat-donor@example.com", role="DONOR", is_verified=True)
    donor.password = "donor-password"
    db.session.add_all([requester, donor])
    db.session.commit()
    profile = DonorProfile(user_id=donor.id, blood_group="A-", city="Lucknow", state="Uttar Pradesh", availability="available", visibility="public")
    blood_request = BloodRequest(
        requester_id=requester.id,
        patient_name="Patient",
        blood_group="B+",
        units_required=1,
        city="Lucknow",
        state="Uttar Pradesh",
        urgency="normal",
        status="OPEN",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.session.add_all([profile, blood_request])
    db.session.commit()
    client.post("/api/auth/login", json={"email": donor.email, "password": "donor-password"})
    response = client.post(f"/api/requests/{blood_request.id}/interest", json={})
    assert response.status_code == 400


def test_admin_pages_require_admin_role(client):
    anonymous_response = client.get("/admin")
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith("/login")
    for path in ["/admin/users", "/admin/donors", "/admin/requests", "/admin/hospitals", "/admin/reports", "/admin/analytics", "/admin/settings"]:
        assert client.get(path).status_code == 302


def test_initial_admin_setup_is_token_gated_and_one_time(client):
    app = client.application
    app.config["ADMIN_SETUP_TOKEN"] = None
    locked_page = client.get("/admin/setup")
    assert locked_page.status_code == 200
    assert b"Initial admin creation is locked" in locked_page.data
    assert client.post("/admin/setup", data={}).status_code == 404

    app.config["ADMIN_SETUP_TOKEN"] = "test-only-private-bootstrap-token"
    login_page = client.get("/login")
    assert b"Set up the initial administrator" in login_page.data

    denied = client.post("/admin/setup", data={
        "name": "RAKTA Admin",
        "email": "admin@gmail.com",
        "setup_token": "wrong-token",
        "password": "admin-password",
    })
    assert denied.status_code == 403
    assert User.query.filter_by(email="admin@gmail.com").first() is None

    created = client.post("/admin/setup", data={
        "name": "RAKTA Admin",
        "email": "admin@gmail.com",
        "setup_token": "test-only-private-bootstrap-token",
        "password": "admin-password",
    })
    assert created.status_code == 302
    assert created.headers["Location"].endswith("/admin")
    assert User.query.filter_by(email="admin@gmail.com", role="ADMIN").first() is not None
    assert client.get("/admin/setup").status_code == 404
    assert b"Set up the initial administrator" not in client.get("/login").data

    user = User(name="Regular User", email="regular@example.com", role="USER")
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()
    login_response = client.post(
        "/api/auth/login",
        json={"email": "regular@example.com", "password": "secret123"},
    )

    assert login_response.status_code == 200
    assert client.get("/admin").status_code == 403


def test_admin_can_save_global_appearance(client):
    admin = User(name="Admin", email="admin@example.com", role="ADMIN")
    admin.password = "admin-password"
    db.session.add(admin)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin-password"})

    response = client.patch("/api/admin/appearance", json={
        "palette": "ocean",
        "motion_level": "expressive",
        "live_background": False,
    })
    assert response.status_code == 200
    assert client.get("/api/site/appearance").get_json()["data"] == {
        "palette": "ocean",
        "motion_level": "expressive",
        "live_background": False,
    }
    assert client.get("/admin/settings").status_code == 200


def test_admin_appearance_accepts_each_supported_palette(client):
    admin = User(name="Admin", email="palette-admin@example.com", role="ADMIN")
    admin.password = "admin-password"
    db.session.add(admin)
    db.session.commit()
    client.post("/api/auth/login", json={"email": admin.email, "password": "admin-password"})

    for palette in ("red-blue", "berry", "ocean", "forest", "lavender", "sunset", "gold"):
        response = client.patch("/api/admin/appearance", json={
            "palette": palette,
            "motion_level": "balanced",
            "live_background": False,
        })
        assert response.status_code == 200
        assert response.get_json()["data"]["palette"] == palette

    unsupported = client.patch("/api/admin/appearance", json={
        "palette": "unknown",
        "motion_level": "balanced",
        "live_background": False,
    })
    assert unsupported.status_code == 400


def test_admin_adds_and_verifies_hospital_before_public_listing(client):
    admin = User(name="Admin", email="hospital-admin@example.com", role="ADMIN")
    admin.password = "admin-password"
    db.session.add(admin)
    db.session.commit()
    client.post("/api/auth/login", json={"email": admin.email, "password": "admin-password"})

    created = client.post("/api/admin/hospitals", json={
        "name": "RAKTA City Hospital",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "phone": "1234567890",
    })
    assert created.status_code == 201
    hospital_id = created.get_json()["data"]["id"]
    assert client.get("/api/hospitals").get_json()["data"]["items"] == []

    updated = client.patch(f"/api/admin/hospitals/{hospital_id}", json={
        "address": "Central Lucknow",
        "verified": True,
    })
    assert updated.status_code == 200
    listed = client.get("/api/hospitals").get_json()["data"]["items"]
    assert len(listed) == 1
    assert listed[0]["name"] == "RAKTA City Hospital"
    assert listed[0]["city"] == "Lucknow"


def test_admin_can_update_user_access_without_self_lockout(client):
    admin = User(name="Admin", email="admin@gmail.com", role="ADMIN")
    admin.password = "admin-password"
    member = User(name="Member", email="member@example.com", role="USER")
    member.password = "member-password"
    db.session.add_all([admin, member])
    db.session.commit()

    login = client.post(
        "/api/auth/login",
        json={"email": "admin@gmail.com", "password": "admin-password"},
    )
    assert login.status_code == 200
    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert b"Manage users" in admin_page.data

    for path, expected in [
        ("/admin/users", b"adminUsersTable"),
        ("/admin/donors", b"adminDonorsTable"),
        ("/admin/requests", b"adminRequestsTable"),
        ("/admin/hospitals", b"adminHospitalsTable"),
        ("/admin/reports", b"adminReportsTable"),
        ("/admin/analytics", b"adminActivitiesTable"),
        ("/admin/settings", b"appearanceSettingsForm"),
    ]:
        page = client.get(path)
        assert page.status_code == 200
        assert expected in page.data

    update = client.patch(f"/api/admin/users/{member.id}", json={"is_active": False})
    assert update.status_code == 200
    assert db.session.get(User, member.id).is_active is False

    self_update = client.patch(f"/api/admin/users/{admin.id}", json={"is_active": False})
    assert self_update.status_code == 400

    activities = client.get("/api/admin/activities").get_json()["data"]["items"]
    assert activities[0]["action"] == "Updated user account"


def test_notification_preferences_and_email_delivery_status(client):
    user = User(name="Preferences User", email="preferences@example.com", role="USER")
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})

    preferences = client.get("/api/notifications/preferences")
    assert preferences.get_json()["data"]["email_notifications_enabled"] is True
    saved = client.patch("/api/notifications/preferences", json={"email_notifications_enabled": False})
    assert saved.status_code == 200

    notification = Notification(user_id=user.id, title="Test", message="Test message", type="test")
    db.session.add(notification)
    db.session.commit()
    assert send_notification_email(user, notification.title, notification.message, notification) is False
    assert notification.email_delivery_status == "DISABLED"
    assert client.get("/api/notifications").get_json()["data"][0]["email_delivery_status"] == "DISABLED"

    invalid = client.patch("/api/notifications/preferences", json={"email_notifications_enabled": "false"})
    assert invalid.status_code == 400


def test_requester_can_fulfill_request_and_close_pending_contacts(client):
    requester = User(name="Requester", email="fulfill-requester@example.com", role="USER")
    requester.password = "requester-password"
    donor = User(name="Donor", email="fulfill-donor@example.com", role="DONOR", is_verified=True)
    donor.password = "donor-password"
    db.session.add_all([requester, donor])
    db.session.commit()
    request_item = BloodRequest(
        requester_id=requester.id,
        patient_name="Patient",
        blood_group="O+",
        units_required=1,
        city="Lucknow",
        state="Uttar Pradesh",
        urgency="normal",
        status="OPEN",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.session.add(request_item)
    db.session.flush()
    contact = ContactRequest(
        requester_id=requester.id,
        donor_id=donor.id,
        initiator_id=donor.id,
        blood_request_id=request_item.id,
        status="PENDING",
    )
    db.session.add(contact)
    db.session.commit()

    client.post("/api/auth/login", json={"email": requester.email, "password": "requester-password"})
    response = client.patch(f"/api/requests/{request_item.id}", json={"status": "FULFILLED"})
    assert response.status_code == 200
    assert db.session.get(BloodRequest, request_item.id).status == "FULFILLED"
    assert db.session.get(ContactRequest, contact.id).status == "CANCELLED"
    donor_notification = Notification.query.filter_by(user_id=donor.id, type="request_status").first()
    assert donor_notification is not None
    assert donor_notification.email_delivery_status == "NOT_CONFIGURED"


def test_account_removal_anonymizes_and_disables_donor_profile(client):
    user = User(name="Remove Me", email="remove-me@example.com", phone="1234567890", role="USER")
    user.password = "secret123"
    db.session.add(user)
    db.session.commit()
    profile = DonorProfile(
        user_id=user.id,
        blood_group="O+",
        city="Lucknow",
        state="Uttar Pradesh",
        availability="available",
        visibility="public",
        bio="Personal profile details",
    )
    db.session.add(profile)
    db.session.commit()
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})

    denied = client.delete("/api/auth/me", json={"password": "wrong-password"})
    assert denied.status_code == 400
    removed = client.delete("/api/auth/me", json={"password": "secret123"})
    assert removed.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert user.name == "Deleted user"
    assert user.email.endswith("@deleted.invalid")
    assert user.phone is None
    assert user.is_active is False
    assert DonorProfile.query.filter_by(user_id=user.id).first() is None


def test_listing_report_is_submitted_and_admin_can_resolve(client):
    reporter = User(name="Reporter", email="reporter@example.com", role="USER")
    reporter.password = "reporter-password"
    admin = User(name="Admin", email="report-admin@example.com", role="ADMIN")
    admin.password = "admin-password"
    donor = User(name="Reported Donor", email="reported-donor@example.com", role="DONOR")
    donor.password = "donor-password"
    db.session.add_all([reporter, admin, donor])
    db.session.commit()
    profile = DonorProfile(
        user_id=donor.id,
        blood_group="B+",
        city="Lucknow",
        state="Uttar Pradesh",
        availability="available",
        visibility="public",
    )
    db.session.add(profile)
    db.session.commit()

    client.post("/api/auth/login", json={"email": reporter.email, "password": "reporter-password"})
    submitted = client.post("/api/listing-reports", json={
        "target_type": "donor",
        "target_id": profile.id,
        "reason": "The location appears to be incorrect.",
    })
    assert submitted.status_code == 201
    duplicate = client.post("/api/listing-reports", json={
        "target_type": "donor",
        "target_id": profile.id,
        "reason": "The location appears to be incorrect.",
    })
    assert duplicate.status_code == 409

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": admin.email, "password": "admin-password"})
    listing = client.get("/api/admin/listing-reports")
    report_id = listing.get_json()["data"]["items"][0]["id"]
    reviewed = client.patch(f"/api/admin/listing-reports/{report_id}", json={
        "status": "RESOLVED",
        "resolution_notes": "Contact details verified.",
    })
    assert reviewed.status_code == 200
    assert client.get("/admin/reports").status_code == 200


def test_admin_can_correct_or_hide_a_donor_listing(client):
    admin = User(name="Admin", email="donor-review-admin@example.com", role="ADMIN")
    admin.password = "admin-password"
    donor = User(name="Donor", email="donor-review@example.com", role="USER", is_verified=True)
    donor.password = "donor-password"
    db.session.add_all([admin, donor])
    db.session.commit()
    profile = DonorProfile(
        user_id=donor.id,
        blood_group="O+",
        city="Lucknow",
        state="Uttar Pradesh",
        availability="available",
        visibility="public",
    )
    db.session.add(profile)
    db.session.commit()
    client.post("/api/auth/login", json={"email": admin.email, "password": "admin-password"})

    updated = client.patch(f"/api/admin/donors/{profile.id}", json={
        "blood_group": "A+",
        "city": "Kanpur",
        "state": "Uttar Pradesh",
        "visibility": "private",
    })
    assert updated.status_code == 200
    assert profile.blood_group == "A+"
    assert profile.city == "Kanpur"
    assert profile.visibility == "private"
    assert client.get("/api/donors").get_json()["data"]["items"] == []

    invalid = client.patch(f"/api/admin/donors/{profile.id}", json={"blood_group": "X+"})
    assert invalid.status_code == 400


def test_state_changes_require_a_session_csrf_token_outside_tests(client):
    client.application.config["TESTING"] = False
    page = client.get("/")
    token = page.data.split(b'<meta name="csrf-token" content="', 1)[1].split(b'"', 1)[0].decode()
    payload = {"name": "CSRF User", "email": "csrf@example.com", "password": "secret123"}

    rejected = client.post("/api/auth/register", json=payload)
    assert rejected.status_code == 400
    accepted = client.post("/api/auth/register", json=payload, headers={"X-CSRF-Token": token})
    assert accepted.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
        headers={"X-CSRF-Token": token},
    )
    assert login.status_code == 200
    stale_token = client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert stale_token.status_code == 400
    fresh_page = client.get("/")
    fresh_token = fresh_page.data.split(b'<meta name="csrf-token" content="', 1)[1].split(b'"', 1)[0].decode()
    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": fresh_token})
    assert logout.status_code == 200


def test_production_startup_rejects_development_secrets():
    original = {
        key: getattr(Config, key)
        for key in ("ENVIRONMENT", "SECRET_KEY", "ADMIN_SETUP_TOKEN", "RATELIMIT_STORAGE_URI")
    }
    try:
        Config.ENVIRONMENT = "production"
        Config.SECRET_KEY = "change-me"
        Config.ADMIN_SETUP_TOKEN = None
        Config.RATELIMIT_STORAGE_URI = "redis://localhost:6379/0"
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app()
    finally:
        for key, value in original.items():
            setattr(Config, key, value)


def test_health_check_confirms_database_is_reachable(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_health_check_is_not_limited(client):
    responses = [client.get("/healthz") for _ in range(55)]
    assert all(response.status_code == 200 for response in responses)


def test_database_url_converts_render_postgres_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@host.example/db")
    assert get_database_url() == "postgresql://user:password@host.example/db"
