from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class DonorProfile(db.Model):
    __tablename__ = "donor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(10), nullable=False)
    date_of_birth: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    gender: Mapped[str] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=True)
    state: Mapped[str] = mapped_column(String(80), nullable=True)
    area: Mapped[str] = mapped_column(String(80), nullable=True)
    availability: Mapped[str] = mapped_column(String(30), default="available", nullable=False)
    last_donation_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    emergency_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile_image: Mapped[str] = mapped_column(String(255), nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="public", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="donor_profile")
