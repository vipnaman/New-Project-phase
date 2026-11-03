import smtplib
from email.message import EmailMessage

from flask import current_app

from app.extensions import db


def send_notification_email(user, title, message, notification=None):
    server = current_app.config.get("MAIL_SERVER")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not user.email_notifications_enabled:
        status = "DISABLED"
    elif not server or not sender or not user.email:
        status = "NOT_CONFIGURED"
    else:
        email = EmailMessage()
        email["Subject"] = f"RAKTA: {title}"
        email["From"] = sender
        email["To"] = user.email
        email.set_content(f"{message}\n\nSign in to RAKTA to review this update.")

        port = current_app.config.get("MAIL_PORT", 587)
        timeout = current_app.config.get("MAIL_TIMEOUT", 8)
        try:
            if current_app.config.get("MAIL_USE_SSL"):
                with smtplib.SMTP_SSL(server, port, timeout=timeout) as connection:
                    _authenticate(connection)
                    connection.send_message(email)
            else:
                with smtplib.SMTP(server, port, timeout=timeout) as connection:
                    connection.ehlo()
                    if current_app.config.get("MAIL_USE_TLS", True):
                        connection.starttls()
                        connection.ehlo()
                    _authenticate(connection)
                    connection.send_message(email)
            status = "SENT"
        except (OSError, smtplib.SMTPException):
            current_app.logger.exception("Notification email delivery failed")
            status = "FAILED"

    if notification is not None:
        notification.email_delivery_status = status
        db.session.commit()
    return status == "SENT"


def _authenticate(connection):
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    if username and password:
        connection.login(username, password)
