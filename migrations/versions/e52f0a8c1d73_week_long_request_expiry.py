"""keep open blood requests visible for at least one week

Revision ID: e52f0a8c1d73
Revises: d41c8f73a2b9
Create Date: 2026-11-05 15:15:00.000000
"""
from datetime import timedelta

from alembic import op
import sqlalchemy as sa


revision = "e52f0a8c1d73"
down_revision = "d41c8f73a2b9"
branch_labels = None
depends_on = None


def upgrade():
    requests = sa.table(
        "blood_requests",
        sa.column("id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("expires_at", sa.DateTime()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(requests.c.id, requests.c.created_at, requests.c.expires_at)
        .where(requests.c.status == "OPEN")
    ).mappings()
    for row in rows:
        minimum_expiry = row["created_at"] + timedelta(days=7)
        if row["expires_at"] is None or row["expires_at"] < minimum_expiry:
            connection.execute(
                sa.update(requests)
                .where(requests.c.id == row["id"])
                .values(expires_at=minimum_expiry)
            )


def downgrade():
    requests = sa.table(
        "blood_requests",
        sa.column("id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("urgency", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("expires_at", sa.DateTime()),
    )
    legacy_expiry = {
        "normal": timedelta(days=3),
        "urgent": timedelta(days=1),
        "emergency": timedelta(hours=6),
    }
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(requests.c.id, requests.c.urgency, requests.c.created_at)
        .where(requests.c.status == "OPEN")
    ).mappings()
    for row in rows:
        duration = legacy_expiry.get(row["urgency"])
        if duration is not None:
            connection.execute(
                sa.update(requests)
                .where(requests.c.id == row["id"])
                .values(expires_at=row["created_at"] + duration)
            )
