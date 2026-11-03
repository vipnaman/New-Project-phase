from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class BloodRequest(db.Model):
    __tablename__ = "blood_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    blood_group: Mapped[str] = mapped_column(String(10), nullable=False)
    units_required: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=True)
    state: Mapped[str] = mapped_column(String(80), nullable=True)
    urgency: Mapped[str] = mapped_column(String(30), default="normal", nullable=False)
    required_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    contact_preference: Mapped[str] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    requester: Mapped["User"] = relationship(back_populates="requests", foreign_keys=[requester_id])
    hospital: Mapped["Hospital"] = relationship()
