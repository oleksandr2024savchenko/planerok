"""recurring tasks with streaks

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-27 14:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule", sa.String(128), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("streak_current", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_best", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recurrences_space_id", "recurrences", ["space_id"])
    op.add_column("tasks", sa.Column("recurrence_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_recurrence_id", "tasks", "recurrences", ["recurrence_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_tasks_recurrence_id", "tasks", ["recurrence_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_recurrence_id", table_name="tasks")
    op.drop_constraint("fk_tasks_recurrence_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "recurrence_id")
    op.drop_index("ix_recurrences_space_id", table_name="recurrences")
    op.drop_table("recurrences")
