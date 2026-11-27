"""task status, updated_at and soft delete

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-27 13:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_status = sa.Enum("backlog", "todo", "doing", "done", name="task_status")


def upgrade() -> None:
    task_status.create(op.get_bind(), checkfirst=True)
    op.add_column("tasks", sa.Column("status", task_status, nullable=False, server_default="todo"))
    op.execute("UPDATE tasks SET status = 'done' WHERE is_completed")
    op.add_column(
        "tasks",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("tasks", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_tasks_deleted_at", "tasks", ["deleted_at"])


def downgrade() -> None:
    op.execute("DELETE FROM tasks WHERE deleted_at IS NOT NULL")
    op.drop_index("ix_tasks_deleted_at", table_name="tasks")
    op.drop_column("tasks", "deleted_at")
    op.drop_column("tasks", "updated_at")
    op.drop_column("tasks", "status")
    task_status.drop(op.get_bind(), checkfirst=True)
