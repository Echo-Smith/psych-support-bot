"""Reconcile plan_enrollments missing from the historical Alembic chain.

Revision ID: 20261005_0001
Revises: c1d3dc0400bd
"""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0001"
down_revision = "c1d3dc0400bd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("plan_enrollments"):
        expected = {
            "id",
            "user_id",
            "plan_id",
            "enrolled_at",
            "completed_days_json",
            "current_day",
            "status",
            "updated_at",
        }
        actual = {column["name"] for column in inspector.get_columns("plan_enrollments")}
        if not expected.issubset(actual):
            raise RuntimeError("Existing plan_enrollments has an unsupported schema")
        return
    op.create_table(
        "plan_enrollments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(), nullable=False),
        sa.Column("completed_days_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("current_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    # Older deployments may already own this table via create_all. Retain it
    # on rollback instead of erasing data whose creation predates this revision.
    pass
