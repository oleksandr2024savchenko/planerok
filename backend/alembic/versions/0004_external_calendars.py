"""external ical subscriptions

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-05 09:40:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_calendars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"]),
        sa.UniqueConstraint("user_id", "url", name="uq_external_calendars_user_url"),
    )
    op.create_index("ix_external_calendars_user_id", "external_calendars", ["user_id"])
    op.create_table(
        "external_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("calendar_id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=700), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["calendar_id"], ["external_calendars.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("calendar_id", "uid", name="uq_external_events_calendar_uid"),
    )
    op.create_index("ix_external_events_calendar_id", "external_events", ["calendar_id"])
    op.create_index("ix_external_events_start_time", "external_events", ["start_time"])


def downgrade() -> None:
    op.drop_index("ix_external_events_start_time", table_name="external_events")
    op.drop_index("ix_external_events_calendar_id", table_name="external_events")
    op.drop_table("external_events")
    op.drop_index("ix_external_calendars_user_id", table_name="external_calendars")
    op.drop_table("external_calendars")
