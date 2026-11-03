import hmac
import secrets

from flask import Flask, jsonify, redirect, request, url_for
from flask import session
from sqlalchemy import text

from app.config import Config
from app.extensions import db, limiter, login_manager, migrate
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.donors import donors_bp
from app.routes.main import main_bp
from app.routes.notifications import notifications_bp
from app.routes.requests import requests_bp
from app.routes.reports import reports_bp


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(Config)
    if app.config["ENVIRONMENT"] == "production":
        secret_key = app.config["SECRET_KEY"]
        if not isinstance(secret_key, str) or len(secret_key) < 32 or secret_key.lower() in {
            "change-me",
            "dev-only-change-me",
        }:
            raise RuntimeError("Set SECRET_KEY to a unique random value of at least 32 characters in production.")
        setup_token = app.config["ADMIN_SETUP_TOKEN"]
        if setup_token and (
            len(setup_token) < 32 or setup_token == "generate-a-long-random-one-time-value"
        ):
            raise RuntimeError("ADMIN_SETUP_TOKEN must be a unique random value of at least 32 characters.")
    if app.config["ENVIRONMENT"] == "production" and app.config["RATELIMIT_STORAGE_URI"].startswith("memory://"):
        raise RuntimeError("Configure RATELIMIT_STORAGE_URI with shared Redis storage in production.")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "main.login_page"

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": "Please sign in to continue."}), 401
        return redirect(url_for("main.login_page", next=request.full_path))
    limiter.init_app(app)

    @app.before_request
    def protect_session_mutations():
        if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"} or app.config["TESTING"]:
            return None
        expected = session.get("_csrf_token")
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(str(expected), str(supplied)):
            return jsonify({"success": False, "message": "Your session token is missing or expired. Reload the page and try again."}), 400
        return None

    @app.context_processor
    def inject_csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return {"csrf_token": session["_csrf_token"]}

    @app.cli.command("create-admin")
    def create_admin():
        import click
        from werkzeug.security import generate_password_hash
        from app.models.user import User

        email = click.prompt("Admin email", default="admin@gmail.com").strip().lower()
        if email != "admin@gmail.com":
            raise click.ClickException("The administrator email must be admin@gmail.com.")
        password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)
        if len(password) < 10:
            raise click.ClickException("Use an admin password with at least 10 characters.")
        db.create_all()
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(name="RAKTA Administrator", email=email, role="ADMIN")
            db.session.add(user)
        user.role = "ADMIN"
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        click.echo(f"Administrator account provisioned for {email}.")

    @app.cli.command("expire-requests")
    def expire_requests_command():
        import click
        from app.services.request_lifecycle import expire_stale_requests

        expired_count = expire_stale_requests()
        click.echo(f"Expired {expired_count} blood request(s).")

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User

        return db.session.get(User, int(user_id))

    @app.errorhandler(404)
    def not_found(error):
        return "Page not found", 404

    @app.errorhandler(500)
    def server_error(error):
        return "Server error", 500

    @app.get("/healthz")
    def health_check():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            app.logger.exception("Health check could not reach the database")
            return jsonify({"status": "unavailable"}), 503
        return jsonify({"status": "ok"}), 200

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(donors_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)

    return app
