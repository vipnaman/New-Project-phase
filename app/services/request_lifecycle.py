from datetime import datetime

from app.extensions import db
from app.models.blood_request import BloodRequest
from app.models.contact_request import ContactRequest
from app.models.notification import Notification
from app.services.email_service import send_notification_email


def notify_request_status(request_item, notify_requester=True):
    if request_item.status not in {"FULFILLED", "CANCELLED", "EXPIRED"}:
        return []
    status = request_item.status.lower()
    title = "Blood request status updated"
    message = f"Your {request_item.blood_group} blood request in {request_item.city or 'your area'} was {status}."
    alerts = []
    if notify_requester:
        notification = Notification(
            user_id=request_item.requester_id,
            title=title,
            message=message,
            type="request_status",
        )
        db.session.add(notification)
        alerts.append((request_item.requester, notification, title, message))

    contacts = ContactRequest.query.filter(
        ContactRequest.blood_request_id == request_item.id,
        ContactRequest.status == "PENDING",
    ).all()
    donor_title = "Blood request closed"
    donor_message = f"The {request_item.blood_group} blood request in {request_item.city or 'your area'} was {status}."
    for contact in contacts:
        contact.status = "CANCELLED"
        contact.responded_at = datetime.utcnow()
        recipient = contact.donor
        notification = Notification(
            user_id=recipient.id,
            title=donor_title,
            message=donor_message,
            type="request_status",
        )
        db.session.add(notification)
        alerts.append((recipient, notification, donor_title, donor_message))
    return alerts


def expire_stale_requests():
    now = datetime.utcnow()
    stale = BloodRequest.query.filter(
        BloodRequest.status == "OPEN",
        BloodRequest.expires_at.is_not(None),
        BloodRequest.expires_at <= now,
    ).all()
    alerts = []
    for item in stale:
        item.status = "EXPIRED"
        alerts.extend(notify_request_status(item))
    if stale:
        db.session.commit()
        for user, notification, title, message in alerts:
            send_notification_email(user, title, message, notification)
    return len(stale)
