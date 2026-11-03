"""track initiator on contact requests

Revision ID: c93f4e1a7b20
Revises: b78d1a2e4c90
Create Date: 2026-10-03 10:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "c93f4e1a7b20"
down_revision = "b78d1a2e4c90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contact_requests") as batch_op:
        batch_op.add_column(sa.Column("initiator_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_contact_requests_initiator_id_users", "users", ["initiator_id"], ["id"])
    op.execute("UPDATE contact_requests SET initiator_id = requester_id WHERE initiator_id IS NULL")


def downgrade():
    with op.batch_alter_table("contact_requests") as batch_op:
        batch_op.drop_constraint("fk_contact_requests_initiator_id_users", type_="foreignkey")
        batch_op.drop_column("initiator_id")