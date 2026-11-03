from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    donor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    blood_request_id: Mapped[int] = mapped_column(ForeignKey("blood_requests.id"), nullable=True)
    message: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    requester: Mapped["User"] = relationship(back_populates="contact_requests_sent", foreign_keys=[requester_id])
    donor: Mapped["User"] = relationship(back_populates="contact_requests_received", foreign_keys=[donor_id])
