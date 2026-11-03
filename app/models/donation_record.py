from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class DonationRecord(db.Model):
    __tablename__ = "donation_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    donation_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    hospital: Mapped[str] = mapped_column(String(150), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    donor: Mapped["User"] = relationship(back_populates="donation_records")
