from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="USER", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    donor_profile: Mapped["DonorProfile"] = relationship(back_populates="user", uselist=False)
    requests: Mapped[list["BloodRequest"]] = relationship(back_populates="requester", foreign_keys="BloodRequest.requester_id")
    contact_requests_sent: Mapped[list["ContactRequest"]] = relationship(back_populates="requester", foreign_keys="ContactRequest.requester_id")
    contact_requests_received: Mapped[list["ContactRequest"]] = relationship(back_populates="donor", foreign_keys="ContactRequest.donor_id")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")
    donation_records: Mapped[list["DonationRecord"]] = relationship(back_populates="donor")
    admin_actions: Mapped[list["AdminActivity"]] = relationship(back_populates="admin")

    @property
    def password(self):
        raise AttributeError("password is not readable")

    @password.setter
    def password(self, plain_password):
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(plain_password)

    def verify_password(self, plain_password):
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, plain_password)

    def __repr__(self):
        return f"<User {self.email}>"
