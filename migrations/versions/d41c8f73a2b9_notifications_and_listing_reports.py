"""track notification preferences and listing reports

Revision ID: d41c8f73a2b9
Revises: c93f4e1a7b20
Create Date: 2026-11-03 12:51:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "d41c8f73a2b9"
down_revision = "c93f4e1a7b20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("email_delivery_status", sa.String(length=20), nullable=False, server_default="NOT_REQUESTED"))
    op.create_table(
        "listing_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reporter_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_listing_reports_status", "listing_reports", ["status"])


def downgrade():
    op.drop_index("ix_listing_reports_status", table_name="listing_reports")
    op.drop_table("listing_reports")
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_column("email_delivery_status")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("email_notifications_enabled")
