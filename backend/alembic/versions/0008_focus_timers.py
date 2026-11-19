"""focus timers on tasks

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-19 12:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("focused_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "task_timers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="focus"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("running_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_timers_user_id", "task_timers", ["user_id"])
    op.create_index("ix_task_timers_task_id", "task_timers", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_timers_task_id", table_name="task_timers")
    op.drop_index("ix_task_timers_user_id", table_name="task_timers")
    op.drop_table("task_timers")
    op.drop_column("tasks", "focused_seconds")
