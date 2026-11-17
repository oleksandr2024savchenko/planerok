"""relative reminders (minutes before the event)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17 12:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("remind_before_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "remind_before_minutes")
