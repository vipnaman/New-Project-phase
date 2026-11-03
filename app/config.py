import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def get_database_url():
    value = os.getenv("DATABASE_URL")
    if value:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value
    if os.getenv("FLASK_ENV", "development").lower() == "production":
        raise RuntimeError("DATABASE_URL must be set when FLASK_ENV=production.")
    sqlite_path = BASE_DIR / "instance" / "rakta.db"
    sqlite_path.parent.mkdir(exist_ok=True)
    return f"sqlite:///{sqlite_path}"


class Config:
    ENVIRONMENT = os.getenv("FLASK_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY") or ("dev-only-change-me" if ENVIRONMENT != "production" else None)
    ADMIN_SETUP_TOKEN = os.getenv("ADMIN_SETUP_TOKEN")
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_TIMEOUT = 8
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = ENVIRONMENT == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = ENVIRONMENT == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    JSON_SORT_KEYS = False
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    TESTING = ENVIRONMENT == "testing"
    DEBUG = ENVIRONMENT != "production"
