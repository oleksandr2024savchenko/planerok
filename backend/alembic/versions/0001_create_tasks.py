"""create tasks table

Revision ID: 0001
Revises:
Create Date: 2026-11-03 17:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

priority_enum = sa.Enum("low", "medium", "high", name="task_priority")


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("priority", priority_enum, nullable=False, server_default="medium"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_category", "tasks", ["category"])
    op.create_index("ix_tasks_deadline", "tasks", ["deadline"])


def downgrade() -> None:
    op.drop_index("ix_tasks_deadline", table_name="tasks")
    op.drop_index("ix_tasks_category", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
    priority_enum.drop(op.get_bind(), checkfirst=True)
