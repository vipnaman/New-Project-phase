from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class SiteAppearance(db.Model):
    __tablename__ = "site_appearance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    palette: Mapped[str] = mapped_column(String(30), default="red-blue", nullable=False)
    motion_level: Mapped[str] = mapped_column(String(20), default="balanced", nullable=False)
    live_background: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)