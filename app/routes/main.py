from functools import wraps

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.models.user import User

main_bp = Blueprint("main", __name__)


def admin_page_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "ADMIN":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


@main_bp.route("/")
def index():
    return render_template("index.html", current_user=current_user)


@main_bp.route("/find-blood")
def find_blood():
    return render_template("find-blood.html", current_user=current_user)


@main_bp.route("/donate")
def donate():
    return render_template("donate.html", current_user=current_user)


@main_bp.route("/blood-requests")
def blood_requests_page():
    return render_template("blood-requests.html", current_user=current_user)


@main_bp.route("/request-blood")
def request_blood():
    return render_template("request-blood.html", current_user=current_user)


@main_bp.route("/how-it-works")
def how_it_works():
    return render_template("how-it-works.html", current_user=current_user)


@main_bp.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@main_bp.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html", current_user=current_user)


@main_bp.route("/terms")
def terms():
    return render_template("terms.html", current_user=current_user)


@main_bp.route("/login")
def login_page():
    initial_admin_missing = not User.query.filter_by(role="ADMIN").first()
    return render_template("login.html", current_user=current_user, admin_setup_available=initial_admin_missing)


@main_bp.route("/register")
def register_page():
    return render_template("register.html", current_user=current_user)


@main_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot-password.html", current_user=current_user)


@main_bp.route("/reset-password")
def reset_password():
    return render_template("reset-password.html", current_user=current_user)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", current_user=current_user)


@main_bp.route("/profile")
@login_required
def profile():
    return render_template("profile.html", current_user=current_user)


@main_bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html", current_user=current_user)


@main_bp.route("/notifications")
@login_required
def notifications_page():
    return render_template("notifications.html", current_user=current_user)


@main_bp.route("/donor/profile")
@login_required
def donor_profile_page():
    return render_template("donor-profile.html", current_user=current_user)


@main_bp.route("/donor/requests")
@login_required
def donor_requests_page():
    return render_template("donor-requests.html", current_user=current_user)


@main_bp.route("/admin")
@admin_page_required
def admin_dashboard():
    return render_template("admin/dashboard.html", current_user=current_user)


@main_bp.route("/admin/users")
@admin_page_required
def admin_users():
    return render_template("admin/users.html", current_user=current_user)


@main_bp.route("/admin/donors")
@admin_page_required
def admin_donors():
    return render_template("admin/donors.html", current_user=current_user)


@main_bp.route("/admin/requests")
@admin_page_required
def admin_requests():
    return render_template("admin/requests.html", current_user=current_user)


@main_bp.route("/admin/hospitals")
@admin_page_required
def admin_hospitals():
    return render_template("admin/hospitals.html", current_user=current_user)


@main_bp.route("/admin/reports")
@admin_page_required
def admin_reports():
    return render_template("admin/reports.html", current_user=current_user)


@main_bp.route("/admin/analytics")
@admin_page_required
def admin_analytics():
    return render_template("admin/analytics.html", current_user=current_user)


@main_bp.route("/admin/settings")
@admin_page_required
def admin_settings():
    return render_template("admin/settings.html", current_user=current_user)
