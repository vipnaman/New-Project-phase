"""add site appearance settings

Revision ID: b78d1a2e4c90
Revises: 9c14aa7560a8
Create Date: 2026-10-02 22:30:00.000000
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "b78d1a2e4c90"
down_revision = "9c14aa7560a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_appearance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("palette", sa.String(length=30), nullable=False),
        sa.Column("motion_level", sa.String(length=20), nullable=False),
        sa.Column("live_background", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        sa.table(
            "site_appearance",
            sa.column("id", sa.Integer()),
            sa.column("palette", sa.String()),
            sa.column("motion_level", sa.String()),
            sa.column("live_background", sa.Boolean()),
            sa.column("updated_at", sa.DateTime()),
        ),
        [{"id": 1, "palette": "red-blue", "motion_level": "balanced", "live_background": True, "updated_at": datetime(2026, 10, 2, 22, 30)}],
    )


def downgrade():
    op.drop_table("site_appearance")