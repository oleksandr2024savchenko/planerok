"""users and shared tasks

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04 22:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("partner_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("google_calendar_id", sa.String(length=255), nullable=True),
        sa.Column("morning_time", sa.Time(), nullable=False, server_default="08:00:00"),
        sa.Column("afternoon_time", sa.Time(), nullable=False, server_default="14:00:00"),
        sa.Column("evening_time", sa.Time(), nullable=False, server_default="20:00:00"),
        sa.Column("theme_accent", sa.String(length=32), nullable=False, server_default="violet"),
    )
    op.execute(
        """
        INSERT INTO users (telegram_id)
        SELECT DISTINCT user_id FROM tasks
        ON CONFLICT (telegram_id) DO NOTHING
        """
    )
    op.add_column("tasks", sa.Column("owner_id", sa.BigInteger(), nullable=True))
    op.add_column("tasks", sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tasks", sa.Column("assigned_to_id", sa.BigInteger(), nullable=True))
    op.add_column("tasks", sa.Column("partner_google_event_id", sa.String(length=255), nullable=True))
    op.execute("UPDATE tasks SET owner_id = user_id WHERE owner_id IS NULL")
    op.alter_column("tasks", "owner_id", nullable=False)
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.create_foreign_key("fk_tasks_owner_id", "tasks", "users", ["owner_id"], ["telegram_id"])
    op.create_index("uq_tasks_partner_google_event_id", "tasks", ["partner_google_event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_tasks_partner_google_event_id", table_name="tasks")
    op.drop_constraint("fk_tasks_owner_id", "tasks", type_="foreignkey")
    op.drop_index("ix_tasks_owner_id", table_name="tasks")
    op.drop_column("tasks", "partner_google_event_id")
    op.drop_column("tasks", "assigned_to_id")
    op.drop_column("tasks", "is_shared")
    op.drop_column("tasks", "owner_id")
    op.drop_table("users")
