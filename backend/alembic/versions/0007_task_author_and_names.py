"""task author and user first names

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-17 15:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("created_by_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_tasks_created_by_id", "tasks", ["created_by_id"])
    # Until now the creator was always the owner, except tasks given to the partner (unknown author).
    op.execute("UPDATE tasks SET created_by_id = owner_id WHERE assigned_to_id IS NULL")
    op.add_column("users", sa.Column("first_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "first_name")
    op.drop_index("ix_tasks_created_by_id", table_name="tasks")
    op.drop_column("tasks", "created_by_id")
