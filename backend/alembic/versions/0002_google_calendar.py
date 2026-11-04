"""google calendar fields and sync state

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04 10:30:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("end_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("google_event_id", sa.String(length=255), nullable=True))
    op.add_column("tasks", sa.Column("sync_token", sa.Text(), nullable=True))
    op.create_index("ix_tasks_start_time", "tasks", ["start_time"])
    op.create_index("uq_tasks_google_event_id", "tasks", ["google_event_id"], unique=True)

    op.create_table(
        "google_calendar_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("calendar_id", sa.String(length=255), nullable=False, server_default="primary"),
        sa.Column("sync_token", sa.Text(), nullable=True),
        sa.Column("channel_id", sa.String(length=128), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("channel_token", sa.String(length=255), nullable=True),
        sa.Column("channel_expiration", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("google_calendar_state")
    op.drop_index("uq_tasks_google_event_id", table_name="tasks")
    op.drop_index("ix_tasks_start_time", table_name="tasks")
    op.drop_column("tasks", "sync_token")
    op.drop_column("tasks", "google_event_id")
    op.drop_column("tasks", "end_time")
    op.drop_column("tasks", "start_time")
