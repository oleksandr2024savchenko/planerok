"""remember which external calendar events were marked done

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-05 11:00:00+01:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "external_events",
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("external_events", "is_completed")
